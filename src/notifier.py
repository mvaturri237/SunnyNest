"""Notification service for new rental listings.

Sends alerts via multiple channels (email, WhatsApp) when new
listings matching the user's filters are discovered.

Architecture
------------
- ``BaseNotificationChannel`` — abstract base class for all channels.
- ``EmailChannel`` — SMTP-based email implementation.
- ``WhatsAppChannel`` — Meta WhatsApp Business Cloud API implementation.
- ``NotificationService`` — orchestrator with anti-spam guard that
  queries unnotified listings from the local DB, dispatches via
  registered channels, marks listings as notified, and logs results.

The legacy ``send_notification()`` function is preserved for backward
compatibility with ``ScraperOrchestrator._notify_new_listings()``.
"""

from __future__ import annotations

import abc
import html as html_module
import logging
import os
import smtplib
import ssl
import warnings
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

import certifi

from src.utils import load_config

logger = logging.getLogger("rental_finder.notifier")

# Path to the Palo Alto Networks Enterprise Root CA, exported from the
# macOS System Keychain.  When present, it is loaded into the SSL context
# so that connections through a GlobalProtect TLS-decryption proxy succeed.
_PANW_CA_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "certs" / "panw-root-ca.pem"
)


# ---------------------------------------------------------------------------
# Channel adapter pattern
# ---------------------------------------------------------------------------


class BaseNotificationChannel(abc.ABC):
    """Abstract base class for notification channels.

    Subclasses must implement :meth:`send` and the :attr:`channel_name`
    property so that ``NotificationService`` can dispatch generically.
    """

    @property
    @abc.abstractmethod
    def channel_name(self) -> str:
        """Return a short identifier for this channel (e.g. ``"email"``)."""

    @abc.abstractmethod
    def send(self, listings: list[Any], config: dict[str, Any]) -> bool:
        """Send a notification containing *listings*.

        Args:
            listings: Listing ORM objects (or dicts) to include.
            config: The full application config dictionary.

        Returns:
            ``True`` if the notification was sent successfully.
        """

    @abc.abstractmethod
    def get_recipient(self, config: dict[str, Any]) -> str:
        """Return the recipient identifier for logging.

        Args:
            config: The full application config dictionary.

        Returns:
            A string identifying the recipient (e.g. email address).
        """

    @abc.abstractmethod
    def is_enabled(self, config: dict[str, Any]) -> bool:
        """Return whether this channel is enabled in config.

        Args:
            config: The full application config dictionary.

        Returns:
            ``True`` if the channel should be used for dispatch.
        """


