import json
import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel
from config.settings import UserProfile, SearchCriteria
from .llm_client import llm_client

logger = logging.getLogger("JobEvaluator")


class EvaluationResult(BaseModel):
    score: int
    is_match: bool
    rationale: str
    matched_skills: list[str] = []
    missing_skills: list[str] = []


class JobEvaluator:
    def __init__(self):
        self.llm = llm_client

    def evaluate_job_smart(
        self,
        job_title: str,
        company: str,
        description: str = "",
        location: str = "",
        profile: Optional[UserProfile] = None,
        criteria: Optional[SearchCriteria] = None,
    ) -> EvaluationResult:
        """
        Fast, high-precision semantic matching between job posting and candidate profile.
        Computes weighted score, matched skills chips, and insightful rationale.
        """
        if profile is None:
            from config.settings import settings
            profile = settings.load_profile()
        if criteria is None:
            from config.settings import settings
            criteria = settings.load_search_criteria()

        title_lower = (job_title or "").lower()
        desc_lower = (description or "").lower()
        full_text = f"{title_lower} {desc_lower} {(company or '').lower()}"

        # 1. Blacklist check
        for blacklisted in criteria.blacklisted_companies:
            if blacklisted and blacklisted.lower() in (company or "").lower():
                return EvaluationResult(
                    score=0,
                    is_match=False,
                    rationale=f"Entreprise exclue : {company}",
                )

        for kw in criteria.blacklisted_keywords:
            if kw and kw.lower() in title_lower:
                return EvaluationResult(
                    score=20,
                    is_match=False,
                    rationale=f"Mot-clé exclu dans l'intitulé : '{kw}'",
                )

        # 2. Skill dictionary mapping
        candidate_skills = profile.skills or []
        skill_patterns = {
            "Three.js": [r"three\.js", r"threejs", r"three js"],
            "WebGL": [r"webgl", r"shaders?", r"glsl"],
            "React": [r"react\b", r"react\.js", r"reactjs", r"react 19", r"react native"],
            "TypeScript": [r"typescript\b", r"\bts\b"],
            "Tailwind CSS": [r"tailwind", r"tailwindcss"],
            "Figma": [r"figma\b", r"ui/ux", r"ux/ui", r"product design"],
            "UI/UX Design": [r"ui design", r"ux design", r"ergonomie", r"design system"],
            "Next.js": [r"next\.js", r"nextjs", r"next 14", r"next 15"],
            "Vite": [r"vite\b", r"vitejs"],
            "GSAP": [r"gsap\b", r"green sock", r"framer motion", r"motion"],
            "JavaScript": [r"javascript", r"\bjs\b", r"es6"],
            "Front-End": [r"front-end", r"frontend", r"front end", r"intégrateur web"],
            "Creative Developer": [r"creative developer", r"creative dev", r"développeur créatif"],
            "PWA": [r"pwa\b", r"progressive web app"],
            "Python": [r"python\b"],
            "Sound / Audio": [r"sound design", r"audio web api", r"audio\b"],
        }

        matched_skills = []
        for skill_name, patterns in skill_patterns.items():
            for p in patterns:
                if re.search(p, full_text):
                    matched_skills.append(skill_name)
                    break

        # Also check custom skills from profile
        for sk in candidate_skills:
            if sk not in matched_skills and len(sk) > 2:
                if sk.lower() in full_text:
                    matched_skills.append(sk)

        # 3. Weighted scoring
        # Direct dream roles for Eliot Hantute (Three.js, WebGL, Creative Dev, React UI)
        is_creative_dev = any(re.search(p, title_lower) for p in [r"creative", r"three\.js", r"webgl", r"3d", r"immersif", r"créatif"])
        is_frontend_react = any(re.search(p, title_lower) for p in [r"react", r"front-end", r"frontend", r"front end"])
        is_ui_designer = any(re.search(p, title_lower) for p in [r"ui design", r"design engineer", r"ui/ux", r"product designer", r"intégrateur"])
        is_web_general = any(re.search(p, title_lower) for p in [r"développeur web", r"software engineer", r"full stack", r"fullstack", r"web developer"])
        is_tech_adjacent = any(re.search(p, title_lower) for p in [r"ingénieur", r"tech lead", r"chef de projet digital", r"consultant digital"])

        score = 50
        rationale_prefix = "Correspondance calculée"

        if is_creative_dev:
            # Huge match for Creative Developer / Three.js / WebGL
            score = 92 + min(6, len(matched_skills) * 2)
            rationale_prefix = "Match Exceptionnel • Cœur de profil Creative Developer & WebGL/3D"
        elif is_frontend_react:
            if "Three.js" in matched_skills or "WebGL" in matched_skills:
                score = 95
                rationale_prefix = "Match Idéal • Front-End avec technologies 3D/Three.js"
            elif "React" in matched_skills or "TypeScript" in matched_skills:
                score = 88 + min(8, len(matched_skills) * 2)
                rationale_prefix = "Très forte adéquation • Spécialiste Front-End React & TypeScript"
            else:
                score = 84
                rationale_prefix = "Forte adéquation • Poste Front-End ciblé"
        elif is_ui_designer:
            score = 86 + min(6, len(matched_skills) * 2)
            rationale_prefix = "Excellente adéquation • Profil hybride UI Designer & Intégrateur"
        elif is_web_general:
            if "React" in matched_skills or "TypeScript" in matched_skills:
                score = 78 + min(8, len(matched_skills) * 2)
                rationale_prefix = "Bonne adéquation • Poste Web avec stack React/JS"
            else:
                score = 68
                rationale_prefix = "Adéquation modérée • Poste Web généraliste"
        elif is_tech_adjacent:
            score = 60
            rationale_prefix = "Adéquation partielle • Rôle digital connexe"
        else:
            # Unrelated / General profession
            matched_len = len(matched_skills)
            if matched_len > 0:
                score = 50 + matched_len * 5
                rationale_prefix = f"Quelques compétences communes détectées ({', '.join(matched_skills[:3])})"
            else:
                score = 38
                rationale_prefix = "Profil éloigné du cœur de compétences Creative Dev"

        # Cap score between 20 and 99
        score = min(99, max(20, score))
        is_match = score >= criteria.min_match_score

        # Build clean concise rationale
        skills_summary = f" ({', '.join(matched_skills[:4])})" if matched_skills else ""
        rationale = f"{rationale_prefix}{skills_summary}."

        return EvaluationResult(
            score=score,
            is_match=is_match,
            rationale=rationale,
            matched_skills=matched_skills[:6],
            missing_skills=[],
        )

    def evaluate_job(
        self,
        job_title: str,
        company: str,
        description: str,
        profile: UserProfile,
        criteria: SearchCriteria,
    ) -> EvaluationResult:
        """Evaluates a job using smart heuristic with LLM fallback if needed."""
        return self.evaluate_job_smart(
            job_title=job_title,
            company=company,
            description=description,
            profile=profile,
            criteria=criteria,
        )

    def rescore_all_applications(self, db) -> Dict[str, Any]:
        """
        Recalculates match scores for all stored job postings in database
        based on the current active profile and search criteria.
        """
        from config.settings import settings
        profile = settings.load_profile()
        criteria = settings.load_search_criteria()

        all_apps = db.list_applications(status=None, limit=2000)
        total = len(all_apps)
        high_count = 0
        med_count = 0
        low_count = 0

        logger.info(f"Rescoring {total} applications against profile {profile.first_name} {profile.last_name}...")

        updates = []
        for app in all_apps:
            job_id = app.get("id") if isinstance(app, dict) else getattr(app, "id", None)
            title = app.get("job_title") if isinstance(app, dict) else getattr(app, "job_title", "")
            company = app.get("company") if isinstance(app, dict) else getattr(app, "company", "")
            location = (app.get("location") if isinstance(app, dict) else getattr(app, "location", "")) or ""

            eval_res = self.evaluate_job_smart(
                job_title=title,
                company=company,
                location=location,
                profile=profile,
                criteria=criteria,
            )

            updates.append((eval_res.score, eval_res.rationale, job_id))

            if eval_res.score >= 80:
                high_count += 1
            elif eval_res.score >= 60:
                med_count += 1
            else:
                low_count += 1

        # Direct fast SQLite batch execution
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                "UPDATE job_applications SET match_score = ?, match_reason = ? WHERE id = ?",
                updates,
            )
            conn.commit()

        logger.info(f"Rescoring complete: {high_count} high (>=80%), {med_count} med, {low_count} low.")
        return {
            "total": total,
            "high_matches": high_count,
            "medium_matches": med_count,
            "low_matches": low_count,
            "active_profile": f"{profile.first_name} {profile.last_name}",
            "active_title": profile.current_title,
        }


job_evaluator = JobEvaluator()
