import logging
from datetime import datetime
from typing import Dict, Any
from playwright.async_api import Page
from platforms.base import JobPost
from core.browser.browser_manager import BrowserManager
from core.llm.job_evaluator import job_evaluator
from core.storage.db import ApplicationRecord
from config.settings import settings, UserProfile

logger = logging.getLogger("FranceTravailApply")


class FranceTravailApply:
    def __init__(self, browser_manager: BrowserManager):
        self.bm = browser_manager

    async def apply_to_job(self, job: JobPost, profile: UserProfile) -> ApplicationRecord:
        page: Page = self.bm.page or await self.bm.start()
        record = ApplicationRecord(
            platform="francetravail",
            job_id=job.job_id,
            job_title=job.title,
            company=job.company,
            location=job.location,
            job_url=job.url,
            status="found",
        )

        try:
            logger.info(f"Navigating to France Travail job: {job.title} ({job.url})")
            await page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
            await self.bm.random_delay(1.5, 2.5)

            # Human reading simulation: scroll through description
            await self.bm.human_scroll_and_read(min_seconds=2.0, max_seconds=3.5)

            # Extract job description
            desc_elem = page.locator("[itemprop='description'], .description, #popin-details").first
            job_desc = (await desc_elem.inner_text()) if await desc_elem.count() > 0 else ""
            job.description = job_desc

            # LLM Evaluation
            criteria = settings.load_search_criteria()
            eval_result = job_evaluator.evaluate_job(
                job_title=job.title,
                company=job.company,
                description=job_desc or job.title,
                profile=profile,
                criteria=criteria,
            )
            record.match_score = eval_result.score
            record.match_reason = eval_result.rationale

            if not eval_result.is_match:
                logger.info(f"Skipping France Travail job {job.title} - Score {eval_result.score} < {criteria.min_match_score}")
                record.status = "skipped"
                return record

            # Check postuler button
            apply_btn = page.locator("a:has-text('Postuler'), button:has-text('Postuler'), a.btn-primary").first
            if await apply_btn.count() == 0:
                record.status = "skipped"
                record.error_message = "Bouton postuler introuvable"
                return record

            # Dismiss cookie banner or overlay if present to prevent click interception
            try:
                await page.evaluate("""
                    () => {
                        const cookieEl = document.querySelector('pe-cookies');
                        if (cookieEl) cookieEl.remove();
                        const modalBackdrops = document.querySelectorAll('.modal-backdrop, [class*="cookie"]');
                        modalBackdrops.forEach(el => {
                            if (el.tagName.toLowerCase() === 'pe-cookies' || el.id.includes('cookie')) {
                                el.remove();
                            }
                        });
                    }
                """)
                await self.bm.random_delay(0.5, 1.0)
            except Exception as e:
                logger.debug(f"Cookie banner removal note: {e}")

            await self.bm.human_click(apply_btn)
            await self.bm.random_delay(2.0, 3.5)

            screenshot_path = await self.bm.take_screenshot(f"francetravail_{job.job_id}_ready")
            record.screenshot_path = screenshot_path

            if settings.human_in_the_loop:
                record.status = "requires_review"
                logger.info("HUMAN IN THE LOOP: France Travail application prepared.")
                await self.bm.random_delay(3.0, 5.0)
            else:
                record.status = "applied"
                record.applied_at = datetime.utcnow().isoformat()

            return record

        except Exception as e:
            logger.error(f"Error on France Travail apply: {e}")
            record.status = "failed"
            record.error_message = str(e)
            return record
