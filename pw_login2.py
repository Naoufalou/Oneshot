#!/usr/bin/env python3
# LinkedIn login via Playwright CDP — comportement humain (email tapé, mot de passe manuel)
import sys, os, time, random
ONESHOT = "C:/Users/pixel/AppData/Local/Temp/Oneshot-tmp"
sys.path.insert(0, ONESHOT)
from playwright.sync_api import sync_playwright

def delay(t=1.0):
    time.sleep(t + random.uniform(0.3, 1.5))

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222", timeout=20000)
    context = browser.contexts[0]
    page = context.new_page()
    page.set_viewport_size({"width": 1080, "height": 2400})

    print("=== LinkedIn Login (comportement humain) ===", flush=True)
    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60000)
    delay(2)

    # Scroll down to reveal all elements (lazy loaded)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
    delay(1)
    page.evaluate("window.scrollTo(0, 0);")
    delay(1)

    # Check for Google sign-in
    page_text = page.evaluate("document.body.innerText || ''")
    has_google = "google" in page_text.lower() or "Google" in page_text
    print(f"\nTexte Google trouvé: {has_google}", flush=True)

    if has_google:
        print("  Recherche du bouton Google...", flush=True)
        for sel in ["text=/Sign in with Google/i", "text=/Google/i",
                     "[aria-label*='oogle']", "button:has-text('Google')"]:
            try:
                btn = page.wait_for_selector(sel, timeout=3000)
                if btn:
                    btn.scroll_into_view_if_needed()
                    delay(1)
                    btn.click()
                    print(f"  ✓ Clic: {sel}", flush=True)
                    delay(3)
                    # Check for Google account suggestion
                    acct = page.query_selector("text=/pixelcreate/i")
                    if acct:
                        acct.click()
                        print("  ✓ Compte Google sélectionné", flush=True)
                        delay(4)
                    break
            except:
                pass

    # If Google sign-in didn't work or wasn't found → type email manually
    cur_url = page.url
    print(f"\nURL actuelle: {cur_url}", flush=True)
    print(f"Title: {page.title()[:60]}", flush=True)

    if "login" in cur_url or "signin" in cur_url.lower():
        print("\n→ Taper email (manuel, sans mot de passe)...", flush=True)
        email_field = page.wait_for_selector("input#username, input[name='session_key']", timeout=5000)
        email_field.click()
        delay(0.5)
        # Human typing ~45 WPM
        for ch in "pixelcreate.news@gmail.com":
            email_field.type(ch)
            time.sleep(random.uniform(0.02, 0.08))
        delay(1)
        print("  ✓ Email tapé", flush=True)

        # Click Sign In / Next
        for sel in ["button:has-text('Sign in')", "button:has-text('Connectez-vous')",
                    "input[type='submit']", "button[type='submit']"]:
            try:
                btn = page.wait_for_selector(sel, timeout=5000)
                btn.click()
                print(f"  ✓ Clic: {sel}", flush=True)
                delay(3)
                break
            except:
                pass

        print("\n⏱ ATTENTION: Page mot de passe affichée sur l'émulateur.", flush=True)
        print("   Entrez le mot de passe manuellement sur le téléphone émulé.", flush=True)
        print("   Le script capture l'écran pour vérification...", flush=True)

        # Wait for login to complete (poll URL change)
        for i in range(12):
            delay(3)
            url = page.url
            title = page.title()
            print(f"  poll {i+1}: url={url[:50]} title={title[:30]}", flush=True)
            if "login" not in url and "signin" not in url.lower() and "linkedin.com" in url:
                print(f"\n  ✓ Connecté! URL: {url}", flush=True)
                # Search for jobs
                page.goto("https://www.linkedin.com/jobs", wait_until="domcontentloaded")
                delay(3)
                print(f"  Jobs page title: {page.title()[:60]}", flush=True)
                page.screenshot(path=os.path.join(ONESHOT, "linkedin_jobs.png"))
                print("  Screenshot: linkedin_jobs.png", flush=True)
                break
        else:
            page.screenshot(path=os.path.join(ONESHOT, "linkedin_password_wait.png"))
            print("  Screenshot: linkedin_password_wait.png", flush=True)

    page.screenshot(path=os.path.join(ONESHOT, "linkedin_login_final.png"))
    print("\n=== Final screenshots saved ===", flush=True)

    context.close()
    browser.close()
    print("Done!", file=sys.stderr, flush=True)
