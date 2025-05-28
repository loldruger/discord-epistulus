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

    /// 특정 서버의 모든 피드 로드
    pub async fn load_feeds_by_guild(&self, guild_id: u64) -> Result<HashMap<String, FeedSource>, FirestoreError> {
        // 모든 피드를 가져와서 클라이언트에서 필터링
        let all_feeds: Vec<(String, FeedSource)> = self.db
            .fluent()
            .select()
            .from("feeds")
            .obj()
            .query()
            .await
            .map_err(FirestoreError::FirestoreError)?;

        let mut feed_map = HashMap::new();
        for (_doc_id, feed) in all_feeds {
            // 해당 서버의 피드만 필터링
            if feed.guild_id == Some(guild_id) {
                let key = format!("{}:{}", guild_id, feed.id);
                feed_map.insert(key, feed);
            }
        }

        println!("서버 {}의 {}개 피드를 Firestore에서 로드함", guild_id, feed_map.len());
        Ok(feed_map)
    }

    /// 서버별로 분리된 피드 키 생성
    pub fn create_feed_key(&self, guild_id: Option<u64>, feed_id: &str) -> String {
        match guild_id {
            Some(gid) => format!("{}:{}", gid, feed_id),
            None => format!("global:{}", feed_id), // DM에서 사용할 경우
        }
    }

    /// 피드 키에서 guild_id와 feed_id 분리
    pub fn parse_feed_key(&self, key: &str) -> (Option<u64>, String) {
        if let Some((prefix, feed_id)) = key.split_once(':') {
            if prefix == "global" {
                (None, feed_id.to_string())
            } else if let Ok(guild_id) = prefix.parse::<u64>() {
                (Some(guild_id), feed_id.to_string())
            } else {
                (None, key.to_string()) // 잘못된 형식인 경우 전체를 feed_id로 처리
            }
        } else {
            (None, key.to_string()) // 구분자가 없는 경우
        }
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