class EmailChannel(BaseNotificationChannel):
    """SMTP email notification channel.

    Reads SMTP credentials and recipient from the ``email`` section of
    the application config.  The HTML body includes a table of listing
    details and a link to the SunnyNest dashboard.
    """

    @property
    def channel_name(self) -> str:  # noqa: D401
        return "email"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_recipient(self, config: dict[str, Any]) -> str:  # noqa: D401
        """Return the recipient email address, preferring env var."""
        env_recipient = os.environ.get("NOTIFICATION_RECIPIENT")
        if env_recipient:
            return env_recipient
        return config.get("email", {}).get("recipient_email", "unknown")

    def is_enabled(self, config: dict[str, Any]) -> bool:
        """Return whether email notifications are enabled in config."""
        return config.get("email", {}).get("enabled", False)

    def send(self, listings: list[Any], config: dict[str, Any]) -> bool:
        """Send an HTML email with the supplied listings.

        Args:
            listings: Listing ORM objects to include in the email.
            config: Full application config (needs ``email`` section).

        Returns:
            ``True`` on success, ``False`` otherwise.
        """
        email_cfg = config.get("email", {})

        if not email_cfg.get("enabled", False):
            logger.info("Email notifications are disabled in config.")
            return False

        sender_email: str = email_cfg.get("sender_email", "")

        # P1-2: Prefer SMTP_PASSWORD env var over config value
        sender_password: str = os.environ.get("SMTP_PASSWORD", "")
        if not sender_password:
            sender_password = email_cfg.get("sender_password", "")
            if sender_password:
                logger.warning(
                    "SMTP password read from config file — consider setting the "
                    "SMTP_PASSWORD environment variable instead for better security."
                )

        # P2-10: Prefer NOTIFICATION_RECIPIENT env var over config value
        recipient_email: str = os.environ.get("NOTIFICATION_RECIPIENT", "")
        if not recipient_email:
            recipient_email = email_cfg.get("recipient_email", "")

        if not sender_email or not sender_password or not recipient_email:
            logger.warning(
                "Email credentials are incomplete — skipping notification. "
                "Set sender_email, sender_password, and recipient_email in config.yaml."
            )
            return False

        if not listings:
            logger.info("No listings to notify about.")
            return False

        smtp_server: str = email_cfg.get("smtp_server", "smtp.gmail.com")
        smtp_port: int = email_cfg.get("smtp_port", 587)
        dashboard_url: str = email_cfg.get("dashboard_url", "http://sunnynest:8000")

        # --- Build the email ---
        count = len(listings)
        subject = f"{count} new listing{'s' if count != 1 else ''} added"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = recipient_email

        html_body = self._build_html_body(listings, dashboard_url)
        msg.attach(MIMEText(html_body, "html"))

        # --- Send via SMTP ---
        try:
            logger.info(
                "Sending email notification (%d listing(s)) via %s:%d …",
                count,
                smtp_server,
                smtp_port,
            )
            with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, recipient_email, msg.as_string())

            logger.info("Email notification sent successfully to %s.", recipient_email)
            return True

        except smtplib.SMTPAuthenticationError:
            logger.error(
                "SMTP authentication failed. Check sender_email and sender_password "
                "(use an app-specific password for Gmail)."
            )
            return False
        except smtplib.SMTPRecipientsRefused:
            logger.error("Recipient address refused: %s", recipient_email)
            return False
        except smtplib.SMTPException as exc:
            logger.error("SMTP error while sending notification: %s", exc)
            return False
        except OSError as exc:
            logger.error("Network error while sending notification: %s", exc)
            return False
        except Exception:
            logger.exception("Unexpected error while sending email notification")
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_html_body(listings: list[Any], dashboard_url: str) -> str:
        """Build an HTML email body with a table of listing details.

        Accepts both ORM ``Listing`` objects and plain dicts.

        Args:
            listings: Listing objects or dicts.
            dashboard_url: URL to the SunnyNest dashboard.

        Returns:
            An HTML string suitable for the email body.
        """

        def _get(obj: Any, key: str, default: Any = None) -> Any:
            """Retrieve an attribute or dict key."""
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        rows = ""
        for listing in listings:
            title = html_module.escape(str(_get(listing, "title", "N/A")))
            price = _get(listing, "price")
            price_str = f"${price:,.0f}/mo" if price else "N/A"
            bedrooms = _get(listing, "bedrooms", "N/A")
            sqft = _get(listing, "sqft")
            sqft_str = f"{sqft:,} sqft" if sqft else "N/A"
            address = html_module.escape(str(_get(listing, "address", "N/A")))
            url = _get(listing, "url", "#")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                url = "#"
            source = html_module.escape(str(_get(listing, "source", "unknown")))

            rows += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;">
                    <a href="{url}" style="color: #1a73e8; text-decoration: none;">{title}</a>
                </td>
                <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold; color: #2e7d32;">
                    {price_str}
                </td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">
                    {bedrooms}
                </td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">
                    {sqft_str}
                </td>
                <td style="padding: 8px; border: 1px solid #ddd;">
                    {address}
                </td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">
                    <span style="background: {'#1a73e8' if source == 'zillow' else '#ff6d00'};
                                 color: white; padding: 2px 8px; border-radius: 4px;
                                 font-size: 12px;">
                        {source.capitalize() if isinstance(source, str) else source}
                    </span>
                </td>
                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">
                    <a href="{url}" style="color: #1a73e8;">View&nbsp;→</a>
                </td>
            </tr>"""

        html = f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                     color: #333; max-width: 900px; margin: 0 auto;">
            <h2 style="color: #1a73e8;">🏠 New Rental Listings in Sunnyvale</h2>
            <p>We found <strong>{len(listings)}</strong> new listing(s) matching your criteria:</p>
            <table style="border-collapse: collapse; width: 100%; font-size: 14px;">
                <thead>
                    <tr style="background: #f5f5f5;">
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Title</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Price</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: center;">Beds</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: center;">Size</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: left;">Address</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: center;">Source</th>
                        <th style="padding: 10px; border: 1px solid #ddd; text-align: center;">Link</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
            <p style="margin-top: 20px;">
                <a href="{html_module.escape(dashboard_url, quote=True)}" style="display: inline-block; padding: 10px 20px;
                   background: #1a73e8; color: white; text-decoration: none;
                   border-radius: 6px; font-weight: bold;">
                    Open SunnyNest Dashboard
                </a>
            </p>
            <p style="margin-top: 20px; font-size: 12px; color: #999;">
                This email was sent by the SunnyNest Rental Finder.
                Update your filters in config.yaml to change notification criteria.
            </p>
        </body>
        </html>
        """
        return html


