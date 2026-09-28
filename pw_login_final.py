#!/usr/bin/env python3
# LinkedIn login via Playwright CDP — JS DOM direct, selecteurs robustes
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

    print("=== LinkedIn Login (JS DOM direct, anti-bot safe) ===", flush=True)
    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60000)
    delay(4)

    # 1. Fill email via direct DOM manipulation
    result = page.evaluate("""(email) => {
        const inputs = document.querySelectorAll('input[type="email"]');
        if (inputs.length === 0) return "no email input found";
        const el = inputs[0];
        el.focus();
        el.value = email;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        el.dispatchEvent(new Event('keydown', { key: 'a', code: 'KeyA', bubbles: true }));
        return "email field filled via DOM, value=" + el.value.slice(0, 10) + "...";
    }""", "pixelcreate.news@gmail.com")
    print(f"\n[1] {result}", flush=True)
    delay(1)

    # 2. Click EXACT "Sign in" button (NOT "with Apple"/"with passkey")
    result = page.evaluate("""() => {
        const btns = document.querySelectorAll('button');
        let candidates = [];
        for (const b of btns) {
            const t = b.textContent?.trim().toLowerCase();
            if (t === 'sign in' || t === 'connexion' || t === 'suivant') {
                const rect = b.getBoundingClientRect();
                const visible = rect.width > 0 && rect.height > 0;
                candidates.push({ text: t, visible });
                if (visible && (t === 'sign in' || t === 'connexion')) {
                    b.click();
                    return "clicked: " + t + " (visible)";
                }
            }
        }
        return "candidates=" + JSON.stringify(candidates) + " -> no visible exact match";
    }""")
    print(f"[2] {result}", flush=True)
    delay(4)

    # 3. Check state after click
    url = page.url
    title = page.title()
    print(f"[3] URL: {url[:70]}", flush=True)
    print(f"    Title: {title[:60]}", flush=True)

    # 4. Look for password field
    pw_result = page.evaluate("""() => {
        const pw = document.querySelector('input[type="password"]');
        if (pw) return "found password field, value=" + (pw.value || "(empty)");
        const err = document.querySelector('[role="alert"], .error, .alert');
        if (err) return "error: " + err.textContent.trim().slice(0, 100);
        return "no password field, no error";
    }""")
    print(f"[4] {pw_result}", flush=True)

    if "found password" in pw_result:
        print("\n⏱ ATTENTION: Mot de passe demandé sur l'émulateur.", flush=True)
        print("   Tapez-le manuellement sur le téléphone émulé, puis appuyez sur 'Sign in'.", flush=True)
        print("   Le script vérifiera toutes les 3s si la connexion a réussi...", flush=True)

        for i in range(15):
            delay(3)
            u = page.url
            t = page.title()
            print(f"   poll {i+1}: url={u[:50]} title={t[:30]}", flush=True)
            if "login" not in u and "signin" not in u.lower() and "linkedin.com" in u:
                print(f"\n  ✓ Connecté! URL={u[:60]}", flush=True)
                try:
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight/2);")
                    delay(1)
                    page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded", timeout=60000)
                    delay(3)
                    print(f"  Jobs: {page.title()[:60]}", flush=True)
                except:
                    pass
                page.screenshot(path=os.path.join(ONESHOT, "linkedin_connected.png"), timeout=60000)
                print("  Screenshot: linkedin_connected.png", flush=True)
                break
        else:
            print("  → Timeout: entrez le mot de passe plus rapidement", flush=True)

    # Final screenshot
    try:
        page.screenshot(path=os.path.join(ONESHOT, "linkedin_final_state.png"), timeout=60000)
        print("  Screenshot: linkedin_final_state.png", flush=True)
    except Exception as e:
        print(f"  Screenshot error: {e}", flush=True)

    context.close()
    browser.close()
    print("\n=== Done ===", flush=True)
