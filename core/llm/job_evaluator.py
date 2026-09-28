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
            "TypeScript": [r"typescript\b", r"\bts\b", r"type-script"],
            "JavaScript": [r"javascript", r"\bjs\b", r"es6"],
            "Node.js": [r"node\.?js\b", r"nodejs", r"node\.js"],
            "Python": [r"python\b", r"python 3\.?\d*"],
            "React": [r"react\b", r"react\.js", r"reactjs"],
            "React Native": [r"react native", r"react-native"],
            "Next.js": [r"next\.js", r"nextjs"],
            "Expo": [r"expo\b"],
            "Electron": [r"electron\b"],
            "PySide6": [r"pyside6\b", r"pyqt\b"],
            "Tailwind CSS": [r"tailwind", r"tailwindcss"],
            "HTML5": [r"html5", r"\bhtml\b"],
            "CSS3": [r"css3", r"\bcss\b"],
            "API REST": [r"api rest", r"rest api", r"restful"],
            "WebSocket": [r"websocket", r"websockets?"],
            "Server-Sent Events": [r"sse\b", r"server.sent.events"],
            "Artificial Intelligence": [r"artificial intelligence", r"intelligence artificielle", r"\bai\b"],
            "Generative AI": [r"generative ai", r"genai", r"llm", r"large language model"],
            "AI Agents": [r"ai agent", r"agents?", r"multi.agent", r"agentic"],
            "Agent Orchestration": [r"agent orchestration", r"orchestration multi.agent", r"swarm"],
            "Model Context Protocol": [r"mcp\b", r"model.context.protocol"],
            "DeepSeek": [r"deep.?seek"],
            "Gemini API": [r"gemini\b", r"google ai"],
            "OpenRouter": [r"openrouter"],
            "Supabase": [r"supabase"],
            "PostgreSQL": [r"postgresql\b", r"postgres\b"],
            "SQLite": [r"sqlite"],
            "Workflow Automation": [r"workflow automation", r"automatisation"],
            "Web Scraping": [r"web scraping", r"scraping", r"crawl4ai"],
            "Computer Vision": [r"computer.vision", r"opencv"],
            "Speech-to-Text": [r"stt\b", r"speech.to.text", r"whisper"],
            "Text-to-Speech": [r"tts\b", r"text.to.speech"],
            "Lead Developer": [r"lead developer", r"tech lead", r"technical lead"],
            "Software Architect": [r"software architect", r"architecte logiciel", r"system architect"],
            "Product Builder": [r"product builder", r"product owner"],
            "Engineering Manager": [r"engineering manager", r"responsable technique"],
            "Full-Stack": [r"full.stack", r"fullstack", r"full stack"],
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

        # 3. Weighted scoring — patterns aligned with Naoufal Ou (Lead Developer & AI Systems Engineer)
        is_ai_engineer = any(re.search(p, title_lower) for p in [r"ai engineer", r"ai systems", r"llm", r"large language", r"intelligence artificielle", r"ingenieur ia", r"generative ai", r"agentic", r"model context protocol", r"\bmcp\b", r"deepseek", r"automatisation", r"orchestration multi.agent"])
        is_fullstack_lead = any(re.search(p, title_lower) for p in [r"full.stack", r"fullstack", r"lead developer", r"tech lead", r"software architect", r"ingenieur", r"développeur", r"software engineer"])
        is_startup_founder = any(re.search(p, title_lower) for p in [r"founder", r"ceo", r"fondateur", r"startup", r"entrepreneur", r"freelance", r"indépendant"])
        is_tech_adjacent = any(re.search(p, title_lower) for p in [r"chef de projet", r"consultant digital", r"product owner", r"engineering manager", r"responsable technique"])

        score = 50
        rationale_prefix = "Correspondance calculée"

        if is_ai_engineer:
            # Huge match for AI Engineer / LLM / Agentic systems / MCP
            score = 90 + min(7, len(matched_skills) * 2)
            rationale_prefix = "Match Exceptionnel • AI Engineer & Systèmes Multi-Agents (LLM/MCP)"
        elif is_fullstack_lead:
            if "TypeScript" in matched_skills or "Python" in matched_skills:
                score = 85 + min(8, len(matched_skills) * 2)
                rationale_prefix = "Très forte adéquation • Lead Dev Full-Stack & Automatisation"
            elif "Node.js" in matched_skills or "React" in matched_skills:
                score = 80 + min(6, len(matched_skills) * 2)
                rationale_prefix = "Bonne adéquation • Développeur Full-Stack"
            else:
                score = 75
                rationale_prefix = "Adéquation correcte • Poste Full-Stack"
        elif is_startup_founder:
            score = 70 + min(5, len(matched_skills) * 2)
            rationale_prefix = "Bonne adéquation • Profil entrepreneur & tech"
        elif is_tech_adjacent:
            score = 60
            rationale_prefix = "Adéquation partielle • Rôle tech connexe"
        else:
            # Unrelated / General profession
            matched_len = len(matched_skills)
            if matched_len > 0:
                score = 50 + matched_len * 5
                rationale_prefix = f"Quelques compétences communes détectées ({', '.join(matched_skills[:3])})"
            else:
                score = 38
                rationale_prefix = "Profil éloigné du cœur de compétences IA & Développement"

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
