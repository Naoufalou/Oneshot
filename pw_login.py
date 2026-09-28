#!/usr/bin/env python3
"""
Playwright CDP → Chrome Android emulator: login Google + recherche emploi
Comportement humain (delays, scroll, typing). Nous Portal LLM pour l'intelligence.
"""
import sys, os, time, random

ONESHOT = "C:/Users/pixel/AppData/Local/Temp/Oneshot-tmp"
sys.path.insert(0, ONESHOT)

from playwright.sync_api import sync_playwright

def humain_delay(t=1.0):
    time.sleep(t + random.uniform(0.2, 1.0))

def human_typing(page, selector, text):
    """Type text character by character like a human (45 WPM)."""
    field = page.locator(selector)
    field.click()
    for ch in text:
        field.type(ch)
        time.sleep(random.uniform(0.02, 0.08))
    humain_delay()

with sync_playwright() as p:
    print("=== Playwright CDP → Chrome Android Emulator ===", flush=True)
    browser = p.chromium.connect_over_cdp("http://localhost:9222", timeout=20000)
    context = browser.contexts[0]
    page = context.new_page()
    page.set_viewport_size({"width": 1080, "height": 2400})

    # 1. Login LinkedIn via Google (compte déjà connecté sur le téléphone)
    print("\n[1] Ouverture LinkedIn login...", flush=True)
    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    humain_delay(3)

    # Try Google sign-in button
    google_btn_found = False
    for selector in ['[aria-label*="Google"]', 'button:has-text("Google")',
                     '[alt*="Google"]', 'button:has-text("Connectez-vous")']:
        try:
            btn = page.wait_for_selector(selector, timeout=5000)
            btn.click()
            print("  ✓ Clic bouton Google", flush=True)
            google_btn_found = True
            humain_delay(3)
            break
        except:
            pass

    if google_btn_found:
        # Click the Google account (pixelcreate.news@gmail.com)
        print("[2] Selection du compte Google...", flush=True)
        account_found = False
        for sel in [f"button:has-text('pixelcreate')", "button:has-text('pixelcreate')",
                     "[data-identifier='pixelcreate']"]:
            try:
                btn = page.wait_for_selector(sel, timeout=8000)
                btn.click()
                print("  ✓ Compte sélectionné", flush=True)
                account_found = True
                humain_delay(4)
                break
            except:
                pass
        if not account_found:
            print("  → Compte Google non autofill (attente saisie manuelle)", flush=True)
            page.screenshot(path=os.path.join(ONESHOT, "linkedin_after_google.png"))
    else:
        print("  → Pas de bouton Google (login manuel nécessaire)", flush=True)

    # 3. Verify login status
    print("[3] Vérification login...", flush=True)
    try:
        title = page.title()
        cur_url = page.url
        print(f"  Title: {title[:60]}", flush=True)
        print(f"  URL: {cur_url[:70]}", flush=True)
        if "linkedin.com/feed" in cur_url or "linkedin.com/in" in cur_url:
            print("  ✓ Connecté à LinkedIn!", flush=True)
        elif "login" in cur_url.lower():
            print("  → Toujours sur la page login", flush=True)
    except Exception as e:
        print(f"  Erreur: {e}", flush=True)

    page.screenshot(path=os.path.join(ONESHOT, "linkedin_final.png"))
    print(f"\n  Screenshots: linkedin_after_google.png, linkedin_final.png", flush=True)

    context.close()
    browser.close()
    print("=== Done ===", flush=True)
