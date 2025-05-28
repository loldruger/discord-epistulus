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