# ---------------------------------------------------------------------------
# WhatsApp channel (Meta Business Cloud API)
# ---------------------------------------------------------------------------


class WhatsAppChannel(BaseNotificationChannel):
    """WhatsApp notification channel via Meta Business Cloud API.

    Sends a concise text message with listing summaries using the
    WhatsApp Business Cloud API.  Credentials are read from environment
    variables (``WHATSAPP_API_TOKEN``, ``WHATSAPP_PHONE_NUMBER_ID``,
    ``WHATSAPP_RECIPIENT_PHONE``).

    WhatsApp text messages have a 4096-character limit — the listing
    list is truncated if it exceeds this.
    """

    _WHATSAPP_TEXT_LIMIT: int = 4096
    _API_BASE: str = "https://graph.facebook.com/v21.0"

    @property
    def channel_name(self) -> str:  # noqa: D401
        return "whatsapp"

    # ------------------------------------------------------------------
    # SSL helper (mirrors BaseScraper._build_ssl_context without coupling)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_ssl_context() -> ssl.SSLContext:
        """Build an SSL context for Meta Graph API requests.

        The context:
        * Uses certifi's CA bundle as the trust base.
        * Loads the PANW Enterprise Root CA on top (if the PEM file
          exists) so that connections through a Palo Alto Networks
          GlobalProtect TLS-decryption proxy are trusted.
        * Clears the ``VERIFY_X509_STRICT`` flag — the decrypt proxy
          generates leaf certificates that lack the Authority Key
          Identifier (AKI) extension, which OpenSSL >= 3.6 rejects
          under strict mode.
        * Preserves ``verify_mode=CERT_REQUIRED`` and
          ``check_hostname=True`` — full chain validation is still
          enforced.

        Returns:
            A configured :class:`ssl.SSLContext`.
        """
        ctx = ssl.create_default_context(cafile=certifi.where())

        if _PANW_CA_PATH.exists():
            ctx.load_verify_locations(cafile=str(_PANW_CA_PATH))
            logger.info(
                "WhatsApp: loaded PANW Enterprise Root CA for TLS decryption proxy (%s)",
                _PANW_CA_PATH,
            )

        # OpenSSL 3.6+ rejects leaf certs missing AKI under strict mode.
        # Clear the flag while keeping all other security properties.
        ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT

        return ctx

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_recipient(self, config: dict[str, Any]) -> str:  # noqa: D401
        """Return the recipient phone number, preferring env var."""
        env_phone = os.environ.get("WHATSAPP_RECIPIENT_PHONE", "").strip()
        if env_phone:
            return env_phone
        return config.get("whatsapp", {}).get("recipient_phone", "unknown")

    def is_enabled(self, config: dict[str, Any]) -> bool:
        """Return whether WhatsApp notifications are enabled in config."""
        return config.get("whatsapp", {}).get("enabled", False)

    def send(self, listings: list[Any], config: dict[str, Any]) -> bool:
        """Send a WhatsApp text message with listing summaries.

        Args:
            listings: Listing ORM objects to include in the message.
            config: Full application config (needs ``whatsapp`` section).

        Returns:
            ``True`` on success, ``False`` otherwise.
        """
        if not config.get("whatsapp", {}).get("enabled", False):
            logger.info("WhatsApp notifications are disabled in config.")
            return False

        # --- Credentials from env vars ---
        api_token = os.environ.get("WHATSAPP_API_TOKEN", "").strip()
        phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
        recipient_phone = os.environ.get("WHATSAPP_RECIPIENT_PHONE", "").strip()
        if not recipient_phone:
            recipient_phone = (
                config.get("whatsapp", {}).get("recipient_phone", "").strip()
            )

        if not api_token or not phone_number_id or not recipient_phone:
            logger.warning(
                "WhatsApp credentials are incomplete — skipping notification. "
                "Set WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID, and "
                "WHATSAPP_RECIPIENT_PHONE environment variables."
            )
            return False

        if not listings:
            logger.info("No listings to notify about via WhatsApp.")
            return False

        # --- Build message body ---
        body = self._build_text_body(listings)

        # --- Send via Meta Cloud API ---
        url = f"{self._API_BASE}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "text",
            "text": {"body": body},
        }

        try:
            import httpx

            ssl_ctx = self._build_ssl_context()

            logger.info(
                "Sending WhatsApp notification (%d listing(s)) to %s …",
                len(listings),
                recipient_phone,
            )
            with httpx.Client(timeout=30, verify=ssl_ctx) as client:
                resp = client.post(url, headers=headers, json=payload)

            if resp.status_code in (200, 201):
                logger.info(
                    "WhatsApp notification sent successfully to %s.",
                    recipient_phone,
                )
                return True

            logger.error(
                "WhatsApp API returned HTTP %d: %s",
                resp.status_code,
                resp.text[:500],
            )
            return False

        except ImportError:
            logger.error(
                "httpx is not installed — cannot send WhatsApp notifications. "
                "Run: pip install httpx"
            )
            return False
        except Exception:
            logger.exception("Unexpected error while sending WhatsApp notification")
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_text_body(self, listings: list[Any]) -> str:
        """Build a concise text message with one line per listing.

        Respects the 4096-char WhatsApp text limit by truncating the
        listing list and appending a "… and N more" note.

        Args:
            listings: Listing ORM objects or dicts.

        Returns:
            A plain-text string for the WhatsApp message body.
        """

        def _get(obj: Any, key: str, default: Any = None) -> Any:
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        count = len(listings)
        header = f"🏠 {count} new listing{'s' if count != 1 else ''} in Sunnyvale\n\n"

        lines: list[str] = []
        for listing in listings:
            title = str(_get(listing, "title", "N/A"))
            price = _get(listing, "price")
            price_str = f"${price:,.0f}/mo" if price else "N/A"
            bedrooms = _get(listing, "bedrooms", "?")
            address = str(_get(listing, "address", ""))
            url = _get(listing, "url", "")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                url = ""

            parts = [f"• {title}", price_str, f"{bedrooms}BR"]
            if address:
                parts.append(address)
            if url:
                parts.append(url)
            lines.append(" | ".join(parts))

        # Truncate to fit within the 4096-char limit
        result = header
        truncated = 0
        for i, line in enumerate(lines):
            candidate = result + line + "\n"
            # Reserve space for a potential "… and N more" footer
            footer_reserve = 30
            if len(candidate) + footer_reserve > self._WHATSAPP_TEXT_LIMIT:
                truncated = len(lines) - i
                break
            result = candidate

        if truncated:
            result += f"\n… and {truncated} more listing{'s' if truncated != 1 else ''}"

        return result.strip()


