#!/usr/bin/env python3
"""Standalone scraper entry point — called by launchd daily.

Runs all scrapers via ScraperOrchestrator.run_sync_blocking(),
logs results, and exits. No web server, no APScheduler.
"""
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from src.database import init_db
from src.orchestrator import ScraperOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sunnynest.scraper-job")


def main() -> int:
    logger.info("=== Daily scrape starting at %s ===", datetime.now(timezone.utc).isoformat())
    init_db()
    orchestrator = ScraperOrchestrator()
    try:
        summary = orchestrator.run_sync_blocking()
        logger.info("Scrape complete: %s", summary)
        return 0
    except Exception:
        logger.exception("Scrape failed with unhandled error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
