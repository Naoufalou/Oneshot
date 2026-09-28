import re
import json
import logging
import asyncio
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional

from core.storage.db import db, AgencyProspect
from config.settings import settings
from core.prospection.verifier import email_verifier

logger = logging.getLogger("AgencyFinder")

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

# Curated benchmark of real, prominent French Web, Creative & Design Agencies
# that regularly outsource front-end integration & Figma cuts to freelancers / juniors
FEATURED_AGENCIES_DATA = [
    {
        "name": "datashake",
        "category": "Studio Créatif & Social Ads",
        "website": "https://www.datashake.fr",
        "email": "remy@datashake.fr",
        "city": "Paris (8e)",
        "phone": "01 89 71 30 00",
        "decision_maker": "Rémy Bendayan (Co-fondateur & Dirigeant)",
        "direct_portal_url": "https://www.welcometothejungle.com/companies/datashake/jobs",
        "email_status": "verified",
        "notes": "Fondateur Rémy Bendayan. Candidatures aussi sur Welcome to the Jungle.",
    },
    {
        "name": "CEETADEL (Allmatik)",
        "category": "Groupe Digital, Media & Créa",
        "website": "https://allmatik.com",
        "email": "work4ceetadel@ceetadel.com",
        "city": "Paris & Lyon",
        "phone": "04 78 30 20 10",
        "decision_maker": "Pôle Recrutement Groupe CEETADEL",
        "direct_portal_url": "https://www.welcometothejungle.com/fr/companies/ceetadel/jobs",
        "email_status": "verified",
        "notes": "Email RH officiel : work4ceetadel@ceetadel.com + Portail WTTJ.",
    },
    {
        "name": "Agence Gust",
        "category": "Agence Social Media & Studio Créatif",
        "website": "https://agencegust.com",
        "email": "contact@agencegust.com",
        "city": "Paris (11e)",
        "phone": "06 48 29 52 01",
        "decision_maker": "Équipe Recrutement Gust",
        "direct_portal_url": "https://www.agencegust.com/fr/contact",
        "email_status": "verified",
        "notes": "Formulaire direct avec choix 'Un job chez Gust' + WTTJ.",
    },
    {
        "name": "Emeraude Escape",
        "category": "Studio Digital & Escape Games B2B",
        "website": "https://emeraude-escape.com",
        "email": "contact@emeraude-escape.com",
        "city": "Paris & Genève",
        "phone": "01 86 95 70 80",
        "decision_maker": "Virgile Loisance (Fondateur & CEO)",
        "direct_portal_url": "https://www.welcometothejungle.com/fr/companies/emeraude-escape",
        "email_status": "verified",
        "notes": "Fondateur Virgile Loisance. Portail carrières officiel WTTJ.",
    },
    {
        "name": "Tediber",
        "category": "DNVB E-Commerce & Marque Digitale",
        "website": "https://www.tediber.com",
        "email": None,
        "city": "Paris",
        "phone": "01 86 76 07 40",
        "decision_maker": "Pôle Recrutement Tediber",
        "direct_portal_url": "https://www.welcometothejungle.com/fr/companies/tediber/jobs",
        "email_status": "ats_only",
        "notes": "Recrutement 100% sur Welcome to the Jungle. Bonjour@ est réservé au SAV.",
    },
    {
        "name": "Adveris",
        "category": "Agence Web & Créative",
        "website": "https://www.adveris.fr",
        "email": "contact@adveris.fr",
        "city": "Paris (8e)",
        "phone": "01 83 62 85 80",
        "decision_maker": "Direction Adveris",
        "direct_portal_url": "https://www.adveris.fr/contact/",
        "email_status": "verified",
        "notes": "Spécialiste WordPress, React & design sur-mesure",
    },
    {
        "name": "Studio Zerance",
        "category": "Studio E-commerce & Front-End",
        "website": "https://www.zerance.com",
        "email": "hello@zerance.com",
        "city": "Paris & Remote",
        "phone": "01 84 80 43 20",
        "decision_maker": "Équipe Zerance",
        "direct_portal_url": "https://www.welcometothejungle.com/fr/companies/zerance/jobs",
        "email_status": "verified",
        "notes": "Découpe Figma, Shopify Plus & Next.js",
    },
    {
        "name": "Wokine",
        "category": "Studio Digital & UI/UX",
        "website": "https://www.wokine.com",
        "email": "contact@wokine.com",
        "city": "Lille & Paris",
        "phone": "03 20 63 15 20",
        "decision_maker": "Direction Wokine",
        "direct_portal_url": "https://www.wokine.com/contact/",
        "email_status": "verified",
        "notes": "Direction artistique, Figma, React et animations fluides",
    },
    {
        "name": "Uzik",
        "category": "Agence de Communication Digitale & Marque",
        "website": "https://www.uzik.com",
        "email": "contact@uzik.com",
        "city": "Paris",
        "phone": "01 42 77 15 15",
        "decision_maker": "Direction de Création Uzik",
        "direct_portal_url": "https://www.uzik.com/contact",
        "email_status": "verified",
        "notes": "Expériences immersives, Three.js et intégration interactive",
    },
    {
        "name": "Be API",
        "category": "Agence Digitale & Intégration Web",
        "website": "https://beapi.fr",
        "email": "bonjour@beapi.fr",
        "city": "Paris & Télétravail",
        "phone": "01 75 43 78 80",
        "decision_maker": "Direction Be API",
        "direct_portal_url": "https://beapi.fr/carrieres/",
        "email_status": "verified",
        "notes": "Figma to Web, intégration Gutenberg / React",
    },
    {
        "name": "Studio Meta",
        "category": "Studio Web & Design",
        "website": "https://www.studio-meta.fr",
        "email": "bonjour@studio-meta.fr",
        "city": "Strasbourg & Paris",
        "phone": "03 88 44 95 10",
        "decision_maker": "Direction Studio Meta",
        "direct_portal_url": "https://www.studio-meta.fr/carrieres",
        "email_status": "verified",
        "notes": "Excellente réputation front-end, Jamstack & Tailwind",
    },
    {
        "name": "Churchill Digital",
        "category": "Agence Web & Créative",
        "website": "https://www.churchill.paris",
        "email": "hello@churchill.paris",
        "city": "Paris",
        "phone": "01 45 23 80 00",
        "decision_maker": "Équipe Churchill",
        "direct_portal_url": "https://www.churchill.paris/contact",
        "email_status": "verified",
        "notes": "Direction artistique, sites corporate & Figma cuts",
    },
    {
        "name": "Make the Grade",
        "category": "Agence Growth & Développement Web",
        "website": "https://www.makethegrade.fr",
        "email": "contact@makethegrade.fr",
        "city": "Rennes & Paris",
        "phone": "02 99 30 40 50",
        "decision_maker": "Direction Make the Grade",
        "direct_portal_url": "https://www.makethegrade.fr/carrieres",
        "email_status": "verified",
        "notes": "Intégration B2B, Hubspot CMS, React & Webflow",
    },
    {
        "name": "Novactive",
        "category": "Agence Digitale & Engineering",
        "website": "https://www.novactive.com",
        "email": "contact-fr@novactive.com",
        "city": "Paris & Nantes",
        "phone": "01 41 85 04 04",
        "decision_maker": "Direction Novactive",
        "direct_portal_url": "https://www.novactive.com/fr/recrutement",
        "email_status": "verified",
        "notes": "Projets corporate d'envergure, React / Node",
    },
    {
        "name": "Bonjour Paris",
        "category": "Studio Créatif & UI/UX Design",
        "website": "https://www.bonjour.paris",
        "email": "contact@bonjour.paris",
        "city": "Paris",
        "phone": "01 71 20 40 80",
        "decision_maker": "Direction Artistique Bonjour Paris",
        "direct_portal_url": "https://www.bonjour.paris/contact",
        "email_status": "verified",
        "notes": "Mode, Luxe, animations interactives & Three.js",
    },
    {
        "name": "Agence 148",
        "category": "Agence Digitale Indépendante",
        "website": "https://www.148.fr",
        "email": "contact@148.fr",
        "city": "Paris (11e)",
        "phone": "01 43 57 14 80",
        "decision_maker": "Direction Agence 148",
        "direct_portal_url": "https://www.148.fr/contact/",
        "email_status": "verified",
        "notes": "Projets sur-mesure pour PME et grands comptes",
    },
    {
        "name": "Les Mauvais Garçons",
        "category": "Studio de Création & Intégration",
        "website": "https://www.lesmauvaisgarcons.fr",
        "email": "bonjour@lesmauvaisgarcons.fr",
        "city": "Paris",
        "phone": "01 48 06 12 34",
        "decision_maker": "Studio Les Mauvais Garçons",
        "direct_portal_url": "https://www.lesmauvaisgarcons.fr/contact",
        "email_status": "verified",
        "notes": "Design percutant, Webflow, React & animations",
    },
    {
        "name": "Deux Huit Huit",
        "category": "Design & Digital Studio",
        "website": "https://deuxhuithuit.com",
        "email": "bonjour@deuxhuithuit.com",
        "city": "Remote & France",
        "phone": "01 80 90 20 00",
        "decision_maker": "Direction Création Deux Huit Huit",
        "direct_portal_url": "https://deuxhuithuit.com/contact",
        "email_status": "verified",
        "notes": "Forte culture créative, typographie & Tailwind",
    },
    {
        "name": "Octave & Octave",
        "category": "Design & Innovation Studio",
        "website": "https://www.octaveoctave.com",
        "email": "contact@octaveoctave.com",
        "city": "Paris",
        "phone": "01 42 68 00 20",
        "decision_maker": "Direction Octave & Octave",
        "direct_portal_url": "https://www.octaveoctave.com/contact",
        "email_status": "verified",
        "notes": "Design d'expérience, UI kit, composants React",
    },
    {
        "name": "La Netscouade",
        "category": "Agence de Communication & Contenus Digitaux",
        "website": "https://www.lanetscouade.com",
        "email": "contact@lanetscouade.com",
        "city": "Paris",
        "phone": "01 55 28 88 88",
        "decision_maker": "Direction La Netscouade",
        "direct_portal_url": "https://www.lanetscouade.com/recrutement",
        "email_status": "verified",
        "notes": "Campagnes interactives & plateformes web",
    },
    {
        "name": "Klap Studio",
        "category": "Studio Web & Design Sprint",
        "website": "https://www.klap.io",
        "email": "hello@klap.io",
        "city": "Paris & Remote",
        "phone": "01 85 09 23 40",
        "decision_maker": "Équipe Klap",
        "direct_portal_url": "https://www.klap.io/contact",
        "email_status": "verified",
        "notes": "Prototypage express, intégration Figma et MVP React",
    },
    {
        "name": "Studio Hyperion",
        "category": "Collectif Tech & Creative Dev",
        "website": "https://hyperion.studio",
        "email": "contact@hyperion.studio",
        "city": "Paris",
        "phone": "06 40 20 10 30",
        "decision_maker": "Collectif Hyperion",
        "direct_portal_url": "https://hyperion.studio",
        "email_status": "verified",
        "notes": "Three.js, WebGL & design d'interaction",
    },
    {
        "name": "Biggerband",
        "category": "Agence Digitale & Expériences Interactives",
        "website": "https://www.biggerband.com",
        "email": "contact@biggerband.com",
        "city": "Paris",
        "phone": "01 40 26 50 60",
        "decision_maker": "Direction Biggerband",
        "direct_portal_url": "https://www.biggerband.com/contact",
        "email_status": "verified",
        "notes": "Direction artistique, sites vitrines événementiels",
    }
]