# ---------------------------------------------------------------------------
# Notification service (orchestrator)
# ---------------------------------------------------------------------------


class NotificationService:
    """Orchestrates the scheduled notification flow.

    1. Check anti-spam guard (max 2 sends per day).
    2. Query unnotified listings from the local SQLite DB.
    3. Dispatch to all registered channels.
    4. Mark listings as notified.
    5. Log the notification result.

    The ``MAX_DAILY_NOTIFICATIONS`` constant is **hard-coded** and not
    configurable — this is an intentional anti-spam safeguard.
    """

    MAX_DAILY_NOTIFICATIONS: int = 2

    def __init__(
        self,
        channels: list[BaseNotificationChannel] | None = None,
    ) -> None:
        self._channels: list[BaseNotificationChannel] = channels or []

    def add_channel(self, channel: BaseNotificationChannel) -> None:
        """Register a notification channel."""
        self._channels.append(channel)

    def run(self) -> dict[str, Any]:
        """Execute the full notification pipeline.

        Returns:
            A summary dict with keys ``listings_found``, ``sent``,
            ``skipped_reason`` (if skipped).
        """
        # Import DB helpers here to avoid circular imports at module level
        from src.database import (
            get_today_notification_count,
            get_unnotified_listings,
            log_notification,
            mark_listings_notified,
        )

        # --- 0. Pre-flight: verify at least one channel has credentials ---
        # Each channel's send() handles its own credential validation and
        # fails silently if credentials are missing.  We only skip the
        # entire pipeline if there are NO registered channels at all.
        if not self._channels:
            logger.warning(
                "No notification channels registered — skipping pipeline."
            )
            return {
                "listings_found": 0,
                "sent": False,
                "skipped_reason": "no_channels_registered",
            }

        # --- 1. Anti-spam guard ---
        today_count = get_today_notification_count()
        if today_count >= self.MAX_DAILY_NOTIFICATIONS:
            logger.info(
                "Anti-spam: already sent %d notification(s) today (max %d). Skipping.",
                today_count,
                self.MAX_DAILY_NOTIFICATIONS,
            )
            return {
                "listings_found": 0,
                "sent": False,
                "skipped_reason": "daily_limit_reached",
            }

        # --- 2. Load config (needed for both filters and channel dispatch) ---
        try:
            config = load_config()
        except FileNotFoundError:
            logger.warning("config.yaml not found — using empty config.")
            config = {}

        # --- 3. Query unnotified listings (DB only, no API calls) ---
        # Apply user's search criteria from config.yaml so notifications
        # only include listings matching their preferences.
        notification_filters: dict[str, Any] = {}
        filters_cfg = config.get("filters", {})
        if filters_cfg.get("min_price"):
            notification_filters["min_price"] = filters_cfg["min_price"]
        if filters_cfg.get("max_price"):
            notification_filters["max_price"] = filters_cfg["max_price"]
        if filters_cfg.get("min_bedrooms"):
            notification_filters["min_bedrooms"] = filters_cfg["min_bedrooms"]
        if filters_cfg.get("max_bedrooms"):
            notification_filters["max_bedrooms"] = filters_cfg["max_bedrooms"]
        if filters_cfg.get("property_types"):
            notification_filters["property_type"] = filters_cfg["property_types"]

        unnotified = get_unnotified_listings(
            filters=notification_filters if notification_filters else None,
        )
        if not unnotified:
            logger.info("No unnotified listings found.")
            return {"listings_found": 0, "sent": False, "skipped_reason": "no_listings"}

        logger.info("Found %d unnotified listing(s).", len(unnotified))

        # --- 4. Dispatch to all channels ---
        listing_ids = [listing.id for listing in unnotified]
        any_success = False

        for channel in self._channels:
            if not channel.is_enabled(config):
                logger.info(
                    "Channel %s is disabled — skipping.", channel.channel_name
                )
                continue

            try:
                recipient = channel.get_recipient(config)
                success = channel.send(unnotified, config)
                any_success = any_success or success

                # Log the notification attempt
                log_notification(
                    channel=channel.channel_name,
                    listing_count=len(unnotified),
                    recipient=recipient,
                    success=success,
                )
            except Exception:
                logger.exception(
                    "Channel %s failed unexpectedly.", channel.channel_name
                )
                # Log the failure
                log_notification(
                    channel=channel.channel_name,
                    listing_count=len(unnotified),
                    recipient=channel.get_recipient(config),
                    success=False,
                )

        # --- 5. Mark listings as notified (only if at least one channel succeeded) ---
        if any_success:
            mark_listings_notified(listing_ids)
            logger.info(
                "Notification pipeline complete: %d listing(s) sent via %d channel(s).",
                len(unnotified),
                len(self._channels),
            )
        else:
            logger.warning(
                "No channel succeeded — listings NOT marked as notified."
            )

        return {
            "listings_found": len(unnotified),
            "sent": any_success,
        }


