"""Central anti-ban rate limiter for platform automation.

Enforces per-platform daily application caps and minimum intervals between
searches and applications, with randomized jitter so pacing never looks
mechanical. Used by every apply/search path: 1-click, batch apply, watcher
auto-apply, CLI `run`, and the realtime scanner.

Keep this module free of top-level project imports (stdlib only) so it can be
imported from anywhere, including config/settings.py, without cycles.
"""
import asyncio
import logging
import random
import time
from typing import Dict, Optional

logger = logging.getLogger("RateLimiter")


class RateLimitExceeded(Exception):
    """Raised when a platform's daily apply quota has been reached."""


class PlatformBlockedError(Exception):
    """Raised when the platform shows a rate-limit, captcha, or security wall."""


# Common wall / limit / bot-detection signals across LinkedIn (FR + EN).
BLOCK_PHRASES = [
    "reached the limit",
    "you've reached the limit",
    "atteint votre limite",
    "atteinnt votre limite",
    "limite de candidatures",
    "too many requests",
    "trop de requêtes",
    "unusual activity",
    "activité inhabituelle",
    "activite inhabituelle",
    "security check",
    "vérification de sécurité",
    "verification de securite",
    "verify you're a real person",
    "confirmer que vous êtes",
    "confirmez que vous êtes",
    "checkpoint",
    "captcha",
    "we've detected automated behavior",
    "comportement automatisé",
    "comportement automatise",
    "you're doing that too much",
    "veillez réessayer plus tard",
    "please try again later",
    "temporary block",
    "blocage temporaire",
]


def detect_block_reason(text: str, url: str = "") -> Optional[str]:
    """Return a human-readable reason if the page looks like a block wall."""
    blob = f"{text or ''} {url or ''}".lower()
    for phrase in BLOCK_PHRASES:
        if phrase in blob:
            return phrase
    return None


class RateLimiter:
    """Tracks pacing and caps across all apply/search paths."""

    def __init__(self):
        self._apply_locks: Dict[str, asyncio.Lock] = {}
        self._search_locks: Dict[str, asyncio.Lock] = {}
        self._last_apply: Dict[str, float] = {}
        self._last_search: Dict[str, float] = {}
        self._daily_cap: Dict[str, int] = {}
        self._min_apply_interval: Dict[str, float] = {}
        self._min_search_interval: Dict[str, float] = {}

    def configure(
        self,
        platform: str,
        daily_cap: int,
        min_apply_interval: float,
        min_search_interval: float,
    ) -> None:
        self._daily_cap[platform] = daily_cap
        self._min_apply_interval[platform] = min_apply_interval
        self._min_search_interval[platform] = min_search_interval

    def daily_cap(self, platform: str) -> int:
        # Conservative default: assume the strictest platform unless configured.
        return self._daily_cap.get(platform, 10)

    def _apply_lock(self, platform: str) -> asyncio.Lock:
        if platform not in self._apply_locks:
            self._apply_locks[platform] = asyncio.Lock()
        return self._apply_locks[platform]

    def _search_lock(self, platform: str) -> asyncio.Lock:
        if platform not in self._search_locks:
            self._search_locks[platform] = asyncio.Lock()
        return self._search_locks[platform]

    async def wait_before_apply(self, platform: str, applied_today: int) -> None:
        """Block until it is safe to submit another application.

        Raises RateLimitExceeded if the daily cap has already been reached.
        `applied_today` must be the current DB count of applied records for
        the platform (caller queries it fresh at call time).
        """
        cap = self.daily_cap(platform)
        if applied_today >= cap:
            raise RateLimitExceeded(
                f"Quota journalier {platform} atteint ({applied_today}/{cap}) — "
                "candidature annulée pour protéger le compte."
            )

        async with self._apply_lock(platform):
            now = time.monotonic()
            base = self._min_apply_interval.get(platform, 45.0)
            elapsed = now - self._last_apply.get(platform, 0.0)
            if elapsed < base:
                # Randomized interval so spacing never looks mechanical.
                wait = random.uniform(base * 1.1, base * 1.6) - elapsed
                if wait > 0:
                    logger.info(
                        f"[RateLimiter] Pause {wait:.0f}s avant candidature "
                        f"{platform} (intervalle minimum {base:.0f}s respecté)."
                    )
                    await asyncio.sleep(wait)
            self._last_apply[platform] = time.monotonic()

    async def wait_before_search(self, platform: str) -> None:
        """Block until the minimum search interval has elapsed (serializes)."""
        async with self._search_lock(platform):
            now = time.monotonic()
            base = self._min_search_interval.get(platform, 20.0)
            elapsed = now - self._last_search.get(platform, 0.0)
            if elapsed < base:
                wait = (base - elapsed) + random.uniform(0.0, base * 0.5)
                if wait > 0:
                    logger.info(
                        f"[RateLimiter] Pause {wait:.0f}s avant recherche "
                        f"{platform}."
                    )
                    await asyncio.sleep(wait)
            self._last_search[platform] = time.monotonic()


rate_limiter = RateLimiter()


def configure_from_settings(s) -> None:
    """Wire limits from config.settings.Settings into the central limiter."""
    rl = s.rate_limit
    rate_limiter.configure(
        "linkedin",
        rl.linkedin_daily_apply_cap,
        rl.linkedin_min_apply_interval_seconds,
        rl.linkedin_min_search_interval_seconds,
    )
    rate_limiter.configure(
        "indeed",
        rl.indeed_daily_apply_cap,
        rl.min_apply_interval_seconds,
        rl.min_search_interval_seconds,
    )
    rate_limiter.configure(
        "francetravail",
        rl.francetravail_daily_apply_cap,
        rl.min_apply_interval_seconds,
        rl.min_search_interval_seconds,
    )
