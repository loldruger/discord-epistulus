use crate::{BotState, models::{FeedSource, FeedType, ChannelSubscription}};

// Poise 타입 정의
type Error = Box<dyn std::error::Error + Send + Sync>;
type Context<'a> = poise::Context<'a, BotState, Error>;

/// 봇 상태 확인
#[poise::command(slash_command)]
pub async fn ping(ctx: Context<'_>) -> Result<(), Error> {
    ctx.say("🏓 Pong!").await?;
    Ok(())
}

/// 도움말 표시
#[poise::command(slash_command)]
pub async fn help(ctx: Context<'_>) -> Result<(), Error> {
    let help_text = r#"
📰 **Discord Epistulus Bot 명령어**

**피드 관리:**
• `/add_feed` - RSS/Atom 피드 추가
• `/list_feeds` - 등록된 피드 목록 보기
• `/remove_feed` - 피드 제거

**구독 관리:**
• `/subscribe` - 현재 채널에서 피드 구독
• `/unsubscribe` - 현재 채널에서 피드 구독 해제
• `/list_subscriptions` - 현재 채널의 구독 목록

**결제 및 구독:**
• `/billing` - 현재 구독 정보 확인
• `/plans` - 사용 가능한 플랜 정보 보기
• `/upgrade` - 프리미엄/엔터프라이즈 플랜 업그레이드
• `/cancel_subscription` - 구독 취소

**기타:**
• `/ping` - 봇 상태 확인
• `/help` - 이 도움말 표시
• `/test_feed` - 피드 테스트 (최신 1개 포스트 미리보기)
• `/status` - 봇 상태 및 통계 보기
    "#;
    
    ctx.say(help_text).await?;
    Ok(())
}

/// RSS/Atom 피드 추가
#[poise::command(slash_command)]
pub async fn add_feed(
    ctx: Context<'_>,
    #[description = "피드 URL"] url: String,
    #[description = "피드 이름"] name: String,
) -> Result<(), Error> {
    // 서버에서만 실행 가능하도록 제한
    let guild_id = match ctx.guild_id() {
        Some(id) => id.get(),
        None => {
            ctx.say("❌ 이 명령어는 서버에서만 사용할 수 있습니다.").await?;
            return Ok(());
        }
    };

    // URL 유효성 검사
    if !url.starts_with("http://") && !url.starts_with("https://") {
        ctx.say("❌ 올바른 URL을 입력해주세요. (http:// 또는 https://로 시작)").await?;
        return Ok(());
    }

    // 피드 ID 생성 (URL에서 도메인 추출)
    let feed_id = url.replace("https://", "").replace("http://", "")
        .split('/').next().unwrap_or("unknown")
        .replace('.', "_");

    // 서버별 피드 키 생성
    let feed_key = ctx.data().firestore.create_feed_key(Some(guild_id), &feed_id);

    let feed_source = FeedSource {
        id: feed_id.clone(),
        name: name.clone(),
        url: url.clone(),
        feed_type: FeedType::Rss, // 기본값
        last_updated: None,
        enabled: true,
        tags: vec![],
        guild_id: Some(guild_id), // 서버 ID 저장
    };

    // 피드 저장 (서버별 키 사용)
    {
        let mut feeds = ctx.data().feeds.write().await;
        feeds.insert(feed_key.clone(), feed_source.clone());
    }

    // Firestore에 저장
    if let Err(e) = ctx.data().firestore.save_feed_source(&feed_source).await {
        eprintln!("Firestore에 피드 저장 실패: {}", e);
        ctx.say("❌ 피드 저장 중 오류가 발생했습니다. 다시 시도해주세요.").await?;
        return Ok(());
    }

    ctx.say(format!("✅ 피드가 추가되었습니다!\n**이름:** {}\n**ID:** `{}`\n**URL:** {}", name, feed_id, url)).await?;
    Ok(())
}

