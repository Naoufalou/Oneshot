import urllib.parse
import logging
from typing import List
from playwright.async_api import Page
from platforms.base import JobPost
from core.browser.browser_manager import BrowserManager

logger = logging.getLogger("IndeedSearch")


class IndeedSearcher:
    def __init__(self, browser_manager: BrowserManager):
        self.bm = browser_manager

    async def search(self, query: str, location: str = "France", limit: int = 15) -> List[JobPost]:
        page: Page = self.bm.page or await self.bm.start()

        # Format URL for Indeed France
        params = {
            "q": query,
            "l": location or "France",
        }
        search_url = f"https://fr.indeed.com/jobs?{urllib.parse.urlencode(params)}"
        logger.info(f"Navigating to Indeed search: {search_url}")

        try:
            await page.goto(search_url, wait_until="domcontentloaded", timeout=45000)
            await self.bm.random_delay(2.5, 4.0)

            # Accept cookies if banner present
            cookie_btn = page.locator("#onetrust-accept-btn-handler, button:has-text('Accepter tout'), button:has-text('Accept All')").first
            if await cookie_btn.count() > 0:
                try:
                    await cookie_btn.click()
                    await self.bm.random_delay(0.5, 1.0)
                except Exception:
                    pass

            cards = await page.locator("div.job_seen_beacon, td.resultContent").all()
            logger.info(f"Found {len(cards)} job cards on Indeed")

            results: List[JobPost] = []
            seen_ids = set()

            for card in cards:
                if len(results) >= limit:
                    break
                try:
                    title_elem = card.locator("h2.jobTitle, a[data-jk]").first
                    if await title_elem.count() == 0:
                        continue

                    title = (await title_elem.inner_text()).strip()
                    job_id = await title_elem.get_attribute("data-jk") or ""
                    
                    if not job_id:
                        link_elem = card.locator("a[data-jk], a[href*='jk='], a.jcs-JobTitle").first
                        if await link_elem.count() > 0:
                            job_id = await link_elem.get_attribute("data-jk") or ""
                            if not job_id:
                                href = await link_elem.get_attribute("href") or ""
                                if "jk=" in href:
                                    job_id = href.split("jk=")[1].split("&")[0]

                    clean_id = job_id or str(abs(hash(title + location)))
                    if clean_id in seen_ids:
                        continue
                    seen_ids.add(clean_id)

                    full_url = f"https://fr.indeed.com/viewjob?jk={clean_id}" if job_id else f"https://fr.indeed.com/jobs?q={urllib.parse.quote(title)}"

                    # Company
                    comp_elem = card.locator("[data-testid='company-name'], span.companyName, .companyName").first
                    company = (await comp_elem.inner_text()).strip() if await comp_elem.count() > 0 else "Entreprise"

                    # Location
                    loc_elem = card.locator("[data-testid='text-location'], .companyLocation").first
                    loc = (await loc_elem.inner_text()).strip() if await loc_elem.count() > 0 else location

                    # Easy apply check
                    badge = card.locator("[data-testid='indeedApply'], span:has-text('Candidature facile'), span:has-text('Easily apply')").first
                    is_easy_apply = (await badge.count() > 0)

                    if title and len(title) > 2:
                        results.append(
                            JobPost(
                                platform="indeed",
                                job_id=clean_id,
                                title=title,
                                company=company,
                                location=loc,
                                url=full_url,
                                is_easy_apply=is_easy_apply,
                                description=f"{title} chez {company} ({loc})",
                            )
                        )

                except Exception as e:
                    logger.debug(f"Error parsing Indeed card: {e}")

            return results

        except Exception as e:
            logger.error(f"Error searching on Indeed: {e}")
            return []
