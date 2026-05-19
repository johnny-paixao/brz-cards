"""
cache.py
========
Centralized in-memory cache for BigQuery data used by the BRz Cards bot.

Expiry logic:
    - Cache expires daily at 08:00 Europe/Lisbon.
    - After expiry, the first command call fetches fresh data from BigQuery.
    - Manual reset via /brzcards refresh-cache clears all cached data.

Separation:
    - This cache handles DATA only (BigQuery query results).
    - Image cache (assets/generated/) is managed separately by the card generator.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from database.bigquery_client import (
    get_all_card_players,
    get_ranking_players,
    get_ruler_data,
    get_stat_ranking,
)

logger = logging.getLogger("brzcards.cache")

LISBON_TZ = ZoneInfo("Europe/Lisbon")
CACHE_RESET_HOUR = 8  # 08:00 Europe/Lisbon


class BotDataCache:
    """Centralized in-memory cache for BigQuery data.

    All bot commands that read from BigQuery should go through this cache.
    The cache expires daily at 08:00 Europe/Lisbon, aligning with the
    GitHub Actions pipeline that updates BigQuery each morning.
    """

    def __init__(self) -> None:
        self._players: list[dict] | None = None
        self._ranking: list[dict] | None = None
        self._stat_rankings: dict[str, list[dict]] = {}
        self._ruler: list[dict] | None = None
        self._expires_at: datetime | None = None

    # ------------------------------------------------------------------
    # Expiry helpers
    # ------------------------------------------------------------------

    def _compute_next_expiry(self) -> datetime:
        """Compute the next 08:00 Europe/Lisbon after the current moment."""
        now_lisbon = datetime.now(LISBON_TZ)
        today_reset = now_lisbon.replace(
            hour=CACHE_RESET_HOUR, minute=0, second=0, microsecond=0,
        )
        if now_lisbon >= today_reset:
            return today_reset + timedelta(days=1)
        return today_reset

    def is_valid(self) -> bool:
        """Return True if the cache has not expired yet."""
        if self._expires_at is None:
            return False
        now_lisbon = datetime.now(LISBON_TZ)
        return now_lisbon < self._expires_at

    def _ensure_valid(self) -> None:
        """If the cache has expired, clear all data and set a new expiry."""
        if not self.is_valid():
            logger.info("Cache expired or uninitialised — clearing all data.")
            self._players = None
            self._ranking = None
            self._stat_rankings = {}
            self._ruler = None
            self._expires_at = self._compute_next_expiry()
            logger.info("New cache expiry: %s", self._expires_at.isoformat())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Manually clear all cached data (used by /brzcards refresh-cache)."""
        self._players = None
        self._ranking = None
        self._stat_rankings = {}
        self._ruler = None
        self._expires_at = None
        logger.info("Cache cleared manually via refresh-cache.")

    def get_or_fetch_players(self) -> list[dict]:
        """Return the list of all card players, fetching from BQ if needed."""
        self._ensure_valid()
        if self._players is None:
            logger.info("[BigQuery] Fetching all card players…")
            self._players = get_all_card_players()
            logger.info("[Cache] Players loaded: %d entries.", len(self._players))
        else:
            logger.info("[Cache HIT] Players — serving from cache.")
        return self._players

    def get_or_fetch_ranking(self) -> list[dict]:
        """Return the ranking data, fetching from BQ if needed."""
        self._ensure_valid()
        if self._ranking is None:
            logger.info("[BigQuery] Fetching ranking players…")
            self._ranking = get_ranking_players()
            logger.info("[Cache] Ranking loaded: %d entries.", len(self._ranking))
        else:
            logger.info("[Cache HIT] Ranking — serving from cache.")
        return self._ranking

    def get_or_fetch_stat_ranking(self, stat: str) -> list[dict]:
        """Return the ranking for a specific stat, fetching from BQ if needed."""
        self._ensure_valid()
        stat_upper = stat.upper()
        if stat_upper not in self._stat_rankings:
            logger.info("[BigQuery] Fetching stat ranking for %s…", stat_upper)
            self._stat_rankings[stat_upper] = get_stat_ranking(stat_upper)
            logger.info(
                "[Cache] Stat ranking %s loaded: %d entries.",
                stat_upper,
                len(self._stat_rankings[stat_upper]),
            )
        else:
            logger.info("[Cache HIT] Stat ranking %s — serving from cache.", stat_upper)
        return self._stat_rankings[stat_upper]

    def get_or_fetch_ruler(self) -> list[dict]:
        """Return the consolidated ruler data, fetching from BQ if needed."""
        self._ensure_valid()
        if self._ruler is None:
            logger.info("[BigQuery] Fetching ruler data…")
            self._ruler = get_ruler_data()
            logger.info("[Cache] Ruler loaded: %d entries.", len(self._ruler))
        else:
            logger.info("[Cache HIT] Ruler — serving from cache.")
        return self._ruler
