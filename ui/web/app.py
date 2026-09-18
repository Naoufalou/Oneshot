import asyncio
import json
import time
import re
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from pydantic import BaseModel

logger = logging.getLogger("App")

from config.settings import (
    settings,
    BASE_DIR,
    UserProfile,
    SearchCriteria,
    NotificationSettings,
    WatcherSettings,
    SCREENSHOTS_DIR,
    RESUMES_DIR,
    SESSIONS_DIR,
    GENERATED_DIR,
)
from core.storage.db import db, ApplicationRecord
from core.rate_limiter import rate_limiter, RateLimitExceeded, PlatformBlockedError
from core.documents.application_documents import prepare_application_documents
from core.watcher.watcher_service import watcher_service
from core.watcher.realtime_scanner import realtime_scanner
from core.notifications.dispatcher import notification_dispatcher
from core.browser.session_setup import (
    launch_login_browser,
    close_and_verify_session,
    check_platform_session,
    inject_linkedin_cookie,
)
from platforms.base import JobPost
from platforms.linkedin import LinkedInPlatform
from platforms.indeed import IndeedPlatform
from platforms.francetravail import FranceTravailPlatform

app = FastAPI(title="Job Application Agent & Watcher Dashboard", version="2.0.0")

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

try:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOTS_DIR)), name="screenshots")
except Exception as e:
    logger.debug(f"Screenshots mount note: {e}")

try:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/generated", StaticFiles(directory=str(GENERATED_DIR)), name="generated")
except Exception as e:
    logger.debug(f"Generated mount note: {e}")

# Multi-platform simultaneous runners
PLATFORM_WORKERS: Dict[str, Dict[str, Any]] = {}

def get_initial_platform_state(plat: str) -> Dict[str, Any]:
    return {
        "platform": plat,
        "is_running": False,
        "current_index": 0,
        "total": 0,
        "percent": 0,
        "current_job_id": None,
        "current_job_title": "",
        "current_company": "",
        "success_count": 0,
        "skipped_count": 0,
        "failed_count": 0,
        "last_reason": "",
        "current_task": "En attente",
        "stop_requested": False,
        "started_at": None,
        "finished_at": None,
    }

for p in ["francetravail", "linkedin", "indeed"]:
    PLATFORM_WORKERS[p] = get_initial_platform_state(p)

# Global runner state for batch apply (retained for backward compatibility)
RUNNER_STATE = {
    "is_running": False,
    "current_index": 0,
    "total": 0,
    "current_job_id": None,
    "current_job_title": "",
    "current_company": "",
    "current_platform": "",
    "success_count": 0,
    "skipped_count": 0,
    "failed_count": 0,
    "last_reason": "",
    "current_task": "En attente",
    "stop_requested": False,
    "started_at": None,
    "logs": [],
}


@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = TEMPLATES_DIR / "index.html"
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/stats")
async def get_stats():
    return {
        "stats": db.get_stats(),
        "runner": RUNNER_STATE,
        "watcher": {
            "is_running": watcher_service.is_running,
            "status_message": watcher_service.status_message,
            "last_run_time": watcher_service.last_run_time,
            "total_detected": watcher_service.total_detected_count,
        },
    }


@app.get("/api/applications")
async def get_applications(
    status: Optional[str] = None,
    platform: Optional[str] = None,
    limit: int = 300,
    sort_by: str = "relevance"
):
    return db.list_applications(status=status, platform=platform, limit=limit, sort_by=sort_by)


@app.get("/api/opportunities")
async def get_opportunities(limit: int = 50, sort_by: str = "relevance"):
    """Returns newly detected job opportunities from the watcher feed."""
    return db.list_applications(status="detected", limit=limit, sort_by=sort_by)


class ProfileAnalyzeRequest(BaseModel):
    portfolio_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    resume_filename: Optional[str] = None
    additional_notes: Optional[str] = None


@app.get("/api/profile/current")
async def get_current_profile():
    profile = settings.load_profile()
    criteria = settings.load_search_criteria()
    return {
        "status": "success",
        "profile": profile.model_dump(),
        "criteria": criteria.model_dump(),
        "skills_count": len(profile.skills),
        "top_skills": profile.skills[:12],
    }


@app.post("/api/profile/analyze")
async def analyze_profile_endpoint(req: ProfileAnalyzeRequest):
    from core.llm.profile_analyzer import profile_analyzer
    from core.llm.job_evaluator import job_evaluator

    try:
        profile, criteria = profile_analyzer.apply_and_save_profile(
            portfolio_url=req.portfolio_url,
            linkedin_url=req.linkedin_url,
            resume_filename=req.resume_filename,
            additional_notes=req.additional_notes,
        )
        rescore_stats = job_evaluator.rescore_all_applications(db)

        return {
            "status": "success",
            "message": f"Profil de {profile.first_name} {profile.last_name} analysé avec succès ! {rescore_stats['high_matches']} offres recommandées.",
            "profile": profile.model_dump(),
            "criteria": criteria.model_dump(),
            "rescore_stats": rescore_stats,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Erreur lors de l'analyse du profil: {str(e)}"}
        )


@app.post("/api/jobs/rescore")
async def rescore_jobs_endpoint():
    from core.llm.job_evaluator import job_evaluator
    stats = job_evaluator.rescore_all_applications(db)
    return {
        "status": "success",
        "message": f"Recalcul terminé : {stats['high_matches']} offres hautement recommandées pour {stats['active_profile']}",
        "stats": stats,
    }


@app.get("/api/config")
async def get_config():
    return {
        "profile": settings.load_profile().model_dump(),
        "criteria": settings.load_search_criteria().model_dump(),
        "notifications": settings.notifications.model_dump(),
        "watcher": settings.watcher.model_dump(),
        "settings": {
            "headless_browser": settings.headless_browser,
            "human_in_the_loop": settings.human_in_the_loop,
            "llm_provider": settings.llm_provider,
            "llm_model_name": settings.llm_model_name,
        },
        "rate_limit": settings.rate_limit.model_dump(),
    }


@app.post("/api/config/profile")
async def update_profile(profile: UserProfile):
    settings.save_profile(profile)
    return {"status": "success", "message": "Profil mis à jour avec succès"}


@app.post("/api/config/criteria")
async def update_criteria(criteria: SearchCriteria):
    settings.save_search_criteria(criteria)
    return {"status": "success", "message": "Critères de recherche mis à jour"}


