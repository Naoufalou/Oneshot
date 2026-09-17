import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from config.settings import settings


class ApplicationRecord(BaseModel):
    id: Optional[int] = None
    platform: str
    job_id: str
    job_title: str
    company: str
    location: Optional[str] = None
    job_url: str
    match_score: Optional[int] = None
    match_reason: Optional[str] = None
    status: str = "found"  # found, evaluated, applied, skipped, failed, requires_review
    applied_at: Optional[str] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    form_answers: Optional[Dict[str, Any]] = None
    is_easy_apply: bool = True
    created_at: str = ""
    posted_at: Optional[str] = None
    posted_relative: Optional[str] = None

    def __init__(self, **data):
        if not data.get("created_at"):
            data["created_at"] = datetime.utcnow().isoformat()
        if not data.get("posted_at"):
            data["posted_at"] = data["created_at"]
        if not data.get("posted_relative"):
            data["posted_relative"] = "Récent"
        super().__init__(**data)


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
        except Exception:
            pass
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS job_applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    job_title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT,
                    job_url TEXT NOT NULL,
                    match_score INTEGER,
                    match_reason TEXT,
                    status TEXT NOT NULL,
                    applied_at TEXT,
                    error_message TEXT,
                    screenshot_path TEXT,
                    form_answers TEXT,
                    is_easy_apply INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    UNIQUE(platform, job_id)
                )
                """
            )
            # Migration check for existing databases lacking is_easy_apply column
            try:
                cursor.execute("ALTER TABLE job_applications ADD COLUMN is_easy_apply INTEGER DEFAULT 1")
            except sqlite3.OperationalError:
                pass  # column already exists

            try:
                cursor.execute("ALTER TABLE job_applications ADD COLUMN posted_at TEXT")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE job_applications ADD COLUMN posted_relative TEXT")
            except sqlite3.OperationalError:
                pass

            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_platform_job_id ON job_applications(platform, job_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_status ON job_applications(status)"
            )
            conn.commit()

    def is_job_applied_or_skipped(self, platform: str, job_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status FROM job_applications WHERE platform = ? AND job_id = ?",
                (platform, job_id),
            )
            row = cursor.fetchone()
            if row:
                return row["status"] in ["applied", "skipped", "requires_review"]
            return False

    def save_or_update(self, record: ApplicationRecord) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            answers_json = json.dumps(record.form_answers) if record.form_answers else None

            cursor.execute(
                """
                INSERT INTO job_applications (
                    platform, job_id, job_title, company, location, job_url,
                    match_score, match_reason, status, applied_at, error_message,
                    screenshot_path, form_answers, is_easy_apply, created_at,
                    posted_at, posted_relative
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, job_id) DO UPDATE SET
                    job_title=excluded.job_title,
                    company=excluded.company,
                    location=excluded.location,
                    job_url=excluded.job_url,
                    match_score=COALESCE(excluded.match_score, job_applications.match_score),
                    match_reason=COALESCE(excluded.match_reason, job_applications.match_reason),
                    status=excluded.status,
                    applied_at=COALESCE(excluded.applied_at, job_applications.applied_at),
                    error_message=excluded.error_message,
                    screenshot_path=COALESCE(excluded.screenshot_path, job_applications.screenshot_path),
                    form_answers=COALESCE(excluded.form_answers, job_applications.form_answers),
                    is_easy_apply=COALESCE(excluded.is_easy_apply, job_applications.is_easy_apply),
                    posted_at=COALESCE(excluded.posted_at, job_applications.posted_at),
                    posted_relative=COALESCE(excluded.posted_relative, job_applications.posted_relative)
                """,
                (
                    record.platform,
                    record.job_id,
                    record.job_title,
                    record.company,
                    record.location,
                    record.job_url,
                    record.match_score,
                    record.match_reason,
                    record.status,
                    record.applied_at,
                    record.error_message,
                    record.screenshot_path,
                    answers_json,
                    1 if record.is_easy_apply else 0,
                    record.created_at or datetime.utcnow().isoformat(),
                    record.posted_at or record.created_at or datetime.utcnow().isoformat(),
                    record.posted_relative or "Récent",
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_applications_count_today(self, platform: Optional[str] = None) -> int:
        today_prefix = datetime.utcnow().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if platform:
                cursor.execute(
                    """
                    SELECT COUNT(*) as count FROM job_applications
                    WHERE platform = ? AND status = 'applied' AND applied_at LIKE ?
                    """,
                    (platform, f"{today_prefix}%"),
                )
            else:
                cursor.execute(
                    """
                    SELECT COUNT(*) as count FROM job_applications
                    WHERE status = 'applied' AND applied_at LIKE ?
                    """,
                    (f"{today_prefix}%",),
                )
            row = cursor.fetchone()
            return row["count"] if row else 0

    def list_applications(
        self,
        status: Optional[str] = None,
        platform: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "relevance",
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM job_applications WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status)
        if platform:
            query += " AND platform = ?"
            params.append(platform)

        if sort_by == "relevance":
            query += """
                ORDER BY 
                    COALESCE(match_score, 0) DESC,
                    COALESCE(posted_at, created_at) DESC, 
                    id DESC 
                LIMIT ? OFFSET ?
            """
        else:
            query += """
                ORDER BY 
                    COALESCE(posted_at, created_at) DESC, 
                    id DESC 
                LIMIT ? OFFSET ?
            """
        params.extend([limit, offset])

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                if not item.get("posted_relative"):
                    item["posted_relative"] = "Récent"
                if item.get("form_answers"):
                    try:
                        item["form_answers"] = json.loads(item["form_answers"])
                    except Exception:
                        pass
                results.append(item)
            return results

    def get_unapplied_jobs(
        self,
        platform: Optional[str] = None,
        min_score: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM job_applications WHERE status != 'applied'"
        params: List[Any] = []

        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if min_score is not None and min_score > 0:
            query += " AND COALESCE(match_score, 0) >= ?"
            params.append(min_score)

        query += " ORDER BY COALESCE(match_score, 0) DESC, id DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_unapplied_count(
        self,
        platform: Optional[str] = None,
        min_score: Optional[int] = None,
    ) -> int:
        query = "SELECT COUNT(*) as count FROM job_applications WHERE status != 'applied'"
        params: List[Any] = []

        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if min_score is not None and min_score > 0:
            query += " AND COALESCE(match_score, 0) >= ?"
            params.append(min_score)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return row["count"] if row else 0

    def get_applied_count(
        self,
        platform: Optional[str] = None,
    ) -> int:
        query = "SELECT COUNT(*) as count FROM job_applications WHERE status = 'applied'"
        params: List[Any] = []
        if platform:
            query += " AND platform = ?"
            params.append(platform)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return row["count"] if row else 0

    def get_application_by_id(self, application_id: int) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job_applications WHERE id = ?", (application_id,))
            row = cursor.fetchone()
            if row:
                item = dict(row)
                if item.get("form_answers"):
                    try:
                        item["form_answers"] = json.loads(item["form_answers"])
                    except Exception:
                        pass
                return item
            return None

    def update_status(self, application_id: int, status: str, error_message: Optional[str] = None):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            applied_at = datetime.utcnow().isoformat() if status == "applied" else None
            cursor.execute(
                """
                UPDATE job_applications
                SET status = ?, error_message = ?, applied_at = COALESCE(?, applied_at)
                WHERE id = ?
                """,
                (status, error_message, applied_at, application_id),
            )
            conn.commit()

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM job_applications")
            total = cursor.fetchone()["total"]

            cursor.execute("SELECT status, COUNT(*) as count FROM job_applications GROUP BY status")
            status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

            cursor.execute("SELECT platform, COUNT(*) as count FROM job_applications GROUP BY platform")
            platform_counts = {row["platform"]: row["count"] for row in cursor.fetchall()}

            today_applied = self.get_applications_count_today()

            return {
                "total_records": total,
                "today_applied": today_applied,
                "status_breakdown": status_counts,
                "platform_breakdown": platform_counts,
            }

    def delete_application(self, application_id: int) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM job_applications WHERE id = ?", (application_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_applications_by_ids(self, ids: List[int]) -> int:
        if not ids:
            return 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(ids))
            cursor.execute(f"DELETE FROM job_applications WHERE id IN ({placeholders})", ids)
            conn.commit()
            return cursor.rowcount



db = Database()
