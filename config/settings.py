import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml

import shutil

BASE_DIR = Path(__file__).resolve().parent.parent
IS_VERCEL = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

if IS_VERCEL:
    DATA_DIR = Path("/tmp/data")
    CONFIG_CACHE_DIR = Path("/tmp/config")
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        # Copy seed data from repository bundle if present
        source_data = BASE_DIR / "data"
        if source_data.exists():
            for item in source_data.iterdir():
                dest = DATA_DIR / item.name
                if not dest.exists():
                    if item.is_file():
                        shutil.copy2(item, dest)
                    elif item.is_dir() and item.name not in ["browser_sessions", "screenshots"]:
                        shutil.copytree(item, dest)
        source_config = BASE_DIR / "config"
        if source_config.exists():
            for item in source_config.iterdir():
                dest = CONFIG_CACHE_DIR / item.name
                if not dest.exists() and item.is_file() and item.suffix in [".yaml", ".yml"]:
                    shutil.copy2(item, dest)
    except Exception as e:
        print(f"Vercel /tmp initialization note: {e}")
else:
    DATA_DIR = BASE_DIR / "data"
    CONFIG_CACHE_DIR = BASE_DIR / "config"

SESSIONS_DIR = DATA_DIR / "browser_sessions"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
RESUMES_DIR = DATA_DIR / "resumes"
GENERATED_DIR = DATA_DIR / "generated"

# Ensure directories exist
for folder in [DATA_DIR, SESSIONS_DIR, SCREENSHOTS_DIR, RESUMES_DIR, GENERATED_DIR]:
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


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


class EmailVerificationSettings(BaseModel):
    """IMAP access to the candidate's mailbox, used to auto-validate email
    verification codes sent by external ATS during account creation.

    SECURITY: never commit the password. Use an app-specific password
    (Gmail / Outlook / etc.) stored in .env (EMAIL_IMAP_PASSWORD), not in yaml.
    """
    enabled: bool = False
    imap_host: str = "imap.gmail.com"
    imap_port: int = 993
    email: str = ""          # mailbox address (same as profile.email normally)
    username: str = ""       # login (often == email)
    password: str = ""       # app password — prefer .env EMAIL_IMAP_PASSWORD
    # Policy when a form requires email verification:
    #   "auto"   -> create/verify automatically via IMAP
    #   "skip"   -> leave the application aside (requires_review) for manual action
    verification_policy: str = "skip"
    code_timeout_seconds: int = 180


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
    browser_ws_endpoint: Optional[str] = None  # WebSocket endpoint for remote browser (e.g. Browserless.io)
    
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
    email_verification: EmailVerificationSettings = Field(default_factory=EmailVerificationSettings)
    
    # Database
    db_path: Path = DATA_DIR / "applications.db"
    
    # User Profile & Search config paths
    profile_path: Path = CONFIG_CACHE_DIR / "profile.yaml"
    search_criteria_path: Path = CONFIG_CACHE_DIR / "search_criteria.yaml"

    def load_profile(self) -> UserProfile:
        target = self.profile_path if self.profile_path.exists() else (BASE_DIR / "config" / "profile.yaml")
        if target.exists():
            with open(target, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return UserProfile(**data)
        return UserProfile()

    def save_profile(self, profile: UserProfile):
        with open(self.profile_path, "w", encoding="utf-8") as f:
            yaml.dump(profile.model_dump(), f, allow_unicode=True, default_flow_style=False)

    def load_search_criteria(self) -> SearchCriteria:
        target = self.search_criteria_path if self.search_criteria_path.exists() else (BASE_DIR / "config" / "search_criteria.yaml")
        if target.exists():
            with open(target, "r", encoding="utf-8") as f:
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
