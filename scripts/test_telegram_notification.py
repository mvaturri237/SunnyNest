#!/usr/bin/env python3
"""End-to-end test for the Telegram notification channel.

Sends a test Telegram message with dummy listing data to verify the
notification pipeline works.  Bypasses the normal
``NotificationService.run()`` flow (which queries the DB and has
anti-spam guards) by calling ``TelegramChannel.send_with_diagnostics()``
directly.

Usage::

    # Preview only — print the rendered HTML body to stdout
    python scripts/test_telegram_notification.py --preview

    # Actually send the test message via the Telegram Bot API
    python scripts/test_telegram_notification.py --send

    # No flags → defaults to --preview behaviour
    python scripts/test_telegram_notification.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Ensure the project root is on sys.path so ``from src.…`` imports work
# when running the script from the project root directory.
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load .env so TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are picked up.
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from src.notifier import TelegramChannel  # noqa: E402
from src.utils import load_config, setup_logging  # noqa: E402

logger = setup_logging()

# ---------------------------------------------------------------------------
# Dummy listing data
# ---------------------------------------------------------------------------

DUMMY_LISTINGS: list[dict[str, Any]] = [
    {
        "title": "Spacious 4BR Family Home with Large Backyard",
        "price": 5800,
        "bedrooms": 4,
        "sqft": 2100,
        "address": "742 Sunnyvale Ave, Sunnyvale, CA 94086",
        "url": "https://example.com/listing/1",
        "source": "zillow",
    },
    {
        "title": "Charming 3BR Ranch-Style House Near Downtown",
        "price": 5200,
        "bedrooms": 3,
        "sqft": 1650,
        "address": "1580 Hollenbeck Ave, Sunnyvale, CA 94087",
        "url": "https://example.com/listing/2",
        "source": "craigslist",
    },
    {
        "title": "Renovated 4BR Home with Modern Kitchen & 2-Car Garage",
        "price": 6400,
        "bedrooms": 4,
        "sqft": 2350,
        "address": "385 S Mary Ave, Sunnyvale, CA 94085",
        "url": "https://example.com/listing/3",
        "source": "zillow",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_config() -> dict[str, Any]:
    """Load the application config, defaulting to an enabled-Telegram view."""
    try:
        config = load_config()
    except FileNotFoundError:
        print("ERROR: config.yaml not found in the project root.")
        print("       Run this script from the project root directory.")
        sys.exit(1)

    # For the test script we want to bypass the disabled flag in
    # config.yaml (the user may not have flipped it true yet).
    config.setdefault("telegram", {})
    config["telegram"]["enabled"] = True
    config["telegram"].setdefault("parse_mode", "HTML")
    return config


def _verify_send_config() -> bool:
    """Verify that all env vars are set for sending. Print diagnostics."""
    ok = True
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not token:
        print("  ✗ TELEGRAM_BOT_TOKEN env var is not set")
        ok = False
    else:
        print(f"  ✓ TELEGRAM_BOT_TOKEN: set (length={len(token)})")

    if not chat_id:
        print("  ✗ TELEGRAM_CHAT_ID env var is not set")
        ok = False
    else:
        masked = ("…" + chat_id[-4:]) if len(chat_id) > 4 else "…"
        print(f"  ✓ TELEGRAM_CHAT_ID: {masked} (full length={len(chat_id)})")

    if token:
        # Validate the token before attempting to send.
        print()
        print("  Validating token via getMe …")
        result = TelegramChannel.validate_token(timeout=10.0)
        if result.success:
            print("  ✓ getMe returned 200 — token is valid")
        else:
            print(f"  ✗ getMe failed: [{result.error_category}] {result.error_message}")
            ok = False

    return ok


def _print_summary(listings: list[dict[str, Any]], mode: str) -> None:
    """Print a human-readable summary of what the script is about to do."""
    print()
    print("=" * 60)
    print("  SunnyNest — Telegram Notification Test")
    print("=" * 60)
    print()
    print(f"  Mode:       {'💬 SEND (live message)' if mode == 'send' else '👁  PREVIEW (HTML body only)'}")
    print(f"  Listings:   {len(listings)}")
    print()
    print("  Listings to include:")
    for i, listing in enumerate(listings, 1):
        print(f"    {i}. {listing['title']}")
        print(f"       ${listing['price']:,}/mo · {listing['bedrooms']}BR · {listing['sqft']:,} sqft")
        print(f"       {listing['address']} [{listing['source']}]")
    print()


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def do_preview() -> None:
    """Render the message body to stdout (no network call)."""
    channel = TelegramChannel()
    body = channel._build_text_body(DUMMY_LISTINGS)
    print("--- Telegram message body (HTML, parse_mode=HTML) ---")
    print(body)
    print("--- end of body ---")
    print(f"\nLength: {len(body)} chars (limit: 4096, budget: 4000)")


def do_send(config: dict[str, Any]) -> None:
    """Send a real Telegram message after pre-flight checks + confirmation."""
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    print("Pre-flight checks:")
    if not _verify_send_config():
        print()
        print("❌ Cannot send — fix the issues above and try again.")
        sys.exit(1)
    print()

    masked = ("…" + chat_id[-4:]) if len(chat_id) > 4 else "…"
    answer = input(
        f"Send test Telegram message with {len(DUMMY_LISTINGS)} dummy listing(s) "
        f"to chat_id={masked}? [y/N] "
    ).strip().lower()
    if answer != "y":
        print("Aborted.")
        return

    print()
    channel = TelegramChannel()
    result = channel.send_with_diagnostics(DUMMY_LISTINGS, config)

    if result.success:
        print(f"✅ Test Telegram message sent successfully to chat_id={masked}.")
    else:
        print(
            f"❌ Failed to send test Telegram message: "
            f"[{result.error_category}] {result.error_message}"
        )
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Test the SunnyNest Telegram notification feature with "
            "dummy listings."
        ),
        epilog="If neither --preview nor --send is given, defaults to --preview.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--preview",
        action="store_true",
        help="Render the HTML message body to stdout (no network)",
    )
    group.add_argument(
        "--send",
        action="store_true",
        help="Actually send the test message via the Telegram Bot API",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the test Telegram notification script."""
    args = parse_args()
    mode = "send" if args.send else "preview"

    _print_summary(DUMMY_LISTINGS, mode)

    if mode == "send":
        config = _resolve_config()
        do_send(config)
    else:
        do_preview()


if __name__ == "__main__":
    main()
