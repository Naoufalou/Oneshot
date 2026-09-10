"""Generic external job-application form filler.

When a job posting routes to the employer's own ATS (Workday, Lever,
Greenhouse, SmartRecruiters, Taleo, generic careers page, etc.), LinkedIn's
Easy Apply does not apply — we must navigate to the external URL, fill the
form, upload the tailored CV, and handle account creation / email verification.

This module provides:
  - a label→value resolver driven by the candidate profile
  - a robust form scanner that fills text/number/tel/email inputs, selects,
    radios, checkboxes, and file uploads
  - email-verification handling (auto via IMAP, or "skip" -> leave aside)

It is intentionally defensive: external ATS are highly heterogeneous, so any
step that cannot be confidently handled falls back to `requires_review` (the
application is left aside for manual completion) instead of submitting wrong
data.
"""
import asyncio
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from playwright.async_api import Page, Locator
from config.settings import settings, UserProfile, BASE_DIR
from core.email import email_verifier
from core.rate_limiter import detect_block_reason, PlatformBlockedError

logger = logging.getLogger("ExternalFormFiller")


# ---------------------------------------------------------------------------
# Field semantic resolution
# ---------------------------------------------------------------------------

EMAIL_PATTERNS = [r"\bemail\b", r"e-mail", r"courriel", r"adresse email", r"mail\b"]
FIRST_NAME_PATTERNS = [r"\bfirst[ _-]?name\b", r"\bpr[ée]nom\b", r"given name"]
LAST_NAME_PATTERNS = [r"\blast[ _-]?name\b", r"\bnom\b", r"surname", r"family name"]
FULL_NAME_PATTERNS = [r"full name", r"nom complet", r"your name", r"votre nom"]
PHONE_PATTERNS = [r"\bphone\b", r"\bt[ée]l[ée]phone\b", r"mobile", r"portable", r"num[ée]ro de t"]
CITY_PATTERNS = [r"\bcity\b", r"\bville\b"]
POSTAL_PATTERNS = [r"\bpostal\b", r"\bzip\b", r"code postal", r"postcode"]
COUNTRY_PATTERNS = [r"\bcountry\b", r"\bpays\b"]
ADDRESS_PATTERNS = [r"\baddress\b", r"\badresse\b", r"street"]
SALARY_PATTERNS = [r"\bsalary\b", r"\bsalaire\b", r"compensation", r"pr[ée]tention", r"remuneration", r"r[ée]mun[ée]ration"]
NOTICE_PATTERNS = [r"notice", r"pr[ée]avis", r"d[ée]lai de pr"]
EXPERIENCE_PATTERNS = [r"years? of experience", r"ann[ée]es d.exp[ée]rience", r"experience in years"]
LINKEDIN_PATTERNS = [r"linkedin"]
PORTFOLIO_PATTERNS = [r"portfolio", r"website", r"site web", r"site personnel"]
GITHUB_PATTERNS = [r"github"]
WORK_AUTH_PATTERNS = [r"authori[sz]", r"work (permit|status)", r"droit de travailler", r"eligib"]
SPONSORSHIP_PATTERNS = [r"sponsor", r"visa"]


def _has_any(text: str, patterns) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in patterns)


def resolve_field_semantics(label: str, attrs: Dict[str, str], profile: UserProfile) -> Optional[str]:
    """Map a form field to a semantic key (or None if unknown).

    Uses the label text plus the input's own attributes (name, id, autocomplete,
    aria-label, placeholder) for robustness.
    """
    haystack = " ".join(filter(None, [
        label,
        attrs.get("name", ""),
        attrs.get("id", ""),
        attrs.get("autocomplete", ""),
        attrs.get("aria-label", ""),
        attrs.get("placeholder", ""),
        attrs.get("type", ""),
    ])).lower()

    # autocomplete hints are the strongest signal
    ac = attrs.get("autocomplete", "").lower()
    ac_map = {
        "email": "email",
        "given-name": "first_name",
        "family-name": "last_name",
        "name": "full_name",
        "tel": "phone",
        "tel-national": "phone",
        "address-line1": "address",
        "address-level2": "city",
        "postal-code": "postal_code",
        "country": "country",
    }
    for ac_key, semantic in ac_map.items():
        if ac_key == ac:
            return semantic

    if _has_any(haystack, EMAIL_PATTERNS):
        return "email"
    if _has_any(haystack, FIRST_NAME_PATTERNS):
        return "first_name"
    if _has_any(haystack, LAST_NAME_PATTERNS):
        return "last_name"
    if _has_any(haystack, FULL_NAME_PATTERNS):
        return "full_name"
    if _has_any(haystack, PHONE_PATTERNS):
        return "phone"
    if _has_any(haystack, POSTAL_PATTERNS):
        return "postal_code"
    if _has_any(haystack, CITY_PATTERNS):
        return "city"
    if _has_any(haystack, ADDRESS_PATTERNS):
        return "address"
    if _has_any(haystack, COUNTRY_PATTERNS):
        return "country"
    if _has_any(haystack, SALARY_PATTERNS):
        return "salary"
    if _has_any(haystack, NOTICE_PATTERNS):
        return "notice_period"
    if _has_any(haystack, EXPERIENCE_PATTERNS):
        return "experience_years"
    if _has_any(haystack, LINKEDIN_PATTERNS):
        return "linkedin"
    if _has_any(haystack, PORTFOLIO_PATTERNS):
        return "portfolio"
    if _has_any(haystack, GITHUB_PATTERNS):
        return "github"
    if _has_any(haystack, SPONSORSHIP_PATTERNS):
        return "sponsorship"
    if _has_any(haystack, WORK_AUTH_PATTERNS):
        return "work_authorization"
    return None


