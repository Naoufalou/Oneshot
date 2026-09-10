import logging
import httpx
from typing import Optional

logger = logging.getLogger("TelegramNotifier")


class TelegramNotifier:
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send_job_alert(
        self,
        title: str,
        company: str,
        location: str,
        score: int,
        rationale: str,
        job_url: str,
        platform: str,
    ) -> bool:
        if not self.bot_token or not self.chat_id:
            logger.debug("Telegram notifications not configured (missing token or chat_id).")
            return False

        platform_icons = {
            "linkedin": "💼 LinkedIn",
            "indeed": "🟦 Indeed",
            "francetravail": "🇫🇷 France Travail",
        }
        plat_str = platform_icons.get(platform.lower(), platform.upper())

        msg = (
            f"🎯 *Nouvelle Offre Détectée !* ({score}% de match)\n\n"
            f"📌 *Poste :* {title}\n"
            f"🏢 *Entreprise :* {company}\n"
            f"📍 *Lieu :* {location}\n"
            f"🌐 *Source :* {plat_str}\n\n"
            f"💡 *Analyse IA :* _{rationale}_\n\n"
            f"🔗 [Voir l'offre sur {platform.capitalize()}]({job_url})\n"
            f"⚡ _Postulez en 1 clic depuis votre tableau de bord AutoApply !_"
        )

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    logger.info(f"Telegram alert sent for: {title}")
                    return True
                else:
                    logger.warning(f"Telegram API error {res.status_code}: {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False
