import re
import socket
import logging
import subprocess
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("EmailVerifier")

# Blacklisted domains or extensions that are not valid mailboxes
BLACKLISTED_DOMAINS = {
    "sentry.io",
    "wixpress.com",
    "schema.org",
    "w3.org",
    "example.com",
    "domain.com",
    "wordpress.org",
    "cloudflare.com",
    "google.com",
}

# Known ATS / Job portal domains
KNOWN_ATS_DOMAINS = [
    "welcometothejungle.com",
    "jobs.lever.co",
    "boards.greenhouse.io",
    "apply.workable.com",
    "teamtailor.com",
    "taleez.com",
    "notion.site",
]

# Known agencies that route recruitment EXCLUSIVELY via ATS / Forms and bounce generic contact@ inboxes
KNOWN_ATS_ONLY_DOMAINS = {
    "tediber.com": {
        "portal_url": "https://www.welcometothejungle.com/fr/companies/tediber/jobs",
        "reason": "Recrutement centralisé sur Welcome to the Jungle. L'adresse bonjour@ est réservée au SAV client.",
    },
    "emeraude-escape.com": {
        "portal_url": "https://www.welcometothejungle.com/fr/companies/emeraude-escape",
        "reason": "Candidatures traitées via Welcome to the Jungle ou page recrutement dédiée.",
    },
    "agencegust.com": {
        "portal_url": "https://www.agencegust.com/fr/contact",
        "reason": "Formulaire direct avec choix 'Un job chez Gust' ou portail Welcome to the Jungle.",
    },
}

# Verified decision-makers and specialized recruitment emails
VERIFIED_AGENCY_CONTACTS = {
    "datashake.fr": {
        "email": "remy@datashake.fr",
        "decision_maker": "Rémy Bendayan (Co-fondateur & Dirigeant)",
        "portal_url": "https://www.welcometothejungle.com/companies/datashake/jobs",
        "status": "verified",
    },
    "allmatik.com": {
        "email": "work4ceetadel@ceetadel.com",
        "decision_maker": "Pôle Recrutement Groupe CEETADEL",
        "portal_url": "https://www.welcometothejungle.com/fr/companies/ceetadel/jobs",
        "status": "verified",
    },
    "ceetadel.com": {
        "email": "work4ceetadel@ceetadel.com",
        "decision_maker": "Pôle Recrutement Groupe CEETADEL",
        "portal_url": "https://www.welcometothejungle.com/fr/companies/ceetadel/jobs",
        "status": "verified",
    },
    "adveris.fr": {
        "email": "contact@adveris.fr",
        "decision_maker": "Direction Adveris",
        "portal_url": "https://www.adveris.fr/contact/",
        "status": "verified",
    },
    "zerance.com": {
        "email": "hello@zerance.com",
        "decision_maker": "Équipe Studio Zerance",
        "portal_url": "https://www.zerance.com/pages/contact",
        "status": "verified",
    },
    "wokine.com": {
        "email": "contact@wokine.com",
        "decision_maker": "Direction Wokine",
        "portal_url": "https://www.wokine.com/contact/",
        "status": "verified",
    },
    "uzik.com": {
        "email": "contact@uzik.com",
        "decision_maker": "Direction de Création Uzik",
        "portal_url": "https://www.uzik.com/contact",
        "status": "verified",
    },
    "beapi.fr": {
        "email": "bonjour@beapi.fr",
        "decision_maker": "Direction Be API",
        "portal_url": "https://beapi.fr/carrieres/",
        "status": "verified",
    },
    "studio-meta.fr": {
        "email": "bonjour@studio-meta.fr",
        "decision_maker": "Direction Studio Meta",
        "portal_url": "https://www.studio-meta.fr/carrieres",
        "status": "verified",
    },
    "churchill.paris": {
        "email": "hello@churchill.paris",
        "decision_maker": "Équipe Churchill",
        "portal_url": "https://www.churchill.paris/contact",
        "status": "verified",
    },
    "makethegrade.fr": {
        "email": "contact@makethegrade.fr",
        "decision_maker": "Direction Make the Grade",
        "portal_url": "https://www.makethegrade.fr/carrieres",
        "status": "verified",
    },
}


