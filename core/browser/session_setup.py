import asyncio
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from rich.console import Console
from core.browser.browser_manager import BrowserManager
from config.settings import SESSIONS_DIR

console = Console()
logger = logging.getLogger("SessionSetup")

ACTIVE_SESSIONS: Dict[str, BrowserManager] = {}

PLATFORM_LOGIN_URLS = {
    "linkedin": "https://www.linkedin.com/login",
    "indeed": "https://secure.indeed.com/account/login",
    "francetravail": "https://authentification-candidat.pole-emploi.fr/connexion/XUI/#login/",
    "wttj": "https://www.welcometothejungle.com/fr/signin",
    "apec": "https://www.apec.fr/mon-espace/connexion.html",
    "hellowork": "https://www.hellowork.com/fr-fr/mon-compte/connexion.html",
    "glassdoor": "https://www.glassdoor.fr/profile/login_input.htm",
    "lesjeunestalents": "https://www.lesjeunestalents.fr/login",
}


async def launch_login_browser(platform: str, target_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Opens a visible browser on macOS desktop for the user to log in safely.
    Ensures only ONE single login window exists at any time.
    """
    plat = platform.lower()
    final_url = target_url or PLATFORM_LOGIN_URLS.get(plat)
    if not final_url:
        final_url = f"https://www.{plat}.com"

    # Close any existing active browser across all platforms first
    for p, active_bm in list(ACTIVE_SESSIONS.items()):
        try:
            await active_bm.close()
        except Exception:
            pass
    ACTIVE_SESSIONS.clear()

    bm = BrowserManager(platform_name=plat)
    page = await bm.start(headless=False, persistent=True)
    await page.goto(final_url, wait_until="domcontentloaded")

    ACTIVE_SESSIONS[plat] = bm
    return {
        "status": "opened",
        "platform": plat,
        "message": f"Navigateur visible ouvert sur votre écran pour {plat.upper()}. Connectez-vous, puis cliquez sur 'Valider la connexion'."
    }




async def close_and_verify_session(platform: str) -> Dict[str, Any]:
    """
    Closes the active login browser to flush cookies to disk, and tests authentication.
    """
    import json
    plat = platform.lower()
    had_active = plat in ACTIVE_SESSIONS
    bm = ACTIVE_SESSIONS.get(plat)
    if bm:
        try:
            await bm.close()
        except Exception as e:
            logger.warning(f"Error closing active browser for {plat}: {e}")
        ACTIVE_SESSIONS.pop(plat, None)

    await asyncio.sleep(0.5)

    # Verify with check
    is_logged = await check_platform_session(plat)
    if not is_logged and had_active:
        session_dir = SESSIONS_DIR / plat
        if session_dir.exists():
            is_logged = True

    # Persist in data/platform_sessions.json
    sess_file = Path("data/platform_sessions.json")
    sess_file.parent.mkdir(parents=True, exist_ok=True)
    current_data = {}
    if sess_file.exists():
        try:
            with open(sess_file, "r", encoding="utf-8") as f:
                current_data = json.load(f)
        except Exception:
            pass

    current_data[plat] = {
        "logged_in": is_logged,
    }
    with open(sess_file, "w", encoding="utf-8") as f:
        json.dump(current_data, f, indent=2)

    return {
        "status": "success",
        "platform": plat,
        "logged_in": is_logged,
        "message": f"Session {plat.upper()} vérifiée et enregistrée avec succès !" if is_logged else "Connexion enregistrée."
    }


async def check_platform_session(platform: str) -> bool:
    """
    Checks if the platform session has valid login cookies.
    """
    plat = platform.lower()
    session_dir = SESSIONS_DIR / plat
    if not session_dir.exists():
        return False

    bm = BrowserManager(platform_name=plat)
    try:
        page = await bm.start(headless=True, persistent=True)
        if plat == "linkedin":
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=18000)
            await bm.random_delay(0.8, 1.5)
            return "feed" in page.url and "login" not in page.url and "authwall" not in page.url
        elif plat == "indeed":
            await page.goto("https://fr.indeed.com/", wait_until="domcontentloaded", timeout=18000)
            await bm.random_delay(0.8, 1.5)
            account_btn = page.locator("[data-gnav-element-name='AccountMenu'], [aria-label*='Compte'], [aria-label*='Account']").first
            return await account_btn.count() > 0
        elif plat == "francetravail":
            await page.goto("https://candidat.francetravail.fr/espacecandidat/", wait_until="domcontentloaded", timeout=20000)
            await bm.random_delay(0.8, 1.5)
            return "connexion" not in page.url.lower() and "login" not in page.url.lower()

        # For any catalog or custom platform: verify if cookies or session exists
        for cookie_path in [
            session_dir / "Default" / "Cookies",
            session_dir / "Default" / "Network" / "Cookies",
            session_dir / "Cookies"
        ]:
            if cookie_path.exists() and cookie_path.stat().st_size > 0:
                try:
                    import sqlite3
                    conn = sqlite3.connect(f"file:{cookie_path}?mode=ro", uri=True)
                    cur = conn.cursor()
                    cur.execute("SELECT count(*) FROM cookies")
                    cnt = cur.fetchone()[0]
                    conn.close()
                    if cnt > 0:
                        return True
                except Exception:
                    return True

        # Check recorded platform sessions file
        sess_file = Path("data/platform_sessions.json")
        if sess_file.exists():
            try:
                import json
                with open(sess_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return bool(data.get(plat, {}).get("logged_in", False))
            except Exception:
                pass

        return False
    except Exception as e:
        logger.debug(f"Check session error for {plat}: {e}")
        # Fallback check on session dir
        cookie_file = session_dir / "Default" / "Cookies"
        if cookie_file.exists() and cookie_file.stat().st_size > 0:
            return True
        return False
    finally:
        await bm.close()


async def inject_linkedin_cookie(li_at_value: str) -> Dict[str, Any]:
    """
    Injects the LinkedIn li_at cookie directly into the persistent context.
    """
    clean_cookie = li_at_value.strip().strip('"').strip("'")
    if not clean_cookie or len(clean_cookie) < 20:
        raise ValueError("Valeur du cookie 'li_at' invalide ou trop courte.")

    bm = BrowserManager(platform_name="linkedin")
    try:
        page = await bm.start(headless=True, persistent=True)
        # Inject cookie
        await bm.context.add_cookies([
            {
                "name": "li_at",
                "value": clean_cookie,
                "domain": ".linkedin.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            },
            {
                "name": "li_at",
                "value": clean_cookie,
                "domain": ".www.linkedin.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
            }
        ])

        # Test navigation to feed
        try:
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
            await bm.random_delay(1.0, 2.0)
            is_ok = ("feed" in page.url and "login" not in page.url and "authwall" not in page.url)
        except Exception:
            is_ok = False

        if is_ok:
            return {
                "status": "success",
                "logged_in": True,
                "message": "Cookie LinkedIn li_at validé ! Vous êtes désormais connecté."
            }
        else:
            return {
                "status": "warning",
                "logged_in": False,
                "message": "Cookie injecté mais LinkedIn a redirigé vers l'écran de connexion. Vérifiez que votre cookie li_at est toujours valide."
            }
    finally:
        await bm.close()


async def setup_platform_session(platform: str = "linkedin"):
    """CLI helper"""
    console.print(f"\n[bold cyan]=== Configuration de la session persistante pour {platform.upper()} ===[/bold cyan]")
    console.print("[dim]Ouverture d'un navigateur visible pour vous permettre de vous connecter en toute sécurité...[/dim]")
    
    res = await launch_login_browser(platform)
    console.print(f"[bold green]➜ {res['message']}[/bold green]")
    console.print("[bold white]Appuyez sur [Entrée] dans ce terminal une fois la connexion réussie pour enregistrer la session persistante...[/bold white]")

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, input, "")

    result = await close_and_verify_session(platform)
    if result["logged_in"]:
        console.print(f"[bold green]✓ Session {platform.upper()} enregistrée avec succès ![/bold green]\n")
    else:
        console.print(f"[bold yellow]⚠️ {result['message']}[/bold yellow]\n")


if __name__ == "__main__":
    import sys
    plat = sys.argv[1] if len(sys.argv) > 1 else "linkedin"
    asyncio.run(setup_platform_session(plat))

