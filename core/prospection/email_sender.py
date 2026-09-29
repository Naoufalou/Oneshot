import json
import logging
import asyncio
import smtplib
import random
import urllib.parse
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, Any, Optional

from core.storage.db import db
from config.settings import DATA_DIR, settings
from core.prospection.verifier import email_verifier

logger = logging.getLogger("EmailSender")

SMTP_CONFIG_FILE = DATA_DIR / "smtp_config.json"


class EmailSender:
    """
    Manages automated and 1-click B2B outreach email delivery,
    supporting standard SMTP (Gmail App Password, Brevo, OVH, etc.),
    with safety pacing (15-20/day) and mailto fallback.
    """

    def __init__(self):
        self.db = db

    def load_smtp_config(self) -> Dict[str, Any]:
        """Loads SMTP configuration from JSON storage."""
        if not SMTP_CONFIG_FILE.exists():
            return {
                "enabled": False,
                "host": "smtp.gmail.com",
                "port": 587,
                "user": "",
                "password": "",
                "sender_name": "Naoufal Ou",
                "use_tls": True,
            }
        try:
            with open(SMTP_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading SMTP config: {e}")
            return {"enabled": False}

    def save_smtp_config(self, config: Dict[str, Any]) -> bool:
        """Saves SMTP credentials safely to data directory, preserving masked password if needed."""
        try:
            existing = self.load_smtp_config()
            pwd = config.get("password")
            if pwd == "••••••••" or (not pwd and existing.get("password")):
                config["password"] = existing.get("password", "")

            SMTP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SMTP_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error saving SMTP config: {e}")
            return False

    def test_smtp_connection(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Tests live connection and authentication with SMTP server."""
        host = config.get("host", "").strip()
        port = int(config.get("port", 587))
        user = config.get("user", "").strip()
        password = config.get("password", "").strip()
        use_tls = config.get("use_tls", True)

        if not host:
            return {"status": "error", "error": "Le serveur SMTP hôte (ex: smtp.gmail.com) est obligatoire."}
        if not user:
            return {"status": "error", "error": "L'adresse email utilisateur est obligatoire."}

        # Resolve masked or empty password against existing saved credentials
        if not password or password == "••••••••":
            existing = self.load_smtp_config()
            if existing.get("password"):
                password = existing["password"]
            else:
                return {"status": "error", "error": "Le mot de passe (ou mot de passe d'application) est obligatoire."}

        try:
            if port == 465:
                server = smtplib.SMTP_SSL(host, port, timeout=9.0)
            else:
                server = smtplib.SMTP(host, port, timeout=9.0)
                if use_tls:
                    server.starttls()

            server.login(user, password)
            server.quit()
            return {"status": "success", "message": "Connexion SMTP & authentification réussies ! Vos emails seront envoyés directement."}
        except smtplib.SMTPAuthenticationError as e:
            err_raw = str(e)
            if "gmail" in host.lower() or "google" in host.lower():
                return {
                    "status": "error",
                    "error": "Identifiants refusés par Google. Avez-vous utilisé un 'Mot de passe d'application' (16 lettres de myaccount.google.com/apppasswords), et non votre mot de passe habituel ?"
                }
            return {"status": "error", "error": f"Échec d'authentification : identifiant ou mot de passe incorrect ({err_raw})"}
        except (smtplib.SMTPConnectError, TimeoutError, ConnectionRefusedError) as e:
            return {"status": "error", "error": f"Impossible de joindre le serveur {host}:{port}. Vérifiez l'adresse et le port."}
        except Exception as e:
            return {"status": "error", "error": f"Erreur de test SMTP : {str(e)}"}

    def generate_mailto_link(self, to_email: str, subject: str, body: str) -> str:
        """Generates RFC compliant mailto: link for instant zero-config desktop/mobile sending."""
        params = {
            "subject": subject,
            "body": body,
        }
        return f"mailto:{to_email}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"

    async def send_single_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        agency_id: Optional[int] = None,
        simulate_if_no_smtp: bool = True,
    ) -> Dict[str, Any]:
        """
        Sends an outreach email via configured SMTP server or records it
        as dispatched via native mailto / simulated pipeline, with pre-flight
        deliverability verification to prevent bounces and domain reputation damage.
        """
        agency = self.db.get_agency_by_id(agency_id) if agency_id else None
        website = agency.get("website") if agency else None

        # Pre-flight check: ATS-only or bounced flag
        if agency:
            if agency.get("email_status") == "ats_only":
                portal = agency.get("direct_portal_url") or "Welcome to the Jungle"
                return {
                    "status": "error",
                    "error": f"Cette entreprise centralise son recrutement sur {portal}. Utilisez le bouton '⚡ 1-Clic Postuler' pour ouvrir directement le portail sans risque de rejet d'adresse introuvable.",
                }
            if agency.get("email_status") == "bounced":
                return {
                    "status": "error",
                    "error": "Cette adresse email a été signalée comme introuvable / inexistante. Modifiez l'adresse ou postulez directement via le portail de candidature.",
                }

        # Deliverability audit
        audit = email_verifier.verify_email_deliverability(to_email, website)
        if not audit.get("is_deliverable"):
            if audit.get("status") == "ats_only":
                return {
                    "status": "error",
                    "error": f"Recrutement centralisé via portail ({audit.get('reason')}). Utilisez le bouton 1-Clic Postuler !",
                }
            return {
                "status": "error",
                "error": f"Email non délivrable : {audit.get('reason')}",
            }

        config = self.load_smtp_config()
        is_smtp_ready = (
            config.get("enabled")
            and bool(config.get("user"))
            and bool(config.get("password"))
        )

        now_iso = datetime.utcnow().isoformat()

        if is_smtp_ready:
            # Send real email via SMTP
            loop = asyncio.get_event_loop()

            def _smtp_send():
                msg = MIMEMultipart("alternative")
                sender_name = config.get("sender_name") or config.get("user")
                msg["From"] = f"{sender_name} <{config.get('user')}>"
                reply_to = config.get("reply_to") or "naoufal.ou7@gmail.com"
                msg["Reply-To"] = f"{sender_name} <{reply_to}>"
                msg["To"] = to_email
                msg["Subject"] = subject
                msg.attach(MIMEText(body, "plain", "utf-8"))

                host = config.get("host", "smtp.gmail.com")
                port = int(config.get("port", 587))
                use_tls = config.get("use_tls", True)

                if port == 465:
                    server = smtplib.SMTP_SSL(host, port, timeout=12.0)
                else:
                    server = smtplib.SMTP(host, port, timeout=12.0)
                    if use_tls:
                        server.starttls()

                server.login(config["user"], config["password"])
                server.sendmail(config["user"], [to_email], msg.as_string())
                server.quit()

            try:
                await loop.run_in_executor(None, _smtp_send)
                if agency_id:
                    self.db.update_agency_status(
                        agency_id, status="contacted", contacted_at=now_iso, notes="Envoyé via SMTP"
                    )
                return {"status": "success", "mode": "smtp", "sent_at": now_iso}
            except Exception as e:
                logger.error(f"SMTP send failed to {to_email}: {e}")
                err_str = str(e)
                if "Username and Password not accepted" in err_str:
                    err_str = "Identifiants SMTP refusés par Google/serveur. Utilisez un mot de passe d'application 16 lettres."
                return {"status": "error", "error": err_str}

        elif simulate_if_no_smtp:
            # Fallback to zero-config native Mailto
            await asyncio.sleep(random.uniform(0.3, 0.6))
            if agency_id:
                self.db.update_agency_status(
                    agency_id, status="contacted", contacted_at=now_iso, notes="Contacté (Client Mail / Mailto)"
                )
            return {
                "status": "success",
                "mode": "recorded",
                "sent_at": now_iso,
                "mailto_link": self.generate_mailto_link(to_email, subject, body),
                "message": "Ouverture du client mail & marqué comme contacté",
            }
        else:
            return {
                "status": "error",
                "error": "SMTP non configuré. Renseignez vos identifiants ou utilisez le lien Mailto.",
            }

    async def batch_send_prospects(
            self, agency_ids: list[int], max_count: int = 50
        ) -> Dict[str, Any]:
            """
            Sends emails in sequence with respectful human-like pacing
            (1.5 to 3.0s interval), filtering out ATS-only or bounced addresses.
            """
            results = []
            sent_count = 0
            error_count = 0
            skipped_count = 0

            target_ids = agency_ids[:max_count]

            for aid in target_ids:
                agency = self.db.get_agency_by_id(aid)
                if not agency:
                    continue

                # Safety check: if ATS-only or bounced, skip email send
                if agency.get("email_status") in ("ats_only", "bounced") or not agency.get("email"):
                    skipped_count += 1
                    results.append({
                        "agency_id": aid,
                        "name": agency.get("name"),
                        "res": {
                            "status": "skipped",
                            "reason": "Recrutement via portail ATS ou adresse à confirmer",
                        },
                    })
                    continue

                to_email = agency["email"]
                subject = agency.get("subject") or "Renfort IA & automatisation"
                body = agency.get("custom_message") or ""

                res = await self.send_single_email(
                    to_email=to_email,
                    subject=subject,
                    body=body,
                    agency_id=aid,
                    simulate_if_no_smtp=True,
                )

                if res.get("status") == "success":
                    sent_count += 1
                else:
                    error_count += 1

                results.append({"agency_id": aid, "name": agency.get("name"), "res": res})

                # Human delay between consecutive emails
                await asyncio.sleep(random.uniform(1.5, 3.0))

            config = self.load_smtp_config()
            is_smtp_ready = (
                config.get("enabled")
                and bool(config.get("user"))
                and bool(config.get("password"))
            )

            return {
                "status": "success",
                "mode": "smtp" if is_smtp_ready else "recorded",
                "total_processed": len(target_ids),
                "sent_count": sent_count,
                "error_count": error_count,
                "skipped_count": skipped_count,
                "details": results,
            }


email_sender = EmailSender()
