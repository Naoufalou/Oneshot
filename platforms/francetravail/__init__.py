import logging
from typing import List
from platforms.base import BasePlatform, JobPost
from core.browser.browser_manager import BrowserManager
from core.storage.db import ApplicationRecord, db
from .search import FranceTravailSearcher
from .francetravail_apply import FranceTravailApply

logger = logging.getLogger("FranceTravailPlatform")


class FranceTravailPlatform(BasePlatform):
    def __init__(self):
        super().__init__(platform_name="francetravail")
        self.bm = BrowserManager(platform_name="francetravail")
        self.searcher = FranceTravailSearcher(self.bm)
        self.applicant = FranceTravailApply(self.bm)

    async def is_logged_in(self) -> bool:
        page = self.bm.page or await self.bm.start()
        try:
            await page.goto("https://candidat.francetravail.fr/espacecandidat/", wait_until="domcontentloaded", timeout=30000)
            await self.bm.random_delay(1.0, 2.0)
            return "connexion" not in page.url.lower() and "login" not in page.url.lower()
        except Exception:
            return False

    async def search_jobs(self, query: str, location: str = "France", limit: int = 15) -> List[JobPost]:
        return await self.searcher.search(query=query, location=location, limit=limit)

    async def apply(self, job: JobPost, dry_run: bool = False) -> ApplicationRecord:
        record = await self.applicant.apply_to_job(job, self.profile)
        self.db.save_or_update(record)
        return record

    async def close(self):
        await self.bm.close()


__all__ = ["FranceTravailPlatform", "FranceTravailSearcher", "FranceTravailApply"]
