use crate::models::{FeedSource, FeedType, BlogPost};
use reqwest::Client;
use rss::Channel;
use std::time::Duration;
use tokio::time::timeout;

pub struct FeedCollector {
    client: Client,
    _user_agent: String,
    timeout_duration: Duration,
}

impl FeedCollector {
    pub fn new(user_agent: String) -> Self {
        let client = Client::builder()
            .user_agent(&user_agent)
            .timeout(Duration::from_secs(30))
            .build()
            .expect("HTTP 클라이언트 생성 실패");

        Self {
            client,
            _user_agent: user_agent,
            timeout_duration: Duration::from_secs(30),
        }
    }

    /// RSS 피드에서 새로운 포스트들을 수집
    pub async fn collect_posts(&self, source: &FeedSource) -> Result<Vec<BlogPost>, FeedError> {
        let response = timeout(
            self.timeout_duration,
            self.client.get(&source.url).send()
        ).await
        .map_err(|_| FeedError::Timeout)?
        .map_err(FeedError::Http)?;

        if !response.status().is_success() {
            return Err(FeedError::BadStatus(response.status().as_u16()));
        }

        let content = response.text().await.map_err(FeedError::Http)?;
        
        match source.feed_type {
            FeedType::Rss | FeedType::Atom => self.parse_rss_feed(&content, source).await,
            FeedType::JsonFeed => self.parse_json_feed(&content, source).await,
            FeedType::Newsletter => Err(FeedError::UnsupportedType),
        }
    }

    /// RSS/Atom 피드 파싱
    async fn parse_rss_feed(&self, content: &str, source: &FeedSource) -> Result<Vec<BlogPost>, FeedError> {
        let channel = Channel::read_from(content.as_bytes())
            .map_err(|e| FeedError::ParseError(e.to_string()))?;

        let mut posts = Vec::new();

        for item in channel.items() {
            let post = BlogPost {
                id: self.generate_post_id(source, item.link().unwrap_or(""), item.title().unwrap_or("")),
                title: item.title().unwrap_or("제목 없음").to_string(),
                link: item.link().unwrap_or("").to_string(),
                description: item.description().map(|s| s.to_string()),
                author: item.author().map(|s| s.to_string()),
                published: item.pub_date()
                    .and_then(|date_str| chrono::DateTime::parse_from_rfc2822(date_str).ok())
                    .map(|dt| dt.with_timezone(&chrono::Utc)),
                updated: None,
                source_id: source.id.clone(),
                tags: item.categories()
                    .iter()
                    .map(|cat| cat.name().to_string())
                    .collect(),
                content: item.content().map(|s| s.to_string()),
            };
            posts.push(post);
        }

        Ok(posts)
    }

    /// JSON Feed 파싱 (미래 확장용)
    async fn parse_json_feed(&self, _content: &str, _source: &FeedSource) -> Result<Vec<BlogPost>, FeedError> {
        // TODO: JSON Feed 지원 구현
        Err(FeedError::UnsupportedType)
    }

    /// 포스트 ID 생성 (중복 체크용)
    fn generate_post_id(&self, source: &FeedSource, link: &str, title: &str) -> String {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};

        let mut hasher = DefaultHasher::new();
        source.id.hash(&mut hasher);
        link.hash(&mut hasher);
        title.hash(&mut hasher);
        
        format!("{}_{:x}", source.id, hasher.finish())
    }

    /// 피드가 유효한지 검증
    pub async fn validate_feed(&self, url: &str) -> Result<FeedType, FeedError> {
        let response = timeout(
            self.timeout_duration,
            self.client.head(url).send()
        ).await
        .map_err(|_| FeedError::Timeout)?
        .map_err(FeedError::Http)?;

        if !response.status().is_success() {
            return Err(FeedError::BadStatus(response.status().as_u16()));
        }

        // Content-Type으로 피드 타입 추정
        if let Some(content_type) = response.headers().get("content-type") {
            let content_type = content_type.to_str().unwrap_or("");
            if content_type.contains("application/rss+xml") {
                return Ok(FeedType::Rss);
            } else if content_type.contains("application/atom+xml") {
                return Ok(FeedType::Atom);
            } else if content_type.contains("application/feed+json") {
                return Ok(FeedType::JsonFeed);
            }
        }

        // 실제 콘텐츠를 조금 받아서 확인
        let response = self.client.get(url).send().await.map_err(FeedError::Http)?;
        let partial_content = response.text().await.map_err(FeedError::Http)?;
        
        if partial_content.contains("<rss") {
            Ok(FeedType::Rss)
        } else if partial_content.contains("<feed") && partial_content.contains("xmlns=\"http://www.w3.org/2005/Atom\"") {
            Ok(FeedType::Atom)
        } else {
            Err(FeedError::UnsupportedType)
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum FeedError {
    #[error("HTTP 요청 실패: {0}")]
    Http(#[from] reqwest::Error),
    
    #[error("요청 시간 초과")]
    Timeout,
    
    #[error("HTTP 상태 오류: {0}")]
    BadStatus(u16),
    
    #[error("피드 파싱 오류: {0}")]
    ParseError(String),
    
    #[error("지원하지 않는 피드 타입")]
    UnsupportedType,
}
