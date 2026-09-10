import urllib.parse
import asyncio
import logging
from typing import List
from playwright.async_api import Page
from platforms.base import JobPost
from core.browser.browser_manager import BrowserManager

logger = logging.getLogger("LinkedInSearch")


class LinkedInSearcher:
    def __init__(self, browser_manager: BrowserManager):
        self.bm = browser_manager

    async def search(self, query: str, location: str = "France", easy_apply_only: bool = False, limit: int = 15) -> List[JobPost]:
        page: Page = await self.bm.start()

        # Build LinkedIn Search URL
        params = {
            "keywords": query,
            "location": location or "France",
            "position": "1",
            "pageNum": "0",
        }
        if easy_apply_only:
            params["f_AL"] = "true"

        search_url = f"https://www.linkedin.com/jobs/search?{urllib.parse.urlencode(params)}"
        logger.info(f"Navigating to LinkedIn search: {search_url}")

        try:
            await page.goto(search_url, wait_until="load", timeout=45000)
            await asyncio.sleep(2.0)

            # Wait for job list
            try:
                await page.wait_for_selector("div.base-search-card, li.job-card-container, ul.jobs-search__results-list li", timeout=15000)
            except Exception:
                pass

            cards = await page.locator("div.base-search-card, li.job-card-container, ul.jobs-search__results-list li").all()
            logger.info(f"Found {len(cards)} job cards on LinkedIn")

            results: List[JobPost] = []
            seen_ids = set()

            for card in cards:
                if len(results) >= limit:
                    break
                try:
                    title_elem = card.locator("h3.base-search-card__title, a.job-card-list__title, h3").first
                    if await title_elem.count() == 0:
                        continue
                    title = (await title_elem.inner_text()).strip()

                    link_elem = card.locator("a.base-card__full-link, a.job-card-list__title, a").first
                    href = await link_elem.get_attribute("href") if await link_elem.count() > 0 else ""
                    clean_url = href.split("?")[0] if href else ""
                    if clean_url and not clean_url.startswith("http"):
                        clean_url = f"https://www.linkedin.com{clean_url}"

                    job_id = ""
                    if "/view/" in clean_url:
                        parts = [p for p in clean_url.split("/") if p]
                        job_id = parts[-1].split("-")[-1] if "-" in parts[-1] else parts[-1]
                    else:
                        job_id = str(abs(hash(clean_url or title)))

                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    comp_elem = card.locator("h4.base-search-card__subtitle, a.hidden-nested-link, .job-card-container__company-name").first
                    company = (await comp_elem.inner_text()).strip() if await comp_elem.count() > 0 else "Entreprise"

                    loc_elem = card.locator("span.job-search-card__location, .job-card-container__metadata-item").first
                    loc = (await loc_elem.inner_text()).strip() if await loc_elem.count() > 0 else location

                    if title and len(title) > 2:
                        results.append(
                            JobPost(
                                platform="linkedin",
                                job_id=job_id,
                                title=title,
                                company=company,
                                location=loc,
                                url=clean_url or f"https://www.linkedin.com/jobs/view/{job_id}",
                                is_easy_apply=True,
                                description=f"{title} chez {company} ({loc})",
                            )
                        )
                except Exception as e:
                    logger.debug(f"Error parsing LinkedIn card: {e}")

            return results

        except Exception as e:
            logger.error(f"Error navigating LinkedIn search: {e}")
            return []