/// 등록된 피드 목록 보기
#[poise::command(slash_command)]
pub async fn list_feeds(ctx: Context<'_>) -> Result<(), Error> {
    // 서버에서만 실행 가능하도록 제한
    let guild_id = match ctx.guild_id() {
        Some(id) => id.get(),
        None => {
            ctx.say("❌ 이 명령어는 서버에서만 사용할 수 있습니다.").await?;
            return Ok(());
        }
    };

    let feeds = ctx.data().feeds.read().await;
    
    let mut response = "📚 **이 서버의 등록된 피드 목록:**\n\n".to_string();
    
    // 현재 서버의 피드만 필터링
    let server_feeds: Vec<_> = feeds.iter()
        .filter(|(key, feed)| {
            // 키가 "guild_id:feed_id" 형태인지 확인하고 guild_id가 일치하는지 체크
            key.starts_with(&format!("{}:", guild_id)) && 
            feed.guild_id == Some(guild_id)
        })
        .collect();
    
    if server_feeds.is_empty() {
        response.push_str("등록된 피드가 없습니다. `/add_feed` 명령어로 피드를 추가해보세요!");
    } else {
        for (key, feed) in server_feeds {
            let status = if feed.enabled { "🟢" } else { "🔴" };
            // 키에서 feed_id만 추출해서 표시
            let display_id = key.split(':').nth(1).unwrap_or(&feed.id);
            response.push_str(&format!("• {} **{}** (`{}`)\n  {}\n\n", status, feed.name, display_id, feed.url));
        }
    }

    ctx.say(response).await?;
    Ok(())
}

/// 피드 제거
#[poise::command(slash_command)]
pub async fn remove_feed(
    ctx: Context<'_>,
    #[description = "제거할 피드 ID"] feed_id: String,
) -> Result<(), Error> {
    // 서버에서만 실행 가능하도록 제한
    let guild_id = match ctx.guild_id() {
        Some(id) => id.get(),
        None => {
            ctx.say("❌ 이 명령어는 서버에서만 사용할 수 있습니다.").await?;
            return Ok(());
        }
    };

    // 서버별 피드 키 생성
    let feed_key = ctx.data().firestore.create_feed_key(Some(guild_id), &feed_id);

    let mut feeds = ctx.data().feeds.write().await;
    if let Some(removed_feed) = feeds.remove(&feed_key) {
        drop(feeds); // 락 해제
        
        // Firestore에서도 삭제 (실제 document ID 사용)
        if let Err(e) = ctx.data().firestore.delete_feed_source(&feed_id).await {
            eprintln!("Firestore에서 피드 삭제 실패: {}", e);
            ctx.say("❌ 피드 삭제 중 오류가 발생했습니다.").await?;
            return Ok(());
        }
        
        ctx.say(format!("✅ 피드 '{}'이 제거되었습니다.", removed_feed.name)).await?;
    } else {
        ctx.say(format!("❌ 이 서버에서 피드 ID '{}'를 찾을 수 없습니다.", feed_id)).await?;
    }
    Ok(())
}

/// 현재 채널에서 피드 구독
#[poise::command(slash_command)]
pub async fn subscribe(
    ctx: Context<'_>,
    #[description = "구독할 피드 ID"] feed_id: String,
) -> Result<(), Error> {
    // 서버에서만 실행 가능하도록 제한
    let guild_id = match ctx.guild_id() {
        Some(id) => id.get(),
        None => {
            ctx.say("❌ 이 명령어는 서버에서만 사용할 수 있습니다.").await?;
            return Ok(());
        }
    };

    // 서버별 피드 키 생성
    let feed_key = ctx.data().firestore.create_feed_key(Some(guild_id), &feed_id);

    // 피드가 이 서버에 존재하는지 확인
    let feeds = ctx.data().feeds.read().await;
    if !feeds.contains_key(&feed_key) {
        ctx.say(format!("❌ 이 서버에서 피드 ID '{}'를 찾을 수 없습니다.", feed_id)).await?;
        return Ok(());
    }
    let feed_name = feeds.get(&feed_key).unwrap().name.clone();
    drop(feeds);

    // 채널 구독 추가/업데이트
    let channel_id = ctx.channel_id().get();
    let mut subscriptions = ctx.data().subscriptions.write().await;
    
    if let Some(subscription) = subscriptions.get_mut(&channel_id) {
        if !subscription.subscribed_sources.contains(&feed_id) {
            subscription.subscribed_sources.push(feed_id.clone());
        }
    } else {
        let new_subscription = ChannelSubscription {
            channel_id,
            guild_id: Some(guild_id),
            subscribed_sources: vec![feed_id.clone()],
            filters: Default::default(),
            notification_settings: Default::default(),
        };
        subscriptions.insert(channel_id, new_subscription);
    }

    // Firestore에 구독 정보 저장
    if let Some(subscription) = subscriptions.get(&channel_id) {
        if let Err(e) = ctx.data().firestore.save_subscription(subscription).await {
            eprintln!("Firestore에 구독 정보 저장 실패: {}", e);
        }
    }

    ctx.say(format!("✅ 이 채널에서 '{}'을(를) 구독하기 시작했습니다!", feed_name)).await?;
    Ok(())
}

