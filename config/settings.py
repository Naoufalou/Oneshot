import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SESSIONS_DIR = DATA_DIR / "browser_sessions"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
RESUMES_DIR = DATA_DIR / "resumes"
GENERATED_DIR = DATA_DIR / "generated"

# Ensure directories exist
for folder in [DATA_DIR, SESSIONS_DIR, SCREENSHOTS_DIR, RESUMES_DIR, GENERATED_DIR]:
    folder.mkdir(parents=True, exist_ok=True)


class UserProfile(BaseModel):
    first_name: str = "Jean"
    last_name: str = "Dupont"
    email: str = "jean.dupont@example.com"
    phone_country_code: str = "+33"
    phone_number: str = "612345678"
    city: str = "Paris"
    country: str = "France"
    postal_code: str = "75001"
    address: str = "10 Rue de la Paix"
    
    current_title: str = "Développeur Full Stack"
    total_years_experience: int = 4
    linkedin_url: Optional[str] = "https://www.linkedin.com/in/jeandupont"
    github_url: Optional[str] = "https://github.com/jeandupont"
    portfolio_url: Optional[str] = "https://jeandupont.dev"
    
    summary: str = "Développeur passionné par Python, JavaScript, React et l'architecture Cloud."
    skills: List[str] = ["Python", "JavaScript", "TypeScript", "React", "Node.js", "Docker", "SQL", "Git"]
    languages: Dict[str, str] = {"Français": "Natif", "Anglais": "Professionnel (C1)"}
    
    # Common questions answers
    work_authorization_eu: bool = True
    requires_sponsorship: bool = False
    salary_expectation_annual_eur: int = 48000
    notice_period_weeks: int = 4
    willing_to_relocate: bool = False
    
    custom_qa: Dict[str, str] = Field(
        default_factory=lambda: {
            "permis": "Oui, Permis B",
            "statut": "Cadre",
            "diplome": "Bac+5 Master Informatique",
        }
    )
    resume_path: Optional[str] = None

    # Structured career data (truthful; used by the ATS CV builder). Empty by
    # default — the CV builder emits a skills/projects-based résumé when these
    # are not populated, rather than inventing experience.
    experience: List[Dict[str, str]] = Field(default_factory=list)
    education: List[Dict[str, str]] = Field(default_factory=list)
    projects: List[Dict[str, str]] = Field(default_factory=list)


class SearchCriteria(BaseModel):
    keywords: List[str] = ["Développeur Python", "Full Stack Developer", "Software Engineer"]
    locations: List[str] = ["Paris, France", "Remote", "Île-de-France"]
    remote_only: bool = False
    contract_types: List[str] = ["CDI", "Freelance"]
    min_match_score: int = 60  # LLM score (0-100) to proceed
    min_alert_score: int = 70  # Minimum score to send push notification
    max_applications_per_day: int = 25
    easy_apply_only: bool = True
    blacklisted_companies: List[str] = []
    blacklisted_keywords: List[str] = ["Stage", "Alternance", "Senior 10+ ans"]


class NotificationSettings(BaseModel):
    enable_telegram: bool = False
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    
    enable_discord: bool = False
    discord_webhook_url: Optional[str] = None
    
    enable_in_app: bool = True


class WatcherSettings(BaseModel):
    enabled: bool = False
    interval_minutes: int = 30
    auto_apply_on_high_match: bool = False  # If True and score >= 85, auto applies
    high_match_threshold: int = 85
    platforms: List[str] = ["linkedin", "indeed", "francetravail"]


class RateLimitSettings(BaseModel):
    # Daily caps (conservative: LinkedIn Easy Apply blocks ~10-15/day in practice)
    linkedin_daily_apply_cap: int = 10
    indeed_daily_apply_cap: int = 25
    francetravail_daily_apply_cap: int = 25
    # Minimum interval between two applications (seconds, jittered upward)
    min_apply_interval_seconds: float = 45.0
    linkedin_min_apply_interval_seconds: float = 45.0
    # Minimum interval between two search page loads (seconds)
    min_search_interval_seconds: float = 20.0
    linkedin_min_search_interval_seconds: float = 20.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")
    
    # App Mode
    app_env: str = "development"
    headless_browser: bool = True
    human_in_the_loop: bool = False  # Automated background applications without manual blocker
    
    # LLM Settings
    llm_provider: str = "gemini"  # "gemini", "openai", "ollama"
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    llm_model_name: str = "gemini-2.5-flash"
    
    # Notifications & Watcher
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    watcher: WatcherSettings = Field(default_factory=WatcherSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    
    # Database
    db_path: Path = DATA_DIR / "applications.db"
    
    # User Profile & Search config paths
    profile_path: Path = BASE_DIR / "config" / "profile.yaml"
    search_criteria_path: Path = BASE_DIR / "config" / "search_criteria.yaml"

    def load_profile(self) -> UserProfile:
        if self.profile_path.exists():
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return UserProfile(**data)
        return UserProfile()

    def save_profile(self, profile: UserProfile):
        with open(self.profile_path, "w", encoding="utf-8") as f:
            yaml.dump(profile.model_dump(), f, allow_unicode=True, default_flow_style=False)

    def load_search_criteria(self) -> SearchCriteria:
        if self.search_criteria_path.exists():
            with open(self.search_criteria_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return SearchCriteria(**data)
        return SearchCriteria()

    def save_search_criteria(self, criteria: SearchCriteria):
        with open(self.search_criteria_path, "w", encoding="utf-8") as f:
            yaml.dump(criteria.model_dump(), f, allow_unicode=True, default_flow_style=False)


settings = Settings()

# Wire anti-ban rate limits into the central limiter once at import time.
from core.rate_limiter import configure_from_settings  # noqa: E402
configure_from_settings(settings)