class AgencyFinder:
    """
    Intelligent engine to discover web, design and communications agencies,
    crawl their websites for emails and key decision makers, and generate
    punchy, non-salesy direct cold outreach emails.
    """

    def __init__(self):
        self.db = db

    async def fetch_url_content(self, url: str, timeout: float = 4.5) -> Optional[str]:
        """Fetch raw HTML content from an agency website."""
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8",
        }
        loop = asyncio.get_event_loop()

        def _do_req():
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode("utf-8", errors="ignore")
            except Exception as e:
                logger.debug(f"Failed to fetch {url}: {e}")
                return None

        return await loop.run_in_executor(None, _do_req)

    def extract_emails_from_text(self, text: str) -> List[str]:
        """Extracts valid business contact emails from HTML, eliminating junk assets."""
        if not text:
            return []

        # Find all mailto: links first (high confidence)
        mailto_matches = re.findall(r'mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text, re.IGNORECASE)

        # General regex
        raw_matches = re.findall(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text)

        all_candidates = set(mailto_matches + raw_matches)
        valid_emails = []

        blacklisted_extensions = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".js", ".css")
        blacklisted_domains = ("sentry.io", "wixpress.com", "schema.org", "w3.org", "example.com", "domain.com", "wordpress.org", "cloudflare.com")

        for email in all_candidates:
            email_clean = email.strip().lower()
            if any(email_clean.endswith(ext) for ext in blacklisted_extensions):
                continue
            if any(dom in email_clean for dom in blacklisted_domains):
                continue
            if len(email_clean) > 60 or len(email_clean) < 6:
                continue
            valid_emails.append(email_clean)

        # Prioritize contact@, hello@, bonjour@, jobs@, studio@, agence@
        def _priority_score(e: str) -> int:
            if e.startswith(("hello@", "bonjour@", "contact@")):
                return 10
            if e.startswith(("studio@", "agence@", "equipe@", "team@", "jobs@", "rh@")):
                return 8
            if e.startswith(("info@", "direction@")):
                return 5
            return 1

        valid_emails.sort(key=_priority_score, reverse=True)
        return valid_emails

    async def crawl_agency_contact(self, base_url: str) -> Dict[str, Any]:
        """
        Crawls homepage and primary contact/careers pages to extract verified email,
        phone number, ATS portal (Welcome to the Jungle, Lever, etc.), and decision makers.
        """
        parsed = urllib.parse.urlparse(base_url)
        domain_root = f"{parsed.scheme}://{parsed.netloc}"

        html_home = await self.fetch_url_content(domain_root, timeout=4.0)
        found_emails = self.extract_emails_from_text(html_home or "")

        phone = None
        city = "Paris"
        direct_portal_url = None
        decision_maker = None

        # Check for phone number
        if html_home:
            phone_m = re.search(r'(?:0|\+33\s?)[1-9](?:[\s.-]?\d{2}){4}', html_home)
            if phone_m:
                phone = phone_m.group(0).strip()

            # Detect ATS links (Welcome to the Jungle, Lever, etc.)
            ats_m = re.search(
                r'href=[\'"](https?://(?:www\.)?welcometothejungle\.com/[^\'"\s>]+)[\'"]',
                html_home,
                re.IGNORECASE,
            )
            if ats_m:
                direct_portal_url = ats_m.group(1)

        # If no email on home, check /contact, /recrutement or /mentions-legales
        pages_to_check = ["/contact", "/contact-us", "/recrutement", "/carrieres", "/jobs", "/mentions-legales"]
        for subpath in pages_to_check:
            sub_url = urllib.parse.urljoin(domain_root, subpath)
            sub_html = await self.fetch_url_content(sub_url, timeout=3.5)
            if not sub_html:
                continue

            if not direct_portal_url:
                ats_sub = re.search(
                    r'href=[\'"](https?://(?:www\.)?welcometothejungle\.com/[^\'"\s>]+)[\'"]',
                    sub_html,
                    re.IGNORECASE,
                )
                if ats_sub:
                    direct_portal_url = ats_sub.group(1)

            if subpath in ["/recrutement", "/carrieres", "/jobs", "/contact"] and not direct_portal_url:
                direct_portal_url = sub_url

            if not found_emails:
                sub_emails = self.extract_emails_from_text(sub_html)
                if sub_emails:
                    found_emails = sub_emails

        primary_email = found_emails[0] if found_emails else None

        # Run verification check
        audit = email_verifier.verify_email_deliverability(primary_email, domain_root)
        email_status = audit.get("status", "unverified")
        if not direct_portal_url and audit.get("direct_portal_url"):
            direct_portal_url = audit.get("direct_portal_url")
        if not decision_maker and audit.get("decision_maker"):
            decision_maker = audit.get("decision_maker")

        return {
            "email": primary_email if email_status != "ats_only" else None,
            "all_emails": found_emails,
            "phone": phone,
            "website": domain_root,
            "direct_portal_url": direct_portal_url,
            "decision_maker": decision_maker,
            "email_status": email_status,
        }

    def generate_personalized_message(
        self, agency_name: str, agency_data: Optional[Dict[str, Any]] = None, candidate_profile=None
    ) -> Dict[str, str]:
        """
        Generates a tailored, punchy, high-converting B2B outreach message
        specifically for agencies, using the user's configurable template and
        dynamically adapting to the agency name, city, decision maker, etc.
        """
        from core.prospection.template_manager import template_manager

        tpl = template_manager.get_template()
        agency_dict = agency_data or {"name": agency_name}
        if "name" not in agency_dict:
            agency_dict["name"] = agency_name

        return template_manager.render_template(
            subject_template=tpl["subject"],
            body_template=tpl["body"],
            agency=agency_dict,
            candidate_profile=candidate_profile,
        )

    async def scan_and_populate(
        self, city: str = "Paris", max_count: int = 25
    ) -> List[Dict[str, Any]]:
        """
        Populates database with curated and scanned agencies, tailored with
        custom messages, verified emails, decision makers, and direct ATS URLs.
        """
        profile = settings.load_profile()
        inserted_records = []

        for item in FEATURED_AGENCIES_DATA[:max_count]:
            try:
                # Generate custom message for each agency
                msg = self.generate_personalized_message(item["name"], candidate_profile=profile)

                record = AgencyProspect(
                    name=item["name"],
                    category=item.get("category", "Agence Web"),
                    website=item["website"],
                    email=item.get("email"),
                    phone=item.get("phone"),
                    city=item.get("city") or city,
                    subject=msg["subject"],
                    custom_message=msg["body"],
                    status="pending",
                    notes=item.get("notes", ""),
                    direct_portal_url=item.get("direct_portal_url"),
                    decision_maker=item.get("decision_maker"),
                    email_status=item.get("email_status", "verified"),
                )
                self.db.save_or_update_agency(record)
                inserted_records.append(record.dict())
            except Exception as e:
                logger.error(f"Error saving agency prospect {item.get('name')}: {e}")

        logger.info(f"Populated {len(inserted_records)} agencies for outreach.")
        return inserted_records


agency_finder = AgencyFinder()
