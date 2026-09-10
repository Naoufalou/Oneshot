import abc
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from core.storage.db import db, ApplicationRecord
from config.settings import settings, UserProfile, SearchCriteria

logger = logging.getLogger("BasePlatform")


class JobPost(BaseModel):
    platform: str
    job_id: str
    title: str
    company: str
    location: str
    url: str
    is_easy_apply: bool = False
    description: Optional[str] = None


class BasePlatform(abc.ABC):
    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        self.db = db
        self.profile: UserProfile = settings.load_profile()
        self.criteria: SearchCriteria = settings.load_search_criteria()

    @abc.abstractmethod
    async def is_logged_in(self) -> bool:
        """Check if user session is currently authenticated."""
        pass

    @abc.abstractmethod
    async def search_jobs(self, query: str, location: str, limit: int = 15) -> List[JobPost]:
        """Scrapes matching job offers for the given query and location."""
        pass

    @abc.abstractmethod
    async def apply(self, job: JobPost, dry_run: bool = False) -> ApplicationRecord:
        """Fills and submits (or prepares) application for the given job."""
        pass

    async def run(self, max_applications: Optional[int] = None) -> List[ApplicationRecord]:
        """Main execution loop for this platform."""
        self.profile = settings.load_profile()
        self.criteria = settings.load_search_criteria()
        max_apps = max_applications or self.criteria.max_applications_per_day
        
        # Check daily quota
        already_applied_today = self.db.get_applications_count_today(self.platform_name)
        if already_applied_today >= max_apps:
            logger.info(f"Daily quota reached for {self.platform_name}: {already_applied_today}/{max_apps}")
            return []

        results: List[ApplicationRecord] = []

        for keyword in self.criteria.keywords:
            for loc in self.criteria.locations:
                if len(results) + already_applied_today >= max_apps:
                    break

                logger.info(f"Searching {self.platform_name} for '{keyword}' in '{loc}'...")
                try:
                    jobs = await self.search_jobs(keyword, loc)
                    for job in jobs:
                        if len(results) + already_applied_today >= max_apps:
                            break

                        if self.db.is_job_applied_or_skipped(self.platform_name, job.job_id):
                            logger.info(f"Skipping already processed job: {job.title} at {job.company}")
                            continue

                        # Execute application flow
                        record = await self.apply(job)
                        results.append(record)

                except Exception as e:
                    logger.error(f"Error during search loop for {keyword} - {loc}: {e}")

        return results
