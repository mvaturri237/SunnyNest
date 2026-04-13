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
