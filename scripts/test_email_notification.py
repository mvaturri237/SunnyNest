#!/usr/bin/env python3
"""Test script for the email notification feature.

Sends a test email with dummy listing data to verify the email
notification pipeline works end-to-end.  Bypasses the normal
``NotificationService.run()`` flow (which queries the DB and has
anti-spam guards) by calling ``EmailChannel.send()`` directly.

Usage::

    # Preview only — generates HTML and saves to scripts/test_email_preview.html
    python scripts/test_email_notification.py --preview

    # Actually send the email via SMTP
    python scripts/test_email_notification.py --send

    # No flags → defaults to --preview behaviour
    python scripts/test_email_notification.py
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

from src.notifier import EmailChannel  # noqa: E402
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

PREVIEW_OUTPUT_PATH = Path(__file__).resolve().parent / "test_email_preview.html"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_config() -> dict[str, Any]:
    """Load the application config from ``config.yaml``.

    Returns:
        The full config dictionary.

    Raises:
        SystemExit: If the config file cannot be found.
    """
    try:
        return load_config()
    except FileNotFoundError:
        print("ERROR: config.yaml not found in the project root.")
        print("       Run this script from the project root directory.")
        sys.exit(1)


def _get_smtp_password(email_cfg: dict[str, Any]) -> str:
    """Return the SMTP password from env var or config fallback."""
    password = os.environ.get("SMTP_PASSWORD", "")
    if not password:
        password = email_cfg.get("sender_password", "")
    return password


def _get_recipient(email_cfg: dict[str, Any]) -> str:
    """Return the recipient email from env var or config fallback."""
    recipient = os.environ.get("NOTIFICATION_RECIPIENT", "")
    if not recipient:
        recipient = email_cfg.get("recipient_email", "")
    return recipient


def _verify_send_config(config: dict[str, Any]) -> bool:
    """Verify that all required config values are set for sending.

    Prints diagnostic messages for any missing values.

    Args:
        config: The full application config dictionary.

    Returns:
        ``True`` if all required values are present, ``False`` otherwise.
    """
    email_cfg: dict[str, Any] = config.get("email", {})
    ok = True

    sender = email_cfg.get("sender_email", "")
    if not sender:
        print("  ✗ sender_email is not set in config.yaml")
        ok = False
    else:
        print(f"  ✓ sender_email: {sender}")

    password = _get_smtp_password(email_cfg)
    if not password:
        print("  ✗ SMTP_PASSWORD env var is not set (and sender_password is empty in config)")
        ok = False
    else:
        source = "SMTP_PASSWORD env var" if os.environ.get("SMTP_PASSWORD") else "config.yaml"
        print(f"  ✓ SMTP password: set (via {source})")

    recipient = _get_recipient(email_cfg)
    if not recipient:
        print("  ✗ NOTIFICATION_RECIPIENT env var is not set (and recipient_email is empty in config)")
        ok = False
    else:
        source = "NOTIFICATION_RECIPIENT env var" if os.environ.get("NOTIFICATION_RECIPIENT") else "config.yaml"
        print(f"  ✓ recipient_email: {recipient} (via {source})")

    enabled = email_cfg.get("enabled", False)
    if not enabled:
        print("  ✗ email.enabled is False in config.yaml — EmailChannel.send() will refuse to send")
        ok = False
    else:
        print("  ✓ email.enabled: True")

    return ok


def _print_summary(listings: list[dict[str, Any]], recipient: str, mode: str) -> None:
    """Print a human-readable summary of what the script is about to do.

    Args:
        listings: The dummy listings to include.
        recipient: The resolved recipient email address.
        mode: Either ``"preview"`` or ``"send"``.
    """
    print()
    print("=" * 60)
    print("  SunnyNest — Email Notification Test")
    print("=" * 60)
    print()
    print(f"  Mode:       {'📧 SEND (live email)' if mode == 'send' else '👁  PREVIEW (HTML file only)'}")
    print(f"  Listings:   {len(listings)}")
    if mode == "send":
        print(f"  Recipient:  {recipient}")
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


def do_preview(config: dict[str, Any]) -> None:
    """Generate the HTML email body and save it to a local file.

    Args:
        config: The full application config dictionary.
    """
    dashboard_url: str = config.get("email", {}).get(
        "dashboard_url", "http://sunnynest:8000"
    )

    html = EmailChannel._build_html_body(DUMMY_LISTINGS, dashboard_url)

    PREVIEW_OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"✅ HTML preview saved to: {PREVIEW_OUTPUT_PATH}")
    print(f"   Open in browser: file://{PREVIEW_OUTPUT_PATH}")


def do_send(config: dict[str, Any]) -> None:
    """Send a real email via SMTP after user confirmation.

    Args:
        config: The full application config dictionary.
    """
    email_cfg: dict[str, Any] = config.get("email", {})
    recipient = _get_recipient(email_cfg)

    # --- Pre-flight checks ---
    print("Pre-flight checks:")
    all_ok = _verify_send_config(config)
    print()

    if not all_ok:
        print("❌ Cannot send — fix the issues above and try again.")
        sys.exit(1)

    # --- Confirmation prompt ---
    answer = input(
        f"Send test email with {len(DUMMY_LISTINGS)} dummy listing(s) to {recipient}? [y/N] "
    ).strip().lower()

    if answer != "y":
        print("Aborted.")
        return

    # --- Send ---
    print()
    channel = EmailChannel()
    success = channel.send(DUMMY_LISTINGS, config)

    if success:
        print(f"✅ Test email sent successfully to {recipient}.")
    else:
        print("❌ Failed to send test email. Check the logs above for details.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace with ``preview`` and ``send`` flags.
    """
    parser = argparse.ArgumentParser(
        description="Test the SunnyNest email notification feature with dummy listings.",
        epilog="If neither --preview nor --send is given, defaults to --preview.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--preview",
        action="store_true",
        help="Generate HTML email body and save to scripts/test_email_preview.html",
    )
    group.add_argument(
        "--send",
        action="store_true",
        help="Actually send the test email via SMTP",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point for the test email notification script."""
    args = parse_args()

    config = _resolve_config()
    email_cfg: dict[str, Any] = config.get("email", {})
    recipient = _get_recipient(email_cfg)

    # Default to preview if neither flag is given
    mode = "send" if args.send else "preview"

    _print_summary(DUMMY_LISTINGS, recipient, mode)

    if mode == "send":
        do_send(config)
    else:
        do_preview(config)


if __name__ == "__main__":
    main()