class ToggleOptionRequest(BaseModel):
    enabled: bool


@app.post("/api/config/toggle-easy-apply")
async def toggle_easy_apply(req: ToggleOptionRequest):
    criteria = settings.load_search_criteria()
    criteria.easy_apply_only = req.enabled
    settings.save_search_criteria(criteria)
    return {
        "status": "success",
        "easy_apply_only": criteria.easy_apply_only,
        "message": f"Option 'Postuler en 1 Clic' {'activée' if req.enabled else 'désactivée'}"
    }


@app.post("/api/config/notifications")
async def update_notifications(notif: NotificationSettings):
    settings.notifications = notif
    return {"status": "success", "message": "Paramètres de notifications enregistrés"}


@app.post("/api/config/watcher")
async def update_watcher(watch: WatcherSettings):
    settings.watcher = watch
    return {"status": "success", "message": "Paramètres de veille enregistrés"}


# --- RESUMES API & VIEWER ---

class SetActiveResumeRequest(BaseModel):
    filename: str


@app.get("/api/resumes")
async def list_resumes():
    profile = settings.load_profile()
    active_path = profile.resume_path or ""
    active_name = Path(active_path).name if active_path else ""

    resumes = []
    if RESUMES_DIR.exists():
        for file in sorted(RESUMES_DIR.glob("*")):
            if file.is_file() and not file.name.startswith("."):
                is_active = (file.name == active_name)
                stats = file.stat()
                resumes.append({
                    "filename": file.name,
                    "size_kb": round(stats.st_size / 1024, 1),
                    "modified_at": stats.st_mtime,
                    "is_active": is_active,
                    "preview_url": f"/api/resumes/preview/{file.name}",
                    "download_url": f"/api/resumes/download/{file.name}",
                })
    return {
        "resumes": resumes,
        "active_filename": active_name,
        "profile": profile.model_dump(),
    }


@app.get("/api/resumes/active")
async def get_active_resume():
    profile = settings.load_profile()
    active_path = profile.resume_path or ""
    active_name = Path(active_path).name if active_path else ""
    return {
        "active_filename": active_name,
        "active_path": active_path,
        "exists": (RESUMES_DIR / active_name).exists() if active_name else False,
        "preview_url": f"/api/resumes/preview/{active_name}" if active_name else None,
        "profile": profile.model_dump(),
    }


@app.post("/api/resumes/set-active")
async def set_active_resume(req: SetActiveResumeRequest):
    target_file = RESUMES_DIR / req.filename
    if not target_file.exists():
        raise HTTPException(status_code=404, detail="Fichier CV introuvable")

    profile = settings.load_profile()
    try:
        rel_path = str(target_file.relative_to(BASE_DIR))
    except ValueError:
        rel_path = str(target_file)
    profile.resume_path = rel_path
    settings.save_profile(profile)

    return {
        "status": "success",
        "message": f"CV actif mis à jour : {req.filename}",
        "active_filename": req.filename,
    }


@app.post("/api/resumes/upload")
async def upload_resume(file: UploadFile = File(...), set_active: Any = True):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nom de fichier invalide")

    # Safe boolean check
    is_set_active = True
    if isinstance(set_active, bool):
        is_set_active = set_active
    elif isinstance(set_active, str):
        is_set_active = set_active.lower() in ("true", "1", "yes")

    clean_name = Path(file.filename).name.replace(" ", "_")
    target_path = RESUMES_DIR / clean_name

    content = await file.read()
    with open(target_path, "wb") as f:
        f.write(content)

    profile = settings.load_profile()
    if is_set_active or not profile.resume_path:
        try:
            rel_path = str(target_path.relative_to(BASE_DIR))
        except ValueError:
            rel_path = str(target_path)
        profile.resume_path = rel_path
        settings.save_profile(profile)

    return {
        "status": "success",
        "message": f"CV '{clean_name}' ajouté" + (" et défini comme CV actif !" if is_set_active else "!"),
        "filename": clean_name,
        "is_active": is_set_active,
    }


@app.get("/api/resumes/preview/{filename}")
async def preview_resume(filename: str):
    file_path = RESUMES_DIR / Path(filename).name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="CV non trouvé")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{file_path.name}"'}
    )


@app.get("/api/resumes/download/{filename}")
async def download_resume(filename: str):
    file_path = RESUMES_DIR / Path(filename).name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="CV non trouvé")

    return FileResponse(
        path=str(file_path),
        media_type="application/octet-stream",
        filename=file_path.name
    )


@app.delete("/api/resumes/{filename}")
async def delete_resume(filename: str):
    file_path = RESUMES_DIR / Path(filename).name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="CV non trouvé")

    file_path.unlink()
    profile = settings.load_profile()
    if profile.resume_path and Path(profile.resume_path).name == filename:
        # Pick another resume if available
        remaining = [f for f in RESUMES_DIR.glob("*.pdf") if f.is_file()]
        if remaining:
            try:
                profile.resume_path = str(remaining[0].relative_to(BASE_DIR))
            except ValueError:
                profile.resume_path = str(remaining[0])
        else:
            profile.resume_path = None
        settings.save_profile(profile)

    return {"status": "success", "message": f"CV '{filename}' supprimé."}


# --- PLATFORM SESSION / LOGIN CONTROLS ---

CUSTOM_PLATFORMS_FILE = BASE_DIR / "data" / "custom_platforms.json"


def load_custom_platforms() -> List[Dict[str, Any]]:
    if not CUSTOM_PLATFORMS_FILE.exists():
        return []
    try:
        with open(CUSTOM_PLATFORMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_custom_platforms(platforms: List[Dict[str, Any]]):
    CUSTOM_PLATFORMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CUSTOM_PLATFORMS_FILE, "w", encoding="utf-8") as f:
        json.dump(platforms, f, indent=2, ensure_ascii=False)


POPULAR_PLATFORMS_DATA = {
    "wttj": {
        "name": "Welcome to the Jungle",
        "url": "https://www.welcometothejungle.com",
        "login_url": "https://www.welcometothejungle.com/fr/signin",
    },
    "apec": {
        "name": "Apec",
        "url": "https://www.apec.fr",
        "login_url": "https://www.apec.fr/mon-espace/connexion.html",
    },
    "hellowork": {
        "name": "HelloWork",
        "url": "https://www.hellowork.com",
        "login_url": "https://www.hellowork.com/fr-fr/mon-compte/connexion.html",
    },
    "glassdoor": {
        "name": "Glassdoor",
        "url": "https://www.glassdoor.fr",
        "login_url": "https://www.glassdoor.fr/profile/login_input.htm",
    },
    "lesjeunestalents": {
        "name": "Les Jeunes Talents",
        "url": "https://www.lesjeunestalents.fr",
        "login_url": "https://www.lesjeunestalents.fr/login",
    }
}


