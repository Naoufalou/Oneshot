import os
import random
import asyncio
import logging
from pathlib import Path
from typing import Optional, Union
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright, Locator
from playwright_stealth import Stealth
from core.browser.human_actions import HumanActions
from config.settings import settings, SESSIONS_DIR, SCREENSHOTS_DIR

logger = logging.getLogger("BrowserManager")

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]


class BrowserManager:
    def __init__(self, platform_name: str = "general"):
        self.platform_name = platform_name
        self.session_dir = SESSIONS_DIR / platform_name
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        self.playwright: Optional[Playwright] = None
        self.browser = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.human: Optional[HumanActions] = None

    async def _setup_stealth_and_human(self):
        """Applies stealth evasion patches and initializes HumanActions engine on context and page."""
        stealth_js = """
            // Overwrite navigator.webdriver property
            try {
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            } catch (e) {}

            // Mock window.chrome runtime object
            if (!window.chrome) {
                window.chrome = {};
            }
            window.chrome.runtime = window.chrome.runtime || {};
            window.chrome.loadTimes = window.chrome.loadTimes || function() {};
            window.chrome.csi = window.chrome.csi || function() {};
            window.chrome.app = window.chrome.app || {};

            // Mock realistic plugins list
            try {
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            } catch (e) {}

            // Mock languages
            try {
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['fr-FR', 'fr', 'en-US', 'en']
                });
            } catch (e) {}
        """
        if self.context:
            try:
                await self.context.add_init_script(stealth_js)
            except Exception as e:
                logger.debug(f"Context init script note: {e}")

        if self.page:
            try:
                stealth_evasion = Stealth()
                await stealth_evasion.apply_stealth_async(self.page)
            except Exception as e:
                logger.debug(f"playwright_stealth evasion note: {e}")

            try:
                await self.page.add_init_script(stealth_js)
                await self.page.evaluate(stealth_js)
            except Exception as e:
                logger.debug(f"Page init script note: {e}")

            self.human = HumanActions(self.page)

    async def start(self, headless: Optional[bool] = None, persistent: bool = True) -> Page:
        # If page is already active and alive, return it
        if self.page and not self.page.is_closed():
            if not self.human or self.human.page != self.page:
                self.human = HumanActions(self.page)
            return self.page

        is_headless = settings.headless_browser if headless is None else headless
        self.playwright = await async_playwright().start()
        user_agent = random.choice(USER_AGENTS)
        viewport_w = random.randint(1260, 1320)
        viewport_h = random.randint(880, 930)

        chrome_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--window-position=0,0",
            f"--window-size={viewport_w},{viewport_h}",
        ]

        if persistent:
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.session_dir),
                headless=is_headless,
                viewport={"width": viewport_w, "height": viewport_h},
                user_agent=user_agent,
                locale="fr-FR",
                timezone_id="Europe/Paris",
                args=chrome_args,
            )
            self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        else:
            self.browser = await self.playwright.chromium.launch(
                headless=is_headless,
                args=chrome_args,
            )
            self.context = await self.browser.new_context(
                viewport={"width": viewport_w, "height": viewport_h},
                user_agent=user_agent,
                locale="fr-FR",
                timezone_id="Europe/Paris",
            )
            self.page = await self.context.new_page()

        await self._setup_stealth_and_human()

        logger.info(f"Stealth Browser started for {self.platform_name} (headless={is_headless}, persistent={persistent})")
        return self.page

    async def close(self):
        if self.page and not self.page.is_closed():
            try:
                await self.page.close()
            except Exception:
                pass
        self.page = None
        self.human = None

        if self.context:
            try:
                for p in list(self.context.pages):
                    if not p.is_closed():
                        await p.close()
            except Exception:
                pass
            try:
                await self.context.close()
            except Exception:
                pass
            self.context = None

        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
            self.browser = None

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
            self.playwright = None

        logger.info(f"Browser closed for {self.platform_name}")

    async def random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    def _ensure_human(self) -> HumanActions:
        if not self.human or (self.page and self.human.page != self.page):
            if not self.page or self.page.is_closed():
                raise RuntimeError("No active page available for HumanActions")
            self.human = HumanActions(self.page)
        return self.human

    async def human_type(self, selector_or_locator: Union[str, Locator], text: str, with_typos: bool = True):
        """Simulates realistic human typing with gaussian delays, punctuation pauses, and corrected typos."""
        human = self._ensure_human()
        await human.type(selector_or_locator, text, with_typos=with_typos)

    async def human_click(self, selector_or_locator: Union[str, Locator], hover_pause: bool = True):
        """Simulates human click: Bézier mouse travel, hesitation, realistic press duration."""
        human = self._ensure_human()
        await human.click(selector_or_locator, hover_pause=hover_pause)

    async def human_move_mouse(self, target_x: float, target_y: float):
        """Moves cursor along a smooth cubic Bézier curve with micro-jitter."""
        human = self._ensure_human()
        await human.move_mouse(target_x, target_y)

    async def human_scroll_and_read(self, min_seconds: float = 2.0, max_seconds: float = 4.5):
        """Simulates a human reading the offer or form with natural wheel chunks and pauses."""
        human = self._ensure_human()
        await human.scroll_and_read(min_seconds, max_seconds)

    async def human_select_option(self, selector_or_locator: Union[str, Locator], value: str):
        """Selects an option with natural human clicks."""
        human = self._ensure_human()
        await human.select_option(selector_or_locator, value)

    async def human_upload_file(self, file_input_locator: Locator, file_path: str):
        """Uploads a file with realistic human interaction delay."""
        human = self._ensure_human()
        await human.upload_file(file_input_locator, file_path)

    async def take_screenshot(self, name: str) -> str:
        if not self.page or self.page.is_closed():
            return ""
        filepath = SCREENSHOTS_DIR / f"{name}.png"
        await self.page.screenshot(path=str(filepath), full_page=False)
        return str(filepath)