def value_for_semantic(semantic: str, profile: UserProfile) -> str:
    """Return the canonical answer for a resolved semantic key."""
    if semantic == "email":
        return profile.email
    if semantic == "first_name":
        return profile.first_name
    if semantic == "last_name":
        return profile.last_name
    if semantic == "full_name":
        return f"{profile.first_name} {profile.last_name}".strip()
    if semantic == "phone":
        return profile.phone_number
    if semantic == "postal_code":
        return profile.postal_code
    if semantic == "city":
        return profile.city
    if semantic == "address":
        return profile.address or profile.city
    if semantic == "country":
        return profile.country
    if semantic == "salary":
        return str(profile.salary_expectation_annual_eur)
    if semantic == "notice_period":
        return str(profile.notice_period_weeks)
    if semantic == "experience_years":
        return str(profile.total_years_experience)
    if semantic == "linkedin":
        return profile.linkedin_url or ""
    if semantic == "portfolio":
        return profile.portfolio_url or ""
    if semantic == "github":
        return profile.github_url or ""
    if semantic == "sponsorship":
        return "Non" if not profile.requires_sponsorship else "Oui"
    if semantic == "work_authorization":
        return "Oui" if profile.work_authorization_eu else "Non"
    return ""


# ---------------------------------------------------------------------------
# Form scanner
# ---------------------------------------------------------------------------

