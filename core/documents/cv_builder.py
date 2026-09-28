"""ATS-friendly, per-job-tailored résumé builder.

Produces a clean single-column PDF that applicant tracking systems parse
reliably: standard fonts, no tables, no images, no columns, standard section
headings, and the job's keywords echoed in a re-ordered skills list and a
rewritten summary. Content stays truthful — it reorders and re-emphasizes the
candidate's real profile data, it never invents experience.

ATS "red flags" avoided:
  - No tables / text boxes / columns / images / headers-footers
  - No exotic fonts (Helvetica family only)
  - No icons, emoji, or non-latin glyphs
  - Standard section names (Contact, Résumé, Compétences, Expérience, Formation)
  - Searchable text layer (never a scanned image)
"""
import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, ListFlowable, ListItem,
)

from config.settings import UserProfile, BASE_DIR, GENERATED_DIR

logger = logging.getLogger("CVBuilder")


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------

# Aliases mapping a skill name to the tokens an ATS/recruiter might write.
SKILL_ALIASES = {
    "react": ["react", "react.js", "reactjs", "react 19", "react native"],
    "react 19": ["react 19", "react"],
    "llm": ["llm", "large language model", "gpt", "deepseek", "gemini"],
    "mcp": ["mcp", "model context protocol", "protocoles outil"],
    "agents": ["agents", "multi-agent", "agent orchestrator", "orchestration d.agents"],
    "typescript": ["typescript", "ts"],
    "javascript": ["javascript", "js", "es6"],
    "tailwind css": ["tailwind", "tailwindcss"],
    "tailwind": ["tailwind", "tailwindcss"],
    "deepseek": ["deepseek", "deepseek api", "deepseek-v4"],
    "generative ai": ["generative ai", "genai", "llm", "prompt engineering"],
    "next.js": ["next.js", "nextjs", "next 14", "next 15"],
    "vite": ["vite", "vitejs", "bundler"],
    "agent orchestration": ["agent orchestration", "multi-agent", "workflow automation", "chain of agents"],
    "automation": ["automation", "workflow automation", "rpa", "automatisation"],
    "devops": ["devops", "docker", "ci/cd", "déploiement", "kubernetes"],
    "pwa": ["pwa", "progressive web app"],
    "python": ["python"],
    "playwright": ["playwright", "automation", "e2e"],
    "front-end": ["front-end", "frontend", "front end"],
    "ai engineer": ["ai engineer", "ingénieur ia", "ai systems engineer", "agentic systems"],
    "framer motion": ["framer motion", "motion", "gsap"],
    "speech-to-text": ["speech-to-text", "stt", "whisper", "transcription"],
    "text-to-speech": ["text-to-speech", "tts", "synthèse vocale"],
    "computer vision": ["computer vision", "vision par ordinateur", "opencv", "mediapipe"],
}


def _skill_tokens(skill: str) -> List[str]:
    key = skill.lower().strip()
    if key in SKILL_ALIASES:
        return SKILL_ALIASES[key]
    # Fallback: split on spaces/symbols, plus the full phrase itself.
    parts = re.split(r"[^a-z0-9+#.]+", key)
    parts = [p for p in parts if len(p) > 1]
    return [key] + parts


def extract_job_keywords(job_title: str, job_description: str) -> List[str]:
    """Return a lowercased token list from the job title + description."""
    blob = f"{job_title or ''} {job_description or ''}".lower()
    tokens = re.findall(r"[a-z0-9+#.]+", blob)
    # Drop stopwords and single chars.
    stop = {
        "the", "and", "for", "with", "you", "your", "are", "will", "have",
        "has", "not", "this", "that", "from", "une", "une", "des", "les",
        "dans", "pour", "avec", "vous", "votre", "vos", "est", "sont", "être",
        "nous", "notre", "nos", "sur", "the", "a", "an", "of", "to", "in",
        "que", "qui", "et", "ou", "en", "au", "aux", "du", "de", "la", "le",
        "un", "we", "our", "as", "is", "be", "on", "at", "by", "plus",
    }
    out = []
    for t in tokens:
        if t in stop or len(t) <= 2:
            continue
        out.append(t)
    return out


