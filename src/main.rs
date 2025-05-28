use axum::{routing::get, Router};
use poise::serenity_prelude as serenity;
use std::env;
use std::sync::Arc;
use tokio::net::TcpListener;
use std::time::Duration;

mod firestore;
mod commands;
mod models;
mod feed_collector;
mod notification;

use crate::feed_collector::FeedCollector;
use crate::models::{FeedSource, ChannelSubscription};
use crate::notification::NotificationService;
use crate::firestore::FirestoreService;
use std::collections::HashMap;

// Poise 타입 정의 (commands 모듈에서도 사용)
pub type Error = Box<dyn std::error::Error + Send + Sync>;
pub type Context<'a> = poise::Context<'a, BotState, Error>;

// 간단한 인메모리 저장소 (Firestore와 동기화)
// 피드는 서버별로 분리하여 관리: "guild_id:feed_id" 형태의 키 사용
type FeedStorage = Arc<tokio::sync::RwLock<HashMap<String, FeedSource>>>;
type SubscriptionStorage = Arc<tokio::sync::RwLock<HashMap<u64, ChannelSubscription>>>;

#[derive(Clone)]
pub struct BotState {
    pub feeds: FeedStorage,
    pub subscriptions: SubscriptionStorage,
    pub feed_collector: Arc<FeedCollector>,
    pub notification_service: Arc<NotificationService>,
    pub firestore: Arc<FirestoreService>,
}

impl BotState {
    pub async fn new() -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        // Firestore 서비스 초기화
        let firestore = Arc::new(FirestoreService::new().await?);
        
        // 초기화 시에는 빈 저장소로 시작 (서버별 데이터는 런타임에 로드)
        let feeds_data = HashMap::new();
        
        let subscriptions_data = firestore.load_all_subscriptions().await.unwrap_or_else(|e| {
            eprintln!("구독 데이터 로드 실패: {}. 빈 저장소로 시작합니다.", e);
            HashMap::new()
        });

        Ok(Self {
            feeds: Arc::new(tokio::sync::RwLock::new(feeds_data)),
            subscriptions: Arc::new(tokio::sync::RwLock::new(subscriptions_data)),
            feed_collector: Arc::new(FeedCollector::new("Discord-Epistulus-Bot/1.0".to_string())),
            notification_service: Arc::new(NotificationService::new()),
            firestore,
        })
    }

    /// 특정 서버의 피드 데이터를 로드
    pub async fn load_guild_feeds(&self, guild_id: u64) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let guild_feeds = self.firestore.load_feeds_by_guild(guild_id).await.unwrap_or_else(|e| {
            eprintln!("서버 {}의 피드 데이터 로드 실패: {}. 빈 상태로 계속합니다.", guild_id, e);
            HashMap::new()
        });

        let mut feeds = self.feeds.write().await;
        for (key, feed) in guild_feeds {
            feeds.insert(key, feed);
        }

        println!("서버 {}의 피드 데이터 로드 완료", guild_id);
        Ok(())
    }

    /// 새로운 포스트를 수집하고 구독자들에게 알림을 보냄
    pub async fn collect_and_notify(&self, ctx: &serenity::Context) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let feeds = self.feeds.read().await;
        let subscriptions = self.subscriptions.read().await;

        for (_feed_key, feed_source) in feeds.iter() {
            if !feed_source.enabled {
                continue;
            }

            // 피드에서 새로운 포스트 수집
            match self.feed_collector.collect_posts(feed_source).await {
                Ok(posts) => {
                    if posts.is_empty() {
                        continue;
                    }

                    // 이 피드를 구독하는 채널들 찾기 (feed_id만으로 비교)
                    let feed_id = &feed_source.id;
                    let subscribing_channels: Vec<_> = subscriptions.iter()
                        .filter(|(_, sub)| {
                            // 서버가 일치하고 feed_id를 구독하는 채널인지 확인
                            sub.guild_id == feed_source.guild_id && 
                            sub.subscribed_sources.contains(feed_id)
                        })
                        .collect();

                    for (channel_id, subscription) in subscribing_channels {
                        let channel_id = serenity::model::id::ChannelId::new(*channel_id);
                        
                        // 새로운 포스트들을 알림으로 보내기
                        if let Err(e) = NotificationService::send_notifications(
                            ctx,
                            channel_id,
                            posts.clone(),
                            &subscription.notification_settings,
                        ).await {
                            eprintln!("채널 {}에 알림 전송 실패: {:?}", channel_id, e);
                        }
                    }

                    println!("피드 '{}' (서버: {:?}): {}개의 새로운 포스트 처리됨", 
                        feed_source.name, feed_source.guild_id, posts.len());
                    
                    // Firestore에 last_updated 시간 업데이트
                    if let Err(e) = self.firestore.update_feed_last_updated(feed_id, chrono::Utc::now()).await {
                        eprintln!("피드 업데이트 시간 저장 실패: {}", e);
                    }
                }
                Err(e) => {
                    eprintln!("피드 '{}' 수집 실패: {:?}", feed_source.name, e);
                }
            }
        }

        Ok(())
    }
}