class ExternalFormFiller:
    """Fills a generic ATS application form on an arbitrary page."""

    def __init__(self, page: Page, bm=None):
        self.page = page
        self.bm = bm
        self.filled: Dict[str, str] = {}
        self.unresolved_fields: List[str] = []

    async def _attrs(self, loc: Locator) -> Dict[str, str]:
        attrs = {}
        for key in ["name", "id", "type", "autocomplete", "aria-label", "placeholder"]:
            try:
                v = await loc.get_attribute(key)
                if v:
                    attrs[key] = v
            except Exception:
                pass
        return attrs

    async def _label_for(self, loc: Locator) -> str:
        """Best-effort label text for an input."""
        try:
            inp_id = await loc.get_attribute("id") or ""
            if inp_id:
                lbl = self.page.locator(f"label[for='{inp_id}']").first
                if await lbl.count() > 0:
                    return (await lbl.inner_text()).strip()
            # climb to nearest parent container and read a label / legend
            parent = loc.locator("xpath=ancestor::div[1]")
            lbl = parent.locator("label, legend, .label, span").first
            if await lbl.count() > 0:
                txt = (await lbl.inner_text()).strip()
                if txt and len(txt) < 200:
                    return txt
        except Exception:
            pass
        return await loc.get_attribute("aria-label") or ""

    async def fill_inputs(self, profile: UserProfile) -> None:
        """Fill all visible text-like inputs, resolving semantics."""
        inputs = await self.page.locator(
            "input[type='text'], input[type='email'], input[type='tel'], "
            "input[type='number'], textarea, input:not([type])"
        ).all()
        for inp in inputs:
            try:
                if not await inp.is_visible() or await inp.is_disabled():
                    continue
                cur = await inp.input_value()
                if cur and cur.strip():
                    continue
                attrs = await self._attrs(inp)
                label = await self._label_for(inp)
                semantic = resolve_field_semantics(label, attrs, profile)
                if semantic:
                    val = value_for_semantic(semantic, profile)
                    if val:
                        await inp.fill(val)
                        self.filled[semantic] = val
                        logger.info(f"[External] filled '{semantic}' = {val[:40]}")
                        continue
                # record unresolved for later LLM/fallback
                key = label or attrs.get("name") or attrs.get("id") or "?"
                self.unresolved_fields.append(key)
            except Exception as e:
                logger.debug(f"[External] skip input: {e}")

    async def fill_selects(self, profile: UserProfile) -> None:
        """Set selects/comboboxes to sensible values for known semantics."""
        selects = await self.page.locator("select").all()
        for sel in selects:
            try:
                if not await sel.is_visible():
                    continue
                attrs = await self._attrs(sel)
                label = await self._label_for(sel)
                semantic = resolve_field_semantics(label, attrs, profile)
                options = await sel.locator("option").all_inner_texts()
                clean = [o.strip() for o in options if o.strip() and "select" not in o.lower() and "sélectionner" not in o.lower()]
                if not clean:
                    continue
                if semantic == "country":
                    want = profile.country.lower()
                    for o in clean:
                        if want in o.lower() or o.lower() in want:
                            await sel.select_option(label=o)
                            self.filled["country"] = o
                            break
                elif semantic == "sponsorship":
                    target = "non" if not profile.requires_sponsorship else "oui"
                    for o in clean:
                        if target in o.lower():
                            await sel.select_option(label=o)
                            self.filled["sponsorship"] = o
                            break
                elif semantic == "work_authorization":
                    target = "oui" if profile.work_authorization_eu else "non"
                    for o in clean:
                        if target in o.lower():
                            await sel.select_option(label=o)
                            self.filled["work_authorization"] = o
                            break
            except Exception as e:
                logger.debug(f"[External] skip select: {e}")

    async def upload_resume(self, cv_path: Optional[str], profile: UserProfile) -> bool:
        """Upload the tailored CV into the first visible file input."""
        resume = cv_path or profile.resume_path
        if not resume:
            return False
        resolved = Path(resume)
        if not resolved.is_absolute():
            resolved = (BASE_DIR / resolved).resolve()
        if not resolved.exists():
            return False
        file_inputs = await self.page.locator("input[type='file']").all()
        for finp in file_inputs:
            try:
                await finp.set_input_files(str(resolved))
                self.filled["resume"] = resolved.name
                logger.info(f"[External] uploaded resume: {resolved.name}")
                return True
            except Exception as e:
                logger.warning(f"[External] resume upload failed: {e}")
        return False

    def is_account_creation_form(self) -> bool:
        """Heuristic: page asks to create an account / sign up."""
        # synchronous text scan via page.content is not available here; the
        # caller passes a snapshot of body text.
        return False

    def is_email_verification_step(self, body_text: str) -> bool:
        t = body_text.lower()
        signals = ["verify", "verification", "vérifi", "confirmation code", "code de confirmation",
                   "check your email", "vérifiez votre", "entrez le code", "one-time", "otp", "6-digit", "6 chiffres"]
        return any(s in t for s in signals)


async def handle_email_verification(
    page: Page,
    body_text: str,
    profile: UserProfile,
    bm=None,
) -> Tuple[str, Optional[str]]:
    """Handle an email-verification step.

    Returns (status, code_or_link):
      - ("auto", code/link) if verification was completed automatically
      - ("skip", None)      if policy is to leave the application aside
      - ("unconfigured", None) if policy is auto but IMAP is not set up
    """
    cfg = settings.email_verification
    import os
    policy = os.getenv("EMAIL_VERIFICATION_POLICY") or cfg.verification_policy or "skip"
    if policy != "auto":
        logger.info("[External] Email verification policy=skip → leaving application aside.")
        return ("skip", None)

    if not email_verifier.is_configured:
        logger.warning("[External] Email verification policy=auto but IMAP not configured.")
        return ("unconfigured", None)

    # The verification email is triggered by the previous submit action; poll.
    code_or_link = await asyncio.to_thread(email_verifier.wait_for_code)
    if not code_or_link:
        logger.warning("[External] No verification code received within timeout.")
        return ("timeout", None)

    # If it's a link, navigate; else try to fill a code input.
    if code_or_link.startswith("http"):
        await page.goto(code_or_link, wait_until="domcontentloaded", timeout=30000)
        return ("auto", code_or_link)

    # Fill the code into the first short numeric input
    code_inputs = await page.locator("input[type='text'], input[type='number'], input:not([type])").all()
    for ci in code_inputs:
        try:
            if not await ci.is_visible():
                continue
            attrs = {}
            for key in ["name", "id", "aria-label", "placeholder"]:
                v = await ci.get_attribute(key)
                if v:
                    attrs[key] = v
            blob = " ".join(attrs.values()).lower()
            if any(s in blob for s in ["code", "otp", "pin", "verif", "vérif", "digit"]):
                await ci.fill(code_or_link)
                return ("auto", code_or_link)
        except Exception:
            pass
    return ("auto", code_or_link)


