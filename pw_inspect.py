# Script CDP Playwright login LinkedIn via credential manager Chrome sur émulateur Android.
import sys, os, time, random
ONESHOT = "C:/Users/pixel/AppData/Local/Temp/Oneshot-tmp"
sys.path.insert(0, ONESHOT)
from playwright.sync_api import sync_playwright

def delay(t=1.0):
    time.sleep(t + random.uniform(0.2, 1.0))

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9222", timeout=20000)
    context = browser.contexts[0]
    page = context.new_page()
    page.set_viewport_size({"width": 1080, "height": 2400})

    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    delay(3)

    # List all buttons/links on the page
    elements = page.eval_on_selector_all("button, a, [role='button']",
        "els => els.map(e => ({ text: e.textContent?.trim().slice(0,30), tag: e.tagName, href: e.href?.slice(0,60) }))")
    print("Page elements (buttons/links):")
    for e in (elements or [])[:15]:
        print(f"  {e.get('tag','?')}: {e.get('text','?')} href={e.get('href','')[:40]}")

    # Check if email field exists
    email_field = page.query_selector("input#username, input[name='session_key'], input[type='email']")
    if email_field:
        print(f"\nEmail field found. Placeholder={email_field.get_attribute('placeholder')}")
        # Click to trigger Chrome credential manager
        email_field.click()
        delay(2)
        page.screenshot(path=os.path.join(ONESHOT, "linkedin_email_tapped.png"))
        print("Screenshot: linkedin_email_tapped.png")
    else:
        print("Email field NOT found")

    # List ALL elements with text > 0 chars for debugging
    all_text = page.eval_on_selector_all("*", "els => els.filter(e => e.textContent?.trim()).map(e => e.textContent.trim().slice(0,30))")
    print("\nAll text elements:")
    for t in (all_text or [])[:20]:
        print(f"  '{t}'")

    context.close()
    browser.close()
    print("\nDone!", file=sys.stderr, flush=True)
