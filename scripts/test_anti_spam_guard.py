"""Regression test for the anti-spam guard counting only successful sends.

Background
----------
On 2026-06-03 the user noticed a 7-day Telegram notification silence
(May 27 → Jun 3).  Root cause: ``get_today_notification_count()`` was
counting **all** rows in ``notification_log`` for the current day,
including failures.  Two morning network failures consumed the 2-send
daily cap, and the evening run was silently skipped with
``skipped_reason='daily_limit_reached'`` — even though the network had
recovered by then.

The fix is a one-line change to the function: filter on
``NotificationLog.success == True``.  Failed attempts are never
delivered to the recipient, so they should not count toward the
"already sent N today" anti-spam ceiling.

This test asserts the new behavior end-to-end against an in-memory
SQLite database and an in-process call to
:func:`src.database.get_today_notification_count`.

Run::

    python scripts/test_anti_spam_guard.py

Exit code 0 = pass, 1 = fail.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

# Ensure project root is importable when run as ``python scripts/test_anti_spam_guard.py``
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import src.database as database_module
from src.database import get_today_notification_count, log_notification
from src.models import Base, NotificationLog


_IST = timezone(timedelta(hours=3))  # Asia/Jerusalem; matches the function under test


def _setup_in_memory_db() -> None:
    """Replace the module-level engine + session factory with in-memory SQLite."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(engine)
    database_module._engine = engine
    database_module._SessionFactory = sessionmaker(bind=engine)


def _insert_log_row(
    *,
    success: bool,
    channel: str = "email",
    when: datetime | None = None,
    error_category: str | None = None,
) -> None:
    """Insert a notification_log row directly (bypasses log_notification's
    helpful side-effects so we can control ``sent_at`` precisely)."""
    if when is None:
        # Default: now-ish in IST -> convert to a UTC-naive datetime
        # because the column is naive (default=lambda: datetime.now(timezone.utc)
        # writes a UTC-aware value, which SQLAlchemy strips on SQLite).
        when = datetime.now(_IST).replace(tzinfo=None)
    with database_module.get_session() as session:
        session.add(
            NotificationLog(
                channel=channel,
                sent_at=when,
                listing_count=5,
                recipient="test@example.com",
                success=success,
                error_category=None if success else (error_category or "network"),
                error_message=None if success else "test failure",
            )
        )


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_only_failures_counts_zero() -> None:
    """5 failure rows for today → count must be 0."""
    _setup_in_memory_db()
    for _ in range(5):
        _insert_log_row(success=False)
    actual = get_today_notification_count()
    assert actual == 0, (
        f"Expected 0 successful sends today (only 5 failures inserted), "
        f"got {actual}.  The anti-spam guard is still counting failures — "
        f"the L2 bug is NOT fixed."
    )
    print("  ✓ 5 failure rows → count == 0")


def test_one_success_counts_one() -> None:
    """5 failures + 1 success for today → count must be 1."""
    _setup_in_memory_db()
    for _ in range(5):
        _insert_log_row(success=False)
    _insert_log_row(success=True)
    actual = get_today_notification_count()
    assert actual == 1, (
        f"Expected 1 successful send today, got {actual}.  Either successes "
        f"are not being counted, or failures still leak in."
    )
    print("  ✓ 5 failures + 1 success → count == 1")


def test_yesterdays_successes_excluded() -> None:
    """A success row from yesterday must NOT count toward today's total."""
    _setup_in_memory_db()
    yesterday = datetime.now(_IST).replace(tzinfo=None) - timedelta(days=1)
    _insert_log_row(success=True, when=yesterday)
    _insert_log_row(success=True)  # today
    actual = get_today_notification_count()
    assert actual == 1, (
        f"Expected 1 (only today's success should count), got {actual}.  "
        f"The date-window filter is broken."
    )
    print("  ✓ yesterday's success ignored; today's counted → count == 1")


def test_failure_after_success_still_counts_one() -> None:
    """A failure logged after a successful send must not bump the count."""
    _setup_in_memory_db()
    _insert_log_row(success=True)
    _insert_log_row(success=False)
    _insert_log_row(success=False)
    actual = get_today_notification_count()
    assert actual == 1, (
        f"Expected 1 successful send today, got {actual}.  Mixed "
        f"success+failure rows must count only the success."
    )
    print("  ✓ 1 success + 2 later failures → count == 1")


def test_ist_day_boundary_not_utc_day() -> None:
    """The count must respect the IST calendar day, not the UTC day.

    NotificationLog.sent_at is stored as naive UTC on SQLite.  Before the
    UTC-window fix the function compared ``func.date(sent_at)`` (UTC date)
    against an IST date and silently undercounted near IST midnight
    (00:00-03:00 IST = previous-day UTC).

    Scenario: insert one success row at IST-midnight-minus-1-hour
    (yesterday IST regardless of UTC) and another at
    IST-midnight-plus-1-hour (today IST regardless of UTC).  The new
    UTC-window comparison must return 1 (only today-IST counts), not 2.
    """
    _setup_in_memory_db()
    today_ist = datetime.now(_IST).date()
    ist_midnight_aware = datetime.combine(today_ist, time(0), tzinfo=_IST)
    # Convert IST instants to UTC-naive (matches how the column stores them).
    yesterday_ist_when = (
        (ist_midnight_aware - timedelta(hours=1))
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    today_ist_when = (
        (ist_midnight_aware + timedelta(hours=1))
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    _insert_log_row(success=True, when=yesterday_ist_when)
    _insert_log_row(success=True, when=today_ist_when)
    actual = get_today_notification_count()
    assert actual == 1, (
        f"Expected 1 (only the IST-today success should count), got {actual}.  "
        f"The function is still comparing on UTC date rather than IST window — "
        f"near IST midnight this silently undercounts the daily cap."
    )
    print("  ✓ yesterday-IST success ignored, today-IST counted → count == 1")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main() -> int:
    tests = [
        test_only_failures_counts_zero,
        test_one_success_counts_one,
        test_yesterdays_successes_excluded,
        test_failure_after_success_still_counts_one,
        test_ist_day_boundary_not_utc_day,
    ]
    passed = 0
    failed = 0
    for test in tests:
        name = test.__name__
        try:
            print(f"\nRunning {name}:")
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}")
            failed += 1
        except Exception:
            print(f"  ✗ ERROR (unexpected):")
            traceback.print_exc()
            failed += 1

    total = passed + failed
    print(f"\n{'=' * 60}")
    print(f"Anti-spam guard test results: {passed}/{total} passed")
    print(f"{'=' * 60}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
