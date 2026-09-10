"""ATS-specific fill strategies for external job applications.

Extends the generic ExternalFormFiller with ATS-aware selectors and flows.
Each strategy implements:
  - open_apply_flow(): reach the application form (click "Apply" when needed)
  - fill(): fill identity/contact fields, upload the tailored CV
  - submit(): drive Next/Continue/Submit to completion (best-effort)

The generic filler remains the fallback for unknown ATS. Strategies are
data-driven via the selector maps in ats_detector.py, with targeted extra
logic only where an ATS is structurally different (Workday's dynamic
data-automation-id questions, Greenhouse's cover-letter textarea, etc.).
"""
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from playwright.async_api import Page

from config.settings import settings, UserProfile, BASE_DIR
from core.browser.ats_detector import selectors_for
from core.browser.external_form_filler import (
    value_for_semantic,
    resolve_field_semantics,
)
from core.llm.form_filler import form_filler

logger = logging.getLogger("ATSStrategies")


class BaseATSStrategy:
    """Shared behaviour: fill fields from a selector map, upload CV."""

    key: str = ""  # set by subclasses

    # semantic key -> (candidate value source) for identity fields
    FIELD_VALUES = {
        "first_name": "first_name",
        "last_name": "last_name",
        "name": "full_name",
        "email": "email",
        "phone": "phone",
        "city": "city",
        "postal_code": "postal_code",
        "address": "address",
        "country": "country",
        "linkedin": "linkedin",
        "portfolio": "portfolio",
        "github": "github",
    }

    def __init__(self, page: Page, profile: UserProfile, bm=None):
        self.page = page
        self.profile = profile
        self.bm = bm
        self.selectors = selectors_for(self.key)
        self.filled: Dict[str, str] = {}
        # Optional context injected by run_external_apply (used by Greenhouse).
        self._job_title: str = ""
        self._company: str = ""
        self._pending_cover_letter: Optional[str] = None

    async def _fill_field(self, selector: str, semantic: str) -> bool:
        try:
            loc = self.page.locator(selector).first
            if await loc.count() == 0:
                return False
            if not await loc.is_visible():
                # Some ATS hide inputs; try to fill anyway if enabled
                if await loc.is_disabled():
                    return False
            val = value_for_semantic(semantic, self.profile)
            if not val:
                return False
            cur = await loc.input_value()
            if cur and cur.strip():
                return True  # already filled
            await loc.fill(val)
            self.filled[semantic] = val
            logger.info(f"[ATS:{self.key}] filled {semantic} = {val[:40]}")
            return True
        except Exception as e:
            logger.debug(f"[ATS:{self.key}] fill {semantic} failed: {e}")
            return False

    async def fill(self) -> None:
        """Fill identity/contact fields from the selector map."""
        for key, semantic in self.FIELD_VALUES.items():
            sel = self.selectors.get(key)
            if sel:
                await self._fill_field(sel, semantic)

    async def upload_resume(self, cv_path: Optional[str]) -> bool:
        resume = cv_path or self.profile.resume_path
        if not resume:
            return False
        resolved = Path(resume)
        if not resolved.is_absolute():
            resolved = (BASE_DIR / resolved).resolve()
        if not resolved.exists():
            return False

        sel = self.selectors.get("resume") or "input[type='file']"
        inputs = await self.page.locator(sel).all()
        for finp in inputs:
            try:
                await finp.set_input_files(str(resolved))
                self.filled["resume"] = resolved.name
                logger.info(f"[ATS:{self.key}] uploaded resume: {resolved.name}")
                return True
            except Exception as e:
                logger.warning(f"[ATS:{self.key}] resume upload failed: {e}")
        return False

    async def submit(self) -> bool:
        """Click the submit button (best-effort)."""
        sel = self.selectors.get("submit") or "button[type='submit']"
        try:
            btn = self.page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                await asyncio.sleep(2.0)
                return True
        except Exception as e:
            logger.debug(f"[ATS:{self.key}] submit failed: {e}")
        return False

    async def open_apply_flow(self) -> None:
        """Override to click an 'Apply' button before the form appears."""
        return None


