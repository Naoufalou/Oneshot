import json
import re
import logging
from typing import List, Optional, Union
from config.settings import UserProfile
from .llm_client import llm_client

logger = logging.getLogger("FormFiller")


class FormFiller:
    def __init__(self):
        self.llm = llm_client

    def answer_question(
        self,
        question_text: str,
        question_type: str,  # "text", "number", "boolean", "select", "radio"
        options: Optional[List[str]] = None,
        profile: Optional[UserProfile] = None,
        job_context: Optional[str] = None,
    ) -> Union[str, int, bool]:
        if not profile:
            from config.settings import settings
            profile = settings.load_profile()

        q_lower = question_text.lower()

        # 1. Quick Heuristic Rules for common job questions
        # Years of experience questions
        if "expérience" in q_lower or "experience" in q_lower or "years" in q_lower or "années" in q_lower:
            # Check if mentions a skill in profile
            for skill in profile.skills:
                if skill.lower() in q_lower:
                    if question_type == "number":
                        return profile.total_years_experience
                    return str(profile.total_years_experience)
            if question_type == "number":
                return profile.total_years_experience
            return str(profile.total_years_experience)

        # Sponsorship / Visa questions
        if "sponsor" in q_lower or "visa" in q_lower:
            if profile.requires_sponsorship:
                return "Oui" if "oui" in [o.lower() for o in (options or [])] else True
            else:
                return "Non" if "non" in [o.lower() for o in (options or [])] else False

        # Work authorization
        if "autoris" in q_lower or "legally" in q_lower or "droit de travailler" in q_lower or "authorized" in q_lower:
            if profile.work_authorization_eu:
                return "Oui" if "oui" in [o.lower() for o in (options or [])] else True
            else:
                return "Non" if "non" in [o.lower() for o in (options or [])] else False

        # Salary expectations
        if "salaire" in q_lower or "salary" in q_lower or "compensation" in q_lower or "prétention" in q_lower:
            if question_type == "number":
                return profile.salary_expectation_annual_eur
            return str(profile.salary_expectation_annual_eur)

        # Notice period / préavis
        if "préavis" in q_lower or "notice" in q_lower or "délai" in q_lower:
            if question_type == "number":
                return profile.notice_period_weeks
            return f"{profile.notice_period_weeks} semaines"

        # Check custom user QA map
        for key, val in profile.custom_qa.items():
            if key.lower() in q_lower:
                return val

        # 2. If options are provided (Select/Radio), choose best option via LLM or fuzzy match
        if options and len(options) > 0:
            return self._select_best_option(question_text, options, profile)

        # 3. LLM Generation for complex or open-ended questions
        system_prompt = (
            "Tu es un candidat professionnel qui postule à une offre d'emploi. "
            "Réponds à la question du formulaire de manière concise, précise, "
            "en te basant strictement sur les informations fournies dans le profil du candidat."
        )

        user_prompt = f"""
Profil Candidat:
- Nom: {profile.first_name} {profile.last_name}
- Titre: {profile.current_title}
- Expérience: {profile.total_years_experience} ans
- Compétences: {', '.join(profile.skills)}
- Résumé: {profile.summary}
- Salaire souhaité: {profile.salary_expectation_annual_eur} €
- Préavis: {profile.notice_period_weeks} semaines
- Infos spécifiques: {json.dumps(profile.custom_qa, ensure_ascii=False)}

Contexte de l'offre:
{job_context or "Non spécifié"}

Question du formulaire ({question_type}):
"{question_text}"

Options disponibles (si applicable): {json.dumps(options, ensure_ascii=False) if options else "Aucune"}

Consigne: Donne UNIQUEMENT la réponse directe et finale sans politesse inutile, sans guillemets, prête à être insérée dans le champ du formulaire.
"""

        try:
            answer = self.llm.generate_text(prompt=user_prompt, system_prompt=system_prompt).strip()
            # Clean possible markdown formatting
            answer = re.sub(r"^[\"']|[\"']$", "", answer)

            if question_type == "number":
                match = re.search(r"\d+", answer)
                if match:
                    return int(match.group(0))
                return profile.total_years_experience

            if question_type == "boolean":
                return any(w in answer.lower() for w in ["oui", "yes", "true", "vrai"])

            return answer

        except Exception as e:
            logger.warning(f"Error answering form question: {e}")
            if question_type == "number":
                return profile.total_years_experience
            if question_type == "boolean":
                return True
            return "Oui, je dispose des compétences nécessaires pour ce rôle."

    def _select_best_option(self, question: str, options: List[str], profile: UserProfile) -> str:
        q_lower = question.lower()
        
        # Check simple yes/no
        yes_opts = [o for o in options if o.strip().lower() in ["oui", "yes", "true"]]
        no_opts = [o for o in options if o.strip().lower() in ["non", "no", "false"]]
        
        if "visa" in q_lower or "sponsor" in q_lower:
            if not profile.requires_sponsorship and no_opts:
                return no_opts[0]
            if profile.requires_sponsorship and yes_opts:
                return yes_opts[0]

        if "autoris" in q_lower or "droit" in q_lower or "permis" in q_lower:
            if yes_opts:
                return yes_opts[0]

        # Use LLM to pick the exact string from options
        system_prompt = "Choisis la meilleure option parmi la liste fournie en fonction du profil du candidat. Retourne UNIQUEMENT la chaîne de l'option exacte, sans ajouter de texte."
        prompt = f"""
Question: {question}
Options disponibles:
{chr(10).join(f"- {opt}" for opt in options)}

Profil:
- Titre: {profile.current_title}
- Expérience: {profile.total_years_experience} ans
- Compétences: {', '.join(profile.skills)}

Option choisie (exactement identique à une des options ci-dessus) :
"""
        response = self.llm.generate_text(prompt=prompt, system_prompt=system_prompt).strip()
        for opt in options:
            if opt.strip().lower() == response.lower() or opt.strip().lower() in response.lower():
                return opt
        return options[0]


form_filler = FormFiller()