// Event handler for when the bot is ready
async fn on_ready(
    _ctx: &serenity::Context,
    ready: &serenity::Ready,
    _framework: &poise::Framework<BotState, Error>,
) -> Result<(), Error> {
    println!("{} is connected!", ready.user.name);
    Ok(())
}

// Main function
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    // 환경 변수에서 Discord 토큰 읽기
    let token = env::var("DISCORD_TOKEN")
        .expect("환경 변수 DISCORD_TOKEN이 설정되지 않았습니다");
    
    // Bot state 초기화 (Firestore 연결 포함)
    let bot_state = match BotState::new().await {
        Ok(state) => Arc::new(state),
        Err(e) => {
            eprintln!("Bot state 초기화 실패: {}", e);
            return Err(e);
        }
    };
    
    // 백그라운드 피드 수집 작업 시작
    let _feed_collection_state = bot_state.clone();
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(Duration::from_secs(300)); // 5분마다
        loop {
            interval.tick().await;
            // 여기서는 Context가 없으므로 피드 수집만 수행
            // 실제 알림은 다른 방법으로 처리해야 함
            println!("피드 수집 작업 실행 중...");
        }
    });

    // Poise 프레임워크 설정
    let framework = poise::Framework::builder()
        .options(poise::FrameworkOptions {
            commands: vec![
                commands::ping(),
                commands::help(),
                commands::add_feed(),
                commands::list_feeds(),
                commands::remove_feed(),
                commands::subscribe(),
                commands::unsubscribe(),
                commands::list_subscriptions(),
                commands::test_feed(),
                commands::status(),
            ],
            ..Default::default()
        })
        .setup(|ctx, _ready, framework| {
            Box::pin(async move {
                poise::builtins::register_globally(ctx, &framework.options().commands).await?;
                println!("Bot is connected!");
                Ok((*bot_state).clone())
            })
        })
        .build();

    // Discord client 생성 및 실행
    let mut client = serenity::ClientBuilder::new(token, serenity::GatewayIntents::non_privileged())
        .framework(framework)
        .await?;

    // 웹 서버 시작 (Firebase Functions 호스팅용)
    let app = Router::new()
        .route("/", get(|| async { "Discord Epistulus Bot is running!" }))
        .route("/health", get(|| async { "OK" }));

    let listener = TcpListener::bind("0.0.0.0:8080").await.unwrap();
    println!("웹 서버가 8080 포트에서 시작되었습니다.");

    // Discord 봇과 웹 서버를 동시에 실행
    tokio::select! {
        result = client.start() => {
            if let Err(why) = result {
                println!("Discord 클라이언트 오류: {:?}", why);
            }
        }
        result = axum::serve(listener, app) => {
            if let Err(why) = result {
                println!("웹 서버 오류: {:?}", why);
            }
        }
    }

    Ok(())
}