class WorkdayStrategy(BaseATSStrategy):
    key = "workday"

    async def open_apply_flow(self) -> None:
        # Workday often shows an 'Apply' button that reveals the form.
        apply_btn = self.page.locator(
            "button[data-automation-id='applyManually'], button[data-automation-id='applyNow'], "
            "button[data-automation-id='apply']"
        ).first
        try:
            if await apply_btn.count() > 0 and await apply_btn.is_visible():
                logger.info("[ATS:workday] clicking Apply to open flow")
                await apply_btn.click()
                await asyncio.sleep(3.0)
        except Exception as e:
            logger.debug(f"[ATS:workday] apply click note: {e}")

    async def fill(self) -> None:
        await super().fill()
        # Fill dynamic question selects/radios with safe answers.
        await self._fill_dynamic_questions()

    async def _fill_dynamic_questions(self) -> None:
        """Workday renders questions with data-automation-id; answer the safe
        closed-choice ones (sponsorship, work authorization, permit) and leave
        open-ended questions untouched."""
        # Selects
        selects = await self.page.locator("select[data-automation-id]").all()
        for sel in selects:
            try:
                if not await sel.is_visible():
                    continue
                aid = await sel.get_attribute("data-automation-id") or ""
                opts = await sel.locator("option").all_inner_texts()
                clean = [o.strip() for o in opts if o.strip() and "select" not in o.lower() and "sélectionner" not in o.lower()]
                if not clean:
                    continue
                chosen = None
                if any(s in aid.lower() for s in ["sponsor", "visa"]):
                    target = "non" if not self.profile.requires_sponsorship else "oui"
                    chosen = next((o for o in clean if target in o.lower()), None)
                elif any(s in aid.lower() for s in ["country", "pays"]):
                    chosen = next((o for o in clean if self.profile.country.lower() in o.lower()), None)
                if chosen:
                    await sel.select_option(label=chosen)
                    self.filled[aid] = chosen
                    logger.info(f"[ATS:workday] select '{aid}' = {chosen}")
            except Exception as e:
                logger.debug(f"[ATS:workday] question select skip: {e}")

        # Radio groups (sponsorship / authorization)
        radio_groups = await self.page.locator("fieldset, div[role='radiogroup']").all()
        for group in radio_groups:
            try:
                radios = await group.locator("input[type='radio']").all()
                if not radios:
                    continue
                labels = []
                for r in radios:
                    rid = await r.get_attribute("id") or ""
                    lbl = self.page.locator(f"label[for='{rid}']").first
                    labels.append((await lbl.inner_text()).strip() if await lbl.count() > 0 else "")
                joined = " ".join(labels).lower()
                if "sponsor" in joined or "visa" in joined:
                    target = "non" if not self.profile.requires_sponsorship else "oui"
                    for i, lbl in enumerate(labels):
                        if target in lbl.lower():
                            await radios[i].check()
                            self.filled["sponsorship"] = lbl
                            break
            except Exception as e:
                logger.debug(f"[ATS:workday] radio group skip: {e}")

    async def submit(self) -> bool:
        # Workday flow: drive Continue/Next until a confirmation appears or
        # no more buttons are available (avoids blind repeated clicking).
        confirm_signals = [
            "thank you", "application submitted", "submitted", "your application",
            "merci", "candidature envoyée", "candidature soumise", "we've received",
        ]

        async def _confirmed() -> bool:
            try:
                body = (await self.page.locator("body").inner_text(timeout=3000)).lower()
            except Exception:
                return False
            return any(s in body for s in confirm_signals)

        for _ in range(10):
            if await _confirmed():
                logger.info("[ATS:workday] confirmation detected — application complete")
                return True

            # Prefer explicit submit button.
            submit_btn = self.page.locator(
                "button[data-automation-id='submit'], button[type='submit']"
            ).first
            if await submit_btn.count() > 0 and await submit_btn.is_visible():
                try:
                    await submit_btn.click()
                    await asyncio.sleep(2.5)
                    continue
                except Exception as e:
                    logger.debug(f"[ATS:workday] submit click failed: {e}")

            cont = self.page.locator(
                "button[data-automation-id='bottom-navigation-next-button']"
            ).first
            if await cont.count() > 0 and await cont.is_visible():
                try:
                    await cont.click()
                    await asyncio.sleep(2.5)
                    continue
                except Exception as e:
                    logger.debug(f"[ATS:workday] continue click failed: {e}")
                    break
            # No more buttons — stop.
            break

        return await _confirmed()


class GreenhouseStrategy(BaseATSStrategy):
    key = "greenhouse"

    async def fill(self) -> None:
        await super().fill()
        # Greenhouse has an explicit cover-letter textarea — paste the tailored LM.
        lm_text = getattr(self.profile, "_pending_cover_letter", None)
        if not lm_text:
            lm_text = self._cover_letter_text()
        if lm_text:
            sel = self.selectors.get("cover_letter") or "#cover_letter_text"
            try:
                ta = self.page.locator(sel).first
                if await ta.count() > 0 and await ta.is_visible():
                    cur = await ta.input_value()
                    if not cur.strip():
                        await ta.fill(lm_text)
                        self.filled["cover_letter"] = "(tailored)"
                        logger.info("[ATS:greenhouse] pasted tailored cover letter")
            except Exception as e:
                logger.debug(f"[ATS:greenhouse] cover letter fill failed: {e}")

    def _cover_letter_text(self) -> str:
        try:
            from core.documents.cover_letter_builder import build_cover_letter_text
            return build_cover_letter_text(
                self.profile,
                getattr(self, "_job_title", "") or "ce poste",
                getattr(self, "_company", "") or "",
            )
        except Exception:
            return ""


class LeverStrategy(BaseATSStrategy):
    key = "lever"

    async def open_apply_flow(self) -> None:
        # Lever: an 'Apply for this job' button opens the form (sometimes a modal).
        btn = self.page.locator("button:has-text('Apply for this job'), a:has-text('Apply for this job')").first
        try:
            if await btn.count() > 0 and await btn.is_visible():
                logger.info("[ATS:lever] clicking 'Apply for this job'")
                await btn.click()
                await asyncio.sleep(2.5)
        except Exception as e:
            logger.debug(f"[ATS:lever] apply click note: {e}")


class SmartRecruitersStrategy(BaseATSStrategy):
    key = "smartrecruiters"


def get_strategy(ats_key: Optional[str], page: Page, profile: UserProfile, bm=None):
    if ats_key == "workday":
        return WorkdayStrategy(page, profile, bm)
    if ats_key == "greenhouse":
        return GreenhouseStrategy(page, profile, bm)
    if ats_key == "lever":
        return LeverStrategy(page, profile, bm)
    if ats_key == "smartrecruiters":
        return SmartRecruitersStrategy(page, profile, bm)
    return None
