import logging
from datetime import datetime
from typing import Dict, Any
from pathlib import Path
from playwright.async_api import Page, Locator
from platforms.base import JobPost
from core.browser.browser_manager import BrowserManager
from core.llm.job_evaluator import job_evaluator
from core.llm.form_filler import form_filler
from core.storage.db import ApplicationRecord
from core.browser.external_form_filler import run_external_apply
from core.rate_limiter import PlatformBlockedError
from config.settings import settings, UserProfile, BASE_DIR

logger = logging.getLogger("IndeedApply")


class IndeedApply:
    def __init__(self, browser_manager: BrowserManager):
        self.bm = browser_manager

    async def apply_to_job(self, job: JobPost, profile: UserProfile) -> ApplicationRecord:
        page: Page = self.bm.page or await self.bm.start()
        record = ApplicationRecord(
            platform="indeed",
            job_id=job.job_id,
            job_title=job.title,
            company=job.company,
            location=job.location,
            job_url=job.url,
            status="found",
        )

        try:
            logger.info(f"Navigating to Indeed job: {job.title} at {job.company} ({job.url})")
            await page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
            await self.bm.random_delay(1.5, 2.5)

            # Human reading simulation: scroll through description
            await self.bm.human_scroll_and_read(min_seconds=2.0, max_seconds=3.8)

            # Extract job description
            desc_elem = page.locator("#jobDescriptionText, .jobsearch-JobComponent-description").first
            job_desc = (await desc_elem.inner_text()) if await desc_elem.count() > 0 else ""
            job.description = job_desc

            # Evaluate with LLM
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
                logger.info(f"Skipping Indeed job {job.title} - Score {eval_result.score} < {criteria.min_match_score}")
                record.status = "skipped"
                return record

            # Find Indeed apply button
            apply_btn = page.locator("#indeedApplyButton, button:has-text('Postuler maintenant'), button:has-text('Candidature facile')").first
            if await apply_btn.count() == 0:
                # External employer site (apply on company website)
                ext_btn = page.locator("a:has-text('Postuler sur le site'), a:has-text('Apply on company website'), button:has-text('Postuler sur le site')").first
                if await ext_btn.count() > 0:
                    logger.info(f"Job requires external application for {job.company}. Filling external form…")
                    try:
                        ext_url = await ext_btn.get_attribute("href")
                        if ext_url:
                            await page.goto(ext_url, wait_until="domcontentloaded", timeout=45000)
                            ext_page = page
                        else:
                            async with page.context.expect_page(timeout=20000) as page_info:
                                await self.bm.human_click(ext_btn)
                            ext_page = await page_info.value
                            await ext_page.wait_for_load_state("domcontentloaded", timeout=30000)

                        ext_result = await run_external_apply(
                            ext_page, job, profile,
                            cv_path=profile.resume_path,
                            bm=self.bm,
                        )
                        if ext_result["status"] == "applied":
                            record.status = "applied"
                            record.applied_at = datetime.utcnow().isoformat()
                            record.form_answers = ext_result.get("filled_fields", {})
                        else:
                            record.status = "requires_review"
                            record.error_message = ext_result.get("message", "Candidature externe à finaliser")
                            record.form_answers = ext_result.get("filled_fields", {})
                        return record
                    except PlatformBlockedError:
                        raise
                    except Exception as e:
                        logger.warning(f"External apply failed, leaving aside: {e}")
                        record.status = "requires_review"
                        record.error_message = f"Candidature externe non finalisée: {e}"
                        return record

                logger.info("Job requires external site application or button not found.")
                record.status = "skipped"
                record.error_message = "Candidature externe requise"
                return record

            await self.bm.human_click(apply_btn)
            await self.bm.random_delay(2.0, 4.0)

            # Indeed usually opens an iframe or redirects to indeedapply URL
            form_answers: Dict[str, Any] = {}
            max_steps = 8
            step = 0

            while step < max_steps:
                step += 1
                logger.info(f"Processing Indeed apply step {step}...")
                await self.bm.random_delay(1.5, 3.0)

                # Check if we reached final submission
                submit_btn = page.locator("button:has-text('Envoyer votre candidature'), button:has-text('Submit your application'), button:has-text('Postuler')").first
                continue_btn = page.locator("button:has-text('Continuer'), button:has-text('Continue'), button:has-text('Suivant')").first

                # Fill visible inputs on current step with human interaction
                inputs = await page.locator("input[type='text'], input[type='number'], input[type='tel'], textarea").all()
                for inp in inputs:
                    if not await inp.is_visible() or await inp.is_disabled():
                        continue
                    current_val = await inp.input_value()
                    if current_val:
                        continue

                    label_text = await inp.get_attribute("aria-label") or await inp.get_attribute("name") or "Question"
                    input_type = await inp.get_attribute("type") or "text"
                    answer = form_filler.answer_question(
                        question_text=label_text,
                        question_type="number" if input_type == "number" else "text",
                        profile=profile,
                        job_context=job_desc,
                    )
                    is_numeric = (input_type in ["number", "tel"])
                    await self.bm.human_type(inp, str(answer), with_typos=not is_numeric)
                    form_answers[label_text] = str(answer)

                # Check for file upload inputs (Resume)
                file_inputs = await page.locator("input[type='file']").all()
                if file_inputs and profile.resume_path:
                    resolved_resume = Path(profile.resume_path)
                    if not resolved_resume.is_absolute():
                        resolved_resume = (BASE_DIR / resolved_resume).resolve()
                    if resolved_resume.exists():
                        for finp in file_inputs:
                            try:
                                await self.bm.human_upload_file(finp, str(resolved_resume))
                                form_answers["resume"] = resolved_resume.name
                                logger.info(f"Attached active resume to Indeed: {resolved_resume.name}")
                            except Exception as e:
                                logger.warning(f"Error setting resume on Indeed: {e}")

                if await submit_btn.count() > 0:
                    logger.info("Indeed application ready for final submission.")
                    screenshot_path = await self.bm.take_screenshot(f"indeed_{job.job_id}_ready")
                    record.screenshot_path = screenshot_path
                    record.form_answers = form_answers

                    if settings.human_in_the_loop:
                        record.status = "requires_review"
                        logger.info("HUMAN IN THE LOOP: Application prepared on Indeed.")
                        await self.bm.random_delay(4.0, 6.0)
                    else:
                        await self.bm.human_click(submit_btn)
                        await self.bm.random_delay(2.0, 3.0)
                        record.status = "applied"
                        record.applied_at = datetime.utcnow().isoformat()

                    return record

                elif await continue_btn.count() > 0:
                    await self.bm.human_click(continue_btn)
                    await self.bm.random_delay(1.5, 3.0)
                else:
                    break

            record.status = "failed"
            record.error_message = "Processus Indeed interrompu ou non standard"
            return record

        except Exception as e:
            logger.error(f"Error applying to Indeed job: {e}")
            record.status = "failed"
            record.error_message = str(e)
            return record
