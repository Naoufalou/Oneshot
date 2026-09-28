#!/usr/bin/env python3
"""
Test Playwright CDP → Chrome sur émulateur Android.
Navigue le mobile web comme un humain (UA mobile, viewport 1080x2400).
"""
import os, sys, time, random
ONESHOT = "C:/Users/pixel/AppData/Local/Temp/Oneshot-tmp"
sys.path.insert(0, ONESHOT)

from playwright.sync_api import sync_playwright

CDP_URL = "http://localhost:9222"
MOBILE_UA = ("Mozilla/5.0 (Linux; Android 13; SM-S918B) "
             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Mobile Safari/537.36")

def humain_delay(t=1.0):
    delay = t + random.uniform(0.3, 1.2)
    time.sleep(delay)

with sync_playwright() as p:
    print("Connecting to Chrome on Android emulator via CDP...", flush=True)
    browser = p.chromium.connect_over_cdp(CDP_URL, timeout=20000)
    print(f"Connected! contexts={len(browser.contexts)}", flush=True)

    # List existing pages
    for ctx in browser.contexts:
        for pg in ctx.pages:
            try:
                title = pg.title()
            except:
                title = "?"
            print(f"  existing: title={title[:50]} url={pg.url[:70]}", flush=True)

    # CDP connection: reuse existing context (can't create new with CDP)
    context = browser.contexts[0]
    page = context.new_page()
    # Set mobile viewport (Chrome on Android already has mobile UA)
    page.set_viewport_size({"width": 1080, "height": 2400})

    # Navigate like a human — start at Google, then search LinkedIn
    print("Navigating to m.linkedin.com...", flush=True)
    page.goto("https://m.linkedin.com", wait_until="domcontentloaded")
    humain_delay(2)
    title = page.title()
    print(f"  Title: {title}", flush=True)
    print(f"  URL: {page.url}", flush=True)

    # Screenshot
    ss_path = os.path.join(ONESHOT, "linkedin_login_test.png")
    page.screenshot(path=ss_path)
    print(f"  Screenshot: {ss_path}", flush=True)

    # Check if Google account is auto-filled (since it's logged in on emulator)
    email_field = page.query_selector("input#username, input[name='session_key']")
    if email_field:
        val = email_field.get_attribute("value") or "(empty)"
        print(f"  Email field value: {val}", flush=True)
        if "pixelcreate" in val.lower():
            print("  Google account auto-filled! ✓", flush=True)

    context.close()
    browser.close()
    print("Done!", flush=True)