def score_skill(skill: str, job_tokens: List[str]) -> int:
    """Higher = more relevant to the job. 0 = no direct keyword overlap."""
    skill_toks = _skill_tokens(skill)
    score = 0
    for st in skill_toks:
        if any(st == jt or (len(st) > 3 and st in jt) or (len(jt) > 3 and jt in st) for jt in job_tokens):
            score += 3
        # Partial / substring bonus
        elif any(len(st) > 3 and st in jt for jt in job_tokens):
            score += 1
    # Multi-token skills matching many job tokens are strong signals.
    return score


def prioritize_skills(profile: UserProfile, job_title: str, job_description: str) -> List[str]:
    job_tokens = extract_job_keywords(job_title, job_description)
    skills = [s for s in (profile.skills or []) if s and s.strip()]
    if not job_tokens:
        return skills
    scored = [(score_skill(s, job_tokens), i, s) for i, s in enumerate(skills)]
    # Stable sort: relevance desc, then original order.
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [s for _, _, s in scored]


def build_tailored_summary(profile: UserProfile, job_title: str, job_description: str) -> str:
    """Rewrite the profile summary to foreground skills the job asks for."""
    skills = prioritize_skills(profile, job_title, job_description)
    top = skills[:5]
    base = (profile.summary or "").strip()

    if not top:
        return base

    # Never fabricate: use the candidate's own title + real skills.
    title = profile.current_title or "Développeur"
    skill_list = ", ".join(top)
    intro = (
        f"{title} avec {profile.total_years_experience} ans d'expérience — "
        f"compétences clés pour ce poste : {skill_list}."
    )
    if base:
        return f"{intro} {base}"
    return intro


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return s[:60] or "doc"


def _clean(text: str) -> str:
    """Strip characters that could break the PDF text layer or ATS parsing."""
    if not text:
        return ""
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[\u200b-\u200d\ufeff]", "", text)
    return text.strip()


def _styles() -> dict:
    return {
        "name": ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=colors.black),
        "title": ParagraphStyle("title", fontName="Helvetica", fontSize=12, leading=16, textColor=colors.HexColor("#333333")),
        "contact": ParagraphStyle("contact", fontName="Helvetica", fontSize=9.5, leading=13, textColor=colors.HexColor("#444444")),
        "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=12, leading=16, spaceBefore=10, spaceAfter=2, textColor=colors.black),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=10, leading=14, textColor=colors.black),
        "body_just": ParagraphStyle("body_just", fontName="Helvetica", fontSize=10, leading=14, alignment=4, textColor=colors.black),
        "item": ParagraphStyle("item", fontName="Helvetica", fontSize=10, leading=13, leftIndent=12, bulletIndent=2, textColor=colors.black),
    }


