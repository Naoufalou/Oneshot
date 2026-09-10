"""ATS (Applicant Tracking System) detection.

Identifies which external ATS is hosting a job application so the external
form filler can apply ATS-specific selectors and flows. URL detection is the
strongest signal; DOM heuristics are the fallback.

Known ATS: Workday, Greenhouse, Lever, SmartRecruiters, Taleo, SuccessFactors,
iCIMS, Jobvite, Recruitee, BambooHR, plus a generic fallback.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger("ATSDetector")

# URL host/fragment markers → ATS key (ordered, first match wins)
URL_MARKERS = [
    ("workday", ["myworkdayjobs.com", "workday", "wd1.myworkday"]),
    ("greenhouse", ["greenhouse.io", "greenhouse-api", "boards.greenhouse"]),
    ("lever", ["jobs.lever.co", "lever.co"]),
    ("smartrecruiters", ["smartrecruiters.com", "jobs.smartrecruiters"]),
    ("taleo", ["taleo.net", "tbe.taleo"]),
    ("successfactors", ["successfactors.com", "successfactors.eu", "jobs2.sapsf"]),
    ("icims", ["icims.com"]),
    ("jobvite", ["jobvite.com"]),
    ("recruitee", ["recruitee.com"]),
    ("bamboohr", ["bamboohr.com"]),
    ("ashby", ["jobs.ashbyhq.com", "ashbyhq.com"]),
    ("applytojob", ["applytojob.com"]),
]


def detect_ats(url: str, body_text: str = "", html: str = "") -> Optional[str]:
    """Return the ATS key (or None for generic/unknown)."""
    url_lower = (url or "").lower()

    # 1. URL detection (most reliable)
    for key, markers in URL_MARKERS:
        for m in markers:
            if m in url_lower:
                logger.info(f"[ATS] detected '{key}' via URL marker '{m}'")
                return key

    # 2. DOM heuristics
    html_lower = (html or "").lower()
    body_lower = (body_text or "").lower()

    if 'data-automation-id' in html_lower:
        logger.info("[ATS] detected 'workday' via data-automation-id attribute")
        return "workday"

    if 'greenhouse' in html_lower or 'greenhouse' in body_lower:
        logger.info("[ATS] detected 'greenhouse' via DOM")
        return "greenhouse"

    if 'jobs.lever' in html_lower or 'lever' in url_lower:
        logger.info("[ATS] detected 'lever' via DOM")
        return "lever"

    if 'smartrecruiters' in html_lower:
        logger.info("[ATS] detected 'smartrecruiters' via DOM")
        return "smartrecruiters"

    if 'taleo' in html_lower:
        logger.info("[ATS] detected 'taleo' via DOM")
        return "taleo"

    return None


# --- Per-ATS known selectors (kept here so strategies stay data-driven) ---

WORKDAY_SELECTORS = {
    # data-automation-id values for common fields
    "email": "[data-automation-id='email']",
    "first_name": "[data-automation-id='legalNameSection_firstName'], [data-automation-id='firstName']",
    "last_name": "[data-automation-id='legalNameSection_lastName'], [data-automation-id='lastName']",
    "phone": "[data-automation-id='phone-number'], [data-automation-id='phoneNumber']",
    "address": "[data-automation-id='addressSection_addressLine1']",
    "city": "[data-automation-id='addressSection_city']",
    "postal_code": "[data-automation-id='addressSection_postalCode']",
    "country": "[data-automation-id='addressSection_countryRegion']",
    # Buttons
    "continue": "button[data-automation-id='bottom-navigation-next-button'], button[data-automation-id='nextButton']",
    "submit": "button[data-automation-id='bottom-navigation-next-button'], button[data-automation-id='submit']",
    "apply": "button[data-automation-id='applyManually'], button[data-automation-id='applyNow']",
    "upload": "input[type='file'], [data-automation-id='file-upload-input']",
}

GREENHOUSE_SELECTORS = {
    "first_name": "#first_name, input[name='job_application[first_name]']",
    "last_name": "#last_name, input[name='job_application[last_name]']",
    "email": "#email, input[name='job_application[email]']",
    "phone": "#phone, input[name='job_application[phone]']",
    "linkedin": "#urls_linkedin, input[name='job_application[urls][linkedin]']",
    "portfolio": "#urls_portfolio, input[name='job_application[urls][portfolio]']",
    "resume": "#resume_text, input[name='job_application[resume]']",
    "cover_letter": "#cover_letter_text, textarea[name='job_application[cover_letter_text]']",
    "submit": "#submit_app, button[type='submit']",
}

LEVER_SELECTORS = {
    "name": "input[name='name']",
    "email": "input[name='email']",
    "phone": "input[name='phone']",
    "linkedin": "input[name='urls[LinkedIn]']",
    "portfolio": "input[name='urls[Portfolio]']",
    "resume": "input[name='resume'], input[type='file']",
    "submit": "button[type='submit']:has-text('Submit'), button[type='submit']:has-text('Apply'), button[type='submit']",
}

SMARTRECRUITERS_SELECTORS = {
    "first_name": "input[name='firstName'], input[name='firstname']",
    "last_name": "input[name='lastName'], input[name='lastname']",
    "email": "input[name='email']",
    "phone": "input[name='phoneNumber'], input[name='phone']",
    "resume": "input[type='file']",
    "submit": "button[type='submit'], button:has-text('Apply')",
}


def selectors_for(ats_key: str) -> dict:
    """Return the known-selector map for an ATS key (empty dict if generic)."""
    return {
        "workday": WORKDAY_SELECTORS,
        "greenhouse": GREENHOUSE_SELECTORS,
        "lever": LEVER_SELECTORS,
        "smartrecruiters": SMARTRECRUITERS_SELECTORS,
    }.get(ats_key, {})
