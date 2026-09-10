import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx

from config.settings import settings, SearchCriteria, UserProfile
from core.storage.db import db, ApplicationRecord
from core.llm.job_evaluator import job_evaluator
from core.notifications.dispatcher import notification_dispatcher
from platforms.linkedin import LinkedInPlatform
from platforms.indeed import IndeedPlatform
from platforms.francetravail import FranceTravailPlatform

logger = logging.getLogger("WatcherService")



class WatcherService:
    def __init__(self):
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.last_run_time: Optional[str] = None
        self.total_detected_count: int = 0
        self.status_message: str = "En attente"

    async def start(self, interval_minutes: Optional[int] = None):
        if self.is_running:
            logger.info("WatcherService is already running.")
            return

        interval = interval_minutes or settings.watcher.interval_minutes or 30
        self.is_running = True
        self.status_message = f"Veille active (toutes les {interval} min)"
        logger.info(f"Starting WatcherService with interval of {interval} minutes.")
        self._task = asyncio.create_task(self._watch_loop(interval))

    async def stop(self):
        self.is_running = False
        self.status_message = "Veille arrêtée"
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("WatcherService stopped.")

    async def run_once(self) -> List[ApplicationRecord]:
        """Performs a single round of multi-platform search, AI evaluation and notifications."""
        self.status_message = "Cycle de veille en cours..."
        self.last_run_time = datetime.utcnow().isoformat()
        
        criteria = settings.load_search_criteria()
        profile = settings.load_profile()
        detected_jobs: List[ApplicationRecord] = []

        platforms_to_scan = settings.watcher.platforms or ["linkedin", "indeed", "francetravail"]
        logger.info(f"Running watch cycle on platforms: {platforms_to_scan}")

        for plat_name in platforms_to_scan:
            try:
                platform_instance = self._get_platform_instance(plat_name)
                if not platform_instance:
                    continue

                for keyword in criteria.keywords:
                    for location in criteria.locations:
                        logger.info(f"[Veille] {plat_name.upper()} ➜ '{keyword}' à '{location}'")
                        self.status_message = f"Veille {plat_name.upper()} : '{keyword}'"

                        try:
                            jobs = await platform_instance.search_jobs(keyword, location, limit=10)
                            for job in jobs:
                                # Check if already in DB
                                if db.is_job_applied_or_skipped(plat_name, job.job_id):
                                    continue

                                # Evaluate with LLM / Heuristics
                                eval_res = job_evaluator.evaluate_job(
                                    job_title=job.title,
                                    company=job.company,
                                    description=job.description or job.title,
                                    profile=profile,
                                    criteria=criteria,
                                )

                                if eval_res.is_match:
                                    record = ApplicationRecord(
                                        platform=plat_name,
                                        job_id=job.job_id,
                                        job_title=job.title,
                                        company=job.company,
                                        location=job.location,
                                        job_url=job.url,
                                        match_score=eval_res.score,
                                        match_reason=eval_res.rationale,
                                        status="detected",
                                    )
                                    db.save_or_update(record)
                                    detected_jobs.append(record)
                                    self.total_detected_count += 1

                                    # Send instant notification (Telegram, Discord)
                                    await notification_dispatcher.notify_new_job_opportunity(
                                        title=job.title,
                                        company=job.company,
                                        location=job.location,
                                        score=eval_res.score,
                                        rationale=eval_res.rationale,
                                        job_url=job.url,
                                        platform=plat_name,
                                    )

                                    # Check auto-apply on high match
                                    if settings.watcher.auto_apply_on_high_match and eval_res.score >= settings.watcher.high_match_threshold:
                                        logger.info(f"High match {eval_res.score}% >= {settings.watcher.high_match_threshold}% - Auto-applying...")
                                        await platform_instance.apply(job)

                        except Exception as e:
                            logger.error(f"Error in search iteration ({plat_name}, {keyword}): {e}")

                await platform_instance.close()

            except Exception as e:
                logger.error(f"Error processing platform {plat_name} in watcher: {e}")

        # --- AUTOMATIC CLEANUP OF CLOSED / INACTIVE JOBS ---
        cleanup_res = await self.clean_inactive_jobs()
        deleted_count = cleanup_res.get("deleted_count", 0)

        self.status_message = (
            f"Dernière veille terminée : {len(detected_jobs)} nouvelle(s) offre(s), "
            f"{deleted_count} offre(s) fermée(s) supprimée(s)"
        )
        return detected_jobs

    async def clean_inactive_jobs(self) -> Dict[str, Any]:
        """
        Scans existing unapplied jobs in the database and automatically deletes any that are
        closed, expired, 404, or no longer accepting applications.
        """
        self.status_message = "Vérification et suppression des offres expirées..."
        logger.info("[Nettoyage] Démarrage du scan des offres fermées / expirées...")

        jobs = db.list_applications(limit=500)
        # Protect already applied jobs, audit detected, skipped or failed records
        jobs_to_check = [j for j in jobs if j.get("status") != "applied"]

        if not jobs_to_check:
            return {"deleted_count": 0, "deleted_jobs": []}

        closed_phrases = [
            "no longer accepting applications",
            "n’accepte plus les candidatures",
            "n'accepte plus les candidatures",
            "cette offre d'emploi est expirée",
            "cette offre d’emploi est expirée",
            "cette offre est expirée",
            "cette offre n'est plus disponible",
            "cette offre n’est plus disponible",
            "cette offre d'emploi a expiré",
            "cette offre a expiré",
            "cet emploi n'est plus disponible",
            "cette offre d'emploi a été pourvue",
            "l'offre d'emploi recherchée n'est plus disponible",
            "offre clôturée",
            "cette offre a été clôturée",
            "this job has expired",
            "this job is no longer available",
        ]

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        async def check_single_job(client: httpx.AsyncClient, job: Dict[str, Any]):
            url = job.get("job_url") or ""
            jid = job["id"]
            title = job.get("job_title", "Offre sans titre")

            # Check mock/invalid URLs
            if not url or "test_" in url or "ft_9921" in url or "ind_7743" in url or "li_8832" in url:
                return (jid, title, True, "Lien de maquette ou offre de test")

            try:
                r = await client.get(url, timeout=6.0, follow_redirects=True)
                if r.status_code in [404, 410]:
                    return (jid, title, True, f"HTTP {r.status_code} (Page fermée ou introuvable)")

                text_lower = r.text.lower()
                for phrase in closed_phrases:
                    if phrase in text_lower:
                        return (jid, title, True, f"Mention détectée : {phrase}")

                return (jid, title, False, "Active")
            except Exception as e:
                # Do not delete on transient network failures
                return (jid, title, False, f"Erreur de réseau temporaire : {e}")

        deleted_records = []
        limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
        async with httpx.AsyncClient(headers=headers, limits=limits) as client:
            tasks = [check_single_job(client, j) for j in jobs_to_check]
            results = await asyncio.gather(*tasks)

        closed_ids = [res[0] for res in results if res[2]]
        for res in results:
            if res[2]:
                deleted_records.append({"id": res[0], "title": res[1], "reason": res[3]})

        if closed_ids:
            deleted_count = db.delete_applications_by_ids(closed_ids)
            logger.info(
                f"[Nettoyage] {deleted_count} offre(s) fermée(s) supprimée(s) de la base : "
                f"{[r['title'] for r in deleted_records]}"
            )
        else:
            deleted_count = 0

        return {"deleted_count": deleted_count, "deleted_jobs": deleted_records}

    def _get_platform_instance(self, name: str):
        name = name.lower()
        if name == "linkedin":
            return LinkedInPlatform()
        elif name == "indeed":
            return IndeedPlatform()
        elif name in ["francetravail", "france_travail", "ft"]:
            return FranceTravailPlatform()
        return None

    async def _watch_loop(self, interval_minutes: int):
        while self.is_running:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Error during watcher execution: {e}")

            # Sleep for interval
            logger.info(f"Watcher sleeping for {interval_minutes} minutes...")
            for _ in range(interval_minutes * 60):
                if not self.is_running:
                    break
                await asyncio.sleep(1)


watcher_service = WatcherService()
