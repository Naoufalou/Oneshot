"""Application document orchestration + smart job targeting.

Ties together:
  - Tailored ATS-friendly CV generation (per job)
  - Tailored cover letter generation (per job)
  - Smart ordering: apply to the highest-match jobs first, with a minimum
    score floor to avoid wasting submissions on low-probability offers.
"""
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.settings import UserProfile, SearchCriteria, BASE_DIR, settings
from core.documents.cv_builder import build_ats_cv_pdf
from core.documents.cover_letter_builder import build_cover_letter_pdf, build_cover_letter_text
from core.storage.db import db

logger = logging.getLogger("ApplicationDocuments")

GENERATED_DIR = BASE_DIR / "data" / "generated"


def prepare_application_documents(
    profile: UserProfile,
    job_title: str,
    company: str,
    job_description: str = "",
    location: str = "",
) -> Dict[str, Any]:
    """Generate tailored CV + cover letter for one job. Returns paths + text."""
    cv_path = build_ats_cv_pdf(
        profile,
        job_title=job_title,
        job_description=job_description,
        company=company,
    )
    lm_path = build_cover_letter_pdf(
        profile,
        job_title=job_title,
        company=company,
        job_description=job_description,
        location=location,
    )
    lm_text = build_cover_letter_text(profile, job_title, company, job_description, location)
    return {
        "cv_path": str(cv_path),
        "cover_letter_path": str(lm_path),
        "cover_letter_text": lm_text,
    }


def smart_rank_jobs(
    jobs: List[Dict[str, Any]],
    min_score: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Sort unapplied jobs by match score descending and filter weak matches.

    Priority logic: apply to the offers with the highest probability of a
    positive outcome first (best fit for the loaded profile). Jobs below
    `min_score` are dropped so submissions are not wasted on long shots.
    """
    criteria = settings.load_search_criteria()
    floor = min_score if min_score is not None else criteria.min_match_score
    floor = max(0, floor)

    filtered = [j for j in jobs if (j.get("match_score") or 0) >= floor]
    # Stable sort: highest score first, then most recent.
    filtered.sort(
        key=lambda j: (
            -(j.get("match_score") or 0),
            -(j.get("id") or 0),
        )
    )
    return filtered
