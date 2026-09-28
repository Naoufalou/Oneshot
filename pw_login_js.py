#!/usr/bin/env python3
# Debug + login LinkedIn via JS direct (form dynamique React)
import sys, os, time, random
ONESHOT = "C:/Users/pixel/AppData/Local/Temp/Oneshot-tmp"
sys.path.insert(0, ONESHOT)
from playwright.sync_api import sync_playwright
import base64

def delay(t=1.0):
    time.sleep(t + random.uniform(0.3, 1.5))

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222", timeout=20000)
    context = browser.contexts[0]
    page = context.new_page()
    page.set_viewport_size({"width": 1080, "height": 2400})

    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=60000)
    delay(5)  # Wait for React to render

    # List all inputs
    inputs = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('input')).map(i => ({
            id: i.id, name: i.name, type: i.type,
            placeholder: i.placeholder || '', autocomplete: i.autocomplete || '',
            selector: i.id ? '#' + i.id : i.name ? '[name='+i.name+']' : 'input[type='+i.type+']'
        }));
    }""")
    print("=== Input fields ===", flush=True)
    for inp in inputs:
        print(f"  {inp['type']:10} name={inp['name']:<20} id={inp['id']:<15} placeholder={inp['placeholder'][:30]} selector={inp['selector'][:40]}", flush=True)

    # List all buttons
    buttons = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button')).map(b => ({
            text: b.textContent?.trim().slice(0,30) || '',
            type: b.type, innerHTML: b.innerHTML?.slice(0,50) || ''
        }));
    }""")
    print("\n=== Buttons ===", flush=True)
    for b in buttons:
        print(f"  text={b['text'][:30]} type={b['type']}", flush=True)

    # Find email field by type/placeholder/name
    email_result = page.evaluate("""() => {
        const inputs = document.querySelectorAll('input');
        for (const i of inputs) {
            const t = i.type; const n = (i.name||'').toLowerCase(); const p = (i.placeholder||'').toLowerCase();
            if (t === 'email' || n.includes('email') || n.includes('session_key') || n.includes('username') || p.includes('email') || p.includes('adresse')) {
                return i.id || i.name || 'input[type=' + t + ']';
            }
        }
        return null;
    }""")
    print(f"\nEmail selector found: {email_result}", flush=True)

    if email_result:
        # Type email at human speed
        field = page.query_selector(email_result) if email_result.startswith('#') or email_result.startswith('[') else None
        if field:
            field.click()
            delay(0.5)
            for ch in "pixelcreate.news@gmail.com":
                field.type(ch)
                time.sleep(random.uniform(0.02, 0.08))
            delay(1)
            print("  ✓ Email typed", flush=True)

    # Find submit/sign-in button
    click_result = page.evaluate("""() => {
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            const t = (b.textContent||'').toLowerCase();
            if (t.includes('sign in') || t.includes('connexion') || t.includes('next') || t.includes('suivant') || b.type === 'submit') {
                b.click();
                return t.slice(0, 30);
            }
        }
        // Try form submit
        const form = document.querySelector('form');
        if (form) { form.querySelector('button[type="submit"]')?.click(); return 'submit-btn'; }
        return null;
    }""")
    print(f"Clicked: {click_result}", flush=True)
    delay(4)

    # Screenshot
    page.screenshot(path=os.path.join(ONESHOT, "linkedin_login_debug.png"))
    print(f"Screenshot: linkedin_login_debug.png", flush=True)

    # Check URL after click
    print(f"URL after click: {page.url[:80]}", flush=True)
    print(f"Title: {page.title()[:60]}", flush=True)

    # Check for password field
    pw_field = page.evaluate("""() => {
        const inputs = document.querySelectorAll('input');
        for (const i of inputs) {
            if (i.type === 'password' || (i.name||'').toLowerCase().includes('pass')) {
                return i.id || i.name || 'input[type=password]';
            }
        }
        return null;
    }""")
    if pw_field:
        print(f"✓ Password field found: {pw_field}", flush=True)
        print("  Entrez le mot de passe manuellement sur l'émulateur", flush=True)
    else:
        print("→ Pas de champ mot de passe détecté", flush=True)

    context.close()
    browser.close()
    print("Done!", flush=True)
