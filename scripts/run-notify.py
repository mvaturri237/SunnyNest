#!/usr/bin/env python3
"""Standalone notification entry point — called by launchd twice daily."""
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from src.database import init_db
from src.notifier import EmailChannel, WhatsAppChannel, NotificationService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sunnynest.notify-job")


def main() -> int:
    logger.info("=== Notification check at %s ===", datetime.now(timezone.utc).isoformat())
    init_db()
    service = NotificationService(channels=[EmailChannel(), WhatsAppChannel()])
    try:
        result = service.run()
        logger.info("Notification result: %s", result)
        return 0
    except Exception:
        logger.exception("Notification check failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
