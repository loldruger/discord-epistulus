use serde::{Deserialize, Serialize};

/// RSS 피드 소스 정보
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FeedSource {
    pub id: String,
    pub name: String,
    pub url: String,
    pub feed_type: FeedType,
    pub last_updated: Option<chrono::DateTime<chrono::Utc>>,
    pub enabled: bool,
    pub tags: Vec<String>,
    pub guild_id: Option<u64>, // 서버별 피드 분리를 위한 필드
}

/// 피드 타입 (RSS, Atom, JSON Feed 등)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum FeedType {
    Rss,
    Atom,
    JsonFeed,
    Newsletter, // 이메일 구독용
}

/// 블로그 포스트 정보
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlogPost {
    pub id: String,
    pub title: String,
    pub link: String,
    pub description: Option<String>,
    pub author: Option<String>,
    pub published: Option<chrono::DateTime<chrono::Utc>>,
    pub updated: Option<chrono::DateTime<chrono::Utc>>,
    pub source_id: String,
    pub tags: Vec<String>,
    pub content: Option<String>,
}

/// 디스코드 채널 구독 설정
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChannelSubscription {
    pub channel_id: u64,
    pub guild_id: Option<u64>,
    pub subscribed_sources: Vec<String>, // FeedSource ID들
    pub filters: SubscriptionFilters,
    pub notification_settings: NotificationSettings,
}

/// 구독 필터 설정
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubscriptionFilters {
    pub include_tags: Vec<String>,
    pub exclude_tags: Vec<String>,
    pub keywords: Vec<String>,
    pub min_publish_interval: Option<chrono::Duration>,
}

/// 알림 설정
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationSettings {
    pub format: NotificationFormat,
    pub include_preview: bool,
    pub mention_role: Option<u64>,
    pub max_posts_per_batch: u32,
}

/// 알림 포맷
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum NotificationFormat {
    Simple,     // 제목 + 링크
    Rich,       // 임베드 메시지
    Summary,    // 여러 글을 요약해서
}

/// 봇 설정
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BotConfig {
    pub check_interval: chrono::Duration,
    pub max_concurrent_feeds: usize,
    pub user_agent: String,
    pub database_url: Option<String>,
}

impl Default for BotConfig {
    fn default() -> Self {
        Self {
            check_interval: chrono::Duration::minutes(30),
            max_concurrent_feeds: 10,
            user_agent: "Discord-Epistulus-Bot/0.1.0".to_string(),
            database_url: None,
        }
    }
}

impl Default for SubscriptionFilters {
    fn default() -> Self {
        Self {
            include_tags: vec![],
            exclude_tags: vec![],
            keywords: vec![],
            min_publish_interval: None,
        }
    }
}

impl Default for NotificationSettings {
    fn default() -> Self {
        Self {
            format: NotificationFormat::Rich,
            include_preview: true,
            mention_role: None,
            max_posts_per_batch: 5,
        }
    }
}

/// 구독 플랜 종류
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum SubscriptionTier {
    Free,
    Premium,
    Enterprise,
}

impl SubscriptionTier {
    /// 플랜별 피드 제한 수 (표시용)
    pub fn feed_limit(&self) -> String {
        match self {
            SubscriptionTier::Free => "3개".to_string(),
            SubscriptionTier::Premium => "무제한".to_string(),
            SubscriptionTier::Enterprise => "무제한".to_string(),
        }
    }
    
    /// 플랜별 피드 제한 수 (숫자)
    pub fn feed_limit_number(&self) -> Option<usize> {
        match self {
            SubscriptionTier::Free => Some(3),
            SubscriptionTier::Premium => None, // 무제한
            SubscriptionTier::Enterprise => None, // 무제한
        }
    }
    
    /// 플랜별 월 구독료 (USD 센트)
    pub fn price_cents(&self) -> Option<u64> {
        match self {
            SubscriptionTier::Free => None,
            SubscriptionTier::Premium => Some(999), // $9.99/월
            SubscriptionTier::Enterprise => Some(2999), // $29.99/월
        }
    }
    
    /// 플랜 설명
    pub fn description(&self) -> &'static str {
        match self {
            SubscriptionTier::Free => "기본 RSS/Atom 피드 지원",
            SubscriptionTier::Premium => "무제한 피드, 우선 지원, 고급 필터링",
            SubscriptionTier::Enterprise => "무제한 피드, 다중 서버 지원, 전용 지원, 맞춤 기능",
        }
    }
    
    /// 플랜 이름
    pub fn display_name(&self) -> &'static str {
        match self {
            SubscriptionTier::Free => "무료",
            SubscriptionTier::Premium => "프리미엄",
            SubscriptionTier::Enterprise => "엔터프라이즈",
        }
    }
}

impl std::fmt::Display for SubscriptionTier {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SubscriptionTier::Free => write!(f, "free"),
            SubscriptionTier::Premium => write!(f, "premium"),
            SubscriptionTier::Enterprise => write!(f, "enterprise"),
        }
    }
}

impl std::str::FromStr for SubscriptionTier {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "free" => Ok(SubscriptionTier::Free),
            "premium" => Ok(SubscriptionTier::Premium),
            "enterprise" => Ok(SubscriptionTier::Enterprise),
            _ => Err(format!("유효하지 않은 구독 플랜: {}", s)),
        }
    }
}

/// 서버별 구독 정보
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GuildSubscription {
    pub guild_id: u64,
    pub tier: SubscriptionTier,
    pub stripe_customer_id: Option<String>,
    pub stripe_subscription_id: Option<String>,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub expires_at: Option<chrono::DateTime<chrono::Utc>>,
    pub last_payment_at: Option<chrono::DateTime<chrono::Utc>>,
    pub is_active: bool,
    pub feed_count: usize, // 현재 사용 중인 피드 수
}

impl Default for GuildSubscription {
    fn default() -> Self {
        Self {
            guild_id: 0,
            tier: SubscriptionTier::Free,
            stripe_customer_id: None,
            stripe_subscription_id: None,
            created_at: chrono::Utc::now(),
            expires_at: None,
            last_payment_at: None,
            is_active: true,
            feed_count: 0,
        }
    }
}

impl GuildSubscription {
    /// 구독이 유효한지 확인
    pub fn is_valid(&self) -> bool {
        self.is_active && 
        (self.expires_at.is_none() || 
         self.expires_at.map_or(true, |exp| exp > chrono::Utc::now()))
    }
    
    /// 피드 추가 가능한지 확인
    pub fn can_add_feed(&self) -> bool {
        if !self.is_valid() {
            return false;
        }
        
        match self.tier.feed_limit_number() {
            Some(limit) => self.feed_count < limit,
            None => true, // 무제한
        }
    }
}

/// 결제 히스토리
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaymentHistory {
    pub id: String,
    pub guild_id: u64,
    pub stripe_payment_intent_id: String,
    pub amount_cents: u64,
    pub currency: String,
    pub tier: SubscriptionTier,
    pub status: PaymentStatus,
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub processed_at: Option<chrono::DateTime<chrono::Utc>>,
}

/// 결제 상태
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PaymentStatus {
    Pending,
    Succeeded,
    Failed,
    Canceled,
    Refunded,
}
