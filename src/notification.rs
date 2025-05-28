use crate::models::{BlogPost, NotificationFormat, NotificationSettings};
use serenity::builder::CreateEmbed;
use serenity::model::prelude::*;
use serenity::prelude::*;

pub struct NotificationService;

impl NotificationService {
    /// NotificationService의 새 인스턴스를 생성
    pub fn new() -> Self {
        Self
    }

    /// 새로운 포스트들을 디스코드 채널에 알림
    pub async fn send_notifications(
        ctx: &Context,
        channel_id: ChannelId,
        posts: Vec<BlogPost>,
        settings: &NotificationSettings,
    ) -> Result<(), NotificationError> {
        if posts.is_empty() {
            return Ok(());
        }

        // 배치 크기로 나누어서 전송
        let batches: Vec<_> = posts
            .chunks(settings.max_posts_per_batch as usize)
            .collect();

        for batch in batches {
            match settings.format {
                NotificationFormat::Simple => {
                    Self::send_simple_notifications(ctx, channel_id, batch, settings).await?;
                }
                NotificationFormat::Rich => {
                    Self::send_rich_notifications(ctx, channel_id, batch, settings).await?;
                }
                NotificationFormat::Summary => {
                    Self::send_summary_notification(ctx, channel_id, batch, settings).await?;
                }
            }

            // 스팸 방지를 위한 약간의 딜레이
            tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
        }

        Ok(())
    }

    /// 간단한 텍스트 알림
    async fn send_simple_notifications(
        ctx: &Context,
        channel_id: ChannelId,
        posts: &[BlogPost],
        settings: &NotificationSettings,
    ) -> Result<(), NotificationError> {
        for post in posts {
            let mut message = format!("📰 **{}**\n{}", post.title, post.link);

            if settings.include_preview {
                if let Some(description) = &post.description {
                    let preview = Self::truncate_text(description, 200);
                    message.push_str(&format!("\n> {}", preview));
                }
            }

            if let Some(role_id) = settings.mention_role {
                message = format!("<@&{}> {}", role_id, message);
            }

            channel_id
                .say(&ctx.http, message)
                .await
                .map_err(NotificationError::Discord)?;
        }

        Ok(())
    }

    /// 리치 임베드 알림
    async fn send_rich_notifications(
        ctx: &Context,
        channel_id: ChannelId,
        posts: &[BlogPost],
        settings: &NotificationSettings,
    ) -> Result<(), NotificationError> {
        for post in posts {
            let mut embed = CreateEmbed::new()
                .title(&post.title)
                .url(&post.link)
                .color(0x3498db);

            // 타임스탬프 설정 (옵셔널)
            if let Some(published) = post.published {
                if let Ok(timestamp) = serenity::model::Timestamp::from_unix_timestamp(published.timestamp()) {
                    embed = embed.timestamp(timestamp);
                }
            }

            if let Some(description) = &post.description {
                if settings.include_preview {
                    embed = embed.description(Self::truncate_text(description, 300));
                }
            }

            if let Some(author) = &post.author {
                embed = embed.author(serenity::builder::CreateEmbedAuthor::new(author));
            }

            // 태그 추가
            if !post.tags.is_empty() {
                let tags_text = post.tags.join(", ");
                embed = embed.field("태그", Self::truncate_text(&tags_text, 100), true);
            }

            embed = embed.footer(serenity::builder::CreateEmbedFooter::new(format!("출처: {}", post.source_id)));

            let mut message_builder = serenity::builder::CreateMessage::new().embed(embed);

            if let Some(role_id) = settings.mention_role {
                message_builder = message_builder.content(format!("<@&{}>", role_id));
            }

            channel_id
                .send_message(&ctx.http, message_builder)
                .await
                .map_err(NotificationError::Discord)?;
        }

        Ok(())
    }

    /// 요약 알림
    async fn send_summary_notification(
        ctx: &Context,
        channel_id: ChannelId,
        posts: &[BlogPost],
        settings: &NotificationSettings,
    ) -> Result<(), NotificationError> {
        let title = format!("📰 새로운 글 {}개", posts.len());
        
        let mut embed = CreateEmbed::new()
            .title(&title)
            .color(0x2ecc71);

        // 현재 시간으로 타임스탬프 설정
        if let Ok(timestamp) = serenity::model::Timestamp::from_unix_timestamp(chrono::Utc::now().timestamp()) {
            embed = embed.timestamp(timestamp);
        }

        let mut description = String::new();
        for (i, post) in posts.iter().enumerate() {
            if i > 0 {
                description.push_str("\n\n");
            }
            
            description.push_str(&format!(
                "**[{}]({})**", 
                Self::truncate_text(&post.title, 80),
                post.link
            ));

            if let Some(author) = &post.author {
                description.push_str(&format!(" - {}", author));
            }
        }

        embed = embed.description(Self::truncate_text(&description, 1900));

        let mut message_builder = serenity::builder::CreateMessage::new().embed(embed);

        if let Some(role_id) = settings.mention_role {
            message_builder = message_builder.content(format!("<@&{}>", role_id));
        }

        channel_id
            .send_message(&ctx.http, message_builder)
            .await
            .map_err(NotificationError::Discord)?;

        Ok(())
    }

    /// 텍스트 길이 제한
    fn truncate_text(text: &str, max_len: usize) -> String {
        if text.len() <= max_len {
            text.to_string()
        } else {
            format!("{}...", &text[..max_len.saturating_sub(3)])
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum NotificationError {
    #[error("디스코드 메시지 전송 실패: {0}")]
    Discord(#[from] serenity::Error),
}
