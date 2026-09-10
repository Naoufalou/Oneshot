import logging
import os
from typing import Optional
from config.settings import settings
from .telegram import TelegramNotifier
from .discord import DiscordNotifier

logger = logging.getLogger("NotificationDispatcher")


class NotificationDispatcher:
    def __init__(self):
        pass

    def _get_notifiers(self):
        notif_cfg = settings.notifications
        telegram_token = notif_cfg.telegram_bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        telegram_chat = notif_cfg.telegram_chat_id or os.getenv("TELEGRAM_CHAT_ID")
        discord_url = notif_cfg.discord_webhook_url or os.getenv("DISCORD_WEBHOOK_URL")

        telegram = TelegramNotifier(telegram_token, telegram_chat) if (notif_cfg.enable_telegram or telegram_token) else None
        discord = DiscordNotifier(discord_url) if (notif_cfg.enable_discord or discord_url) else None

        return telegram, discord

    async def notify_new_job_opportunity(
        self,
        title: str,
        company: str,
        location: str,
        score: int,
        rationale: str,
        job_url: str,
        platform: str,
    ):
        criteria = settings.load_search_criteria()
        min_alert = criteria.min_alert_score if hasattr(criteria, "min_alert_score") else 70

        if score < min_alert:
            logger.debug(f"Score {score} < {min_alert}, skipping push notification.")
            return

        telegram, discord = self._get_notifiers()

        if telegram:
            await telegram.send_job_alert(
                title=title,
                company=company,
                location=location,
                score=score,
                rationale=rationale,
                job_url=job_url,
                platform=platform,
            )

        if discord:
            await discord.send_job_alert(
                title=title,
                company=company,
                location=location,
                score=score,
                rationale=rationale,
                job_url=job_url,
                platform=platform,
            )


notification_dispatcher = NotificationDispatcher()
