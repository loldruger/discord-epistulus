use axum::{routing::get, Router};
use serenity::async_trait;
use serenity::model::channel::Message;
use serenity::model::gateway::Ready;
use serenity::prelude::*;
use std::env;
use std::net::SocketAddr;
use tokio::net::TcpListener;

mod firestore;
mod commands;

struct Handler;

#[async_trait]
impl EventHandler for Handler {
    async fn message(&self, ctx: Context, msg: Message) {
        if msg.content == "!ping" {
            if let Err(why) = msg.channel_id.say(&ctx.http, "Pong!").await {
                eprintln!("Error sending message: {:?}", why);
            }
        }
    }

    async fn ready(&self, _: Context, ready: Ready) {
        println!("{} is connected!", ready.user.name);
    }
}

async fn root_handler() -> &'static str {
    "Discord Epistulus Bot is running!"
}

async fn health_handler() -> &'static str {
    "OK"
}

#[tokio::main]
async fn main() {
    // Discord 봇 설정 (옵셔널)
    let token = env::var("DISCORD_TOKEN").ok();
    let intents = GatewayIntents::GUILD_MESSAGES
        | GatewayIntents::DIRECT_MESSAGES
        | GatewayIntents::MESSAGE_CONTENT;

    // Axum 웹 서버 설정
    let app = Router::new()
        .route("/", get(root_handler))
        .route("/health", get(health_handler));

    let port_str = env::var("PORT").unwrap_or_else(|_| "8080".to_string());
    let port = match port_str.parse::<u16>() {
        Ok(p) => p,
        Err(e) => {
            eprintln!("Invalid PORT environment variable '{}': {}. Defaulting to 8080.", port_str, e);
            8080
        }
    };
    let addr = SocketAddr::from(([0, 0, 0, 0], port));

    // TCP 리스너 바인딩 시도
    let listener = match TcpListener::bind(addr).await {
        Ok(l) => {
            println!("Successfully bound Axum server to {}", addr);
            l
        }
        Err(e) => {
            eprintln!("Fatal: Failed to bind Axum server to {}: {}", addr, e);
            std::process::exit(1);
        }
    };
    println!("Axum server will listen on {}", addr);

    let axum_server_future = async {
        println!("Starting Axum server...");
        if let Err(e) = axum::serve(listener, app).await {
            eprintln!("Axum server error: {:?}", e);
        }
        println!("Axum server task completed.");
    };

    let serenity_client_future = async {
        if let Some(token) = token {
            println!("Attempting to create Serenity client instance...");
            let client_result = Client::builder(&token, intents)
                .event_handler(Handler)
                .await;

            let mut client = match client_result {
                Ok(c) => {
                    println!("Serenity client instance created successfully.");
                    c
                }
                Err(e) => {
                    eprintln!("Error creating Serenity client instance: {:?}", e);
                    return;
                }
            };

            println!("Starting Serenity client connection...");
            if let Err(why) = client.start().await {
                eprintln!("Serenity client error during startup or runtime: {:?}", why);
            }
            println!("Serenity client task completed.");
        } else {
            println!("Discord token not provided, skipping Discord bot initialization");
            // Keep the task alive
            loop {
                tokio::time::sleep(tokio::time::Duration::from_secs(3600)).await;
            }
        }
    };
    
    println!("Starting application tasks (Serenity client and Axum server)...");
    tokio::select! {
        _ = serenity_client_future => {
            eprintln!("Serenity client task finished. This might be due to an error or normal shutdown if applicable.");
        },
        _ = axum_server_future => {
            eprintln!("Axum server task finished. This might be due to an error.");
        },
        res = tokio::signal::ctrl_c() => {
            match res {
                Ok(()) => println!("Received Ctrl+C, initiating shutdown."),
                Err(e) => eprintln!("Error waiting for Ctrl+C: {:?}", e),
            }
        }
    }

    println!("Application shutting down.");
}
