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
import json
import logging
import os
import smtplib
import ssl
import warnings
from dataclasses import dataclass
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


@dataclass(frozen=True)
class SendResult:
    """Result of a notification send attempt with structured diagnostics.

    Channels return a ``SendResult`` from :meth:`BaseNotificationChannel.send_with_diagnostics`
    so the orchestrator can persist categorised failure information into
    the ``notification_log`` table for the admin UI to surface.

    Known ``error_category`` values (see also ``log_notification`` docs):
        * ``"missing_credentials"`` — env vars / config missing
        * ``"no_listings"`` — nothing to send
        * ``"disabled"`` — channel disabled in config
        * ``"token_expired"`` — WhatsApp OAuth token expired/invalid (HTTP 401, code 190)
        * ``"auth"`` — generic auth failure (e.g. SMTP auth, 403)
        * ``"rate_limited"`` — HTTP 429
        * ``"recipient_refused"`` — invalid recipient
        * ``"network"`` — connection / DNS / timeout
        * ``"api_error"`` — non-2xx response from upstream API
        * ``"unexpected"`` — unhandled exception
    """

    success: bool
    error_category: str | None = None
    error_message: str | None = None


class BaseNotificationChannel(abc.ABC):
    """Abstract base class for notification channels.

    Subclasses must implement :meth:`send` and the :attr:`channel_name`
    property so that ``NotificationService`` can dispatch generically.

    Subclasses *should* also implement :meth:`send_with_diagnostics` to
    return a :class:`SendResult` with structured failure categorisation.
    The default implementation wraps :meth:`send` and produces only a
    boolean result with no diagnostic detail — channels that override it
    enable the admin UI to display specific warnings (e.g. expired
    OAuth tokens).
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

    def send_with_diagnostics(
        self, listings: list[Any], config: dict[str, Any]
    ) -> SendResult:
        """Send a notification and return structured diagnostics.

        Default implementation delegates to :meth:`send` and returns a
        generic failure category.  Subclasses should override to provide
        precise classification (e.g. ``"token_expired"`` for WhatsApp).

        Args:
            listings: Listing ORM objects (or dicts) to include.
            config: The full application config dictionary.

        Returns:
            A :class:`SendResult` describing the outcome.
        """
        ok = self.send(listings, config)
        if ok:
            return SendResult(success=True)
        return SendResult(
            success=False,
            error_category="unexpected",
            error_message=f"{self.channel_name} channel reported failure (no detail)",
        )

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

        Backward-compatible wrapper around :meth:`send_with_diagnostics`.

        Args:
            listings: Listing ORM objects to include in the email.
            config: Full application config (needs ``email`` section).

        Returns:
            ``True`` on success, ``False`` otherwise.
        """
        return self.send_with_diagnostics(listings, config).success

    def send_with_diagnostics(
        self, listings: list[Any], config: dict[str, Any]
    ) -> SendResult:
        """Send an HTML email and return a :class:`SendResult` with diagnostics."""
        email_cfg = config.get("email", {})

        if not email_cfg.get("enabled", False):
            logger.info("Email notifications are disabled in config.")
            return SendResult(
                success=False,
                error_category="disabled",
                error_message="Email channel is disabled in config.yaml.",
            )

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
            return SendResult(
                success=False,
                error_category="missing_credentials",
                error_message=(
                    "Email credentials incomplete. Set sender_email, "
                    "SMTP_PASSWORD, and recipient_email."
                ),
            )

        if not listings:
            logger.info("No listings to notify about.")
            return SendResult(
                success=False,
                error_category="no_listings",
                error_message="No matching listings to send.",
            )

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
            return SendResult(success=True)

        except smtplib.SMTPAuthenticationError as exc:
            logger.error(
                "SMTP authentication failed. Check sender_email and sender_password "
                "(use an app-specific password for Gmail)."
            )
            return SendResult(
                success=False,
                error_category="auth",
                error_message=(
                    f"SMTP authentication failed: {exc}. "
                    "Use an app-specific password for Gmail."
                ),
            )
        except smtplib.SMTPRecipientsRefused:
            logger.error("Recipient address refused: %s", recipient_email)
            return SendResult(
                success=False,
                error_category="recipient_refused",
                error_message=f"Recipient refused: {recipient_email}",
            )
        except smtplib.SMTPException as exc:
            logger.error("SMTP error while sending notification: %s", exc)
            return SendResult(
                success=False,
                error_category="api_error",
                error_message=f"SMTP error: {exc}",
            )
        except OSError as exc:
            logger.error("Network error while sending notification: %s", exc)
            return SendResult(
                success=False,
                error_category="network",
                error_message=f"Network error: {exc}",
            )
        except Exception as exc:
            logger.exception("Unexpected error while sending email notification")
            return SendResult(
                success=False,
                error_category="unexpected",
                error_message=f"Unexpected error: {exc}",
            )

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

        Backward-compatible wrapper around :meth:`send_with_diagnostics`.

        Args:
            listings: Listing ORM objects to include in the message.
            config: Full application config (needs ``whatsapp`` section).

        Returns:
            ``True`` on success, ``False`` otherwise.
        """
        return self.send_with_diagnostics(listings, config).success

    @staticmethod
    def _classify_meta_error(
        status_code: int, body_text: str
    ) -> tuple[str, str]:
        """Classify a Meta Graph API error response.

        Detects expired/invalid OAuth tokens (the most common failure
        mode for Test Numbers, which issue ~24h tokens) so the admin UI
        can surface a clear "regenerate token" warning.

        Detection rules (from Meta error format docs):
        * HTTP **401** → almost always an OAuth/token problem
        * JSON body with ``error.type == "OAuthException"`` → token issue
        * Meta error ``code`` 190 → "Access token has expired"
        * Meta error ``code`` 102 / 463 / 467 → session expired / token invalid

        Args:
            status_code: HTTP status code from the Graph API response.
            body_text: Response body (truncated to ~500 chars).

        Returns:
            A ``(error_category, error_message)`` tuple ready for
            :func:`log_notification` and the admin banner.
        """
        # Try parsing JSON to extract structured Meta error details.
        meta_type: str = ""
        meta_code: int | None = None
        meta_message: str = ""
        try:
            parsed = json.loads(body_text)
            err = parsed.get("error", {}) if isinstance(parsed, dict) else {}
            meta_type = str(err.get("type", "") or "")
            meta_message = str(err.get("message", "") or "")
            raw_code = err.get("code")
            if isinstance(raw_code, int):
                meta_code = raw_code
            elif isinstance(raw_code, str) and raw_code.isdigit():
                meta_code = int(raw_code)
        except (ValueError, TypeError, json.JSONDecodeError):
            pass  # Non-JSON response — fall back to status_code only.

        is_oauth = (
            status_code == 401
            or meta_type == "OAuthException"
            or meta_code in (190, 102, 463, 467)
        )

        if is_oauth:
            human = (
                meta_message
                or "WhatsApp access token has expired or is invalid."
            )
            detail = (
                f"WhatsApp OAuth failure (HTTP {status_code}"
                + (f", code {meta_code}" if meta_code else "")
                + f"): {human} "
                "Regenerate the token at developers.facebook.com → "
                "your App → WhatsApp → API Setup, then update "
                "WHATSAPP_API_TOKEN in .env."
            )
            return "token_expired", detail

        if status_code == 429:
            return "rate_limited", (
                f"WhatsApp API rate-limited (HTTP 429): "
                f"{meta_message or body_text[:200]}"
            )

        if status_code in (400, 403):
            category = "auth" if status_code == 403 else "api_error"
            return category, (
                f"WhatsApp API HTTP {status_code}"
                + (f" (code {meta_code})" if meta_code else "")
                + f": {meta_message or body_text[:200]}"
            )

        return "api_error", (
            f"WhatsApp API HTTP {status_code}: "
            f"{meta_message or body_text[:200]}"
        )

    @classmethod
    def validate_token(
        cls,
        api_token: str | None = None,
        phone_number_id: str | None = None,
        timeout: float = 10.0,
    ) -> SendResult:
        """Probe the Meta Graph API to verify the WhatsApp token is valid.

        Performs a cheap ``GET /{phone_number_id}`` request that does
        **not** consume any messaging quota.  Used by the FastAPI
        startup hook to surface expired tokens early.

        Args:
            api_token: Override env var ``WHATSAPP_API_TOKEN``.
            phone_number_id: Override env var ``WHATSAPP_PHONE_NUMBER_ID``.
            timeout: Request timeout in seconds.

        Returns:
            A :class:`SendResult` with ``success=True`` if the token is
            valid; otherwise structured failure diagnostics.
        """
        token = (api_token or os.environ.get("WHATSAPP_API_TOKEN", "")).strip()
        phone_id = (
            phone_number_id or os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
        ).strip()

        if not token or not phone_id:
            return SendResult(
                success=False,
                error_category="missing_credentials",
                error_message=(
                    "WHATSAPP_API_TOKEN and/or WHATSAPP_PHONE_NUMBER_ID "
                    "are not set."
                ),
            )

        url = f"{cls._API_BASE}/{phone_id}"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            import httpx

            ssl_ctx = cls._build_ssl_context()
            with httpx.Client(timeout=timeout, verify=ssl_ctx) as client:
                resp = client.get(url, headers=headers)

            if resp.status_code == 200:
                return SendResult(success=True)

            category, message = cls._classify_meta_error(
                resp.status_code, resp.text[:500]
            )
            return SendResult(
                success=False,
                error_category=category,
                error_message=message,
            )
        except ImportError:
            return SendResult(
                success=False,
                error_category="unexpected",
                error_message="httpx not installed.",
            )
        except Exception as exc:
            return SendResult(
                success=False,
                error_category="network",
                error_message=f"Token validation network error: {exc}",
            )

    def send_with_diagnostics(
        self, listings: list[Any], config: dict[str, Any]
    ) -> SendResult:
        """Send a WhatsApp text message and return structured diagnostics.

        Detects token-expired (HTTP 401 / Meta OAuthException / code 190)
        failures distinctly from other API errors so the admin UI can
        surface a precise "regenerate token" warning banner.
        """
        if not config.get("whatsapp", {}).get("enabled", False):
            logger.info("WhatsApp notifications are disabled in config.")
            return SendResult(
                success=False,
                error_category="disabled",
                error_message="WhatsApp channel is disabled in config.yaml.",
            )

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
            return SendResult(
                success=False,
                error_category="missing_credentials",
                error_message=(
                    "WhatsApp credentials incomplete. Set "
                    "WHATSAPP_API_TOKEN, WHATSAPP_PHONE_NUMBER_ID, and "
                    "WHATSAPP_RECIPIENT_PHONE."
                ),
            )

        if not listings:
            logger.info("No listings to notify about via WhatsApp.")
            return SendResult(
                success=False,
                error_category="no_listings",
                error_message="No matching listings to send.",
            )

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
                return SendResult(success=True)

            # Non-2xx — classify the failure for the admin UI.
            body_text = resp.text[:500] if resp.text else ""
            category, message = self._classify_meta_error(
                resp.status_code, body_text
            )

            if category == "token_expired":
                # Loud log line — operators grepping logs will spot it.
                logger.error(
                    "WhatsApp TOKEN EXPIRED (HTTP %d): %s",
                    resp.status_code,
                    body_text,
                )
            else:
                logger.error(
                    "WhatsApp API returned HTTP %d: %s",
                    resp.status_code,
                    body_text,
                )

            return SendResult(
                success=False,
                error_category=category,
                error_message=message,
            )

        except ImportError:
            logger.error(
                "httpx is not installed — cannot send WhatsApp notifications. "
                "Run: pip install httpx"
            )
            return SendResult(
                success=False,
                error_category="unexpected",
                error_message="httpx is not installed.",
            )
        except Exception as exc:
            logger.exception("Unexpected error while sending WhatsApp notification")
            return SendResult(
                success=False,
                error_category="unexpected",
                error_message=f"Unexpected error: {exc}",
            )

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
# Telegram channel (Bot API)
# ---------------------------------------------------------------------------


class TelegramChannel(BaseNotificationChannel):
    """Telegram notification channel via the Bot API.

    Sends a concise text message with listing summaries using the
    Telegram Bot API.  Credentials are read from environment variables
    (``TELEGRAM_BOT_TOKEN``, ``TELEGRAM_CHAT_ID``).

    Why Telegram (vs. WhatsApp)?
        * Bot tokens are long-lived (no ~24 h Test Number expiry).
        * No recipient allowlist for personal DMs (no silent drops).
        * Same 4096-char text limit and HTTPS-JSON contract as WhatsApp,
          so the implementation mirrors :class:`WhatsAppChannel` 1:1.

    Reply formatting uses ``parse_mode=HTML`` (NOT MarkdownV2 — its
    escape rules are notoriously fragile).  Listing fields are passed
    through :func:`html.escape` before substitution as defence-in-depth.
    """

    _TELEGRAM_TEXT_LIMIT: int = 4096
    _TELEGRAM_TEXT_BUDGET: int = 4000  # leave 96-char headroom under the hard limit
    _API_BASE: str = "https://api.telegram.org"

    @property
    def channel_name(self) -> str:  # noqa: D401
        return "telegram"

    # ------------------------------------------------------------------
    # SSL helper (mirrors WhatsAppChannel — see plans/telegram-channel.md §7)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_ssl_context() -> ssl.SSLContext:
        """Build an SSL context for Telegram Bot API requests.

        Identical to :meth:`WhatsAppChannel._build_ssl_context` — both
        services are HTTPS endpoints behind the same PANW GlobalProtect
        TLS-decryption proxy in this deployment.

        Hoisting this helper to module level is deferred to a follow-up
        cleanup PR (see ``plans/telegram-channel.md`` §7 Option B).

        Returns:
            A configured :class:`ssl.SSLContext`.
        """
        ctx = ssl.create_default_context(cafile=certifi.where())

        if _PANW_CA_PATH.exists():
            ctx.load_verify_locations(cafile=str(_PANW_CA_PATH))
            logger.info(
                "Telegram: loaded PANW Enterprise Root CA for TLS decryption proxy (%s)",
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
        """Return the recipient ``chat_id`` from env var.

        ``TELEGRAM_CHAT_ID`` is intentionally an env var (not in
        ``config.yaml``) so it pairs atomically with ``TELEGRAM_BOT_TOKEN``
        and isn't readable by anything that can read ``config.yaml``.
        """
        return os.environ.get("TELEGRAM_CHAT_ID", "").strip() or "unknown"

    def is_enabled(self, config: dict[str, Any]) -> bool:
        """Return whether Telegram notifications are enabled in config."""
        return config.get("telegram", {}).get("enabled", False)

    def send(self, listings: list[Any], config: dict[str, Any]) -> bool:
        """Send a Telegram message with listing summaries.

        Backward-compatible wrapper around :meth:`send_with_diagnostics`.

        Args:
            listings: Listing ORM objects to include in the message.
            config: Full application config (needs ``telegram`` section).

        Returns:
            ``True`` on success, ``False`` otherwise.
        """
        return self.send_with_diagnostics(listings, config).success

    @staticmethod
    def _classify_telegram_error(
        status_code: int, body_text: str
    ) -> tuple[str, str]:
        """Classify a Telegram Bot API error response.

        Maps Telegram error responses to the existing
        :class:`SendResult` ``error_category`` taxonomy.  No new
        categories are introduced — see ``plans/telegram-channel.md`` §4.

        Detection rules:
            * HTTP **401** → ``auth`` (bot token invalid / revoked via
              BotFather — Telegram has no auto-expiry equivalent of
              WhatsApp's ``token_expired``).
            * HTTP **429** → ``rate_limited`` (extracts
              ``parameters.retry_after`` if present).
            * Description contains ``"bot was blocked by the user"`` or
              ``"chat not found"`` → ``recipient_refused`` (Telegram is
              inconsistent on whether it returns 400 or 403 for this).
            * HTTP **400** (other) → ``api_error``.
            * Anything else → ``api_error``.

        Args:
            status_code: HTTP status code from the Bot API response.
            body_text: Response body (truncated to ~500 chars).

        Returns:
            A ``(error_category, error_message)`` tuple ready for
            :func:`log_notification` and the admin banner.
        """
        description: str = ""
        retry_after: int | None = None
        try:
            parsed = json.loads(body_text)
            if isinstance(parsed, dict):
                description = str(parsed.get("description", "") or "").lower()
                params = parsed.get("parameters")
                if isinstance(params, dict):
                    raw_ra = params.get("retry_after")
                    if isinstance(raw_ra, int):
                        retry_after = raw_ra
                    elif isinstance(raw_ra, str) and raw_ra.isdigit():
                        retry_after = int(raw_ra)
        except (ValueError, TypeError, json.JSONDecodeError):
            # Non-JSON response — fall back to status_code only.
            pass

        # 1. Auth — bad / revoked bot token.
        if status_code == 401:
            return "auth", (
                "Telegram bot token invalid (HTTP 401). "
                "Check TELEGRAM_BOT_TOKEN in .env, or regenerate via "
                "@BotFather → /revoke → /token."
            )

        # 2. Recipient refused — must be checked BEFORE the generic 400
        #    branch because Telegram returns "chat not found" as 400.
        if (
            "bot was blocked by the user" in description
            or "chat not found" in description
        ):
            return "recipient_refused", (
                f"Telegram recipient refused (HTTP {status_code}): "
                f"{description[:200]}. "
                "Verify TELEGRAM_CHAT_ID and that the user has not blocked the bot."
            )

        # 3. Rate-limited.
        if status_code == 429:
            ra_str = f" retry_after={retry_after}s" if retry_after else ""
            return "rate_limited", (
                f"Telegram rate-limited (HTTP 429){ra_str}: "
                f"{description[:200] or body_text[:200]}"
            )

        # 4. Generic 400 (bad request body, e.g. malformed HTML).
        if status_code == 400:
            return "api_error", (
                f"Telegram bad request (HTTP 400): "
                f"{description[:200] or body_text[:200]}"
            )

        # 5. Catch-all — 5xx Telegram outages and any other status.
        return "api_error", (
            f"Telegram API HTTP {status_code}: "
            f"{description[:200] or body_text[:200]}"
        )

    @classmethod
    def validate_token(
        cls,
        bot_token: str | None = None,
        timeout: float = 10.0,
    ) -> SendResult:
        """Probe the Telegram Bot API to verify the token is valid.

        Performs a cheap ``GET /bot<token>/getMe`` request — free and
        does NOT consume any messaging quota.  Used by the FastAPI
        startup hook to surface invalid tokens early.

        Args:
            bot_token: Override env var ``TELEGRAM_BOT_TOKEN``.
            timeout: Request timeout in seconds.

        Returns:
            A :class:`SendResult` with ``success=True`` if the token is
            valid; otherwise structured failure diagnostics.
        """
        token = (bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()

        if not token:
            return SendResult(
                success=False,
                error_category="missing_credentials",
                error_message="TELEGRAM_BOT_TOKEN is not set.",
            )

        url = f"{cls._API_BASE}/bot{token}/getMe"

        try:
            import httpx

            ssl_ctx = cls._build_ssl_context()
            with httpx.Client(timeout=timeout, verify=ssl_ctx) as client:
                resp = client.get(url)

            if resp.status_code == 200:
                return SendResult(success=True)

            category, message = cls._classify_telegram_error(
                resp.status_code, resp.text[:500]
            )
            return SendResult(
                success=False,
                error_category=category,
                error_message=message,
            )
        except ImportError:
            return SendResult(
                success=False,
                error_category="unexpected",
                error_message="httpx not installed.",
            )
        except Exception as exc:
            return SendResult(
                success=False,
                error_category="network",
                error_message=f"Token validation network error: {exc}",
            )

    def send_with_diagnostics(
        self, listings: list[Any], config: dict[str, Any]
    ) -> SendResult:
        """Send a Telegram message and return structured diagnostics."""
        if not config.get("telegram", {}).get("enabled", False):
            logger.info("Telegram notifications are disabled in config.")
            return SendResult(
                success=False,
                error_category="disabled",
                error_message="Telegram channel is disabled in config.yaml.",
            )

        # --- Credentials from env vars ---
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

        if not bot_token or not chat_id:
            logger.warning(
                "Telegram credentials are incomplete — skipping notification. "
                "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables."
            )
            return SendResult(
                success=False,
                error_category="missing_credentials",
                error_message=(
                    "Telegram credentials incomplete. Set "
                    "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID."
                ),
            )

        if not listings:
            logger.info("No listings to notify about via Telegram.")
            return SendResult(
                success=False,
                error_category="no_listings",
                error_message="No matching listings to send.",
            )

        # --- Build message body (HTML, escaped) ---
        body = self._build_text_body(listings)
        parse_mode = str(
            config.get("telegram", {}).get("parse_mode", "HTML")
        )

        # --- Send via Telegram Bot API ---
        url = f"{self._API_BASE}/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": body,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        # Mask all but last 4 digits for log lines (chat_id is a co-secret).
        masked_chat = (
            ("…" + chat_id[-4:]) if len(chat_id) > 4 else "…"
        )

        try:
            import httpx

            ssl_ctx = self._build_ssl_context()

            logger.info(
                "Sending Telegram notification (%d listing(s)) to chat_id=%s",
                len(listings),
                masked_chat,
            )
            with httpx.Client(timeout=30, verify=ssl_ctx) as client:
                resp = client.post(url, json=payload)

            if resp.status_code == 200:
                logger.info(
                    "Telegram notification sent successfully to chat_id=%s",
                    masked_chat,
                )
                return SendResult(success=True)

            # Non-2xx — classify the failure for the admin UI.
            body_text = resp.text[:500] if resp.text else ""
            category, message = self._classify_telegram_error(
                resp.status_code, body_text
            )

            logger.error(
                "Telegram API returned HTTP %d: %s",
                resp.status_code,
                body_text,
            )

            return SendResult(
                success=False,
                error_category=category,
                error_message=message,
            )

        except ImportError:
            logger.error(
                "httpx is not installed — cannot send Telegram notifications. "
                "Run: pip install httpx"
            )
            return SendResult(
                success=False,
                error_category="unexpected",
                error_message="httpx is not installed.",
            )
        except Exception as exc:
            # Network / DNS / timeout from httpx are surfaced through the
            # general handler.  ``logger.exception`` per silent-failure-pattern
            # guidance — never speculate in the log message.
            logger.exception("Unexpected error while sending Telegram notification")
            try:
                import httpx as _httpx

                if isinstance(exc, (_httpx.TimeoutException, _httpx.NetworkError)):
                    return SendResult(
                        success=False,
                        error_category="network",
                        error_message=f"Network error: {exc}",
                    )
            except ImportError:
                pass
            return SendResult(
                success=False,
                error_category="unexpected",
                error_message=f"Unexpected error: {exc}",
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_text_body(self, listings: list[Any]) -> str:
        """Build a concise HTML message body — one line per listing.

        Uses Telegram HTML mode: ``<a href="…">…</a>`` for tappable
        links.  All listing fields are passed through
        :func:`html.escape` to prevent rendering breakage from titles
        with ``<``, ``>``, or ``&`` characters (and as defence-in-depth
        per :doc:`security-patterns`).

        Per the Design Bible, area is shown as
        ``1,200 sqft (111 m²)`` when ``sqft`` is present.

        Truncates at ``_TELEGRAM_TEXT_BUDGET`` (4000 chars — leaves
        96-char headroom under Telegram's 4096-char hard limit) and
        appends a ``"…and N more"`` footer.

        Args:
            listings: Listing ORM objects or dicts.

        Returns:
            An HTML string for the Telegram message body.
        """
        # Local import to avoid a top-level circular with src.utils.
        from src.utils import sqft_to_sqm

        def _get(obj: Any, key: str, default: Any = None) -> Any:
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        count = len(listings)
        header = (
            f"🏠 {count} new listing{'s' if count != 1 else ''} in Sunnyvale\n\n"
        )

        lines: list[str] = []
        for listing in listings:
            title = html_module.escape(str(_get(listing, "title", "N/A")))
            price = _get(listing, "price")
            price_str = f"${price:,.0f}/mo" if price else "N/A"
            bedrooms = _get(listing, "bedrooms", "?")
            address = html_module.escape(str(_get(listing, "address", "")))
            sqft = _get(listing, "sqft")
            url = _get(listing, "url", "")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                url = ""

            # Header line: clickable title with price + BR
            heading_text = f"{title} — {price_str}, {bedrooms}BR"
            if url:
                # url goes inside an HTML attribute → escape with quote=True
                safe_url = html_module.escape(url, quote=True)
                first_line = f"• <a href=\"{safe_url}\">{heading_text}</a>"
            else:
                first_line = f"• {heading_text}"

            # Sub-line: address + area (sqft + m²)
            sub_parts: list[str] = []
            if address:
                sub_parts.append(address)
            if sqft:
                try:
                    sqm = sqft_to_sqm(sqft)
                    sub_parts.append(
                        f"{int(sqft):,} sqft ({int(round(sqm)):,} m²)"
                    )
                except (TypeError, ValueError):
                    pass
            sub_line = "  " + " · ".join(sub_parts) if sub_parts else ""

            lines.append(first_line + ("\n" + sub_line if sub_line else ""))

        # Truncate to fit within the 4000-char budget (96-char headroom
        # below the 4096 hard limit).
        result = header
        truncated = 0
        for i, line in enumerate(lines):
            candidate = result + line + "\n"
            footer_reserve = 30
            if len(candidate) + footer_reserve > self._TELEGRAM_TEXT_BUDGET:
                truncated = len(lines) - i
                break
            result = candidate

        if truncated:
            result += (
                f"\n…and {truncated} more "
                f"listing{'s' if truncated != 1 else ''}"
            )

        return result.strip()


# ---------------------------------------------------------------------------
# Notification service (orchestrator)
# ---------------------------------------------------------------------------


def load_notification_filters(config: dict) -> dict[str, Any]:
    """Extract the listing-filter sub-dict that ``NotificationService`` uses
    to gate which listings are eligible for notification.

    Returned shape matches what ``get_unnotified_listings(filters=...)``
    expects.  Single source of truth for two callers:

    - :meth:`NotificationService.run` — decides what to actually send.
    - ``web.routes.dashboard._compute_notification_silence_state`` —
      decides whether the silence-detector banner should appear (must
      mirror what the notifier WOULD have attempted to deliver).

    Keeping the extraction in one place eliminates the drift risk that a
    new filter added on one side and forgotten on the other would silently
    false-positive the silence banner.

    Args:
        config: The full ``config.yaml`` dict (the function reads only the
            ``filters`` sub-dict; missing keys are tolerated).

    Returns:
        A dict containing only the filter keys that are set in config.
        Note the ``property_types`` config key maps to the singular
        ``property_type`` filter key expected by
        :func:`src.database.get_unnotified_listings`.
    """
    filters_cfg = (config.get("filters") or {})
    out: dict[str, Any] = {}
    if filters_cfg.get("min_price"):
        out["min_price"] = filters_cfg["min_price"]
    if filters_cfg.get("max_price"):
        out["max_price"] = filters_cfg["max_price"]
    if filters_cfg.get("min_bedrooms"):
        out["min_bedrooms"] = filters_cfg["min_bedrooms"]
    if filters_cfg.get("max_bedrooms"):
        out["max_bedrooms"] = filters_cfg["max_bedrooms"]
    if filters_cfg.get("property_types"):
        out["property_type"] = filters_cfg["property_types"]
    return out


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
        # only include listings matching their preferences.  Filter
        # extraction lives in ``load_notification_filters`` so the silence
        # detector in web.routes.dashboard stays in lockstep automatically.
        notification_filters = load_notification_filters(config)

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
                result = channel.send_with_diagnostics(unnotified, config)
                any_success = any_success or result.success

                # Log the notification attempt with structured diagnostics.
                log_notification(
                    channel=channel.channel_name,
                    listing_count=len(unnotified),
                    recipient=recipient,
                    success=result.success,
                    error_category=result.error_category,
                    error_message=result.error_message,
                )
            except Exception as exc:
                logger.exception(
                    "Channel %s failed unexpectedly.", channel.channel_name
                )
                # Log the failure with the unhandled-exception tag.
                log_notification(
                    channel=channel.channel_name,
                    listing_count=len(unnotified),
                    recipient=channel.get_recipient(config),
                    success=False,
                    error_category="unexpected",
                    error_message=f"Unhandled exception in channel: {exc}",
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