class EmailVerifier:
    """
    Validates deliverability, resolves MX records, prevents bounce traps,
    and detects ATS direct application portals.
    """

    @staticmethod
    def get_domain_from_email_or_url(target: str) -> str:
        """Extracts bare root domain from email or URL."""
        if not target:
            return ""
        if "@" in target:
            return target.split("@")[-1].strip().lower()
        
        # URL case
        cleaned = re.sub(r"^https?://", "", target, flags=re.IGNORECASE)
        cleaned = cleaned.split("/")[0].split(":")[0].strip().lower()
        if cleaned.startswith("www."):
            cleaned = cleaned[4:]
        return cleaned

    @staticmethod
    def get_mx_records(domain: str) -> List[str]:
        """Resolves DNS MX records for domain via dig/socket."""
        if not domain:
            return []
        try:
            res = subprocess.run(
                ["dig", "+short", "MX", domain],
                capture_output=True,
                text=True,
                timeout=2.5,
            )
            lines = res.stdout.strip().split("\n")
            mx_hosts = []
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 2:
                    host = parts[1].rstrip(".")
                    if host and host != ".":
                        mx_hosts.append(host)
                elif len(parts) == 1 and parts[0]:
                    host = parts[0].rstrip(".")
                    if host and host != ".":
                        mx_hosts.append(host)
            return mx_hosts
        except Exception as e:
            logger.debug(f"Error resolving MX for {domain}: {e}")
            return []

    @classmethod
    def verify_email_deliverability(
        cls, email: Optional[str], website: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive deliverability and routing audit for an agency contact.
        Returns:
            - is_deliverable: bool
            - status: 'verified' | 'unverified' | 'ats_only' | 'invalid' | 'bounced'
            - recommendation: 'email' | 'ats_portal' | 'manual_review'
            - direct_portal_url: Optional[str]
            - decision_maker: Optional[str]
            - reason: str
        """
        web_domain = cls.get_domain_from_email_or_url(website or "")
        email_clean = (email or "").strip().lower()
        email_domain = cls.get_domain_from_email_or_url(email_clean) if email_clean else web_domain

        # Check known ATS-only companies (e.g. Tediber, Emeraude)
        if web_domain in KNOWN_ATS_ONLY_DOMAINS:
            ats_info = KNOWN_ATS_ONLY_DOMAINS[web_domain]
            return {
                "is_deliverable": False,
                "status": "ats_only",
                "recommendation": "ats_portal",
                "direct_portal_url": ats_info["portal_url"],
                "decision_maker": "Pôle Recrutement ATS",
                "reason": ats_info["reason"],
            }

        # Check curated verified contacts
        lookup_dom = email_domain or web_domain
        if lookup_dom in VERIFIED_AGENCY_CONTACTS:
            curated = VERIFIED_AGENCY_CONTACTS[lookup_dom]
            return {
                "is_deliverable": True,
                "status": curated["status"],
                "recommendation": "email",
                "direct_portal_url": curated.get("portal_url"),
                "decision_maker": curated.get("decision_maker"),
                "reason": "Contact vérifié et délivrable avec succès.",
            }

        if not email_clean:
            return {
                "is_deliverable": False,
                "status": "invalid",
                "recommendation": "ats_portal" if website else "manual_review",
                "direct_portal_url": website,
                "decision_maker": None,
                "reason": "Aucune adresse email trouvée.",
            }

        # Syntax check
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email_clean):
            return {
                "is_deliverable": False,
                "status": "invalid",
                "recommendation": "manual_review",
                "direct_portal_url": website,
                "decision_maker": None,
                "reason": "Syntaxe de l'adresse email invalide.",
            }

        # Check blacklisted domains
        if email_domain in BLACKLISTED_DOMAINS:
            return {
                "is_deliverable": False,
                "status": "invalid",
                "recommendation": "manual_review",
                "direct_portal_url": website,
                "decision_maker": None,
                "reason": f"Domaine {email_domain} non destiné à recevoir des candidatures.",
            }

        # Check MX DNS records
        mx_hosts = cls.get_mx_records(email_domain)
        if not mx_hosts:
            return {
                "is_deliverable": False,
                "status": "invalid",
                "recommendation": "ats_portal" if website else "manual_review",
                "direct_portal_url": website,
                "decision_maker": None,
                "reason": f"Aucun serveur mail (MX) n'existe pour @{email_domain}.",
            }

        # Detect high-risk generic prefixes (e.g. info@, support@, bonjour@ on e-commerce)
        if email_clean.startswith(("support@", "sav@", "billing@", "order@")):
            return {
                "is_deliverable": False,
                "status": "invalid",
                "recommendation": "manual_review",
                "direct_portal_url": website,
                "decision_maker": None,
                "reason": "Adresse de support client ou facturation, risque élevé de rejet.",
            }

        # Default: unverified generic email with valid MX
        return {
            "is_deliverable": True,
            "status": "unverified",
            "recommendation": "email",
            "direct_portal_url": website,
            "decision_maker": None,
            "reason": f"Serveur mail actif ({mx_hosts[0]}), adresse générale à confirmer.",
        }


email_verifier = EmailVerifier()