def build_ats_cv_pdf(
    profile: UserProfile,
    job_title: str = "",
    job_description: str = "",
    company: str = "",
    output_dir: Optional[Path] = None,
) -> Path:
    """Build and write an ATS-friendly PDF résumé tailored to a job posting."""
    out_dir = output_dir or GENERATED_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"CV_{_slugify(profile.first_name + ' ' + profile.last_name)}_{_slugify(job_title or 'generic')}.pdf"
    path = out_dir / fname

    s = _styles()
    story = []

    # --- Header (single column, text only) ---
    full_name = f"{profile.first_name} {profile.last_name}".strip()
    story.append(Paragraph(_clean(full_name), s["name"]))
    story.append(Paragraph(_clean(profile.current_title or ""), s["title"]))

    contact_bits = []
    if profile.city:
        contact_bits.append(_clean(profile.city))
    phone = ""
    if profile.phone_number:
        phone = f"{profile.phone_country_code or '+33'} {profile.phone_number}".strip()
        contact_bits.append(phone)
    if profile.email:
        contact_bits.append(_clean(profile.email))
    for label, url in [
        ("Portfolio", profile.portfolio_url),
        ("GitHub", profile.github_url),
        ("LinkedIn", profile.linkedin_url),
    ]:
        if url:
            contact_bits.append(f"{label}: {_clean(url)}")
    story.append(Paragraph(" • ".join(contact_bits), s["contact"]))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#999999"), spaceBefore=4, spaceAfter=4))

    # --- Summary (tailored) ---
    summary = build_tailored_summary(profile, job_title, job_description)
    if summary:
        story.append(Paragraph("Résumé", s["section"]))
        story.append(Paragraph(_clean(summary), s["body_just"]))

    # --- Skills (re-ordered by relevance) ---
    skills = prioritize_skills(profile, job_title, job_description)
    if skills:
        story.append(Paragraph("Compétences", s["section"]))
        story.append(Paragraph(", ".join(_clean(x) for x in skills), s["body"]))

    # --- Experience (truthful, only if provided) ---
    experience = getattr(profile, "experience", None) or []
    if experience:
        story.append(Paragraph("Expérience", s["section"]))
        for exp in experience:
            if isinstance(exp, dict):
                role = _clean(exp.get("title") or exp.get("role") or "")
                org = _clean(exp.get("company") or exp.get("organization") or "")
                period = _clean(exp.get("period") or exp.get("dates") or "")
                desc = _clean(exp.get("description") or "")
                line = f"{role}"
                if org:
                    line += f" — {org}"
                if period:
                    line += f" ({period})"
                story.append(Paragraph(line, s["body"]))
                if desc:
                    story.append(Paragraph(desc, s["item"]))

    # --- Projects (truthful, only if provided) ---
    projects = getattr(profile, "projects", None) or []
    if projects:
        story.append(Paragraph("Projets", s["section"]))
        for proj in projects:
            if isinstance(proj, dict):
                name = _clean(proj.get("name") or proj.get("title") or "")
                desc = _clean(
                    proj.get("description")
                    or proj.get("stack")
                    or proj.get("technologies")
                    or ""
                )
                if not name:
                    continue
                line = name
                if desc:
                    line += f" — {desc}"
                story.append(Paragraph(line, s["item"]))

    # --- Education ---
    education = getattr(profile, "education", None) or []
    diplome = (profile.custom_qa or {}).get("diplome", "")
    if not education and diplome:
        education = [{"title": diplome}]
    if education:
        story.append(Paragraph("Formation", s["section"]))
        for edu in education:
            if isinstance(edu, dict):
                title = _clean(edu.get("title") or edu.get("degree") or "")
                school = _clean(edu.get("school") or edu.get("institution") or "")
                period = _clean(edu.get("period") or edu.get("dates") or "")
                if not title:
                    continue
                line = title
                if school:
                    line += f" — {school}"
                if period:
                    line += f" ({period})"
                story.append(Paragraph(line, s["body"]))
            elif isinstance(edu, str) and edu.strip():
                story.append(Paragraph(_clean(edu), s["body"]))

    # --- Languages ---
    if profile.languages:
        story.append(Paragraph("Langues", s["section"]))
        langs = []
        for lang, level in profile.languages.items():
            langs.append(f"{_clean(lang)} ({_clean(level)})" if level else _clean(lang))
        story.append(Paragraph(", ".join(langs), s["body"]))

    # --- Build PDF ---
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=_clean(full_name),
        author=_clean(full_name),
        subject=f"CV - {_clean(job_title or 'Candidature')}",
        creator="ADHJob",
    )
    doc.build(story)
    logger.info(f"ATS CV written to {path}")
    return path


cv_builder = None  # module-level API via functions above
