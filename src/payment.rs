use axum::{extract::State, http::StatusCode, body::Body};
use axum::extract::Request;
use axum::response::IntoResponse;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use crate::models::{GuildSubscription, SubscriptionTier};
use reqwest::Client;
use hmac::{Hmac, Mac};
use sha2::Sha256;
use std::sync::Arc;
use chrono;

type HmacSha256 = Hmac<Sha256>;

#[derive(Debug, thiserror::Error)]
pub enum PaymentError {
    #[error("HTTP 요청 오류: {0}")]
    HttpError(#[from] reqwest::Error),
    #[error("Firestore 오류: {0}")]
    FirestoreError(#[from] crate::firestore::FirestoreError),
    #[error("구독을 찾을 수 없음: guild_id {0}")]
    SubscriptionNotFound(u64),
    #[error("유효하지 않은 플랜: {0}")]
    InvalidTier(String),
    #[error("웹훅 검증 실패")]
    WebhookVerificationFailed,
    #[error("JSON 파싱 오류: {0}")]
    JsonError(#[from] serde_json::Error),
    #[error("Stripe API 오류: {message}")]
    StripeApiError { message: String },
}

pub struct PaymentService {
    stripe_secret_key: String,
    webhook_secret: String,
    http_client: Client,
    premium_price_id: String,
    enterprise_price_id: String,
}

impl PaymentService {
    /// 결제 서비스 초기화
    pub fn new(stripe_secret_key: String, webhook_secret: String) -> Self {
        Self {
            stripe_secret_key,
            webhook_secret,
            http_client: Client::new(),
            // 실제로는 Stripe 대시보드에서 생성한 Price ID를 사용
            premium_price_id: "price_premium_placeholder".to_string(),
            enterprise_price_id: "price_enterprise_placeholder".to_string(),
        }
    }

    /// 서버의 구독 상태 확인
    pub async fn get_guild_subscription(&self, firestore: &crate::firestore::FirestoreService, guild_id: u64) -> Result<GuildSubscription, PaymentError> {
        match firestore.load_guild_subscription(guild_id).await {
            Ok(subscription) => Ok(subscription),
            Err(_) => {
                // 구독이 없으면 기본 무료 플랜 생성
                let default_subscription = GuildSubscription {
                    guild_id,
                    ..Default::default()
                };
                
                // Firestore에 저장
                firestore.save_guild_subscription(&default_subscription).await?;
                Ok(default_subscription)
            }
        }
    }

    /// 결제 링크 생성 (Stripe Checkout Session)
    pub async fn create_payment_link(&self, guild_id: u64, tier: SubscriptionTier, guild_name: &str) -> Result<String, PaymentError> {
        if tier == SubscriptionTier::Free {
            return Err(PaymentError::InvalidTier("무료 플랜은 결제가 필요하지 않습니다".to_string()));
        }

        let price_id = match tier {
            SubscriptionTier::Premium => &self.premium_price_id,
            SubscriptionTier::Enterprise => &self.enterprise_price_id,
            SubscriptionTier::Free => unreachable!(),
        };

        // Stripe Checkout Session 생성 요청
        let checkout_session = CreateCheckoutSession {
            success_url: "https://your-domain.com/success".to_string(),
            cancel_url: "https://your-domain.com/cancel".to_string(),
            payment_method_types: vec!["card".to_string()],
            mode: "subscription".to_string(),
            line_items: vec![CheckoutSessionLineItem {
                price: price_id.clone(),
                quantity: 1,
            }],
            metadata: {
                let mut metadata = HashMap::new();
                metadata.insert("guild_id".to_string(), guild_id.to_string());
                metadata.insert("tier".to_string(), tier.to_string());
                metadata.insert("guild_name".to_string(), guild_name.to_string());
                metadata
            },
        };

        let mut form_data = HashMap::new();
        form_data.insert("success_url".to_string(), checkout_session.success_url.clone());
        form_data.insert("cancel_url".to_string(), checkout_session.cancel_url.clone());
        form_data.insert("payment_method_types[]".to_string(), "card".to_string());
        form_data.insert("mode".to_string(), checkout_session.mode.clone());
        form_data.insert("line_items[0][price]".to_string(), price_id.to_string());
        form_data.insert("line_items[0][quantity]".to_string(), "1".to_string());
        form_data.insert("metadata[guild_id]".to_string(), guild_id.to_string());
        form_data.insert("metadata[tier]".to_string(), tier.to_string());
        form_data.insert("metadata[guild_name]".to_string(), guild_name.to_string());

        let response = self.http_client
            .post("https://api.stripe.com/v1/checkout/sessions")
            .header("Authorization", format!("Bearer {}", self.stripe_secret_key))
            .header("Content-Type", "application/x-www-form-urlencoded")
            .form(&form_data)
            .send()
            .await?;

        if !response.status().is_success() {
            let error_text = response.text().await?;
            return Err(PaymentError::StripeApiError { 
                message: format!("Checkout session 생성 실패: {}", error_text) 
            });
        }

        let session: CheckoutSessionResponse = response.json().await?;
        Ok(session.url)
    }

    /// 결제 성공 처리 (Webhook에서 호출)
    pub async fn handle_payment_success(
        &self, 
        firestore: &crate::firestore::FirestoreService,
        customer_id: &str,
        subscription_id: &str,
        guild_id: u64, 
        tier: SubscriptionTier
    ) -> Result<(), PaymentError> {
        let mut subscription = self.get_guild_subscription(firestore, guild_id).await?;
        
        // 구독 정보 업데이트
        subscription.tier = tier.clone();
        subscription.is_active = true;
        subscription.stripe_customer_id = Some(customer_id.to_string());
        subscription.stripe_subscription_id = Some(subscription_id.to_string());
        subscription.last_payment_at = Some(chrono::Utc::now());
        subscription.expires_at = Some(chrono::Utc::now() + chrono::Duration::days(30)); // 30일 후 만료
        
        // Firestore에 저장
        firestore.save_guild_subscription(&subscription).await?;
        
        println!("결제 성공 처리 완료: Guild {} -> {:?}", guild_id, tier);
        Ok(())
    }

    /// 구독 취소
    pub async fn cancel_subscription(
        &self,
        firestore: &crate::firestore::FirestoreService, 
        guild_id: u64
    ) -> Result<(), PaymentError> {
        let mut subscription = self.get_guild_subscription(firestore, guild_id).await?;
        
        // Stripe에서 구독 취소
        if let Some(stripe_subscription_id) = &subscription.stripe_subscription_id {
            let response = self.http_client
                .delete(&format!("https://api.stripe.com/v1/subscriptions/{}", stripe_subscription_id))
                .header("Authorization", format!("Bearer {}", self.stripe_secret_key))
                .send()
                .await?;

            if !response.status().is_success() {
                let error_text = response.text().await?;
                println!("Stripe 구독 취소 실패: {}", error_text);
            } else {
                println!("Stripe 구독 취소 성공: {}", stripe_subscription_id);
            }
        }
        
        // 로컬 구독 정보 업데이트
        subscription.tier = SubscriptionTier::Free;
        subscription.is_active = false;
        subscription.expires_at = Some(chrono::Utc::now());
        subscription.stripe_subscription_id = None;
        
        firestore.save_guild_subscription(&subscription).await?;
        
        println!("구독 취소 완료: Guild {}", guild_id);
        Ok(())
    }

    /// 구독 상태 확인 및 갱신
    pub async fn refresh_subscription_status(
        &self,
        firestore: &crate::firestore::FirestoreService,
        guild_id: u64
    ) -> Result<GuildSubscription, PaymentError> {
        let mut subscription = self.get_guild_subscription(firestore, guild_id).await?;
        
        // Stripe에서 구독 상태 확인
        if let Some(stripe_subscription_id) = &subscription.stripe_subscription_id {
            let response = self.http_client
                .get(&format!("https://api.stripe.com/v1/subscriptions/{}", stripe_subscription_id))
                .header("Authorization", format!("Bearer {}", self.stripe_secret_key))
                .send()
                .await?;

            if response.status().is_success() {
                let stripe_sub: StripeSubscription = response.json().await?;
                
                // Stripe 구독 상태에 따라 로컬 상태 업데이트
                match stripe_sub.status.as_str() {
                    "active" => {
                        subscription.is_active = true;
                        if let Some(current_period_end) = stripe_sub.current_period_end {
                            subscription.expires_at = Some(
                                chrono::DateTime::from_timestamp(current_period_end, 0)
                                    .unwrap_or_else(chrono::Utc::now)
                            );
                        }
                    }
                    "canceled" | "unpaid" | "past_due" => {
                        subscription.is_active = false;
                        subscription.tier = SubscriptionTier::Free;
                        subscription.expires_at = Some(chrono::Utc::now());
                    }
                    _ => {
                        println!("처리되지 않은 Stripe 구독 상태: {}", stripe_sub.status);
                    }
                }
                
                firestore.save_guild_subscription(&subscription).await?;
            }
        }
        
        // 만료 확인
        if let Some(expires_at) = subscription.expires_at {
            if expires_at <= chrono::Utc::now() && subscription.tier != SubscriptionTier::Free {
                // 구독 만료됨 - 무료 플랜으로 다운그레이드
                subscription.tier = SubscriptionTier::Free;
                subscription.is_active = false;
                firestore.save_guild_subscription(&subscription).await?;
                
                println!("구독 만료로 무료 플랜으로 변경: Guild {}", guild_id);
            }
        }
        
        Ok(subscription)
    }

    /// Webhook 이벤트 검증 및 처리
    pub async fn handle_webhook_event(
        &self,
        payload: &str,
        signature: &str,
        firestore: &crate::firestore::FirestoreService,
    ) -> Result<(), PaymentError> {
        // Webhook 서명 검증
        if !self.verify_webhook_signature(payload, signature) {
            return Err(PaymentError::WebhookVerificationFailed);
        }

        // 이벤트 파싱
        let event: StripeWebhookEvent = serde_json::from_str(payload)?;

        match event.event_type.as_str() {
            "checkout.session.completed" => {
                if let Some(session) = event.data.object.as_object() {
                    if let (Some(guild_id_val), Some(tier_val)) = (
                        session.get("metadata").and_then(|m| m.get("guild_id")),
                        session.get("metadata").and_then(|m| m.get("tier"))
                    ) {
                        let guild_id: u64 = guild_id_val.as_str().unwrap_or("0").parse().unwrap_or(0);
                        let tier: SubscriptionTier = tier_val.as_str().unwrap_or("free").parse().unwrap_or(SubscriptionTier::Free);
                        
                        let customer_id = session.get("customer").and_then(|c| c.as_str()).unwrap_or("");
                        let subscription_id = session.get("subscription").and_then(|s| s.as_str()).unwrap_or("");
                        
                        self.handle_payment_success(
                            firestore,
                            customer_id,
                            subscription_id,
                            guild_id,
                            tier
                        ).await?;
                    }
                }
            }
            "customer.subscription.updated" | "customer.subscription.deleted" => {
                // 구독 상태 변경 처리
                if let Some(subscription_obj) = event.data.object.as_object() {
                    if let Some(metadata) = subscription_obj.get("metadata").and_then(|m| m.as_object()) {
                        if let Some(guild_id_val) = metadata.get("guild_id") {
                            let guild_id: u64 = guild_id_val.as_str().unwrap_or("0").parse().unwrap_or(0);
                            self.refresh_subscription_status(firestore, guild_id).await?;
                        }
                    }
                }
            }
            _ => {
                println!("처리되지 않은 webhook 이벤트: {}", event.event_type);
            }
        }

        Ok(())
    }

    /// Stripe 웹훅 처리를 위한 Axum 핸들러
    pub async fn handle_webhook(
        State(bot_state): State<Arc<crate::BotState>>,
        request: Request<Body>,
    ) -> impl IntoResponse {
        // 요청 헤더에서 Stripe 서명 가져오기
        let signature = match request.headers().get("stripe-signature") {
            Some(sig) => match sig.to_str() {
                Ok(s) => s.to_string(),
                Err(_) => return (StatusCode::BAD_REQUEST, "Invalid signature header").into_response(),
            },
            None => return (StatusCode::BAD_REQUEST, "Missing signature header").into_response(),
        };

        // 요청 본문 읽기
        let body_bytes = match axum::body::to_bytes(request.into_body(), usize::MAX).await {
            Ok(bytes) => bytes,
            Err(_) => return (StatusCode::BAD_REQUEST, "Failed to read body").into_response(),
        };

        let payload = match std::str::from_utf8(&body_bytes) {
            Ok(s) => s,
            Err(_) => return (StatusCode::BAD_REQUEST, "Invalid UTF-8").into_response(),
        };

        // 웹훅 서명 검증
        if !bot_state.payment_service.verify_webhook_signature(payload, &signature) {
            return (StatusCode::UNAUTHORIZED, "Invalid signature").into_response();
        }

        // 웹훅 이벤트 파싱
        let event: StripeWebhookEvent = match serde_json::from_str(payload) {
            Ok(event) => event,
            Err(e) => {
                eprintln!("웹훅 이벤트 파싱 실패: {}", e);
                return (StatusCode::BAD_REQUEST, "Invalid JSON").into_response();
            }
        };

        // 이벤트 타입에 따른 처리
        match bot_state.payment_service.process_webhook_event(&event, &bot_state.firestore).await {
            Ok(_) => {
                println!("웹훅 이벤트 처리 완료: {} ({})", event.event_type, event.id);
                (StatusCode::OK, "OK").into_response()
            }
            Err(e) => {
                eprintln!("웹훅 이벤트 처리 실패: {}", e);
                (StatusCode::INTERNAL_SERVER_ERROR, "Processing failed").into_response()
            }
        }
    }

    /// 웹훅 이벤트 처리
    async fn process_webhook_event(
        &self,
        event: &StripeWebhookEvent,
        firestore: &crate::firestore::FirestoreService,
    ) -> Result<(), PaymentError> {
        match event.event_type.as_str() {
            "checkout.session.completed" => {
                self.handle_checkout_completed(event, firestore).await?;
            }
            "invoice.payment_succeeded" => {
                self.handle_payment_succeeded(event, firestore).await?;
            }
            "invoice.payment_failed" => {
                self.handle_payment_failed(event, firestore).await?;
            }
            "customer.subscription.deleted" => {
                self.handle_subscription_cancelled(event, firestore).await?;
            }
            _ => {
                println!("처리하지 않는 웹훅 이벤트: {}", event.event_type);
            }
        }
        Ok(())
    }

    /// 체크아웃 세션 완료 처리
    async fn handle_checkout_completed(
        &self,
        event: &StripeWebhookEvent,
        firestore: &crate::firestore::FirestoreService,
    ) -> Result<(), PaymentError> {
        // Checkout session 데이터에서 메타데이터 추출
        let metadata = event.data.object
            .get("metadata")
            .and_then(|m| m.as_object())
            .ok_or_else(|| PaymentError::StripeApiError { 
                message: "메타데이터를 찾을 수 없음".to_string() 
            })?;

        let guild_id_str = metadata.get("guild_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| PaymentError::StripeApiError { 
                message: "guild_id 메타데이터가 없음".to_string() 
            })?;

        let tier_str = metadata.get("tier")
            .and_then(|v| v.as_str())
            .ok_or_else(|| PaymentError::StripeApiError { 
                message: "tier 메타데이터가 없음".to_string() 
            })?;

        let guild_id: u64 = guild_id_str.parse()
            .map_err(|_| PaymentError::StripeApiError { 
                message: "잘못된 guild_id 형식".to_string() 
            })?;

        let tier: SubscriptionTier = tier_str.parse()
            .map_err(|_| PaymentError::InvalidTier(tier_str.to_string()))?;

        // 구독 정보 업데이트
        let subscription = GuildSubscription {
            guild_id,
            tier: tier.clone(),
            is_active: true,
            stripe_customer_id: None, // 추후 customer 정보에서 가져와서 설정
            stripe_subscription_id: Some(event.id.clone()),
            created_at: chrono::Utc::now(),
            expires_at: None, // 추후 subscription 정보에서 가져와서 설정
            last_payment_at: Some(chrono::Utc::now()),
            feed_count: 0,
        };

        firestore.save_guild_subscription(&subscription).await?;
        println!("구독 활성화 완료: 서버 {} -> {:?}", guild_id, tier);

        Ok(())
    }

    /// 결제 성공 처리
    async fn handle_payment_succeeded(
        &self,
        _event: &StripeWebhookEvent,
        _firestore: &crate::firestore::FirestoreService,
    ) -> Result<(), PaymentError> {
        // 필요시 결제 기록 저장 등의 로직 추가
        println!("결제 성공 처리됨");
        Ok(())
    }

    /// 결제 실패 처리
    async fn handle_payment_failed(
        &self,
        event: &StripeWebhookEvent,
        firestore: &crate::firestore::FirestoreService,
    ) -> Result<(), PaymentError> {
        // 결제 실패 시 구독 비활성화 로직
        if let Some(customer_id) = event.data.object.get("customer").and_then(|v| v.as_str()) {
            // customer_id로 guild_id 찾아서 구독 비활성화
            println!("결제 실패로 인한 구독 처리 필요: customer {}", customer_id);
        }
        Ok(())
    }

    /// 구독 취소 처리
    async fn handle_subscription_cancelled(
        &self,
        event: &StripeWebhookEvent,
        firestore: &crate::firestore::FirestoreService,
    ) -> Result<(), PaymentError> {
        // subscription ID로 guild_id 찾아서 구독 비활성화
        if let Some(subscription_id) = event.data.object.get("id").and_then(|v| v.as_str()) {
            println!("구독 취소 처리 필요: subscription {}", subscription_id);
            // TODO: subscription_id로 guild 찾기 및 비활성화
        }
        Ok(())
    }

    /// Webhook 서명 검증
    fn verify_webhook_signature(&self, payload: &str, signature: &str) -> bool {
        // Stripe webhook 서명 형식: t=timestamp,v1=signature
        let parts: Vec<&str> = signature.split(',').collect();
        let mut timestamp = "";
        let mut v1_signature = "";

        for part in parts {
            if let Some((key, value)) = part.split_once('=') {
                match key {
                    "t" => timestamp = value,
                    "v1" => v1_signature = value,
                    _ => {}
                }
            }
        }

        if timestamp.is_empty() || v1_signature.is_empty() {
            return false;
        }

        // HMAC-SHA256으로 서명 검증
        let signed_payload = format!("{}.{}", timestamp, payload);
        
        if let Ok(mut mac) = HmacSha256::new_from_slice(self.webhook_secret.as_bytes()) {
            mac.update(signed_payload.as_bytes());
            let expected_signature = hex::encode(mac.finalize().into_bytes());
            
            // 상수 시간 비교로 보안 강화
            expected_signature == v1_signature
        } else {
            false
        }
    }
}

// Stripe API 요청/응답 구조체들
#[derive(Serialize)]
struct CreateCheckoutSession {
    success_url: String,
    cancel_url: String,
    payment_method_types: Vec<String>,
    mode: String,
    line_items: Vec<CheckoutSessionLineItem>,
    metadata: HashMap<String, String>,
}

#[derive(Serialize)]
struct CheckoutSessionLineItem {
    price: String,
    quantity: u32,
}

#[derive(Deserialize)]
struct CheckoutSessionResponse {
    id: String,
    url: String,
}

#[derive(Deserialize)]
struct StripeSubscription {
    id: String,
    status: String,
    current_period_end: Option<i64>,
}

/// Stripe Webhook 이벤트
#[derive(Debug, Deserialize)]
pub struct StripeWebhookEvent {
    pub id: String,
    #[serde(rename = "type")]
    pub event_type: String,
    pub data: StripeWebhookData,
}

#[derive(Debug, Deserialize)]
pub struct StripeWebhookData {
    pub object: serde_json::Value,
}