# ---------------------------------------------------------------------------
# Top-level external apply flow
# ---------------------------------------------------------------------------

async def run_external_apply(
    page: Page,
    job: Any,
    profile: UserProfile,
    cv_path: Optional[str],
    bm=None,
    cover_letter_text: Optional[str] = None,
) -> Dict[str, Any]:
    """Fill an external ATS application form (ATS-aware when possible).

    Detects the ATS and uses a dedicated strategy (Workday, Greenhouse, Lever,
    SmartRecruiters) with known selectors; falls back to the generic filler for
    unknown ATS. Returns a dict with `status`, `message`, `filled_fields`.
    """
    # 1. Wait for the page/form to be present
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=20000)
    except Exception:
        pass
    await asyncio.sleep(2.0)

    # 2. Detect block walls early
    try:
        body_text = (await page.locator("body").inner_text(timeout=5000))[:10000]
    except Exception:
        body_text = ""
    block = detect_block_reason(body_text, page.url)
    if block:
        raise PlatformBlockedError(f"Mur anti-bot détecté sur le site externe: '{block}'.")

    # 3. Detect ATS
    html = ""
    try:
        html = await page.content()
    except Exception:
        pass
    from core.browser.ats_detector import detect_ats
    ats_key = detect_ats(page.url, body_text, html)

    # 4. Email verification handling (common to all flows)
    async def _maybe_verify_email(filler) -> Optional[Dict[str, Any]]:
        if not filler.is_email_verification_step(body_text):
            return None
        status, code = await handle_email_verification(page, body_text, profile, bm)
        if status in ("skip", "unconfigured", "timeout"):
            return {
                "status": "requires_review",
                "message": f"Vérification email requise — laissée de côté ({status}).",
                "filled_fields": filler.filled,
            }
        return None

    # 5. ATS-specific strategy
    from core.browser.ats_strategies import get_strategy
    strategy = get_strategy(ats_key, page, profile, bm)
    if strategy is not None:
        strategy._job_title = getattr(job, "title", "") or ""
        strategy._company = getattr(job, "company", "") or ""
        if cover_letter_text:
            strategy._pending_cover_letter = cover_letter_text

        await strategy.open_apply_flow()
        # re-read body after opening flow (form may have changed)
        try:
            body_text = (await page.locator("body").inner_text(timeout=5000))[:10000]
        except Exception:
            pass

        # Create a lightweight filler for the email-verification heuristic
        checker = ExternalFormFiller(page, bm)
        verify_result = await _maybe_verify_email(checker)
        if verify_result:
            verify_result.setdefault("filled_fields", {})
            verify_result["filled_fields"].update(strategy.filled)
            return verify_result

        await strategy.fill()
        await strategy.upload_resume(cv_path)
        submitted = await strategy.submit()

        if submitted:
            return {
                "status": "applied",
                "message": f"Candidature externe soumise via {(ats_key or 'ats').upper()} ({len(strategy.filled)} champs remplis).",
                "filled_fields": strategy.filled,
            }
        return {
            "status": "requires_review",
            "message": f"Formulaire {(ats_key or 'ats').upper()} rempli mais soumission non confirmée.",
            "filled_fields": strategy.filled,
        }

    # 6. Generic fallback (unknown ATS)
    filler = ExternalFormFiller(page, bm)
    verify_result = await _maybe_verify_email(filler)
    if verify_result:
        return verify_result

    await filler.fill_inputs(profile)
    await filler.fill_selects(profile)
    await filler.upload_resume(cv_path, profile)

    submitted = await _try_submit(page, bm)
    if not submitted:
        return {
            "status": "requires_review",
            "message": "Formulaire externe rempli mais soumission non confirmée (bouton non trouvé).",
            "filled_fields": filler.filled,
        }

    return {
        "status": "applied",
        "message": f"Candidature externe soumise ({len(filler.filled)} champs remplis).",
        "filled_fields": filler.filled,
    }


async def _try_submit(page: Page, bm=None) -> bool:
    """Click a submit button, trying common labels."""
    submit_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Submit')",
        "button:has-text('Envoyer')",
        "button:has-text('Soumettre')",
        "button:has-text('Apply')",
        "button:has-text('Postuler')",
        "button:has-text('Send application')",
        "button:has-text('Envoyer ma candidature')",
        "a:has-text('Submit')",
        "a:has-text('Apply')",
    ]
    for sel in submit_selectors:
        try:
            btn = page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible():
                if bm and hasattr(bm, "human_click"):
                    await bm.human_click(btn)
                else:
                    await btn.click()
                await asyncio.sleep(2.0)
                return True
        except Exception:
            continue
    return False
