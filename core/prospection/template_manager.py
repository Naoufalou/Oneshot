import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from config.settings import DATA_DIR, settings
from core.storage.db import db

logger = logging.getLogger("TemplateManager")

TEMPLATE_FILE = DATA_DIR / "agency_template.json"

DEFAULT_SUBJECT = "Renfort intégration front-end & Figma pour {nom_agence}"

DEFAULT_BODY = """Hello {destinataire},

Je suis intégrateur & développeur front-end ({competences}).
Si vous avez un trop-plein de maquettes Figma à intégrer ou des petits tickets front sur lesquels vous manquez de temps en ce moment, je suis disponible immédiatement en renfort (au forfait ou à la journée).

Voici 2-3 projets propres et récents que j'ai codés :
👉 Portfolio : {portfolio}
👉 GitHub : {github}

N'hésitez pas si vous avez une maquette urgente à découper cette semaine.

Bonne semaine,
{nom_complet}
{telephone}"""


class TemplateManager:
    """
    Manages custom dynamic outreach email templates with variable substitution
    ({nom_agence}, {destinataire}, {ville}, {portfolio}, etc.).
    """

    def __init__(self):
        self.db = db

    def get_template(self) -> Dict[str, str]:
        """Loads saved template or returns high-converting default."""
        if TEMPLATE_FILE.exists():
            try:
                with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {
                        "subject": data.get("subject", DEFAULT_SUBJECT),
                        "body": data.get("body", DEFAULT_BODY),
                    }
            except Exception as e:
                logger.error(f"Error loading template file: {e}")

        return {
            "subject": DEFAULT_SUBJECT,
            "body": DEFAULT_BODY,
        }

    def save_template(self, subject: str, body: str) -> bool:
        """Persists custom template to disk."""
        try:
            TEMPLATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(TEMPLATE_FILE, "w", encoding="utf-8") as f:
                json.dump({"subject": subject, "body": body}, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error saving template: {e}")
            return False

    def render_template(
        self,
        subject_template: str,
        body_template: str,
        agency: Dict[str, Any],
        candidate_profile=None,
    ) -> Dict[str, str]:
        """
        Renders subject and body with agency-specific dynamic variables.
        """
        profile = candidate_profile or settings.load_profile()
        first_name = (profile.first_name or "Eliot").strip()
        last_name = (profile.last_name or "").strip()
        full_name = f"{first_name} {last_name}".strip()

        portfolio = (profile.portfolio_url or "").strip() or "https://eliot-hantute.com"
        github = (profile.github_url or "").strip()

        skills = profile.skills or ["React", "Tailwind CSS", "Three.js", "Figma", "Webflow"]
        skills_str = ", ".join(skills[:4])

        phone_str = (
            getattr(profile, "phone", None)
            or f"{getattr(profile, 'phone_country_code', '')} {getattr(profile, 'phone_number', '')}".strip()
        )

        agency_name = agency.get("name", "l'équipe")
        city = agency.get("city") or "Paris"

        # If decision_maker exists (e.g. "Rémy Bendayan"), use first name or title
        raw_dm = agency.get("decision_maker") or ""
        if raw_dm:
            # Extract first name if "Prénom Nom (Rôle)"
            dm_name = raw_dm.split("(")[0].strip()
            destinataire = dm_name
        else:
            destinataire = agency_name

        replacements = {
            "{nom_agence}": agency_name,
            "{agency_name}": agency_name,
            "{destinataire}": destinataire,
            "{decision_maker}": destinataire,
            "{ville}": city,
            "{city}": city,
            "{prenom}": first_name,
            "{first_name}": first_name,
            "{nom_complet}": full_name,
            "{full_name}": full_name,
            "{portfolio}": portfolio,
            "{portfolio_url}": portfolio,
            "{github}": github,
            "{github_url}": github,
            "{competences}": skills_str,
            "{skills}": skills_str,
            "{telephone}": phone_str,
            "{phone}": phone_str,
        }

        rendered_subject = subject_template
        rendered_body = body_template

        for var, val in replacements.items():
            rendered_subject = rendered_subject.replace(var, val or "")
            rendered_body = rendered_body.replace(var, val or "")

        # Clean multiple blank lines if GitHub or phone are empty
        rendered_body = "\n".join([line for line in rendered_body.splitlines() if line.strip() != "👉 GitHub : "])

        return {
            "subject": rendered_subject.strip(),
            "body": rendered_body.strip(),
        }

    def apply_to_pending_agencies(self, subject_template: str, body_template: str) -> int:
        """
        Re-renders and updates custom message for all pending prospects in database.
        """
        profile = settings.load_profile()
        pending = self.db.list_agencies(status="pending", limit=500)
        updated_count = 0

        for a in pending:
            rendered = self.render_template(
                subject_template=subject_template,
                body_template=body_template,
                agency=a,
                candidate_profile=profile,
            )
            ok = self.db.update_agency_record(a["id"], {
                "subject": rendered["subject"],
                "custom_message": rendered["body"],
            })
            if ok:
                updated_count += 1

        logger.info(f"Applied template to {updated_count} pending agencies.")
        return updated_count


template_manager = TemplateManager()
