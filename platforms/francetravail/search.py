import urllib.parse
import asyncio
import logging
from typing import List
from playwright.async_api import Page
from platforms.base import JobPost
from core.browser.browser_manager import BrowserManager

logger = logging.getLogger("FranceTravailSearch")


class FranceTravailSearcher:
    def __init__(self, browser_manager: BrowserManager):
        self.bm = browser_manager

    async def search(self, query: str, location: str = "France", limit: int = 15) -> List[JobPost]:
        page: Page = await self.bm.start()

        # Format location for France Travail (e.g. Paris = 75D, Île-de-France = 11R, or empty for France)
        loc_code = ""
        loc_lower = (location or "").lower()
        if "paris" in loc_lower or "75" in loc_lower:
            loc_code = "75D"
        elif "île-de-france" in loc_lower or "ile de france" in loc_lower or "idf" in loc_lower:
            loc_code = "11R"
        elif "lyon" in loc_lower or "69" in loc_lower:
            loc_code = "69D"
        elif "marseille" in loc_lower or "13" in loc_lower:
            loc_code = "13D"
        elif "toulouse" in loc_lower or "31" in loc_lower:
            loc_code = "31D"

        params = {
            "motsCles": query,
            "offresPartenaires": "true",
            "tri": "0",
        }
        if loc_code:
            params["lieux"] = loc_code

        search_url = f"https://candidat.francetravail.fr/offres/recherche?{urllib.parse.urlencode(params)}"
        logger.info(f"Navigating to France Travail search: {search_url}")

        try:
            await page.goto(search_url, wait_until="load", timeout=45000)
            await page.wait_for_selector("li.result", timeout=20000)

            cards = await page.locator("li.result").all()
            logger.info(f"Found {len(cards)} job cards on France Travail")

            results: List[JobPost] = []

            for card in cards[:limit]:
                try:
                    id_offre = await card.get_attribute("data-id-offre")
                    link = card.locator("a").first
                    href = await link.get_attribute("href") if await link.count() > 0 else ""
                    
                    if not id_offre and href and "detail/" in href:
                        id_offre = href.split("detail/")[1].split("?")[0].split("/")[0]

                    clean_id = id_offre or str(abs(hash(href or query)))
                    full_url = f"https://candidat.francetravail.fr/offres/recherche/detail/{clean_id}"

                    card_text = await card.inner_text()
                    lines = [l.strip() for l in card_text.splitlines() if l.strip()]

                    title = lines[0] if len(lines) > 0 else ""
                    comp_loc = lines[1] if len(lines) > 1 else ""
                    snippet = lines[2] if len(lines) > 2 else ""

                    # Split company and location
                    company = "France Travail"
                    loc_extracted = location or "France"
                    if " - " in comp_loc:
                        parts = comp_loc.split(" - ")
                        company = parts[0].strip()
                        loc_extracted = " - ".join(parts[1:]).strip()
                    elif comp_loc:
                        company = comp_loc

                    if title:
                        results.append(
                            JobPost(
                                platform="francetravail",
                                job_id=clean_id,
                                title=title,
                                company=company,
                                location=loc_extracted,
                                url=full_url,
                                is_easy_apply=True,
                                description=f"{title}\n{company} - {loc_extracted}\n{snippet}",
                            )
                        )

                except Exception as e:
                    logger.debug(f"Error parsing France Travail card: {e}")

            return results

        except Exception as e:
            logger.error(f"Error searching on France Travail: {e}")
            return []
