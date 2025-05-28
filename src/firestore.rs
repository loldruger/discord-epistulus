use firestore::*;
use serde::Serialize;
use std::collections::HashMap;
use crate::models::{FeedSource, ChannelSubscription};

#[derive(Debug, thiserror::Error)]
pub enum FirestoreError {
    #[error("Firestore 오류: {0}")]
    FirestoreError(#[from] firestore::errors::FirestoreError),
    #[error("직렬화 오류: {0}")]
    SerializationError(#[from] serde_json::Error),
}

pub struct FirestoreService {
    db: FirestoreDb,
}

impl FirestoreService {
    /// Firestore 서비스 초기화
    pub async fn new() -> Result<Self, FirestoreError> {
        let db = FirestoreDb::new("discord-epistulus")
            .await
            .map_err(FirestoreError::FirestoreError)?;
        
        Ok(Self { db })
    }

    /// 새로운 피드 소스 저장
    pub async fn save_feed_source(&self, feed: &FeedSource) -> Result<(), FirestoreError> {
        self.db
            .fluent()
            .update()
            .in_col("feeds")
            .document_id(&feed.id)
            .object(feed)
            .execute::<()>()
            .await
            .map_err(FirestoreError::FirestoreError)?;
        
        println!("피드 '{}' Firestore에 저장됨", feed.name);
        Ok(())
    }

    /// 피드 소스 삭제
    pub async fn delete_feed_source(&self, feed_id: &str) -> Result<(), FirestoreError> {
        self.db
            .fluent()
            .delete()
            .from("feeds")
            .document_id(feed_id)
            .execute()
            .await
            .map_err(FirestoreError::FirestoreError)?;
        
        println!("피드 '{}' Firestore에서 삭제됨", feed_id);
        Ok(())
    }

    /// 모든 피드 소스 로드
    pub async fn load_all_feeds(&self) -> Result<HashMap<String, FeedSource>, FirestoreError> {
        let feeds: Vec<FeedSource> = self.db
            .fluent()
            .select()
            .from("feeds")
            .obj()
            .query()
            .await
            .map_err(FirestoreError::FirestoreError)?;
        
        let feeds_map: HashMap<String, FeedSource> = feeds.into_iter()
            .map(|feed| (feed.id.clone(), feed))
            .collect();
        
        println!("Firestore에서 {}개의 피드 로드됨", feeds_map.len());
        Ok(feeds_map)
    }

    /// 특정 피드 소스 로드
    pub async fn load_feed_source(&self, feed_id: &str) -> Result<Option<FeedSource>, FirestoreError> {
        let feed: Option<FeedSource> = self.db
            .fluent()
            .select()
            .by_id_in("feeds")
            .obj()
            .one(feed_id)
            .await
            .map_err(FirestoreError::FirestoreError)?;
        
        Ok(feed)
    }

    /// 채널 구독 정보 저장
    pub async fn save_subscription(&self, subscription: &ChannelSubscription) -> Result<(), FirestoreError> {
        let doc_id = subscription.channel_id.to_string();
        
        self.db
            .fluent()
            .update()
            .in_col("subscriptions")
            .document_id(&doc_id)
            .object(subscription)
            .execute::<()>()
            .await
            .map_err(FirestoreError::FirestoreError)?;
        
        println!("채널 {} 구독 정보 Firestore에 저장됨", subscription.channel_id);
        Ok(())
    }

    /// 채널 구독 정보 삭제
    pub async fn delete_subscription(&self, channel_id: u64) -> Result<(), FirestoreError> {
        let doc_id = channel_id.to_string();
        
        self.db
            .fluent()
            .delete()
            .from("subscriptions")
            .document_id(&doc_id)
            .execute()
            .await
            .map_err(FirestoreError::FirestoreError)?;
        
        println!("채널 {} 구독 정보 Firestore에서 삭제됨", channel_id);
        Ok(())
    }

    /// 모든 채널 구독 정보 로드
    pub async fn load_all_subscriptions(&self) -> Result<HashMap<u64, ChannelSubscription>, FirestoreError> {
        let subscriptions: Vec<ChannelSubscription> = self.db
            .fluent()
            .select()
            .from("subscriptions")
            .obj()
            .query()
            .await
            .map_err(FirestoreError::FirestoreError)?;
        
        let subscriptions_map: HashMap<u64, ChannelSubscription> = subscriptions.into_iter()
            .map(|sub| (sub.channel_id, sub))
            .collect();
        
        println!("Firestore에서 {}개의 구독 정보 로드됨", subscriptions_map.len());
        Ok(subscriptions_map)
    }

    /// 특정 채널의 구독 정보 로드
    pub async fn load_subscription(&self, channel_id: u64) -> Result<Option<ChannelSubscription>, FirestoreError> {
        let doc_id = channel_id.to_string();
        
        let subscription: Option<ChannelSubscription> = self.db
            .fluent()
            .select()
            .by_id_in("subscriptions")
            .obj()
            .one(&doc_id)
            .await
            .map_err(FirestoreError::FirestoreError)?;
        
        Ok(subscription)
    }

    /// 피드 소스의 last_updated 시간 업데이트
    pub async fn update_feed_last_updated(&self, feed_id: &str, last_updated: chrono::DateTime<chrono::Utc>) -> Result<(), FirestoreError> {
        #[derive(Serialize, serde::Deserialize)]
        struct UpdateData {
            last_updated: Option<chrono::DateTime<chrono::Utc>>,
        }

        let update_data = UpdateData {
            last_updated: Some(last_updated),
        };

        self.db
            .fluent()
            .update()
            .in_col("feeds")
            .document_id(feed_id)
            .object(&update_data)
            .execute::<()>()
            .await
            .map_err(FirestoreError::FirestoreError)?;
        
        Ok(())
    }

    /// 데이터베이스 초기화 (개발/테스트용)
    pub async fn initialize_database(&self) -> Result<(), FirestoreError> {
        // 필요한 인덱스나 초기 설정을 여기서 처리
        println!("Firestore 데이터베이스 초기화 완료");
        Ok(())
    }
}

impl Clone for FirestoreService {
    fn clone(&self) -> Self {
        Self {
            db: self.db.clone(),
        }
    }
}
