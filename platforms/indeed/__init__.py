import logging
from typing import List
from platforms.base import BasePlatform, JobPost
from core.browser.browser_manager import BrowserManager
from core.storage.db import ApplicationRecord, db
from .search import IndeedSearcher
from .indeed_apply import IndeedApply

logger = logging.getLogger("IndeedPlatform")


class IndeedPlatform(BasePlatform):
    def __init__(self):
        super().__init__(platform_name="indeed")
        self.bm = BrowserManager(platform_name="indeed")
        self.searcher = IndeedSearcher(self.bm)
        self.applicant = IndeedApply(self.bm)

    async def is_logged_in(self) -> bool:
        page = self.bm.page or await self.bm.start()
        try:
            await page.goto("https://fr.indeed.com/", wait_until="domcontentloaded", timeout=30000)
            await self.bm.random_delay(1.5, 2.5)
            account_btn = page.locator("[data-gnav-element-name='AccountMenu'], [aria-label*='Compte'], [aria-label*='Account']").first
            return await account_btn.count() > 0
        except Exception as e:
            logger.debug(f"Indeed login check error: {e}")
            return False

    async def search_jobs(self, query: str, location: str, limit: int = 15) -> List[JobPost]:
        return await self.searcher.search(query=query, location=location, limit=limit)

    async def apply(self, job: JobPost, dry_run: bool = False) -> ApplicationRecord:
        record = await self.applicant.apply_to_job(job, self.profile)
        self.db.save_or_update(record)
        return record

    async def close(self):
        await self.bm.close()


__all__ = ["IndeedPlatform", "IndeedSearcher", "IndeedApply"]
