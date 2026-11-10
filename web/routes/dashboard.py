"""Dashboard route — serves the main SunnyNest page at GET /."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Request

from src.database import (
    get_filtered_listings,
    get_last_successful_notification_at,
    get_unnotified_listings,
)
from src.notifier import load_notification_filters
from src.poi import list_pois
from src.utils import load_config
from web.dependencies import templates
from web.routes import parse_filters

logger = logging.getLogger("rental_finder.web.dashboard")

# Threshold for raising the "notifications appear silent" banner.
# Twice-daily schedule means a successful send normally happens at most
# ~12 h apart; 48 h is two missed cycles, which is the threshold the
# user picked as "definitely broken, not just a quiet day".
_SILENCE_THRESHOLD_HOURS = 48

router = APIRouter()

# Dropdown default values — the source of truth for initial page load.
# These MUST match the hidden input values in dashboard.html.
# Defaults derived from config.yaml filters (min_price=5000, max_price=7500,
# min_bedrooms=3) so the initial view shows the same ~8 listings the user expects.
_DROPDOWN_DEFAULTS = {
    "filter_price_min": "5000",
    "filter_price_max": "7500",
    "filter_beds": "3",
    "filter_baths": "any",
    "filter_source": "all",
    "filter_sort": "newest",
    "filter_sqft_min": "",
    "filter_sqft_max": "",
    "filter_pet": "",
    "filter_ac": "",
    "filter_furnished": "",
    "filter_favorites": "",
    "filter_max_days": "30",
}


def _compute_notification_silence_state() -> dict[str, Any] | None:
    """Detect when the notification pipeline has gone silent unexpectedly.

    Returns a dict ``{"hours_silent": int, "unnotified_count": int}`` when
    BOTH conditions hold:

    1. No successful notification has been logged in the last
       :data:`_SILENCE_THRESHOLD_HOURS` hours (or never).
    2. There are unnotified, active listings matching the user's
       ``config.yaml`` notification filters within the same window
       (so we don't false-alarm during legitimate quiet weeks).

    Returns ``None`` when the system looks healthy or when there is
    simply nothing to notify about.  All exceptions are swallowed and
    logged — the silence banner must never break the dashboard.
    """
    try:
        # ── 1. Last successful send ────────────────────────────────────
        last_success = get_last_successful_notification_at()
        now_utc = datetime.now(timezone.utc)
        cutoff = now_utc - timedelta(hours=_SILENCE_THRESHOLD_HOURS)

        # NotificationLog.sent_at is stored as a naive UTC datetime
        # (SQLite drops tz info on write).  Normalise both sides.
        if last_success is not None:
            last_success_utc = (
                last_success
                if last_success.tzinfo is not None
                else last_success.replace(tzinfo=timezone.utc)
            )
            if last_success_utc >= cutoff:
                return None  # recent success → not silent
            hours_silent = int((now_utc - last_success_utc).total_seconds() // 3600)
        else:
            # No success ever recorded — treat as "silent for the
            # entire threshold window" so the banner shows.
            hours_silent = _SILENCE_THRESHOLD_HOURS

        # ── 2. Would the notifier have had anything to send? ───────────
        # Use the shared load_notification_filters() helper so this check
        # automatically stays in lockstep with NotificationService.run() —
        # any filter added there propagates here with no code change.
        try:
            config = load_config()
        except FileNotFoundError:
            config = {}

        notification_filters = load_notification_filters(config)

        unnotified = get_unnotified_listings(
            filters=notification_filters if notification_filters else None,
        )
        # Only count listings discovered DURING the silent window — older
        # unnotified listings predate the outage and are not evidence of
        # an active failure.
        recent_unnotified = [
            l for l in unnotified
            if l.first_seen is not None and (
                l.first_seen if l.first_seen.tzinfo is not None
                else l.first_seen.replace(tzinfo=timezone.utc)
            ) >= cutoff
        ]
        if not recent_unnotified:
            return None  # silent, but nothing was due to be sent → quiet period

        return {
            "hours_silent": hours_silent,
            "unnotified_count": len(recent_unnotified),
        }
    except Exception:
        # Silence detector is best-effort; never break the dashboard.
        logger.exception("Silence detector failed; suppressing banner.")
        return None


@router.get("/")
async def dashboard(request: Request):
    """Render the full dashboard page with listings from the database."""
    filters = parse_filters(
        filter_price_min=_DROPDOWN_DEFAULTS["filter_price_min"],
        filter_price_max=_DROPDOWN_DEFAULTS["filter_price_max"],
        filter_beds=_DROPDOWN_DEFAULTS["filter_beds"],
        filter_baths=_DROPDOWN_DEFAULTS["filter_baths"],
        filter_source=_DROPDOWN_DEFAULTS["filter_source"],
        filter_sqft_min=_DROPDOWN_DEFAULTS["filter_sqft_min"],
        filter_sqft_max=_DROPDOWN_DEFAULTS["filter_sqft_max"],
        filter_pet=_DROPDOWN_DEFAULTS["filter_pet"],
        filter_ac=_DROPDOWN_DEFAULTS["filter_ac"],
        filter_furnished=_DROPDOWN_DEFAULTS["filter_furnished"],
        filter_favorites=_DROPDOWN_DEFAULTS["filter_favorites"],
        filter_max_days=_DROPDOWN_DEFAULTS["filter_max_days"],
    )

    listings = get_filtered_listings(filters)

    # Sort by newest first
    listings.sort(
        key=lambda l: l.listed_date or (l.first_seen.date() if l.first_seen else date.min),
        reverse=True,
    )

    # Load POIs for the panel
    pois = list_pois()
    category_icons = {
        "work": "🏢",
        "school": "🏫",
        "park": "🌳",
        "transit": "🚉",
        "shopping": "🛒",
        "custom": "📍",
    }

    # Notification health check — surfaces silent failures to the user
    # without requiring a trip to /admin/notifications.
    notification_silence = _compute_notification_silence_state()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        context={
            "listings": listings,
            "listing_count": len(listings),
            "today": date.today(),
            "active_filters": _DROPDOWN_DEFAULTS,
            "pois": pois,
            "category_icons": category_icons,
            "notification_silence": notification_silence,
        },
    )