/// 현재 채널에서 피드 구독 해제
#[poise::command(slash_command)]
pub async fn unsubscribe(
    ctx: Context<'_>,
    #[description = "구독 해제할 피드 ID"] feed_id: String,
) -> Result<(), Error> {
    let channel_id = ctx.channel_id().get();
    let mut subscriptions = ctx.data().subscriptions.write().await;
    
    if let Some(subscription) = subscriptions.get_mut(&channel_id) {
        if let Some(pos) = subscription.subscribed_sources.iter().position(|x| x == &feed_id) {
            subscription.subscribed_sources.remove(pos);
            
            // Firestore에 업데이트된 구독 정보 저장
            if let Err(e) = ctx.data().firestore.save_subscription(subscription).await {
                eprintln!("Firestore에 구독 정보 업데이트 실패: {}", e);
            }
            
            ctx.say(format!("✅ 피드 '{}'의 구독을 해제했습니다.", feed_id)).await?;
        } else {
            ctx.say(format!("❌ 이 채널에서는 피드 '{}'를 구독하고 있지 않습니다.", feed_id)).await?;
        }
    } else {
        ctx.say("❌ 이 채널에는 구독 중인 피드가 없습니다.").await?;
    }
    
    Ok(())
}

/// 현재 채널의 구독 목록
#[poise::command(slash_command)]
pub async fn list_subscriptions(ctx: Context<'_>) -> Result<(), Error> {
    let channel_id = ctx.channel_id().get();
    let subscriptions = ctx.data().subscriptions.read().await;
    let feeds = ctx.data().feeds.read().await;
    
    let mut response = "📋 **이 채널의 구독 목록:**\n\n".to_string();
    
    if let Some(subscription) = subscriptions.get(&channel_id) {
        if subscription.subscribed_sources.is_empty() {
            response.push_str("구독 중인 피드가 없습니다. `/subscribe`로 피드를 구독해보세요!");
        } else {
            for (i, feed_id) in subscription.subscribed_sources.iter().enumerate() {
                if let Some(feed) = feeds.get(feed_id) {
                    let status = if feed.enabled { "🟢" } else { "🔴" };
                    response.push_str(&format!("{}. {} **{}** (`{}`)\n   {}\n\n", 
                        i + 1, status, feed.name, feed_id, feed.url));
                } else {
                    response.push_str(&format!("{}. ❓ **알 수 없는 피드** (`{}`)\n\n", i + 1, feed_id));
                }
            }
            
            response.push_str(&format!("\n총 {}개의 피드를 구독 중입니다.", subscription.subscribed_sources.len()));
        }
    } else {
        response.push_str("구독 중인 피드가 없습니다. `/subscribe`로 피드를 구독해보세요!");
    }

    ctx.say(response).await?;
    Ok(())
}

