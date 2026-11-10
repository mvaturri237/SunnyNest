#!/usr/bin/env python3
"""Mock-based unit tests for ``TelegramChannel.validate_token``.

Two cases exercising the success and 401 paths (per
``plans/telegram-channel.md`` §6).  Run as a plain script — no pytest:

    .venv/bin/python scripts/test_telegram_validate_token.py

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


def _make_fake_httpx(status_code: int, text: str):
    """Construct a fake ``httpx`` module whose ``Client.get`` returns a
    response with the requested ``status_code`` and ``text``."""
    fake_response = MagicMock()
    fake_response.status_code = status_code
    fake_response.text = text

    fake_client = MagicMock()
    fake_client.get.return_value = fake_response

    fake_module = MagicMock()
    fake_module.Client.return_value.__enter__.return_value = fake_client
    fake_module.Client.return_value.__exit__.return_value = False
    return fake_module


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_valid_token_returns_success() -> None:
    """200 + ``{"ok": true, "result": {...}}`` → ``SendResult(success=True)``."""
    print("\nCase 1: getMe returns 200 (valid token) → success")
    body = json.dumps({
        "ok": True,
        "result": {
            "id": 123456789,
            "is_bot": True,
            "first_name": "Test Bot",
            "username": "test_bot",
        },
    })
    fake_httpx = _make_fake_httpx(200, body)

    with patch.dict(sys.modules, {"httpx": fake_httpx}):
        result = TelegramChannel.validate_token(bot_token="dummy_token", timeout=1.0)

    _check("isinstance SendResult", isinstance(result, SendResult), True)
    _check("success is True", result.success, True)
    _check("error_category is None", result.error_category, None)
    _check("error_message is None", result.error_message, None)


def test_invalid_token_returns_auth_failure() -> None:
    """401 → ``SendResult(success=False, error_category='auth')``."""
    print("\nCase 2: getMe returns 401 (invalid token) → auth failure")
    body = json.dumps({
        "ok": False,
        "error_code": 401,
        "description": "Unauthorized",
    })
    fake_httpx = _make_fake_httpx(401, body)

    with patch.dict(sys.modules, {"httpx": fake_httpx}):
        result = TelegramChannel.validate_token(bot_token="garbage", timeout=1.0)

    _check("isinstance SendResult", isinstance(result, SendResult), True)
    _check("success is False", result.success, False)
    _check("category == 'auth'", result.error_category, "auth")
    _check_contains(
        "message mentions BotFather",
        result.error_message or "",
        "BotFather",
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 60)
    print("  TelegramChannel.validate_token — mock-based tests")
    print("=" * 60)

    test_valid_token_returns_success()
    test_invalid_token_returns_auth_failure()

    print()
    print("=" * 60)
    if _failures:
        print(f"  ❌ {len(_failures)} assertion(s) failed:")
        for label in _failures:
            print(f"     - {label}")
        return 1
    print("  ✅ All 2 cases passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
