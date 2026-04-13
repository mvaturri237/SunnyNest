"""Background scheduler for periodic scraping and notifications using APScheduler.

.. deprecated::
    This module is **deprecated** as of 2026-04-06. Scheduling has been
    migrated to macOS launchd agents for reliability:

    - ``com.sunnynest.scraper.plist`` — daily scrape at 06:00
    - ``com.sunnynest.notify-am.plist`` — morning notification at 08:00
    - ``com.sunnynest.notify-pm.plist`` — evening notification at 20:00

    Standalone entry points: ``scripts/run-scraper.py``, ``scripts/run-notify.py``.

    The ``ScrapeScheduler`` class is kept for backward compatibility but
    is no longer instantiated by ``web/main.py`` or ``app.py``.
    See ``plans/scheduler-fix.md`` for the full migration plan.

Legacy description:
    Runs the scraper orchestrator at a configurable interval (default: every
    6 hours) and a notification job at configurable hours (default: 8:00 AM
    and 8:00 PM Asia/Jerusalem) in daemon background threads so they do not
    block the Streamlit event loop.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.notifier import EmailChannel, NotificationService
from src.orchestrator import ScraperOrchestrator
from src.utils import load_config

logger = logging.getLogger("rental_finder.scheduler")


class ScrapeScheduler:
    """Manages periodic scrape and notification jobs via APScheduler.

    The scheduler runs in a daemon thread so it will not prevent the
    main process (e.g. Streamlit) from exiting.

    Jobs:

    - **Periodic scrape** — runs every *interval_hours* hours.
    - **Notification check** — runs at configurable hours (from
      ``notification_schedule`` in config.yaml), queries the local DB
      for unnotified listings, and dispatches via registered channels.

    Args:
        interval_hours: How often to run the scraper, in hours.
            Defaults to ``6``.
    """

    _JOB_ID = "periodic_scrape"
    _NOTIFICATION_JOB_ID = "notification_check"

    def __init__(self, interval_hours: int = 6) -> None:
        self.interval_hours = interval_hours
        self._scheduler = BackgroundScheduler(daemon=True)
        self._orchestrator = ScraperOrchestrator()
        self._last_run_time: datetime | None = None
        self._notification_service = NotificationService(channels=[EmailChannel()])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Add the scrape and notification jobs, then start the scheduler.

        Reads ``notification_schedule`` from config.yaml for cron hours
        and timezone.  Falls back to ``hours=[8, 20]`` and
        ``timezone="Asia/Jerusalem"`` if not configured.

        If the scheduler is already running this is a no-op.
        """
        if self._scheduler.running:
            logger.warning("Scheduler is already running.")
            return

        # --- Periodic scrape job ---
        self._scheduler.add_job(
            func=self._run_job,
            trigger="interval",
            hours=self.interval_hours,
            id=self._JOB_ID,
            replace_existing=True,
            name="Periodic rental scrape",
        )

        # --- Notification job (configurable schedule from config.yaml) ---
        try:
            config = load_config()
        except FileNotFoundError:
            config = {}
        ns = config.get("notification_schedule", {})
        hours = ",".join(str(h) for h in ns.get("hours", [8, 20]))
        tz = ns.get("timezone", "Asia/Jerusalem")

        self._scheduler.add_job(
            func=self._run_notification_job,
            trigger=CronTrigger(hour=hours, minute=0, timezone=tz),
            id=self._NOTIFICATION_JOB_ID,
            replace_existing=True,
            name="Scheduled notification check",
            max_instances=1,
        )

        self._scheduler.start()
        logger.info(
            "Scheduler started — scraping every %d hour(s), "
            "notifications at %s (%s).",
            self.interval_hours,
            hours,
            tz,
        )

    def stop(self) -> None:
        """Shut down the scheduler gracefully.

        If the scheduler is not running this is a no-op.
        """
        if not self._scheduler.running:
            logger.warning("Scheduler is not running — nothing to stop.")
            return

        self._scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")

    def run_now(self) -> None:
        """Trigger an immediate scrape in a background thread.

        The scrape runs in a separate daemon thread so it does not block
        the caller (e.g. a Streamlit button callback).
        """
        logger.info("Manual scrape triggered — running in background thread.")
        thread = threading.Thread(
            target=self._run_job,
            daemon=True,
            name="manual-scrape",
        )
        thread.start()

    def get_next_run_time(self) -> datetime | None:
        """Return the next scheduled scrape time, or ``None`` if not scheduled."""
        job = self._scheduler.get_job(self._JOB_ID)
        if job is not None:
            return job.next_run_time
        return None

    def get_last_run_time(self) -> datetime | None:
        """Return when the last scrape ran, or ``None`` if never."""
        return self._last_run_time

    def is_running(self) -> bool:
        """Return whether the background scheduler is currently active."""
        return self._scheduler.running

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_job(self) -> dict[str, Any]:
        """Execute the orchestrator's blocking scrape and log results.

        Returns:
            The summary dictionary from the orchestrator.
        """
        logger.info("Scheduled scrape starting …")
        try:
            summary = self._orchestrator.run_sync_blocking()
            self._last_run_time = datetime.now(timezone.utc)
            logger.info("Scheduled scrape finished: %s", summary)
            return summary
        except Exception:
            self._last_run_time = datetime.now(timezone.utc)
            logger.exception("Scheduled scrape failed with an unhandled error.")
            return {
                "total_scraped": 0,
                "new_listings": 0,
                "updated_listings": 0,
                "errors": 1,
            }

    def _run_notification_job(self) -> dict[str, Any]:
        """Run the notification service pipeline.

        Reuses the :class:`~src.notifier.NotificationService` instance
        created in ``__init__`` to execute the full notification flow
        (anti-spam → query → dispatch → mark → log).

        Returns:
            The summary dictionary from :meth:`NotificationService.run`.
        """
        logger.info("Scheduled notification check starting …")
        try:
            result = self._notification_service.run()
            logger.info("Notification check finished: %s", result)
            return result
        except Exception:
            logger.exception("Notification check failed with an unhandled error.")
            return {
                "listings_found": 0,
                "sent": False,
                "skipped_reason": "unhandled_error",
            }