/// 피드 테스트 (최신 1개 포스트 미리보기)
#[poise::command(slash_command)]
pub async fn test_feed(
    ctx: Context<'_>,
    #[description = "테스트할 피드 ID"] feed_id: String,
) -> Result<(), Error> {
    // 서버에서만 실행 가능하도록 제한
    let guild_id = match ctx.guild_id() {
        Some(id) => id.get(),
        None => {
            ctx.say("❌ 이 명령어는 서버에서만 사용할 수 있습니다.").await?;
            return Ok(());
        }
    };

    // 서버별 피드 키 생성
    let feed_key = ctx.data().firestore.create_feed_key(Some(guild_id), &feed_id);

    let feeds = ctx.data().feeds.read().await;
    if let Some(feed_source) = feeds.get(&feed_key) {
        ctx.say(format!("🔄 피드 '{}' 테스트 중...", feed_source.name)).await?;

        match ctx.data().feed_collector.collect_posts(feed_source).await {
            Ok(posts) => {
                if posts.is_empty() {
                    ctx.say("📭 이 피드에서 새로운 포스트를 찾을 수 없습니다.").await?;
                } else {
                    // 최신 포스트 1개만 미리보기
                    let post = &posts[0];
                    let preview = format!(
                        "📰 **테스트 결과** (피드: {})\n\n**제목:** {}\n**링크:** {}\n**요약:** {}\n**발행일:** {}",
                        feed_source.name,
                        post.title,
                        post.link,
                        post.description.as_ref().unwrap_or(&"설명 없음".to_string()).chars().take(200).collect::<String>() + if post.description.as_ref().map_or(0, |d| d.len()) > 200 { "..." } else { "" },
                        post.published.map_or("알 수 없음".to_string(), |dt| dt.format("%Y-%m-%d %H:%M").to_string())
                    );
                    ctx.say(preview).await?;
                }
            }
            Err(e) => {
                ctx.say(format!("❌ 피드 테스트 실패: {}", e)).await?;
            }
        }
    } else {
        ctx.say(format!("❌ 이 서버에서 피드 ID '{}'를 찾을 수 없습니다.", feed_id)).await?;
    }
    Ok(())
}

/// 봇 상태 및 통계 보기
#[poise::command(slash_command)]
pub async fn status(ctx: Context<'_>) -> Result<(), Error> {
    let feeds = ctx.data().feeds.read().await;
    let subscriptions = ctx.data().subscriptions.read().await;
    
    if let Some(guild_id) = ctx.guild_id() {
        // 서버별 통계
        let guild_id = guild_id.get();
        let server_feeds: Vec<_> = feeds.iter()
            .filter(|(key, feed)| {
                key.starts_with(&format!("{}:", guild_id)) && 
                feed.guild_id == Some(guild_id)
            })
            .collect();
        
        let server_feed_count = server_feeds.len();
        let active_server_feeds = server_feeds.iter().filter(|(_, f)| f.enabled).count();
        
        let server_subscriptions: Vec<_> = subscriptions.iter()
            .filter(|(_, sub)| sub.guild_id == Some(guild_id))
            .collect();
        
        let total_server_subscriptions: usize = server_subscriptions.iter()
            .map(|(_, s)| s.subscribed_sources.len())
            .sum();
        
        let status_text = format!(
            "🤖 **Discord Epistulus Bot 상태** (이 서버)\n\n\
            📊 **이 서버 통계:**\n\
            • 등록된 피드: {} (활성: {})\n\
            • 총 구독: {}\n\
            • 구독 채널: {}\n\n\
            🟢 **상태:** 정상 작동 중",
            server_feed_count, active_server_feeds, total_server_subscriptions, server_subscriptions.len()
        );
        
        ctx.say(status_text).await?;
    } else {
        // DM에서 실행된 경우 전체 통계 표시
        let total_feeds = feeds.len();
        let active_feeds = feeds.values().filter(|f| f.enabled).count();
        let total_subscriptions: usize = subscriptions.values()
            .map(|s| s.subscribed_sources.len())
            .sum();
        
        let status_text = format!(
            "🤖 **Discord Epistulus Bot 상태** (전체)\n\n\
            📊 **전체 통계:**\n\
            • 등록된 피드: {} (활성: {})\n\
            • 총 구독: {}\n\
            • 구독 채널: {}\n\n\
            🟢 **상태:** 정상 작동 중",
            total_feeds, active_feeds, total_subscriptions, subscriptions.len()
        );
        
        ctx.say(status_text).await?;
    }
    
    Ok(())
}

/// 결제 관련 명령어들
use crate::models::SubscriptionTier;

/// 서버 구독 정보 확인
#[poise::command(slash_command)]
pub async fn billing(ctx: Context<'_>) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("이 명령어는 서버에서만 사용할 수 있습니다.")?;
    
    let subscription = ctx.data().payment_service.get_guild_subscription(&ctx.data().firestore, guild_id.get()).await?;
    
    let status_text = format!(
        "💳 **{}** 구독 정보\n\n\
        📋 **현재 플랜:** {:?}\n\
        🔄 **상태:** {}\n\
        📊 **피드 제한:** {}\n\
        📅 **만료일:** {}\n\
        💰 **마지막 결제:** {}",
        ctx.guild().map(|g| g.name.clone()).unwrap_or_default(),
        subscription.tier,
        if subscription.is_active { "활성" } else { "비활성" },
        subscription.tier.feed_limit(),
        subscription.expires_at
            .map(|dt| dt.format("%Y-%m-%d").to_string())
            .unwrap_or_else(|| "없음".to_string()),
        subscription.last_payment_at
            .map(|dt| dt.format("%Y-%m-%d").to_string())
            .unwrap_or_else(|| "없음".to_string())
    );
    
    ctx.say(status_text).await?;
    Ok(())
}

