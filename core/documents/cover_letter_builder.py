"""Per-job tailored cover letter builder (motivation letter / LM).

Produces a concise, truthful cover letter that references the specific job
title, company, and the skills the posting asks for — foregrounding the
candidate's matching skills. Uses the LLM when configured, else falls back to
a deterministic template built from real profile data (never invents facts).
"""
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from config.settings import UserProfile, BASE_DIR
from core.documents.cv_builder import prioritize_skills, _clean, _slugify, GENERATED_DIR
from core.llm.llm_client import llm_client

logger = logging.getLogger("CoverLetterBuilder")


def _match_skills(profile: UserProfile, job_title: str, job_description: str, n: int = 4) -> list:
    return prioritize_skills(profile, job_title, job_description)[:n]


def build_cover_letter_text(
    profile: UserProfile,
    job_title: str,
    company: str,
    job_description: str = "",
    location: str = "",
) -> str:
    """Return the tailored cover letter body (with greeting + sign-off)."""
    title = (job_title or "ce poste").strip()
    comp = (company or "votre entreprise").strip()
    matched = _match_skills(profile, job_title, job_description)
    name = f"{profile.first_name} {profile.last_name}".strip()
    role = profile.current_title or "développeur"

    # Try LLM first (if configured) for a richer, more natural letter.
    llm_text = _llm_cover_letter(profile, job_title, company, job_description, matched)
    if llm_text:
        return llm_text

    # --- Deterministic template ---
    skill_line = ", ".join(matched) if matched else (profile.skills[:4] and ", ".join(profile.skills[:4]) or "mon expertise")

    p1 = f"Madame, Monsieur,"
    p2 = (
        f"Actuellement {role} avec {profile.total_years_experience} ans d'expérience, "
        f"je vous adresse ma candidature pour le poste de {title} au sein de {comp}. "
        f"Cette opportunité correspond précisément à mon parcours et à mes compétences en {skill_line}."
    )
    p3 = (
        f"Au cours de mes expériences, j'ai développé une expertise solide en {skill_line}, "
        f"que je mets en œuvre au quotidien pour concevoir des interfaces performantes et "
        f"des expériences soignées. {profile.summary}"
    )
    dispo = (profile.custom_qa or {}).get("disponibilite", "")
    if dispo:
        dispo_phrase = f"Disponibilité : {dispo}."
    else:
        dispo_phrase = "Disponible immédiatement."
    p4 = (
        f"Rigoureux et autonome, je serais ravi d'échanger avec vous sur la valeur que je peux "
        f"apporter à {comp}. {dispo_phrase} Je vous remercie de l'attention portée à ma "
        f"candidature et me tiens à votre disposition pour un entretien."
    )
    sign_off = "Cordialement,"

    return "\n\n".join([p1, p2, p3, p4, sign_off, name])


def _llm_cover_letter(profile, job_title, company, job_description, matched) -> Optional[str]:
    # Never hit the heuristic fallback — a fake JSON response is worse than a
    # clean deterministic template. Only use the LLM when it is really available.
    if not llm_client.available:
        return None
    try:
        system = (
            "Tu es un candidat qui rédige une lettre de motivation professionnelle, "
            "concise (150-220 mots), en français, spécifique à l'offre. "
            "N'invente aucune information qui n'est pas dans le profil fourni. "
            "Structure : salutation, intérêt pour le poste/entreprise, compétences "
            "pertinentes, disponibilité, formule de politesse et signature."
        )
        prompt = (
            f"Offre : {job_title} chez {company}\n"
            f"Description : {(job_description or '')[:1200]}\n"
            f"Profil : {profile.first_name} {profile.last_name}, {profile.current_title}, "
            f"{profile.total_years_experience} ans d'expérience.\n"
            f"Compétences : {', '.join(profile.skills)}\n"
            f"Résumé : {profile.summary}\n"
            f"Compétences à mettre en avant pour cette offre : {', '.join(matched)}\n"
            f"Disponibilité : {profile.custom_qa.get('disponibilite', 'immédiate')}\n"
        )
        raw = llm_client.generate_text(prompt=prompt, system_prompt=system).strip()
        # Only accept a reasonably long, real-looking letter.
        if raw and len(raw) > 150:
            return raw
    except Exception as e:
        logger.warning(f"LLM cover letter fallback note: {e}")
    return None


def build_cover_letter_pdf(
    profile: UserProfile,
    job_title: str,
    company: str,
    job_description: str = "",
    location: str = "",
    output_dir: Optional[Path] = None,
) -> Path:
    """Render the tailored cover letter as a clean PDF and return its path."""
    out_dir = output_dir or GENERATED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"LM_{_slugify(profile.first_name + ' ' + profile.last_name)}_{_slugify(job_title or 'generic')}.pdf"
    path = out_dir / fname

    body = build_cover_letter_text(profile, job_title, company, job_description, location)
    name = f"{profile.first_name} {profile.last_name}".strip()

    st_name = ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=13, leading=17, textColor=colors.black)
    st_contact = ParagraphStyle("contact", fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.HexColor("#444444"))
    st_body = ParagraphStyle("body", fontName="Helvetica", fontSize=10.5, leading=15, spaceAfter=8, textColor=colors.black)

    story = []
    story.append(Paragraph(_clean(name), st_name))
    contact = []
    if profile.email:
        contact.append(_clean(profile.email))
    if profile.phone_number:
        contact.append(f"{profile.phone_country_code or '+33'} {profile.phone_number}".strip())
    if profile.city:
        contact.append(_clean(profile.city))
    story.append(Paragraph(" • ".join(contact), st_contact))
    story.append(Spacer(1, 10))
    story.append(Paragraph(_clean(f"Objet : Candidature — {job_title or 'Poste'}"), ParagraphStyle("obj", fontName="Helvetica-Bold", fontSize=10.5, leading=14, spaceAfter=6, textColor=colors.black)))
    story.append(Spacer(1, 4))

    for para in body.split("\n\n"):
        para = _clean(para)
        if not para:
            continue
        story.append(Paragraph(para, st_body))

    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        rightMargin=20 * mm, leftMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Lettre de motivation - {_clean(job_title or '')}",
        author=_clean(name), creator="ADHJob",
    )
    doc.build(story)
    logger.info(f"Cover letter written to {path}")
    return path
