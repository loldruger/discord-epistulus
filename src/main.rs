use axum::{routing::get, Router}; // Axum 추가
use serenity::async_trait;
use serenity::model::channel::Message;
use serenity::model::gateway::Ready;
use serenity::prelude::*;
use std::env;
use std::net::SocketAddr; // SocketAddr 추가

struct Handler;

#[async_trait]
impl EventHandler for Handler {
    async fn message(&self, ctx: Context, msg: Message) {
        if msg.content == "!ping" {
            if let Err(why) = msg.channel_id.say(&ctx.http, "Pong!").await {
                println!("Error sending message: {why:?}");
            }
        }
    }

    async fn ready(&self, _: Context, ready: Ready) {
        println!("{} is connected!", ready.user.name);
    }
}

// Axum 핸들러 함수
async fn root_handler() -> &'static str {
    "Discord Epitulus Bot is running!"
}

async fn health_handler() -> &'static str {
    "OK"
}

#[tokio::main]
async fn main() {
    // 로깅 설정 (선택 사항, tracing 사용 시)
    // tracing_subscriber::fmt::init(); // Cargo.toml에서 tracing 관련 주석 해제 필요

    // Discord 봇 설정
    let token = env::var("DISCORD_TOKEN").expect("Expected a DISCORD_TOKEN in the environment");
    let intents = GatewayIntents::GUILD_MESSAGES
        | GatewayIntents::DIRECT_MESSAGES
        | GatewayIntents::MESSAGE_CONTENT;

    let serenity_client_future = async {
        let mut client = Client::builder(&token, intents)
            .event_handler(Handler)
            .await
            .expect("Err creating client");

        if let Err(why) = client.start().await {
            println!("Serenity client error: {why:?}");
        }
    };

    // Axum 웹 서버 설정
    let app = Router::new()
        .route("/", get(root_handler)) // 루트 경로 핸들러
        .route("/health", get(health_handler)); // 헬스 체크 경로 (Cloud Run 등에서 유용)

    // Cloud Run은 PORT 환경 변수를 통해 포트를 제공합니다. 없으면 8080 사용.
    let port = env::var("PORT").unwrap_or_else(|_| "8080".to_string()).parse::<u16>().expect("PORT must be a valid u16");
    let addr = SocketAddr::from(([0, 0, 0, 0], port)); // 모든 인터페이스에서 수신 대기
    println!("Axum server listening on {}", addr);

    let axum_server_future = async {
        axum::serve(tokio::net::TcpListener::bind(addr).await.unwrap(), app) // axum::Server::bind 변경됨
            .await
            .unwrap();
    };
    
    // Serenity 클라이언트와 Axum 서버를 동시에 실행
    tokio::select! {
        _ = serenity_client_future => {
            println!("Serenity client task completed.");
        },
        _ = axum_server_future => {
            println!("Axum server task completed.");
        },
        _ = tokio::signal::ctrl_c() => { // Ctrl+C (SIGINT) 시그널 처리
            println!("Received Ctrl+C, shutting down.");
        }
    }

    println!("Application shutting down.");
}