/// 프리미엄 구독 업그레이드
#[poise::command(slash_command)]
pub async fn upgrade(
    ctx: Context<'_>,
    #[description = "구독 플랜 (premium 또는 enterprise)"] plan: String,
) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("이 명령어는 서버에서만 사용할 수 있습니다.")?;
    
    let tier = match plan.to_lowercase().as_str() {
        "premium" => SubscriptionTier::Premium,
        "enterprise" => SubscriptionTier::Enterprise,
        _ => {
            ctx.say("❌ 유효한 플랜을 선택하세요: `premium` 또는 `enterprise`").await?;
            return Ok(());
        }
    };
    
    let guild_name = ctx.guild().map(|g| g.name.clone()).unwrap_or_default();
    
    match ctx.data().payment_service.create_payment_link(guild_id.get(), tier.clone(), &guild_name).await {
        Ok(client_secret) => {
            let price = tier.price_cents().unwrap() as f32 / 100.0;
            let upgrade_text = format!(
                "💎 **{}** 플랜 업그레이드\n\n\
                💰 **가격:** ${:.2} USD\n\
                📊 **피드 제한:** {}\n\
                🌟 **혜택:** {}\n\n\
                🔗 **결제 링크:** ||{}_payment_url||",
                format!("{:?}", tier),
                price,
                tier.feed_limit(),
                tier.description(),
                client_secret // 실제로는 완전한 결제 URL이 필요
            );
            
            ctx.say(upgrade_text).await?;
        }
        Err(e) => {
            ctx.say(format!("❌ 결제 링크 생성 실패: {}", e)).await?;
        }
    }
    
    Ok(())
}

/// 구독 취소
#[poise::command(slash_command)]
pub async fn cancel_subscription(ctx: Context<'_>) -> Result<(), Error> {
    let guild_id = ctx.guild_id().ok_or("이 명령어는 서버에서만 사용할 수 있습니다.")?;
    
    let subscription = ctx.data().payment_service.get_guild_subscription(&ctx.data().firestore, guild_id.get()).await?;
    
    if subscription.tier == SubscriptionTier::Free {
        ctx.say("ℹ️ 이미 무료 플랜을 사용 중입니다.").await?;
        return Ok(());
    }
    
    match ctx.data().payment_service.cancel_subscription(&ctx.data().firestore, guild_id.get()).await {
        Ok(_) => {
            ctx.say("✅ 구독이 취소되었습니다. 무료 플랜으로 변경됩니다.").await?;
        }
        Err(e) => {
            ctx.say(format!("❌ 구독 취소 실패: {}", e)).await?;
        }
    }
    
    Ok(())
}

/// 플랜 정보 보기
#[poise::command(slash_command)]
pub async fn plans(ctx: Context<'_>) -> Result<(), Error> {
    let plans_text = format!(
        "💎 **구독 플랜 정보**\n\n\
        🆓 **Free**\n\
        • 가격: 무료\n\
        • 피드 제한: 3개\n\
        • 기본 RSS/Atom 피드 지원\n\n\
        ⭐ **Premium**\n\
        • 가격: ${:.2}/월\n\
        • 피드 제한: 무제한\n\
        • 우선 지원\n\
        • 고급 필터링\n\n\
        🏢 **Enterprise**\n\
        • 가격: ${:.2}/월\n\
        • 피드 제한: 무제한\n\
        • 다중 서버 지원\n\
        • 전용 지원\n\
        • 맞춤 기능\n\n\
        업그레이드하려면 `/upgrade [plan]` 명령어를 사용하세요.",
        SubscriptionTier::Premium.price_cents().unwrap() as f32 / 100.0,
        SubscriptionTier::Enterprise.price_cents().unwrap() as f32 / 100.0
    );
    
    ctx.say(plans_text).await?;
    Ok(())
}
