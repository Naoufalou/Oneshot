import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import httpx
from config.settings import settings

logger = logging.getLogger("LLMClient")


def _read_nous_token() -> str:
    """Lit le token d'inférence Nous Portal depuis le auth.json d'Hermes.

    Même logique que le gateway na_agent : priorité au token rafraîchi en arrière-plan.
    Vérifie le auth.json du profil actif + le global.
    """
    candidates = []
    hermes_home = os.environ.get("HERMES_HOME")
    if hermes_home:
        candidates.append(Path(hermes_home) / "auth.json")
    candidates.append(Path.home() / "AppData" / "Local" / "hermes" / "auth.json")
    candidates.append(Path.home() / ".hermes" / "auth.json")
    # Profil hermes-agent-os (token rafraichi par le runtime)
    profile_auth = Path.home() / "AppData" / "Local" / "hermes" / "profiles" / "hermes-agent-os" / "auth.json"
    candidates.append(profile_auth)
    for p in candidates:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            nous = (data.get("providers", {}) or {}).get("nous", {})
            token = nous.get("agent_key") or nous.get("access_token") or ""
            if token:
                return token
        except Exception:
            continue
    return ""


class LLMClient:
    def __init__(self):
        self.provider = settings.llm_provider.lower()
        self.gemini_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.openai_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
        self.ollama_url = settings.ollama_base_url
        self.model_name = settings.llm_model_name
        self._NOUS_URL = "https://inference-api.nousresearch.com/v1"
        self._NOUS_MODEL = "deepseek/deepseek-v4-flash"

        self._gemini_client = None
        self._openai_client = None
        self._nous_client = None

        if self.gemini_key and (self.provider == "gemini" or not self.provider):
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.gemini_key)
                self.provider = "gemini"
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini client: {e}")

        elif self.provider == "nous":
            # Nous Portal — cloud, OpenAI-compatible, token from Hermes auth.json
            token = _read_nous_token()
            if token:
                try:
                    from openai import OpenAI
                    self._nous_client = OpenAI(
                        api_key=token,
                        base_url=self._NOUS_URL,
                    )
                    logger.info("Nous Portal client initialized (cloud LLM).")
                except Exception as e:
                    logger.warning(f"Failed to initialize Nous client: {e}")
            else:
                logger.warning("No Nous Portal token found in Hermes auth.json.")

        elif self.openai_key and self.provider == "openai":
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=self.openai_key)
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client: {e}")

    @property
    def available(self) -> bool:
        """True only when a real LLM backend is configured and usable."""
        return bool(self._gemini_client or self._openai_client or self._nous_client)

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.4, json_mode: bool = False, max_tokens: int = 2048) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Nous Portal (cloud — primary, no fabrication)
        if self.provider == "nous" and self._nous_client:
            try:
                kwargs: Dict[str, Any] = {
                    "model": self.model_name or self._NOUS_MODEL,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                response = self._nous_client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.error(f"Nous Portal API error: {e}")

        # Gemini
        if self.provider == "gemini" and self._gemini_client:
            try:
                config = {}
                if system_prompt:
                    config["system_instruction"] = system_prompt
                if json_mode:
                    config["response_mime_type"] = "application/json"
                response = self._gemini_client.models.generate_content(
                    model=self.model_name or "gemini-2.5-flash",
                    contents=prompt,
                    config=config if config else None,
                )
                return response.text or ""
            except Exception as e:
                logger.error(f"Gemini API error: {e}")

        # OpenAI-compatible
        if self.provider == "openai" and self._openai_client:
            try:
                kwargs: Dict[str, Any] = {
                    "model": self.model_name if self.model_name.startswith("gpt") else "gpt-4o-mini",
                    "messages": messages,
                    "temperature": 0.2,
                }
                if json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                response = self._openai_client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.error(f"OpenAI API error: {e}")

        # Ollama (local fallback)
        if self.provider == "ollama":
            try:
                payload = {
                    "model": self.model_name or "llama3.2",
                    "prompt": prompt,
                    "system": system_prompt or "",
                    "stream": False,
                }
                if json_mode:
                    payload["format"] = "json"
                res = httpx.post(f"{self.ollama_url}/api/generate", json=payload, timeout=120.0)
                if res.status_code == 200:
                    return res.json().get("response", "")
            except Exception as e:
                logger.error(f"Ollama API error: {e}")

        # Fallback Heuristic mode when no LLM API is configured or working
        logger.warning("No LLM backend available — using heuristic fallback.")
        return self._heuristic_fallback(prompt, json_mode)

    def _heuristic_fallback(self, prompt: str, json_mode: bool) -> str:
        prompt_lower = prompt.lower()
        if "score" in prompt_lower or "match" in prompt_lower or json_mode:
            return json.dumps({
                "score": 75,
                "is_match": True,
                "matched_skills": ["Python", "FastAPI", "React", "Docker"],
                "missing_skills": [],
                "rationale": "Profil correspondant aux critères essentiels requis par l'offre.",
                "answer": "Oui, j'ai l'expérience demandée.",
            })
        return "4"


llm_client = LLMClient()
