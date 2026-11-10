"""Shared utility functions for the Sunnyvale Rental Finder."""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("rental_finder.utils")


def load_config(path: str = "config.yaml") -> dict[str, Any]:
    """Load and return the YAML configuration file.

    Args:
        path: Path to the YAML config file.  Defaults to ``config.yaml``
            in the project root.

    Returns:
        A dictionary with the parsed configuration values.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    with open(config_path, "r", encoding="utf-8") as fh:
        config: dict[str, Any] = yaml.safe_load(fh)

    return config


# ---------------------------------------------------------------------------
# Multi-city scrape territory resolver
# ---------------------------------------------------------------------------

# Default fallback when neither ``cities`` nor ``city`` is configured.
_DEFAULT_CITY = "Sunnyvale"


def resolve_cities(search_cfg: dict[str, Any] | None) -> list[str]:
    """Resolve the scrape-territory city list from a ``search`` config block.

    Backward-compatible bridge between the new ``search.cities`` list and the
    legacy ``search.city`` scalar. All three scrapers and the admin System
    Health page import this single helper so the "which cities do we scrape"
    question has exactly one answer.

    Resolution order (first non-empty wins):

    1. ``search.cities`` — a list of city-name strings (current source of
       truth). Blank/whitespace-only entries are dropped; surrounding
       whitespace is stripped.
    2. ``search.city`` — the legacy scalar string (backward compatibility).
    3. ``[_DEFAULT_CITY]`` — a safe single-city fallback so a scrape never
       silently targets *no* territory.

    A scalar accidentally placed under ``cities`` (e.g. ``cities: Sunnyvale``)
    is tolerated and wrapped into a one-element list.

    Args:
        search_cfg: The ``search`` sub-dict from :func:`load_config`, or
            ``None`` if the section is absent.

    Returns:
        A non-empty ``list[str]`` of city names, order-preserving.
    """
    if not search_cfg:
        return [_DEFAULT_CITY]

    raw_cities = search_cfg.get("cities")

    # Case 1: new-style list (the normal path).
    if isinstance(raw_cities, list):
        cleaned = [str(c).strip() for c in raw_cities if str(c).strip()]
        if cleaned:
            return cleaned

    # Tolerate a scalar mistakenly placed under ``cities``.
    elif isinstance(raw_cities, str) and raw_cities.strip():
        return [raw_cities.strip()]

    # Case 2: legacy scalar ``city``.
    legacy_city = search_cfg.get("city")
    if isinstance(legacy_city, str) and legacy_city.strip():
        return [legacy_city.strip()]

    # Case 3: nothing usable — safe default.
    return [_DEFAULT_CITY]


def sqft_to_sqm(sqft: int | float) -> float:
    """Convert square feet to square metres.

    Args:
        sqft: Area in square feet.

    Returns:
        Area in square metres, rounded to two decimal places.
    """
    return round(float(sqft) * 0.092903, 2)


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the application-wide logger.

    Sets up a ``StreamHandler`` writing to *stdout* with a consistent
    format across all modules.

    Args:
        level: The logging level (default :data:`logging.INFO`).

    Returns:
        The configured root logger for the ``rental_finder`` namespace.
    """
    logger = logging.getLogger("rental_finder")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


# ---------------------------------------------------------------------------
# Email settings helpers (for backoffice Settings page)
# ---------------------------------------------------------------------------


def get_email_settings(path: str = "config.yaml") -> dict[str, Any]:
    """Read email configuration from ``config.yaml``.

    Args:
        path: Path to the YAML config file.

    Returns:
        A dict with keys ``enabled``, ``recipient_email``,
        ``sender_email``, ``smtp_server``, ``smtp_port``.
    """
    try:
        config = load_config(path)
    except FileNotFoundError:
        return {
            "enabled": False,
            "recipient_email": "",
            "sender_email": "",
            "smtp_server": "",
            "smtp_port": 587,
        }

    email_cfg = config.get("email", {})
    return {
        "enabled": bool(email_cfg.get("enabled", False)),
        "recipient_email": str(email_cfg.get("recipient_email", "")),
        "sender_email": str(email_cfg.get("sender_email", "")),
        "smtp_server": str(email_cfg.get("smtp_server", "")),
        "smtp_port": int(email_cfg.get("smtp_port", 587)),
    }


