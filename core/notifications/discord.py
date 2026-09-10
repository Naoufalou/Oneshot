import logging
import httpx
from typing import Optional

logger = logging.getLogger("DiscordNotifier")


class DiscordNotifier:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url

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
        if not self.webhook_url:
            logger.debug("Discord webhook not configured.")
            return False

        # Color: Green if score >= 80, Orange if score >= 65, Blue otherwise
        color = 0x10B981 if score >= 80 else (0xF59E0B if score >= 65 else 0x6366F1)

        platform_names = {
            "linkedin": "LinkedIn",
            "indeed": "Indeed",
            "francetravail": "France Travail",
        }

        embed = {
            "title": f"🎯 {title}",
            "url": job_url,
            "description": f"**Entreprise :** {company}\n**Lieu :** {location}\n**Source :** {platform_names.get(platform, platform)}",
            "color": color,
            "fields": [
                {
                    "name": "📊 Score d'adéquation IA",
                    "value": f"**{score}%** de correspondance avec votre profil",
                    "inline": True,
                },
                {
                    "name": "💡 Analyse IA",
                    "value": rationale or "Offre alignée avec vos critères de recherche.",
                    "inline": False,
                },
            ],
            "footer": {
                "text": "AutoApply AI • Cliquez sur le titre pour voir l'offre ou postulez en 1 clic sur le Dashboard",
            },
        }

        payload = {
            "username": "AutoApply Watcher",
            "avatar_url": "https://cdn-icons-png.flaticon.com/512/4712/4712035.png",
            "embeds": [embed],
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(self.webhook_url, json=payload)
                if res.status_code in [200, 204]:
                    logger.info(f"Discord alert sent for: {title}")
                    return True
                else:
                    logger.warning(f"Discord webhook error {res.status_code}: {res.text}")
                    return False
        except Exception as e:
            logger.error(f"Failed to send Discord alert: {e}")
            return False
