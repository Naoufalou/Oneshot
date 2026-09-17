import logging
from typing import List
from platforms.base import BasePlatform, JobPost
from core.browser.browser_manager import BrowserManager
from core.storage.db import ApplicationRecord, db
from .search import LinkedInSearcher
from .easy_apply import LinkedInEasyApply

logger = logging.getLogger("LinkedInPlatform")


class LinkedInPlatform(BasePlatform):
    def __init__(self):
        super().__init__(platform_name="linkedin")
        self.bm = BrowserManager(platform_name="linkedin")
        self.searcher = LinkedInSearcher(self.bm)
        self.applicant = LinkedInEasyApply(self.bm)

    async def is_logged_in(self) -> bool:
        if not self.bm.context:
            await self.bm.start()
        try:
            cookies = await self.bm.context.cookies()
            has_li_at = any(c.get("name") == "li_at" and len(c.get("value", "")) > 10 for c in cookies)
            if not has_li_at:
                return False
            page = self.bm.page or await self.bm.start()
            await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=25000)
            await self.bm.random_delay(1.0, 2.0)
            return "feed" in page.url and "login" not in page.url and "authwall" not in page.url
        except Exception as e:
            logger.debug(f"LinkedIn login check error: {e}")
            return False

    async def search_jobs(self, query: str, location: str, limit: int = 15) -> List[JobPost]:
        return await self.searcher.search(
            query=query,
            location=location,
            easy_apply_only=self.criteria.easy_apply_only,
            limit=limit,
        )

    async def apply(self, job: JobPost, dry_run: bool = False) -> ApplicationRecord:
        record = await self.applicant.apply_to_job(job, self.profile)
        self.db.save_or_update(record)
        return record

    async def close(self):
        await self.bm.close()


__all__ = ["LinkedInPlatform", "LinkedInSearcher", "LinkedInEasyApply"]