# ---------------------------------------------------------------------------
# Legacy function — backward compatibility
# ---------------------------------------------------------------------------


def _build_html_body(listings: list[dict[str, Any]]) -> str:
    """Build an HTML email body with a table of listing details.

    .. deprecated::
        Use :meth:`EmailChannel._build_html_body` instead.  This wrapper
        delegates to ``EmailChannel._build_html_body`` to avoid code
        duplication.

    Args:
        listings: List of normalized listing dictionaries.

    Returns:
        An HTML string suitable for the email body.
    """
    warnings.warn(
        "_build_html_body() is deprecated — use EmailChannel._build_html_body() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    config = {}
    try:
        config = load_config()
    except FileNotFoundError:
        pass
    dashboard_url = config.get("email", {}).get("dashboard_url", "http://sunnynest:8000")
    return EmailChannel._build_html_body(listings, dashboard_url)


def send_notification(listings: list[dict[str, Any]], config: dict[str, Any]) -> bool:
    """Send an HTML email notification for new rental listings.

    .. deprecated::
        Use :class:`NotificationService` with :class:`EmailChannel` instead.
        This legacy wrapper delegates to ``EmailChannel.send()``.

    Args:
        listings: List of new listing dictionaries (normalized format).
        config: The ``email`` section of the application config, expected
            keys: ``enabled``, ``smtp_server``, ``smtp_port``,
            ``sender_email``, ``sender_password``, ``recipient_email``.

    Returns:
        ``True`` if the email was sent successfully, ``False`` otherwise.
    """
    warnings.warn(
        "send_notification() is deprecated — use NotificationService with "
        "EmailChannel instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    # Wrap the email-section config into a full config dict for EmailChannel
    full_config = {"email": config}
    channel = EmailChannel()
    return channel.send(listings, full_config)
