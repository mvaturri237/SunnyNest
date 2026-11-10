#!/usr/bin/env python3
"""Mock-based unit tests for ``TelegramChannel._classify_telegram_error``.

Six cases exercising the error-categorisation matrix from
``plans/telegram-channel.md`` §4.  Run as a plain script — no pytest:

    .venv/bin/python scripts/test_telegram_classification.py

Exit code is 0 on success, 1 on any failure.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.notifier import SendResult, TelegramChannel  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_failures: list[str] = []


def _check(label: str, actual: object, expected: object) -> None:
    """Assert helper that records failures instead of stopping immediately."""
    if actual == expected:
        print(f"  ✓ {label}")
    else:
        _failures.append(label)
        print(f"  ✗ {label}")
        print(f"      expected: {expected!r}")
        print(f"      actual:   {actual!r}")


def _check_contains(label: str, haystack: str, needle: str) -> None:
    if needle in haystack:
        print(f"  ✓ {label}")
    else:
        _failures.append(label)
        print(f"  ✗ {label}: {needle!r} not in {haystack!r}")


# ---------------------------------------------------------------------------
# Test cases — _classify_telegram_error
# ---------------------------------------------------------------------------


def test_401_invalid_token() -> None:
    """HTTP 401 → ``auth`` (bot token invalid / revoked)."""
    print("\nCase 1: HTTP 401 (invalid bot token) → auth")
    body = json.dumps({
        "ok": False,
        "error_code": 401,
        "description": "Unauthorized",
    })
    category, message = TelegramChannel._classify_telegram_error(401, body)
    _check("category == 'auth'", category, "auth")
    _check_contains("message mentions BotFather", message, "BotFather")
    _check_contains("message mentions TELEGRAM_BOT_TOKEN", message, "TELEGRAM_BOT_TOKEN")


def test_403_blocked_by_user() -> None:
    """HTTP 403 + 'bot was blocked by the user' → ``recipient_refused``."""
    print("\nCase 2: HTTP 403 (bot was blocked by the user) → recipient_refused")
    body = json.dumps({
        "ok": False,
        "error_code": 403,
        "description": "Forbidden: bot was blocked by the user",
    })
    category, message = TelegramChannel._classify_telegram_error(403, body)
    _check("category == 'recipient_refused'", category, "recipient_refused")
    _check_contains("message mentions TELEGRAM_CHAT_ID", message, "TELEGRAM_CHAT_ID")


def test_400_chat_not_found() -> None:
    """HTTP 400 + 'chat not found' → ``recipient_refused`` (Telegram inconsistency)."""
    print("\nCase 3: HTTP 400 (chat not found) → recipient_refused")
    body = json.dumps({
        "ok": False,
        "error_code": 400,
        "description": "Bad Request: chat not found",
    })
    category, message = TelegramChannel._classify_telegram_error(400, body)
    _check("category == 'recipient_refused'", category, "recipient_refused")
    _check_contains("message mentions HTTP 400", message, "400")


def test_429_rate_limited() -> None:
    """HTTP 429 with ``parameters.retry_after`` → ``rate_limited``."""
    print("\nCase 4: HTTP 429 (with retry_after=10) → rate_limited")
    body = json.dumps({
        "ok": False,
        "error_code": 429,
        "description": "Too Many Requests: retry after 10",
        "parameters": {"retry_after": 10},
    })
    category, message = TelegramChannel._classify_telegram_error(429, body)
    _check("category == 'rate_limited'", category, "rate_limited")
    _check_contains("message includes retry_after=10s", message, "retry_after=10s")


def test_500_server_error() -> None:
    """HTTP 500 → ``api_error`` (Telegram-side outage)."""
    print("\nCase 5: HTTP 500 (Telegram outage) → api_error")
    body = "Internal Server Error"  # non-JSON body — exercises fallback path
    category, message = TelegramChannel._classify_telegram_error(500, body)
    _check("category == 'api_error'", category, "api_error")
    _check_contains("message includes HTTP 500", message, "500")


def test_network_exception_via_validate_token() -> None:
    """Network exception path through ``validate_token`` → ``network``.

    ``_classify_telegram_error`` itself only handles HTTP responses;
    network errors are surfaced through the calling code.  This case
    verifies the end-to-end mapping by mocking httpx to raise a network
    error.
    """
    print("\nCase 6: Network exception via validate_token → network")
    fake_httpx = MagicMock()
    fake_httpx.Client.return_value.__enter__ = MagicMock(
        side_effect=ConnectionError("DNS lookup failed")
    )

    with patch.dict(sys.modules, {"httpx": fake_httpx}):
        result = TelegramChannel.validate_token(bot_token="dummy", timeout=1.0)

    _check("validate_token returned SendResult", isinstance(result, SendResult), True)
    _check("success is False", result.success, False)
    _check("category == 'network'", result.error_category, "network")
    _check_contains("message mentions network", result.error_message or "", "network")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 60)
    print("  TelegramChannel._classify_telegram_error — mock-based tests")
    print("=" * 60)

    test_401_invalid_token()
    test_403_blocked_by_user()
    test_400_chat_not_found()
    test_429_rate_limited()
    test_500_server_error()
    test_network_exception_via_validate_token()

    print()
    print("=" * 60)
    if _failures:
        print(f"  ❌ {len(_failures)} assertion(s) failed:")
        for label in _failures:
            print(f"     - {label}")
        return 1
    print("  ✅ All 6 cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