def update_email_settings(
    enabled: bool,
    recipient_email: str,
    path: str = "config.yaml",
) -> None:
    """Update ``email.enabled`` and ``email.recipient_email`` in config.yaml.

    Only these two fields are writable from the backoffice UI.
    Creates a backup (``config.yaml.bak``) before writing.

    Args:
        enabled: Whether email notifications are enabled.
        recipient_email: The recipient email address.
        path: Path to the YAML config file.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    # Create backup before modifying
    backup_path = config_path.with_suffix(".yaml.bak")
    shutil.copy2(config_path, backup_path)
    logger.info("Config backup created: %s", backup_path)

    # Read current config
    with open(config_path, "r", encoding="utf-8") as fh:
        config: dict[str, Any] = yaml.safe_load(fh)

    # Update only the two writable fields
    if "email" not in config:
        config["email"] = {}
    config["email"]["enabled"] = enabled
    config["email"]["recipient_email"] = recipient_email

    # Write back with readable formatting
    with open(config_path, "w", encoding="utf-8") as fh:
        yaml.dump(config, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info(
        "Email settings updated: enabled=%s, recipient=%s",
        enabled,
        recipient_email,
    )


# ---------------------------------------------------------------------------
# WhatsApp settings helpers (for backoffice Settings page)
# ---------------------------------------------------------------------------


def get_whatsapp_settings(path: str = "config.yaml") -> dict[str, Any]:
    """Read WhatsApp configuration from ``config.yaml``.

    Args:
        path: Path to the YAML config file.

    Returns:
        A dict with keys ``enabled`` and ``recipient_phone``.
    """
    try:
        config = load_config(path)
    except FileNotFoundError:
        return {
            "enabled": False,
            "recipient_phone": "",
        }

    wa_cfg = config.get("whatsapp", {})
    return {
        "enabled": bool(wa_cfg.get("enabled", False)),
        "recipient_phone": str(wa_cfg.get("recipient_phone", "")),
    }


def update_whatsapp_settings(
    enabled: bool,
    recipient_phone: str,
    path: str = "config.yaml",
) -> None:
    """Update ``whatsapp.enabled`` and ``whatsapp.recipient_phone`` in config.yaml.

    Only these two fields are writable from the backoffice UI.
    Creates a backup (``config.yaml.bak``) before writing.

    Args:
        enabled: Whether WhatsApp notifications are enabled.
        recipient_phone: The recipient phone number.
        path: Path to the YAML config file.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    # Create backup before modifying
    backup_path = config_path.with_suffix(".yaml.bak")
    shutil.copy2(config_path, backup_path)
    logger.info("Config backup created: %s", backup_path)

    # Read current config
    with open(config_path, "r", encoding="utf-8") as fh:
        config: dict[str, Any] = yaml.safe_load(fh)

    # Update only the two writable fields
    if "whatsapp" not in config:
        config["whatsapp"] = {}
    config["whatsapp"]["enabled"] = enabled
    config["whatsapp"]["recipient_phone"] = recipient_phone

    # Write back with readable formatting
    with open(config_path, "w", encoding="utf-8") as fh:
        yaml.dump(config, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info(
        "WhatsApp settings updated: enabled=%s, recipient=%s",
        enabled,
        recipient_phone,
    )


# ---------------------------------------------------------------------------
# Telegram settings helpers (for backoffice Settings page)
# ---------------------------------------------------------------------------


def get_telegram_settings(path: str = "config.yaml") -> dict[str, Any]:
    """Read Telegram configuration from ``config.yaml``.

    Note that the recipient ``chat_id`` and bot token live in environment
    variables (``TELEGRAM_CHAT_ID`` / ``TELEGRAM_BOT_TOKEN``) — they are
    intentionally NOT in ``config.yaml`` so they pair atomically as
    co-secrets (see ``plans/telegram-channel.md`` §2).

    Args:
        path: Path to the YAML config file.

    Returns:
        A dict with keys ``enabled`` and ``parse_mode``.
    """
    try:
        config = load_config(path)
    except FileNotFoundError:
        return {
            "enabled": False,
            "parse_mode": "HTML",
        }

    tg_cfg = config.get("telegram", {})
    return {
        "enabled": bool(tg_cfg.get("enabled", False)),
        "parse_mode": str(tg_cfg.get("parse_mode", "HTML")),
    }


def update_telegram_settings(
    enabled: bool,
    path: str = "config.yaml",
) -> None:
    """Update ``telegram.enabled`` in config.yaml.

    Only the ``enabled`` toggle is writable from the backoffice UI.
    The bot token and ``chat_id`` are env vars (co-secret pair) and
    must be set via ``.env`` — never via the Settings page.

    Creates a backup (``config.yaml.bak``) before writing.

    Args:
        enabled: Whether Telegram notifications are enabled.
        path: Path to the YAML config file.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")

    # Create backup before modifying
    backup_path = config_path.with_suffix(".yaml.bak")
    shutil.copy2(config_path, backup_path)
    logger.info("Config backup created: %s", backup_path)

    # Read current config
    with open(config_path, "r", encoding="utf-8") as fh:
        config: dict[str, Any] = yaml.safe_load(fh)

    # Update only the writable field
    if "telegram" not in config:
        config["telegram"] = {"parse_mode": "HTML"}
    config["telegram"]["enabled"] = enabled

    # Write back with readable formatting
    with open(config_path, "w", encoding="utf-8") as fh:
        yaml.dump(config, fh, default_flow_style=False, allow_unicode=True, sort_keys=False)

    logger.info("Telegram settings updated: enabled=%s", enabled)
