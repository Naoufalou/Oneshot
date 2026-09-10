import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from playwright.async_api import Page, Locator
from pathlib import Path
from platforms.base import JobPost
from core.browser.browser_manager import BrowserManager
from core.llm.job_evaluator import job_evaluator
from core.llm.form_filler import form_filler
from core.storage.db import ApplicationRecord
from core.rate_limiter import detect_block_reason, PlatformBlockedError
from core.documents.application_documents import prepare_application_documents
from core.browser.external_form_filler import run_external_apply
from config.settings import settings, UserProfile, BASE_DIR

logger = logging.getLogger("LinkedInEasyApply")


class LinkedInEasyApply:
    def __init__(self, browser_manager: BrowserManager):
        self.bm = browser_manager

    async def apply_to_job(self, job: JobPost, profile: UserProfile) -> ApplicationRecord:
        page: Page = self.bm.page or await self.bm.start()
        record = ApplicationRecord(
            platform="linkedin",
            job_id=job.job_id,
            job_title=job.title,
            company=job.company,
            location=job.location,
            job_url=job.url,
            status="found",
        )

        try:
            logger.info(f"Navigating to job: {job.title} at {job.company} ({job.url})")
            await page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
            await self.bm.random_delay(1.5, 2.5)

            # Detect rate-limit / captcha / security walls EARLY and stop the
            # whole run instead of retrying into the block.
            try:
                page_text = (await page.locator("body").inner_text(timeout=4000))[:8000]
            except Exception:
                page_text = ""
            block_reason = detect_block_reason(page_text, page.url)
            if block_reason:
                logger.warning(f"LinkedIn block detected before applying: '{block_reason}' at {page.url}")
                raise PlatformBlockedError(f"LinkedIn bloque l'accès (signal détecté : '{block_reason}'). Run interrompu pour protéger le compte.")

            # Human reading simulation: scroll through description
            await self.bm.human_scroll_and_read(min_seconds=2.0, max_seconds=3.8)

            # Extract job description
            desc_elem = page.locator(".jobs-description__content, #job-details, .jobs-box__html-content").first
            job_description = (await desc_elem.inner_text()) if await desc_elem.count() > 0 else ""
            job.description = job_description

            # Evaluate with LLM
            criteria = settings.load_search_criteria()
            eval_result = job_evaluator.evaluate_job(
                job_title=job.title,
                company=job.company,
                description=job_description or job.title,
                profile=profile,
                criteria=criteria,
            )
            record.match_score = eval_result.score
            record.match_reason = eval_result.rationale

            if not eval_result.is_match:
                logger.info(f"Skipping job {job.title} - Match score {eval_result.score}/100 < {criteria.min_match_score}")
                record.status = "skipped"
                self.bm.db.save_or_update(record) if hasattr(self.bm, "db") else None
                return record

            logger.info(f"Match score: {eval_result.score}/100 - Proceeding to apply!")

            # Check for LinkedIn Authwall redirection
            if "authwall" in page.url or "login" in page.url or "signup" in page.url:
                logger.warning(f"LinkedIn redirected to Authwall ({page.url}) : Session non connectée.")
                record.status = "skipped"
                record.error_message = "Session LinkedIn requise (Authwall)"
                return record

            # Generate tailored ATS CV + cover letter for THIS job before applying.
            tailored_cv_path = None
            tailored_lm_path = None
            tailored_lm_text = None
            try:
                documents = prepare_application_documents(
                    profile,
                    job_title=job.title,
                    company=job.company,
                    job_description=job_description,
                    location=job.location or "",
                )
                tailored_cv_path = documents["cv_path"]
                tailored_lm_path = documents["cover_letter_path"]
                tailored_lm_text = documents["cover_letter_text"]
                logger.info(f"Tailored documents generated for {job.title} → {tailored_cv_path}")
            except Exception as e:
                logger.warning(f"Could not generate tailored documents (will fall back to static CV): {e}")

            # Locate Easy Apply button
            apply_btn = page.locator("button.jobs-apply-button, button:has-text('Candidature simplifiée'), button:has-text('Easy Apply'").first
            if await apply_btn.count() == 0:
                ext_btn = page.locator("button:has-text('Postuler sur le site'), button:has-text('Apply on company website'), a:has-text('Postuler sur le site')").first
                if await ext_btn.count() > 0:
                    # External employer ATS — fill the form on their site.
                    logger.info(f"Job requires external application for {job.company}. Filling external form…")
                    try:
                        ext_url = await ext_btn.get_attribute("href")
                        if ext_url:
                            await page.goto(ext_url, wait_until="domcontentloaded", timeout=45000)
                            ext_page = page
                        else:
                            # Button likely opens a new tab.
                            async with page.context.expect_page(timeout=20000) as page_info:
                                await self.bm.human_click(ext_btn)
                            ext_page = await page_info.value
                            await ext_page.wait_for_load_state("domcontentloaded", timeout=30000)

                        ext_result = await run_external_apply(
                            ext_page,
                            job,
                            profile,
                            cv_path=tailored_cv_path,
                            bm=self.bm,
                            cover_letter_text=tailored_lm_text,
                        )
                        if ext_result["status"] == "applied":
                            record.status = "applied"
                            record.applied_at = datetime.utcnow().isoformat()
                            record.form_answers = ext_result.get("filled_fields", {})
                            logger.info(f"External application submitted for {job.title}.")
                        else:
                            record.status = "requires_review"
                            record.error_message = ext_result.get("message", "Candidature externe à finaliser")
                            record.form_answers = ext_result.get("filled_fields", {})
                            logger.info(f"External application left aside: {ext_result.get('message')}")
                        return record
                    except PlatformBlockedError:
                        raise
                    except Exception as e:
                        logger.warning(f"External apply failed, leaving aside: {e}")
                        record.status = "requires_review"
                        record.error_message = f"Candidature externe non finalisée: {e}"
                        return record
                else:
                    logger.warning("No Easy Apply button found on page.")
                    record.status = "skipped"
                    record.error_message = "Non Easy-Apply (ou session requise)"
                return record

            await self.bm.human_click(apply_btn)
            await self.bm.random_delay(1.5, 3.0)

            modal = page.locator("div.jobs-easy-apply-modal, div[role='dialog']").first
            if await modal.count() == 0:
                logger.warning("Application modal did not appear.")
                record.status = "failed"
                record.error_message = "Modal introuvable"
                return record

            # Process multi-step modal
            form_answers: Dict[str, Any] = {
                "tailored_cv_path": tailored_cv_path,
                "cover_letter_path": tailored_lm_path,
            }
            max_steps = 10
            step = 0

            while step < max_steps:
                step += 1
                logger.info(f"Processing Easy Apply step {step}...")
                await self.bm.random_delay(1.0, 2.0)

                # Fill current step inputs with human interaction
                await self._fill_step_inputs(modal, profile, job_description, form_answers, tailored_cv_path)

                # Check if we are on the Submit step
                submit_btn = modal.locator("button:has-text('Envoyer la candidature'), button:has-text('Submit application')").first
                review_btn = modal.locator("button:has-text('Vérifier'), button:has-text('Review')").first
                next_btn = modal.locator("button:has-text('Suivant'), button:has-text('Next')").first

                if await submit_btn.count() > 0:
                    logger.info("Reached final submission step.")
                    screenshot_path = await self.bm.take_screenshot(f"linkedin_{job.job_id}_ready")
                    record.screenshot_path = screenshot_path
                    record.form_answers = form_answers

                    if settings.human_in_the_loop:
                        logger.info("HUMAN IN THE LOOP: Application prepared. Waiting 5s before auto-closing or manual submit.")
                        record.status = "requires_review"
                        # In semi-auto, we pause briefly for visual check
                        await self.bm.random_delay(4.0, 6.0)
                    else:
                        await self.bm.human_click(submit_btn)
                        await self.bm.random_delay(2.0, 3.0)
                        record.status = "applied"
                        record.applied_at = datetime.utcnow().isoformat()

                    # Dismiss any confirmation modal
                    close_btn = page.locator("button[aria-label='Dismiss'], button[aria-label='Fermer'], button:has-text('Terminé')").first
                    if await close_btn.count() > 0:
                        await self.bm.human_click(close_btn)

                    return record

                elif await review_btn.count() > 0:
                    await self.bm.human_click(review_btn)
                    await self.bm.random_delay(1.5, 2.5)

                elif await next_btn.count() > 0:
                    await self.bm.human_click(next_btn)
                    await self.bm.random_delay(1.5, 2.5)

                    # Check for form validation error
                    error_msg = modal.locator(".artdeco-inline-feedback--error, .fb-form-element--error").first
                    if await error_msg.count() > 0:
                        err_text = await error_msg.inner_text()
                        logger.warning(f"Validation error on step: {err_text}")
                else:
                    logger.warning("Neither Next nor Submit button found. Ending form loop.")
                    break

            record.status = "failed"
            record.error_message = "Formulaire non finalisé (trop d'étapes ou bloqué)"
            return record

        except PlatformBlockedError:
            # Let the block signal propagate so batch/watcher/run halt entirely.
            raise
        except Exception as e:
            logger.error(f"Error applying to LinkedIn job: {e}")
            record.status = "failed"
            record.error_message = str(e)
            return record

    async def _fill_step_inputs(self, modal: Locator, profile: UserProfile, job_desc: str, answers_log: Dict[str, Any], cv_path_override: Optional[str] = None):
        # 1. Fill Phone Input if present
        phone_inputs = await modal.locator("input[id*='phoneNumber'], input[autocomplete='tel'], input[name*='phone']").all()
        for inp in phone_inputs:
            current_val = await inp.input_value()
            if not current_val:
                await self.bm.human_type(inp, profile.phone_number, with_typos=False)
                answers_log["phone"] = profile.phone_number

        # 2. Fill Text and Number inputs
        text_inputs = await modal.locator("input[type='text'], input[type='number'], textarea").all()
        for inp in text_inputs:
            # Skip hidden, disabled or already filled inputs
            if not await inp.is_visible() or await inp.is_disabled():
                continue
            
            # Find label or question text
            inp_id = await inp.get_attribute("id") or ""
            label_elem = modal.locator(f"label[for='{inp_id}']").first if inp_id else None
            
            question_text = ""
            if label_elem and await label_elem.count() > 0:
                question_text = (await label_elem.inner_text()).strip()
            else:
                aria_label = await inp.get_attribute("aria-label")
                question_text = aria_label or inp_id

            current_val = await inp.input_value()
            if current_val and len(current_val.strip()) > 0:
                continue

            input_type = await inp.get_attribute("type") or "text"
            answer = form_filler.answer_question(
                question_text=question_text or "Information",
                question_type="number" if input_type == "number" else "text",
                profile=profile,
                job_context=job_desc,
            )

            is_numeric = (input_type == "number")
            await self.bm.human_type(inp, str(answer), with_typos=not is_numeric)
            answers_log[question_text] = str(answer)

        # 3. Radio groups
        radio_groups = await modal.locator("fieldset").all()
        for fieldset in radio_groups:
            legend = fieldset.locator("legend").first
            question_text = (await legend.inner_text()).strip() if await legend.count() > 0 else ""
            radios = await fieldset.locator("input[type='radio']").all()
            
            if radios:
                options = []
                for r in radios:
                    r_id = await r.get_attribute("id") or ""
                    r_label = fieldset.locator(f"label[for='{r_id}']").first
                    if await r_label.count() > 0:
                        options.append((await r_label.inner_text()).strip())

                selected_option = form_filler.answer_question(
                    question_text=question_text,
                    question_type="radio",
                    options=options,
                    profile=profile,
                )

                for idx, opt in enumerate(options):
                    if str(selected_option).lower() in opt.lower():
                        await self.bm.human_click(radios[idx])
                        answers_log[question_text] = opt
                        break

        # 4. Select Dropdowns
        selects = await modal.locator("select").all()
        for sel in selects:
            if not await sel.is_visible():
                continue
            options = await sel.locator("option").all_inner_texts()
            clean_options = [o.strip() for o in options if o.strip() and "sélectionner" not in o.lower() and "select" not in o.lower()]
            if clean_options:
                chosen = form_filler.answer_question(
                    question_text="Sélectionnez une option",
                    question_type="select",
                    options=clean_options,
                    profile=profile,
                )
                try:
                    await self.bm.human_select_option(sel, chosen)
                    answers_log["select"] = chosen
                except Exception:
                    pass

        # 5. File inputs (Resume upload) — prefer the tailored CV for this job.
        file_inputs = await modal.locator("input[type='file']").all()
        resume_to_use = cv_path_override or profile.resume_path
        if file_inputs and resume_to_use:
            resolved_resume = Path(resume_to_use)
            if not resolved_resume.is_absolute():
                resolved_resume = (BASE_DIR / resolved_resume).resolve()
            if resolved_resume.exists():
                for finp in file_inputs:
                    try:
                        await self.bm.human_upload_file(finp, str(resolved_resume))
                        answers_log["resume"] = resolved_resume.name
                        logger.info(f"Attached {'tailored' if cv_path_override else 'static'} resume: {resolved_resume.name}")
                    except Exception as e:
                        logger.warning(f"Error setting resume file input: {e}")

