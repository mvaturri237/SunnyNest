"""Shared dependencies for the FastAPI web application."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.templating import Jinja2Templates

from src.utils import load_config

# Templates directory relative to the project root
_TEMPLATES_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# Custom Jinja2 filters
# ---------------------------------------------------------------------------

# Known placeholder image patterns that should be treated as "no image"
_PLACEHOLDER_PATTERNS = ("empty.png",)


def _parse_first_image(image_urls_str: str | None) -> str | None:
    """Extract the first valid HTTP(S) image URL from a JSON-encoded list.

    Skips known placeholder images (e.g. Craigslist's ``empty.png``).

    Replaces the brittle ``listing.image_urls[2:-2].split(...)`` slicing
    that was previously done inside the template.
    """
    if not image_urls_str:
        return None
    try:
        urls = json.loads(image_urls_str)
        if isinstance(urls, list):
            for url in urls:
                url = str(url)
                if not url.startswith(("http://", "https://")):
                    continue
                if any(p in url for p in _PLACEHOLDER_PATTERNS):
                    continue
                return url
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def _abbreviate_school(name: str | None) -> str:
    """Abbreviate common school-level suffixes for compact display.

    Examples:
        - ``"Cherry Chase Elementary School"`` → ``"Cherry Chase Elem"``
        - ``"Columbia Middle School"`` → ``"Columbia Middle"``
        - ``"Fremont High School"`` → ``"Fremont HS"``
        - ``"Sunnyvale Elementary"`` → ``"Sunnyvale Elem"``
    """
    if not name:
        return ""
    # Order matters — match longer patterns first
    replacements = [
        ("Elementary School", "Elem"),
        ("Elementary", "Elem"),
        ("Middle School", "Middle"),
        ("High School", "HS"),
    ]
    for pattern, replacement in replacements:
        name = name.replace(pattern, replacement)
    return name.strip()


templates.env.filters["first_image"] = _parse_first_image
templates.env.filters["abbreviate_school"] = _abbreviate_school


# ---------------------------------------------------------------------------
# Environment health check
# ---------------------------------------------------------------------------


def get_env_status() -> dict[str, dict[str, str]]:
    """Return the configuration status of each monitored env var.

    Used by the admin dashboard to render the System Health panel.

    Returns:
        A dict keyed by env-var name, each value being a dict with
        ``status`` (``"configured"`` | ``"missing"``) and ``detail``.
    """
    status: dict[str, dict[str, str]] = {}

    # RAPIDAPI_KEY
    if os.environ.get("RAPIDAPI_KEY"):
        status["RAPIDAPI_KEY"] = {
            "status": "configured",
            "detail": "Zillow scraper is active",
        }
    else:
        status["RAPIDAPI_KEY"] = {
            "status": "missing",
            "detail": "Zillow scraper will be disabled",
        }

    # REALTOR_RAPIDAPI_KEY (with RAPIDAPI_KEY fallback)
    realtor_key = os.environ.get("REALTOR_RAPIDAPI_KEY") or os.environ.get("RAPIDAPI_KEY")
    if realtor_key:
        status["REALTOR_RAPIDAPI_KEY"] = {
            "status": "configured",
            "detail": (
                "Realtor.com scraper is active"
                + (" (using RAPIDAPI_KEY fallback)" if not os.environ.get("REALTOR_RAPIDAPI_KEY") else "")
            ),
        }
    else:
        try:
            config = load_config()
            realtor_enabled = config.get("realtor_api", {}).get("enabled", True)
        except FileNotFoundError:
            realtor_enabled = True

        if realtor_enabled:
            status["REALTOR_RAPIDAPI_KEY"] = {
                "status": "missing",
                "detail": "Realtor.com scraper will be disabled",
            }
        else:
            status["REALTOR_RAPIDAPI_KEY"] = {
                "status": "configured",
                "detail": "Realtor.com scraper is disabled in config — key not required",
            }

    # SMTP_PASSWORD
    if os.environ.get("SMTP_PASSWORD"):
        status["SMTP_PASSWORD"] = {
            "status": "configured",
            "detail": "Email credentials set",
        }
    else:
        try:
            config = load_config()
            email_enabled = config.get("email", {}).get("enabled", False)
        except FileNotFoundError:
            email_enabled = False

        if email_enabled:
            status["SMTP_PASSWORD"] = {
                "status": "missing",
                "detail": "Email is enabled but password not set — notifications will fail",
            }
        else:
            status["SMTP_PASSWORD"] = {
                "status": "configured",
                "detail": "Email is disabled in config — password not required",
            }

    # NOTIFICATION_RECIPIENT
    if os.environ.get("NOTIFICATION_RECIPIENT"):
        status["NOTIFICATION_RECIPIENT"] = {
            "status": "configured",
            "detail": "Recipient set via env var",
        }
    else:
        status["NOTIFICATION_RECIPIENT"] = {
            "status": "configured",
            "detail": "Using recipient_email from config.yaml",
        }

    return status