class CookieInjectRequest(BaseModel):
    li_at: str


class PlatformBrowserOpenRequest(BaseModel):
    target_url: Optional[str] = None


def is_cookie_in_db(cookie_file: Path, cookie_names: List[str]) -> bool:
    if not cookie_file.exists():
        return False
    try:
        import sqlite3
        conn = sqlite3.connect(f"file:{cookie_file}?mode=ro", uri=True)
        cur = conn.cursor()
        placeholders = ",".join("?" for _ in cookie_names)
        cur.execute(f"SELECT 1 FROM cookies WHERE name IN ({placeholders}) LIMIT 1", cookie_names)
        row = cur.fetchone()
        conn.close()
        return bool(row)
    except Exception:
        return False


def check_session_cookie_generic(plat: str) -> bool:
    plat_lower = plat.lower()
    # 1. Check data/platform_sessions.json
    sess_file = BASE_DIR / "data" / "platform_sessions.json"
    if sess_file.exists():
        try:
            with open(sess_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if plat_lower in data and data[plat_lower].get("logged_in") is True:
                    return True
                if f"custom_{plat_lower}" in data and data[f"custom_{plat_lower}"].get("logged_in") is True:
                    return True
        except Exception:
            pass

    # 2. Check cookie database in sessions dir
    for target_name in [plat_lower, f"custom_{plat_lower}"]:
        session_dir = SESSIONS_DIR / target_name
        for p in [
            session_dir / "Default" / "Cookies",
            session_dir / "Default" / "Network" / "Cookies",
            session_dir / "Cookies"
        ]:
            if p.exists() and p.stat().st_size > 0:
                try:
                    import sqlite3
                    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
                    cur = conn.cursor()
                    cur.execute("SELECT count(*) FROM cookies")
                    cnt = cur.fetchone()[0]
                    conn.close()
                    if cnt > 0:
                        return True
                except Exception:
                    return True
    return False


def resolve_platform_url(plat: str) -> Optional[str]:
    plat_lower = plat.lower()
    if plat_lower in POPULAR_PLATFORMS_DATA:
        return POPULAR_PLATFORMS_DATA[plat_lower]["login_url"]
    custom_plats = load_custom_platforms()
    match = next((p for p in custom_plats if p["id"] == plat_lower or f"custom_{p['id']}" == plat_lower), None)
    if match:
        return match.get("login_url") or match.get("url")
    return None


@app.get("/api/platforms/status")
async def get_platforms_status():
    linkedin_cookie_file = SESSIONS_DIR / "linkedin" / "Default" / "Cookies"
    indeed_cookie_file = SESSIONS_DIR / "indeed" / "Default" / "Cookies"
    francetravail_cookie_file = SESSIONS_DIR / "francetravail" / "Default" / "Cookies"

    # Precise cookie check
    linkedin_logged = (
        is_cookie_in_db(linkedin_cookie_file, ["li_at"])
        or is_cookie_in_db(SESSIONS_DIR / "linkedin" / "Default" / "Network" / "Cookies", ["li_at"])
        or is_cookie_in_db(SESSIONS_DIR / "linkedin" / "Cookies", ["li_at"])
    )
    indeed_logged = is_cookie_in_db(indeed_cookie_file, ["SHARED_SESSION", "SURF", "indeed_rcon", "ACCOUNT_USER_IDENTIFIER"]) or check_session_cookie_generic("indeed")
    francetravail_logged = is_cookie_in_db(francetravail_cookie_file, ["SMSESSION", "auth_token", "pe_id", "candidat_token"]) or check_session_cookie_generic("francetravail")

    result = {
        "linkedin": {
            "name": "LinkedIn",
            "logged_in": linkedin_logged,
            "login_url": "https://www.linkedin.com/login",
            "has_cookie_support": True,
            "tip": "Se connecter directement dans le navigateur ou coller votre cookie li_at.",
        },
        "indeed": {
            "name": "Indeed",
            "logged_in": indeed_logged,
            "login_url": "https://secure.indeed.com/account/login",
            "has_cookie_support": False,
            "tip": "Se connecter dans la fenêtre Chromium ouverte (email + code/mot de passe).",
        },
        "francetravail": {
            "name": "France Travail",
            "logged_in": francetravail_logged,
            "login_url": "https://authentification-candidat.pole-emploi.fr/connexion/XUI/#login/",
            "has_cookie_support": False,
            "tip": "Se connecter avec vos identifiants candidat France Travail.",
        }
    }

    # Add all popular catalog platforms
    for pid, pdata in POPULAR_PLATFORMS_DATA.items():
        result[pid] = {
            "name": pdata["name"],
            "logged_in": check_session_cookie_generic(pid),
            "login_url": pdata["login_url"],
            "has_cookie_support": False,
            "isBuiltinCatalog": True,
            "tip": f"Connectez-vous à {pdata['name']} via Chromium puis cliquez sur Valider ma connexion.",
        }

    # Add custom platforms
    custom_plats = load_custom_platforms()
    for cp in custom_plats:
        cpid = cp["id"]
        result[cpid] = {
            "name": cp["name"],
            "logged_in": check_session_cookie_generic(cpid),
            "login_url": cp.get("login_url") or cp.get("url"),
            "has_cookie_support": False,
            "is_custom": True,
            "tip": f"Connectez-vous à {cp['name']} puis cliquez sur Valider ma connexion.",
        }

    return result


@app.post("/api/platforms/{platform}/login-window")
async def open_platform_login_window(platform: str, req: Optional[PlatformBrowserOpenRequest] = None):
    try:
        plat = platform.lower()
        target_url = (req.target_url if req else None) or resolve_platform_url(plat)
        res = await launch_login_browser(plat, target_url=target_url)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/platforms/custom/{platform_id}/open-browser")
async def open_custom_platform_browser(platform_id: str, req: Optional[PlatformBrowserOpenRequest] = None):
    try:
        plat = platform_id.lower()
        target_url = (req.target_url if req else None) or resolve_platform_url(plat)
        res = await launch_login_browser(plat, target_url=target_url)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/platforms/{platform}/verify-session")
async def verify_platform_session(platform: str):
    try:
        res = await close_and_verify_session(platform.lower())
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/platforms/custom/{platform_id}/verify-session")
async def verify_custom_platform_session(platform_id: str):
    try:
        res = await close_and_verify_session(platform_id.lower())
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/platforms/{platform}/close-browser")
@app.post("/api/platforms/custom/{platform}/close-browser")
async def close_platform_browser(platform: str):
    from core.browser.session_setup import ACTIVE_SESSIONS
    plat = platform.lower()
    bm = ACTIVE_SESSIONS.pop(plat, None)
    if bm:
        try:
            await bm.close()
        except Exception:
            pass
    return {"status": "closed", "platform": plat, "message": f"Navigateur {plat.upper()} fermé."}


@app.post("/api/platforms/{platform}/disconnect")
@app.post("/api/platforms/custom/{platform}/disconnect")
async def disconnect_platform(platform: str):
    plat = platform.lower()
    from core.browser.session_setup import ACTIVE_SESSIONS
    bm = ACTIVE_SESSIONS.pop(plat, None)
    if bm:
        try:
            await bm.close()
        except Exception:
            pass

    sess_file = BASE_DIR / "data" / "platform_sessions.json"
    if sess_file.exists():
        try:
            with open(sess_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if plat in data:
                data[plat]["logged_in"] = False
            if f"custom_{plat}" in data:
                data[f"custom_{plat}"]["logged_in"] = False
            with open(sess_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    for target in [plat, f"custom_{plat}"]:
        c_file = SESSIONS_DIR / target / "Default" / "Cookies"
        if c_file.exists():
            try:
                c_file.unlink()
            except Exception:
                pass

    return {"status": "disconnected", "platform": plat, "message": f"Plateforme {plat.upper()} déconnectée."}


@app.post("/api/platforms/linkedin/set-cookie")
async def set_linkedin_cookie(req: CookieInjectRequest):
    try:
        res = await inject_linkedin_cookie(req.li_at)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/platforms/kill-all-browsers")
async def kill_all_browsers():
    from core.browser.session_setup import ACTIVE_SESSIONS
    for p, bm in list(ACTIVE_SESSIONS.items()):
        try:
            await bm.close()
        except Exception:
            pass
    ACTIVE_SESSIONS.clear()
    import subprocess
    subprocess.run(["pkill", "-f", "Google Chrome for Testing"], check=False)
    return {"status": "killed", "message": "Tous les navigateurs ont été fermés."}


# --- BANNER IMAGE MANAGEMENT ---

BANNER_DIR = STATIC_DIR / "banner"
BANNER_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_BANNER_PATH = BANNER_DIR / "default_banner.jpg"


@app.post("/api/banner/upload")
async def upload_custom_banner(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Fichier invalide")
    content = await file.read()
    ext = Path(file.filename).suffix.lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".jfif", ".avif", ".heic"]:
        ext = ".png"

    # Remove any existing custom banner
    for existing in BANNER_DIR.glob("custom_banner.*"):
        try:
            existing.unlink()
        except Exception:
            pass

    target = BANNER_DIR / f"custom_banner{ext}"
    with open(target, "wb") as f:
        f.write(content)

    timestamp = int(time.time())
    return {
        "status": "success",
        "message": "Bannière personnalisée enregistrée avec succès !",
        "url": f"/static/banner/custom_banner{ext}?t={timestamp}",
    }


@app.get("/api/banner")
async def get_active_banner():
    for existing in BANNER_DIR.glob("custom_banner.*"):
        if existing.is_file():
            return {
                "has_custom": True,
                "url": f"/static/banner/{existing.name}?t={int(existing.stat().st_mtime)}",
            }
    return {
        "has_custom": False,
        "url": "/static/banner/default_banner.jpg",
    }


@app.post("/api/banner/reset")
async def reset_banner_to_default():
    for existing in BANNER_DIR.glob("custom_banner.*"):
        try:
            existing.unlink()
        except Exception:
            pass
    return {
        "status": "success",
        "message": "Bannière par défaut rétablie",
        "url": "/static/banner/default_banner.jpg",
    }


# --- CUSTOM JOB PLATFORMS MANAGEMENT ---

class CustomPlatformCreate(BaseModel):
    name: str
    category: Optional[str] = "Généraliste"
    url: str
    login_url: Optional[str] = ""
    search_url: Optional[str] = ""
    notes: Optional[str] = ""
    icon: Optional[str] = "fa-globe"


@app.get("/api/platforms/custom")
async def get_custom_platforms():
    return load_custom_platforms()


@app.post("/api/platforms/custom")
async def add_custom_platform(item: CustomPlatformCreate):
    platforms = load_custom_platforms()
    clean_name = item.name.strip()
    if not clean_name:
        raise HTTPException(status_code=400, detail="Le nom de la plateforme est requis")

    plat_id = re.sub(r"[^a-zA-Z0-9_]", "", clean_name.lower().replace(" ", "_"))
    if not plat_id:
        plat_id = f"custom_{int(time.time())}"

    # Verify duplicate
    if any(p["id"] == plat_id for p in platforms):
        raise HTTPException(status_code=400, detail="Cette plateforme est déjà enregistrée")

    new_platform = {
        "id": plat_id,
        "name": clean_name,
        "category": item.category or "Généraliste",
        "url": item.url.strip(),
        "login_url": (item.login_url or item.url).strip(),
        "search_url": (item.search_url or "").strip(),
        "notes": (item.notes or "").strip(),
        "icon": item.icon or "fa-globe",
        "created_at": datetime.utcnow().isoformat(),
        "is_connected": False,
    }

    platforms.append(new_platform)
    save_custom_platforms(platforms)
    return {
        "status": "success",
        "message": f"Plateforme '{clean_name}' ajoutée avec succès !",
        "platform": new_platform,
    }


@app.delete("/api/platforms/custom/{platform_id}")
async def delete_custom_platform(platform_id: str):
    platforms = load_custom_platforms()
    filtered = [p for p in platforms if p["id"] != platform_id]
    if len(filtered) == len(platforms):
        raise HTTPException(status_code=404, detail="Plateforme introuvable")
    save_custom_platforms(filtered)
    return {"status": "success", "message": "Plateforme supprimée"}



# --- WATCHER CONTROLS ---

class WatcherStartRequest(BaseModel):
    interval_minutes: int = 30


@app.post("/api/watcher/start")
async def start_watcher(req: WatcherStartRequest):
    await watcher_service.start(interval_minutes=req.interval_minutes)
    return {"status": "success", "message": f"Veille automatique activée (intervalle: {req.interval_minutes}m)"}


@app.post("/api/watcher/stop")
async def stop_watcher():
    await watcher_service.stop()
    return {"status": "success", "message": "Veille automatique arrêtée"}


@app.post("/api/jobs/sync-realtime")
async def sync_realtime_jobs():
    """Fast multi-source real-time job synchronization (France Travail, LinkedIn, Tech Remote)."""
    res = await realtime_scanner.scan_all()
    return {
        "status": "success",
        "message": f"{res['new_count']} nouvelles offres en direct synchronisées !",
        "new_count": res["new_count"],
        "timestamp": res["timestamp"],
    }


@app.post("/api/watcher/run-now")
async def run_watcher_now(background_tasks: BackgroundTasks):
    # Run immediate real-time synchronization first, and background verification
    res = await realtime_scanner.scan_all()
    background_tasks.add_task(watcher_service.run_once)
    return {
        "status": "success",
        "message": f"Scan terminé : {res['new_count']} offres en temps réel synchronisées avec succès !",
        "new_count": res["new_count"],
    }


@app.post("/api/jobs/clean-inactive")
async def clean_inactive_jobs_endpoint():
    res = await watcher_service.clean_inactive_jobs()
    return {
        "status": "success",
        "message": f"{res['deleted_count']} offre(s) expirée(s) ou fermée(s) supprimée(s) avec succès !",
        "deleted_count": res["deleted_count"],
        "deleted_jobs": res["deleted_jobs"],
    }



# --- 1-CLICK APPLY ON SINGLE JOB ---

async def execute_single_job_apply(job_id: int):
    record_data = db.get_application_by_id(job_id)
    if not record_data:
        return

    # Enforce background headless execution (NO visible browser tabs popping up!)
    settings.headless_browser = True

    plat_name = record_data["platform"]
    job_post = JobPost(
        platform=plat_name,
        job_id=record_data["job_id"],
        title=record_data["job_title"],
        company=record_data["company"],
        location=record_data.get("location") or "France",
        url=record_data["job_url"],
        is_easy_apply=True,
    )

    platform_instance = None
    if plat_name == "linkedin":
        platform_instance = LinkedInPlatform()
    elif plat_name == "indeed":
        platform_instance = IndeedPlatform()
    elif plat_name == "francetravail":
        platform_instance = FranceTravailPlatform()

    if platform_instance:
        try:
            # Enforce daily cap + minimum interval before applying.
            applied_today = db.get_applications_count_today(plat_name)
            await rate_limiter.wait_before_apply(plat_name, applied_today)
            res_record = await platform_instance.apply(job_post)
            db.save_or_update(res_record)
        except PlatformBlockedError:
            db.update_status(job_id, "failed", error_message="Mur anti-bot détecté — run interrompu")
            raise
        except RateLimitExceeded as e:
            db.update_status(job_id, "skipped", error_message=str(e))
        except Exception as e:
            db.update_status(job_id, "failed", error_message=str(e))
        finally:
            await platform_instance.close()



@app.post("/api/jobs/{job_id}/apply")
async def apply_single_job(job_id: int, background_tasks: BackgroundTasks):
    record = db.get_application_by_id(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Offre introuvable")

    db.update_status(job_id, "applying")
    background_tasks.add_task(execute_single_job_apply, job_id)
    return {"status": "started", "message": f"Candidature 1-clic initiée pour {record['job_title']}"}


@app.post("/api/jobs/{job_id}/prepare-documents")
async def prepare_job_documents(job_id: int):
    """Generate a tailored ATS CV + cover letter for one stored job offer."""
    record = db.get_application_by_id(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Offre introuvable")

    profile = settings.load_profile()
    documents = prepare_application_documents(
        profile,
        job_title=record["job_title"],
        company=record["company"],
        job_description=record.get("match_reason") or "",
        location=record.get("location") or "",
    )
    return {
        "status": "success",
        "job_id": job_id,
        "job_title": record["job_title"],
        "company": record["company"],
        "documents": documents,
    }


@app.get("/api/jobs/{job_id}/status")
async def get_single_job_status(job_id: int):
    record = db.get_application_by_id(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    return {
        "id": record["id"],
        "status": record["status"],
        "applied_at": record.get("applied_at"),
        "error_message": record.get("error_message"),
        "screenshot_path": record.get("screenshot_path"),
        "company": record.get("company"),
        "job_title": record.get("job_title"),
    }



class BatchApplyRequest(BaseModel):
    job_ids: List[int]


class ApplyAllRequest(BaseModel):
    platform: Optional[str] = None
    min_score: Optional[int] = None
    limit: Optional[int] = None
    job_ids: Optional[List[int]] = None
    mode: Optional[str] = "parallel"  # "parallel" (simultaneous per platform) or "serial"
    platforms: Optional[List[str]] = None


class StopBatchRequest(BaseModel):
    platform: Optional[str] = None


async def execute_platform_batch_task(platform: str, job_ids: List[int]):
    global PLATFORM_WORKERS
    if platform not in PLATFORM_WORKERS:
        PLATFORM_WORKERS[platform] = get_initial_platform_state(platform)

    worker = PLATFORM_WORKERS[platform]
    worker["is_running"] = True
    worker["stop_requested"] = False
    worker["total"] = len(job_ids)
    worker["current_index"] = 0
    worker["percent"] = 0
    worker["success_count"] = 0
    worker["skipped_count"] = 0
    worker["failed_count"] = 0
    worker["last_reason"] = ""
    worker["started_at"] = datetime.utcnow().isoformat()
    worker["current_task"] = f"Initialisation worker {platform.capitalize()} ({len(job_ids)} offres)..."

    logger.info(f"[{platform.upper()} Worker] Démarrage du worker simultané pour {len(job_ids)} offres...")

    platform_instance = None
    try:
        if platform == "linkedin":
            platform_instance = LinkedInPlatform()
            is_logged = await platform_instance.is_logged_in()
            if not is_logged:
                logger.warning("[LINKEDIN Worker] Session LinkedIn non connectée (Authwall). Annulation pour protéger les offres.")
                worker["is_running"] = False
                worker["current_task"] = "Session LinkedIn requise : connectez-vous ou collez votre cookie li_at dans Menu > Sessions."
                worker["last_reason"] = "Session LinkedIn requise (Authwall / non connecté)"
                for jid in job_ids:
                    rec = db.get_application_by_id(jid)
                    if rec and rec.get("status") == "applying":
                        db.update_status(jid, "found")
                return
        elif platform == "indeed":
            platform_instance = IndeedPlatform()
        elif platform == "francetravail":
            platform_instance = FranceTravailPlatform()

        for idx, jid in enumerate(job_ids, 1):
            if worker.get("stop_requested"):
                logger.info(f"[{platform.upper()} Worker] Interruption demandée par l'utilisateur.")
                worker["current_task"] = "Interrompu par l'utilisateur."
                break

            record_data = db.get_application_by_id(jid)
            if not record_data:
                continue

            title = record_data.get("job_title", "Offre")
            company = record_data.get("company", "Entreprise")

            worker["current_index"] = idx
            worker["percent"] = int((idx / max(1, len(job_ids))) * 100)
            worker["current_job_id"] = jid
            worker["current_job_title"] = title
            worker["current_company"] = company
            worker["current_task"] = f"Postulation {idx}/{len(job_ids)} : {title} chez {company}"

            logger.info(f"[{platform.upper()} Worker] Traitement {idx}/{len(job_ids)} (ID: {jid}) : {title} ({company})...")

            try:
                job_post = JobPost(
                    platform=platform,
                    job_id=record_data["job_id"],
                    title=title,
                    company=company,
                    location=record_data.get("location") or "France",
                    url=record_data["job_url"],
                    is_easy_apply=True,
                )

                if platform_instance:
                    res_record = await platform_instance.apply(job_post)
                    db.save_or_update(res_record)
                else:
                    await execute_single_job_apply(jid)

                updated = db.get_application_by_id(jid)
                status = updated.get("status") if updated else "failed"
                err_msg = (updated.get("error_message") or "").strip()
                worker["last_reason"] = err_msg

                if status == "applied":
                    worker["success_count"] += 1
                    worker["current_task"] = f"Succès : {title} ({company})"
                elif status == "skipped":
                    worker["skipped_count"] += 1
                    if "Quota journalier" in err_msg:
                        logger.info(f"[{platform.upper()} Worker] Daily quota reached for {platform}. Stopping batch.")
                        worker["current_task"] = f"Arrêt : {err_msg}"
                        break
                    elif "Session" in err_msg or "Authwall" in err_msg:
                        worker["current_task"] = f"Ignorée : Connexion {platform.capitalize()} requise"
                    elif "externe" in err_msg.lower():
                        worker["current_task"] = f"Ignorée : Redirection externe ({company})"
                    else:
                        worker["current_task"] = f"Ignorée : {err_msg or 'Non Easy-Apply'}"
                else:
                    worker["failed_count"] += 1
                    worker["current_task"] = f"Échec : {err_msg or 'Erreur'}"
            except PlatformBlockedError as e:
                logger.error(f"[{platform.upper()} Worker] Platform block on job ID {jid}: {e}. Halting batch.")
                db.update_status(jid, "failed", error_message=str(e))
                worker["failed_count"] += 1
                worker["last_reason"] = str(e)
                worker["current_task"] = f"Arrêt : {e}"
                worker["stop_requested"] = True
                break
            except Exception as e:
                logger.error(f"[{platform.upper()} Worker] Erreur sur job ID {jid}: {e}")
                db.update_status(jid, "failed", error_message=str(e))
                worker["failed_count"] += 1
                worker["last_reason"] = str(e)
                worker["current_task"] = f"Erreur : {str(e)[:50]}"

            # Human pacing between consecutive applications is enforced centrally
            # by core.rate_limiter.wait_before_apply(); no manual sleep here to
            # avoid double-counting delays.

        worker["percent"] = 100
        success = worker["success_count"]
        skipped = worker["skipped_count"]
        worker["current_task"] = f"Terminé ! {success} envoyée(s), {skipped} ignorée(s)."
    except Exception as exc:
        logger.error(f"[{platform.upper()} Worker] Erreur inattendue : {exc}")
        worker["current_task"] = f"Erreur : {exc}"
    finally:
        if platform_instance:
            try:
                await platform_instance.close()
            except Exception:
                pass
        worker["is_running"] = False
        worker["finished_at"] = datetime.utcnow().isoformat()
        logger.info(f"[{platform.upper()} Worker] Session de candidatures terminée.")


async def execute_multi_platform_batch(platform_jobs_map: Dict[str, List[int]]):
    """Executes platform workers simultaneously in parallel using asyncio.gather."""
    tasks = []
    for plat, ids in platform_jobs_map.items():
        if ids:
            tasks.append(execute_platform_batch_task(plat, ids))
    if tasks:
        logger.info(f"[Multi-Batch] Lancement simultané de {len(tasks)} workers de plateformes...")
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("[Multi-Batch] Tous les workers de plateformes ont terminé.")


async def execute_batch_apply_task(job_ids: List[int]):
    """Wrapper that partitions jobs by platform and executes them concurrently."""
    jobs_by_platform: Dict[str, List[int]] = {}
    for jid in job_ids:
        rec = db.get_application_by_id(jid)
        if rec:
            plat = rec.get("platform") or "francetravail"
            if plat not in jobs_by_platform:
                jobs_by_platform[plat] = []
            jobs_by_platform[plat].append(jid)
    await execute_multi_platform_batch(jobs_by_platform)


def get_aggregate_batch_status() -> Dict[str, Any]:
    global PLATFORM_WORKERS
    active_workers = [w for w in PLATFORM_WORKERS.values() if w.get("is_running")]
    is_running = len(active_workers) > 0

    total = sum(w.get("total", 0) for w in PLATFORM_WORKERS.values())
    current = sum(w.get("current_index", 0) for w in PLATFORM_WORKERS.values())
    success = sum(w.get("success_count", 0) for w in PLATFORM_WORKERS.values())
    skipped = sum(w.get("skipped_count", 0) for w in PLATFORM_WORKERS.values())
    failed = sum(w.get("failed_count", 0) for w in PLATFORM_WORKERS.values())
    percent = int((current / max(1, total)) * 100) if total > 0 else 0

    active_platforms = [w["platform"] for w in active_workers]

    if is_running:
        if len(active_platforms) > 1:
            plat_names = ", ".join(p.capitalize() for p in active_platforms)
            current_task = f"⚡ {len(active_platforms)} plateformes en simultané ({plat_names}) • {current}/{total} offres traitées"
        elif len(active_platforms) == 1:
            current_task = active_workers[0].get("current_task") or "Candidature en cours..."
        else:
            current_task = "Candidatures en cours..."
    else:
        if total > 0 and current >= total:
            current_task = f"Session terminée ! {success} envoyée(s), {skipped} ignorée(s)."
        else:
            current_task = "En attente"

    latest_job = next((w for w in active_workers if w.get("current_job_id")), None)
    current_job_id = latest_job["current_job_id"] if latest_job else None
    current_job_title = latest_job["current_job_title"] if latest_job else ""
    current_company = latest_job["current_company"] if latest_job else ""
    current_platform = latest_job["platform"] if latest_job else ""
    last_reason = latest_job["last_reason"] if latest_job else ""

    return {
        "is_running": is_running,
        "current_index": current,
        "total": total,
        "percent": percent,
        "success_count": success,
        "skipped_count": skipped,
        "failed_count": failed,
        "current_job_id": current_job_id,
        "current_job_title": current_job_title,
        "current_company": current_company,
        "current_platform": current_platform,
        "last_reason": last_reason,
        "current_task": current_task,
        "active_platforms": active_platforms,
        "platforms": {p: dict(w) for p, w in PLATFORM_WORKERS.items()},
    }


@app.get("/api/jobs/batch-status")
async def get_batch_status():
    return get_aggregate_batch_status()


@app.get("/api/jobs/unapplied-stats")
async def get_unapplied_stats(platform: Optional[str] = None):
    total_unapplied = db.get_unapplied_count(platform=platform)
    high_unapplied = db.get_unapplied_count(platform=platform, min_score=80)
    total_applied = db.get_applied_count(platform=platform)

    # Global breakdown for quick platform switching in UI
    platforms_breakdown = {
        "all": {
            "unapplied": db.get_unapplied_count(platform=None),
            "high": db.get_unapplied_count(platform=None, min_score=80),
            "applied": db.get_applied_count(platform=None),
        },
        "francetravail": {
            "unapplied": db.get_unapplied_count(platform="francetravail"),
            "high": db.get_unapplied_count(platform="francetravail", min_score=80),
            "applied": db.get_applied_count(platform="francetravail"),
        },
        "linkedin": {
            "unapplied": db.get_unapplied_count(platform="linkedin"),
            "high": db.get_unapplied_count(platform="linkedin", min_score=80),
            "applied": db.get_applied_count(platform="linkedin"),
        },
        "indeed": {
            "unapplied": db.get_unapplied_count(platform="indeed"),
            "high": db.get_unapplied_count(platform="indeed", min_score=80),
            "applied": db.get_applied_count(platform="indeed"),
        },
    }
    return {
        "status": "success",
        "platform": platform or "all",
        "total_unapplied": total_unapplied,
        "high_match_unapplied": high_unapplied,
        "total_applied": total_applied,
        "breakdown": platforms_breakdown,
    }


@app.post("/api/jobs/apply-all")
async def apply_all_jobs_endpoint(req: ApplyAllRequest, background_tasks: BackgroundTasks):
    global PLATFORM_WORKERS

    target_plat = req.platform.strip().lower() if req.platform else ""
    is_single_platform = bool(target_plat and target_plat != "all")

    if is_single_platform:
        # User requested a specific platform
        worker = PLATFORM_WORKERS.get(target_plat)
        if worker and worker.get("is_running"):
            return JSONResponse(
                status_code=409,
                content={
                    "status": "already_running",
                    "message": f"Le worker pour {target_plat.capitalize()} est déjà en cours d'exécution."
                }
            )

        if req.job_ids and len(req.job_ids) > 0:
            target_ids = req.job_ids
        else:
            unapplied = db.get_unapplied_jobs(
                platform=target_plat,
                min_score=req.min_score,
                limit=req.limit,
            )
            if not unapplied:
                unapplied = db.get_unapplied_jobs(
                    platform=target_plat,
                    min_score=None,
                    limit=req.limit,
                )
            target_ids = [j["id"] for j in unapplied]

        if not target_ids:
            raise HTTPException(status_code=400, detail=f"Aucune offre non postulée trouvée pour {target_plat.capitalize()}")

        for jid in target_ids:
            db.update_status(jid, "applying")

        background_tasks.add_task(execute_platform_batch_task, target_plat, target_ids)
        return {
            "status": "started",
            "count": len(target_ids),
            "platform": target_plat,
            "mode": "single_platform",
            "message": f"Postulation 1 Clic lancée pour {len(target_ids)} offre(s) sur {target_plat.capitalize()} !",
        }

    # All platforms requested (Simultaneous parallel execution by default)
    if req.job_ids and len(req.job_ids) > 0:
        all_candidates = [db.get_application_by_id(jid) for jid in req.job_ids]
        all_candidates = [c for c in all_candidates if c]
    else:
        # Smart targeting: by default only apply to offers at/above the profile's
        # minimum match score, ordered highest-match first
        criteria = settings.load_search_criteria()
        floor = req.min_score if req.min_score is not None else criteria.min_match_score
        all_candidates = db.get_unapplied_jobs(
            platform=None,
            min_score=floor,
            limit=req.limit,
        )
        if not all_candidates:
            # Fallback to all unapplied jobs without strict score floor
            all_candidates = db.get_unapplied_jobs(
                platform=None,
                min_score=None,
                limit=req.limit,
            )

    if not all_candidates:
        raise HTTPException(status_code=400, detail="Aucune offre non postulée trouvée pour ces critères")

    # Group candidate jobs by platform
    jobs_by_platform: Dict[str, List[int]] = {}
    for j in all_candidates:
        p = (j.get("platform") or "francetravail").strip().lower()
        if req.platforms and p not in req.platforms:
            continue
        if p not in jobs_by_platform:
            jobs_by_platform[p] = []
        jobs_by_platform[p].append(j["id"])

    to_launch: Dict[str, List[int]] = {}
    already_running_platforms = []
    total_jobs_launched = 0

    for plat, ids in jobs_by_platform.items():
        w = PLATFORM_WORKERS.get(plat)
        if w and w.get("is_running"):
            already_running_platforms.append(plat)
            continue
        to_launch[plat] = ids
        total_jobs_launched += len(ids)
        for jid in ids:
            db.update_status(jid, "applying")

    if not to_launch:
        if already_running_platforms:
            return JSONResponse(
                status_code=409,
                content={
                    "status": "already_running",
                    "message": f"Toutes les plateformes sélectionnées ont déjà un worker actif ({', '.join(already_running_platforms)})."
                }
            )
        raise HTTPException(status_code=400, detail="Aucune offre à lancer pour les plateformes sélectionnées")

    if req.mode == "serial":
        # Classical serial fallback if requested
        flattened_ids = [jid for ids in to_launch.values() for jid in ids]
        background_tasks.add_task(execute_batch_apply_task, flattened_ids)
        msg = f"Candidatures séquentielles lancées pour {len(flattened_ids)} offre(s)."
    else:
        # Default: simultaneous parallel workers across platforms!
        background_tasks.add_task(execute_multi_platform_batch, to_launch)
        plat_names = ", ".join(p.capitalize() for p in to_launch.keys())
        msg = f"⚡ Candidatures simultanées lancées pour {total_jobs_launched} offre(s) en parallèle sur {len(to_launch)} plateforme(s) ({plat_names}) !"

    return {
        "status": "started",
        "count": total_jobs_launched,
        "platforms": list(to_launch.keys()),
        "mode": req.mode or "parallel",
        "already_running": already_running_platforms,
        "message": msg,
    }


@app.post("/api/jobs/apply-batch")
async def apply_batch_jobs(req: BatchApplyRequest, background_tasks: BackgroundTasks):
    return await apply_all_jobs_endpoint(ApplyAllRequest(job_ids=req.job_ids), background_tasks)


@app.post("/api/jobs/stop-batch")
async def stop_batch_endpoint(req: Optional[StopBatchRequest] = None):
    global PLATFORM_WORKERS
    target = (req.platform.strip().lower() if req and req.platform else None)
    if target and target in PLATFORM_WORKERS:
        PLATFORM_WORKERS[target]["stop_requested"] = True
        PLATFORM_WORKERS[target]["current_task"] = f"Arrêt demandé pour {target.capitalize()}..."
        return {"status": "success", "message": f"Arrêt demandé pour le worker {target.capitalize()}"}
    else:
        stopped_any = False
        for p, w in PLATFORM_WORKERS.items():
            if w.get("is_running"):
                w["stop_requested"] = True
                w["current_task"] = "Arrêt demandé..."
                stopped_any = True
        return {
            "status": "success",
            "message": "Arrêt demandé pour tous les workers de plateformes" if stopped_any else "Aucun worker actif"
        }


class ResetSkippedRequest(BaseModel):
    platform: Optional[str] = None


@app.post("/api/jobs/reset-skipped")
async def reset_skipped_jobs_endpoint(req: Optional[ResetSkippedRequest] = None):
    plat = req.platform.strip().lower() if req and req.platform else None
    with db._get_connection() as conn:
        cursor = conn.cursor()
        if plat and plat != "all":
            cursor.execute(
                "UPDATE job_applications SET status = 'found', error_message = NULL WHERE platform = ? AND status = 'skipped'",
                (plat,)
            )
        else:
            cursor.execute(
                "UPDATE job_applications SET status = 'found', error_message = NULL WHERE status = 'skipped'"
            )
        count = cursor.rowcount
        conn.commit()
    return {
        "status": "success",
        "reset_count": count,
        "message": f"{count} offre(s) ignorée(s) réinitialisée(s) avec succès !"
    }



@app.post("/api/jobs/{job_id}/ignore")
async def ignore_job(job_id: int):
    record = db.get_application_by_id(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Offre introuvable")

    db.update_status(job_id, "skipped")
    return {"status": "success", "message": "Offre ignorée"}


# --- TEST NOTIFICATION ---

@app.post("/api/notifications/test")
async def test_notification():
    await notification_dispatcher.notify_new_job_opportunity(
        title="[Test] Développeur Full Stack Python / React",
        company="Startup Innovante",
        location="Paris (Hybride)",
        score=92,
        rationale="Excellente adéquation : compétences Python, React et Docker validées.",
        job_url="https://example.com/job/test",
        platform="linkedin",
    )
    return {"status": "success", "message": "Notification de test envoyée !"}


# --- BATCH APPLY RUNNER ---

class RunRequest(BaseModel):
    platform: str = "all"
    headless: bool = True
    limit: Optional[int] = None


async def execute_run_task(platform: str, headless: bool, limit: Optional[int]):
    RUNNER_STATE["is_running"] = True
    RUNNER_STATE["logs"] = []
    settings.headless_browser = headless

    def add_log(msg: str):
        RUNNER_STATE["logs"].append(msg)
        RUNNER_STATE["current_task"] = msg

    add_log(f"Démarrage de l'agent sur {platform.upper()} (headless={headless})...")

    try:
        platforms = []
        if platform in ["linkedin", "all"]:
            platforms.append(LinkedInPlatform())
        if platform in ["indeed", "all"]:
            platforms.append(IndeedPlatform())
        if platform in ["francetravail", "all"]:
            platforms.append(FranceTravailPlatform())

        for p in platforms:
            add_log(f"Recherche et traitement sur {p.platform_name.upper()}...")
            results = await p.run(max_applications=limit)
            add_log(f"Fin du traitement {p.platform_name.upper()} : {len(results)} offres traitées.")
            await p.close()

        add_log("Session de candidature terminée avec succès.")
    except Exception as e:
        add_log(f"Erreur lors de l'exécution : {str(e)}")
    finally:
        RUNNER_STATE["is_running"] = False
        RUNNER_STATE["current_task"] = "Terminé"


@app.post("/api/run")
async def trigger_run(req: RunRequest, background_tasks: BackgroundTasks):
    if RUNNER_STATE["is_running"]:
        raise HTTPException(status_code=400, detail="Une exécution est déjà en cours")

    background_tasks.add_task(execute_run_task, req.platform, req.headless, req.limit)
    return {"status": "started", "message": f"Run lancé pour {req.platform}"}


@app.get("/api/logs")
async def get_logs():
    return {
        "is_running": RUNNER_STATE["is_running"],
        "current_task": RUNNER_STATE["current_task"],
        "logs": RUNNER_STATE["logs"][-50:],
    }
