"""Admin panel routes for the SunnyNest backoffice.

Serves the admin dashboard under ``/admin/`` with pages for:
- Dashboard (KPIs and overview)
- Listing Analytics (price distribution, source breakdown)
- API Usage (budget tracking, call log)
- Notifications (send history, delivery stats)
- Settings (read-only config display)
"""

from __future__ import annotations

import asyncio
import calendar
import logging
import os
import time
import traceback
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from src.database import (
    get_api_call_count,
    get_api_call_count_for_period,
    get_api_calls_by_day,
    get_api_success_rate_by_day,
    get_batch_price_changes,
    get_data_freshness,
    get_filtered_listings,
    get_lifecycle_by_bedrooms,
    get_lifecycle_by_price_range,
    get_lifecycle_stats,
    get_listing_inventory_timeline,
    get_listing_stats,
    get_notification_history,
    get_notification_stats,
    get_notifications_by_day,
    get_recent_api_calls,
    get_scrape_activity_grid,
    get_session,
    get_source_counts,
    get_source_counts_with_inactive,
    get_today_notification_count,
)
from src.utils import get_email_settings, get_whatsapp_settings, load_config, sqft_to_sqm
from web.dependencies import get_env_status, templates

logger = logging.getLogger("sunnynest.admin")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def _check_admin_auth(
    request: Request,
    admin_key: str | None = Query(None, alias="key"),
):
    """Simple shared-secret auth for admin panel.

    If ADMIN_SECRET_KEY env var is set, requires ?key=<secret> query param.
    If not set (dev mode), all access is allowed.
    """
    expected = os.environ.get("ADMIN_SECRET_KEY", "").strip()
    if not expected:
        return  # No secret configured — dev mode, allow all
    if admin_key != expected:
        raise HTTPException(status_code=403, detail="Forbidden — invalid admin key")


router = APIRouter(prefix="/admin", dependencies=[Depends(_check_admin_auth)])

# Budget limit constants per source
API_BUDGET_LIMITS: dict[str, int] = {
    "zillow": 500,
    "realtor": 150,
}
# Legacy alias used in a few places
API_BUDGET_LIMIT = API_BUDGET_LIMITS["zillow"]

# NOTE: Module-level lock — only effective with a single Uvicorn worker.
# If scaling to multiple workers, use a distributed lock (Redis, file lock, etc.)
_sync_lock = asyncio.Lock()

# Rate-limit: 5-minute cooldown between manual syncs to protect API budget
_last_sync_time: float = 0.0
_SYNC_COOLDOWN_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _relative_time(dt: datetime | None) -> str:
    """Format a datetime as a human-readable relative time string."""
    if dt is None:
        return "No data"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days == 1:
        return "1d ago"
    return f"{days}d ago"


def _format_datetime(dt: datetime | None) -> str:
    """Format a datetime for table display."""
    if dt is None:
        return "—"
    if isinstance(dt, str):
        return dt
    return dt.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/")
async def admin_dashboard(request: Request):
    """Admin dashboard with KPI cards and summary data."""
    stats = get_listing_stats()
    notif_count = get_today_notification_count()
    freshness = get_data_freshness()
    source_counts = get_source_counts({})

    # Load config for per-source budget limits
    try:
        config = load_config()
    except FileNotFoundError:
        config = {}
    realtor_cfg = config.get("realtor_api", {})

    # Compute worst-case budget across all API sources
    budget_entries = [
        ("Zillow", get_api_call_count("zillow"), API_BUDGET_LIMITS["zillow"]),
        ("Realtor.com", get_api_call_count("realtor"), realtor_cfg.get("monthly_budget", API_BUDGET_LIMITS["realtor"])),
    ]
    worst_pct = 0.0
    worst_source = ""
    total_calls = 0
    total_budget = 0
    for display_name, calls, budget in budget_entries:
        pct = (calls / budget * 100) if budget else 0
        total_calls += calls
        total_budget += budget
        if pct > worst_pct:
            worst_pct = pct
            worst_source = display_name

    if worst_pct < 60:
        budget_status = "green"
    elif worst_pct < 80:
        budget_status = "amber"
    else:
        budget_status = "red"

    # Recent listings (last 10)
    recent_listings = get_filtered_listings({"is_active": True})[:10]

    # Environment health check
    env_status = get_env_status()

    # Scrape activity heatmap (last 30 days)
    scrape_activity = get_scrape_activity_grid(days=30)

    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        context={
            "active_page": "dashboard",
            "stats": stats,
            "api_calls": total_calls,
            "api_budget": total_budget,
            "budget_pct": round(worst_pct, 1),
            "budget_status": budget_status,
            "budget_worst_source": worst_source,
            "notif_count": notif_count,
            "freshness": _relative_time(freshness),
            "source_counts": source_counts,
            "recent_listings": recent_listings,
            "env_status": env_status,
            "scrape_activity": scrape_activity,
        },
    )


@router.post("/sync")
async def admin_sync(request: Request):
    """Trigger a manual scraper sync and return an HTML partial with results."""
    global _last_sync_time

    # Cooldown check — prevent API budget exhaustion
    elapsed = time.monotonic() - _last_sync_time
    if _last_sync_time > 0 and elapsed < _SYNC_COOLDOWN_SECONDS:
        remaining = int(_SYNC_COOLDOWN_SECONDS - elapsed)
        return HTMLResponse(
            '<div id="sync-result" class="sync-result sync-result--error">'
            '<span class="sync-result__icon">⏳</span>'
            f'<span class="sync-result__text">Please wait {remaining}s before syncing again.</span>'
            '<button class="sync-result__close" onclick="this.parentElement.remove()"'
            ' aria-label="Dismiss">✕</button>'
            "</div>"
        )

    if _sync_lock.locked():
        return HTMLResponse(
            '<div id="sync-result" class="sync-result sync-result--error">'
            '<span class="sync-result__icon">⚠️</span>'
            '<span class="sync-result__text">A sync is already in progress. Please wait.</span>'
            '<button class="sync-result__close" onclick="this.parentElement.remove()"'
            ' aria-label="Dismiss">✕</button>'
            "</div>"
        )

    async with _sync_lock:
        try:
            _last_sync_time = time.monotonic()

            from src.orchestrator import ScraperOrchestrator

            orchestrator = ScraperOrchestrator()
            result = await orchestrator.run_sync()

            total = result.get("total_scraped", 0)
            new = result.get("new_listings", 0)
            updated = result.get("updated_listings", 0)
            errors = result.get("errors", 0)

            return HTMLResponse(
                '<div id="sync-result" class="sync-result sync-result--success">'
                '<span class="sync-result__icon">✅</span>'
                "<span class=\"sync-result__text\">"
                f"Sync complete — <strong>{total}</strong> scraped, "
                f"<strong>{new}</strong> new, "
                f"<strong>{updated}</strong> updated, "
                f"<strong>{errors}</strong> errors"
                "</span>"
                '<button class="sync-result__close" onclick="this.parentElement.remove()"'
                ' aria-label="Dismiss">✕</button>'
                "</div>"
                "<script>setTimeout(()=>{const el=document.getElementById('sync-result');"
                "if(el)el.remove()},30000)</script>"
            )
        except Exception:
            logger.exception("Manual sync failed")
            return HTMLResponse(
                '<div id="sync-result" class="sync-result sync-result--error">'
                '<span class="sync-result__icon">❌</span>'
                '<span class="sync-result__text">Sync failed — check server logs for details.</span>'
                '<button class="sync-result__close" onclick="this.parentElement.remove()"'
                ' aria-label="Dismiss">✕</button>'
                "</div>",
                status_code=500,
            )


@router.get("/analytics")
async def admin_analytics(request: Request):
    """Listing analytics with price distribution and source breakdown."""
    # Load config filters so analytics reflect the user's search criteria
    try:
        config = load_config()
    except FileNotFoundError:
        config = {}
    filters_cfg = config.get("filters", {})

    # Build filter dict for DB queries
    analytics_filters: dict = {"is_active": True}
    if filters_cfg.get("min_price"):
        analytics_filters["min_price"] = filters_cfg["min_price"]
    if filters_cfg.get("max_price"):
        analytics_filters["max_price"] = filters_cfg["max_price"]
    if filters_cfg.get("min_bedrooms"):
        analytics_filters["min_bedrooms"] = filters_cfg["min_bedrooms"]
    if filters_cfg.get("max_bedrooms"):
        analytics_filters["max_bedrooms"] = filters_cfg["max_bedrooms"]
    if filters_cfg.get("property_types"):
        analytics_filters["property_type"] = filters_cfg["property_types"]

    # Use filtered listings for all analytics
    all_listings = get_filtered_listings(analytics_filters)
    prices = [l.price for l in all_listings if l.price is not None]

    # Build price histogram buckets
    price_buckets: list[dict] = []
    if prices:
        min_p = int(min(prices) // 1000 * 1000)
        max_p = int(max(prices) // 1000 * 1000) + 1000
        for bucket_start in range(min_p, max_p, 1000):
            bucket_end = bucket_start + 1000
            count = sum(1 for p in prices if bucket_start <= p < bucket_end)
            if count > 0:
                price_buckets.append({
                    "range": f"${bucket_start:,}–${bucket_end:,}",
                    "count": count,
                })

    # Source breakdown (active vs inactive)
    source_data = get_source_counts_with_inactive()
    bedroom_counts: dict[str, int] = {}
    for listing in all_listings:
        br = listing.bedrooms
        key = f"{br} BR" if br else "Unknown"
        bedroom_counts[key] = bedroom_counts.get(key, 0) + 1

    # Price changes
    listing_ids = [l.id for l in all_listings if l.price is not None]
    listing_info = {
        l.id: {"address": l.address, "sqft": l.sqft}
        for l in all_listings
    }
    price_changes_list: list[dict] = []
    if listing_ids:
        price_changes = get_batch_price_changes(listing_ids)
        for lid, data in price_changes.items():
            if data["price_change"] != 0:
                info = listing_info.get(lid, {})
                sqft_val = info.get("sqft")
                area_str = (
                    f"{sqft_val:,} sqft ({sqft_to_sqm(sqft_val):,.0f} m²)"
                    if sqft_val
                    else "N/A"
                )
                price_changes_list.append({
                    "address": info.get("address", "Unknown"),
                    "old_price": data["first_price"],
                    "new_price": data["current_price"],
                    "change": data["price_change"],
                    "area": area_str,
                })

    # Inventory timeline
    timeline = get_listing_inventory_timeline()

    # Lifecycle analytics
    lifecycle_stats = get_lifecycle_stats()
    lifecycle_by_bedrooms = get_lifecycle_by_bedrooms()
    lifecycle_by_price = get_lifecycle_by_price_range()

    return templates.TemplateResponse(
        request,
        "admin/analytics.html",
        context={
            "active_page": "analytics",
            "price_buckets": price_buckets,
            "source_data": source_data,
            "bedroom_counts": bedroom_counts,
            "price_changes": price_changes_list,
            "timeline": timeline,
            "total_prices": len(prices),
            "avg_price": round(sum(prices) / len(prices), 0) if prices else 0,
            "median_price": sorted(prices)[len(prices) // 2] if prices else 0,
            "lifecycle_stats": lifecycle_stats,
            "lifecycle_by_bedrooms": lifecycle_by_bedrooms,
            "lifecycle_by_price": lifecycle_by_price,
        },
    )


# Status code to human-readable text mapping
_STATUS_CODE_TEXT: dict[int, str] = {
    200: "200 OK",
    201: "201 Created",
    204: "204 No Content",
    400: "400 Bad Request",
    401: "401 Unauthorized",
    403: "403 Forbidden",
    404: "404 Not Found",
    429: "429 Rate Limited",
    500: "500 Server Error",
    502: "502 Bad Gateway",
    503: "503 Service Unavailable",
}


def _build_budget_data(
    display_name: str,
    source_key: str,
    api_calls: int,
    budget_limit: int,
    daily_calls: list[dict],
    last_10_calls: list[dict],
    source_config: dict,
    api_key_configured: bool,
    prev_month_calls: int = 0,
) -> dict:
    """Build budget tracking data for a single API source.

    Extracts the common budget calculation logic so it can be reused
    for Zillow, Realtor.com, and any future API sources.

    Args:
        display_name: Human-readable source name (e.g. ``"Zillow"``).
        source_key: Database source key (e.g. ``"zillow"``).
        api_calls: Total API calls this month for this source.
        budget_limit: Monthly budget limit for this source.
        daily_calls: Daily call breakdown from ``get_api_calls_by_day()``.
        last_10_calls: Last 10 API calls from ``get_recent_api_calls()``.
        source_config: Config dict for this source (e.g. ``config["zillow_api"]``).
        api_key_configured: Whether the API key is set for this source.
        prev_month_calls: API calls in the previous month (same day range).

    Returns:
        A dict with all budget KPI data for template rendering.
    """
    budget_pct = (api_calls / budget_limit * 100) if budget_limit else 0
    if budget_pct < 60:
        budget_status = "green"
        budget_text = "✓ Within budget"
    elif budget_pct < 80:
        budget_status = "amber"
        budget_text = "⚠ Approaching limit"
    else:
        budget_status = "red"
        budget_text = "⚠ Near limit"

    # Projection
    today = date.today()
    first_of_month = today.replace(day=1)
    days_elapsed = (today - first_of_month).days + 1
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    projected = int((api_calls / days_elapsed) * days_in_month) if days_elapsed > 0 else api_calls
    remaining = budget_limit - api_calls
    daily_avg = round(api_calls / days_elapsed, 1) if days_elapsed > 0 else 0
    days_remaining = days_in_month - days_elapsed

    # Last API call info (from last_10_calls)
    last_call_str: str | None = None
    days_since_last_call: int | None = None
    last_call_status: str = "ok"
    last_call_status_text: str = "No data"
    if last_10_calls:
        most_recent = last_10_calls[0]
        last_dt = most_recent.get("called_at")
        if last_dt is not None:
            last_call_str = _format_datetime(last_dt)
            if isinstance(last_dt, datetime):
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                delta = datetime.now(timezone.utc) - last_dt
                days_since_last_call = delta.days

        status_code = most_recent.get("status_code")
        if status_code is not None:
            last_call_status = "ok" if status_code == 200 else "error"
            last_call_status_text = _STATUS_CODE_TEXT.get(
                status_code, f"{status_code} Error"
            )
        else:
            last_call_status = "error"
            last_call_status_text = "Connection Error"

    return {
        "display_name": display_name,
        "source_key": source_key,
        "api_calls": api_calls,
        "api_budget": budget_limit,
        "budget_pct": round(budget_pct, 1),
        "budget_status": budget_status,
        "budget_text": budget_text,
        "projected": projected,
        "remaining": remaining,
        "daily_avg": daily_avg,
        "days_remaining": days_remaining,
        "over_budget": projected > budget_limit,
        "over_by": projected - budget_limit if projected > budget_limit else 0,
        "daily_calls": daily_calls,
        "last_10_calls": last_10_calls,
        "last_call_status": last_call_status,
        "last_call_status_text": last_call_status_text,
        "api_key_configured": api_key_configured,
        "last_call": last_call_str,
        "days_since_last_call": days_since_last_call,
        "prev_month_calls": prev_month_calls,
    }


@router.get("/api-usage")
async def admin_api_usage(request: Request):
    """API call tracking and budget monitoring — multi-source redesign."""
    # Config
    try:
        config = load_config()
    except FileNotFoundError:
        config = {}
    zillow_config = config.get("zillow_api", {})
    realtor_config = config.get("realtor_api", {})

    # --- Zillow ---
    zillow_calls = get_api_call_count("zillow")
    zillow_daily = get_api_calls_by_day("zillow")
    zillow_last_10 = get_recent_api_calls("zillow", 10)
    zillow_env_key = os.environ.get("RAPIDAPI_KEY", "").strip()
    zillow_cfg_key = zillow_config.get("rapidapi_key", "").strip()
    zillow_key_ok = bool(zillow_env_key or zillow_cfg_key)

    # --- Realtor.com ---
    realtor_calls = get_api_call_count("realtor")
    realtor_daily = get_api_calls_by_day("realtor")
    realtor_last_10 = get_recent_api_calls("realtor", 10)
    realtor_env_key = os.environ.get("REALTOR_RAPIDAPI_KEY", "").strip()
    realtor_key_ok = bool(realtor_env_key or zillow_env_key)  # falls back to RAPIDAPI_KEY

    realtor_budget = realtor_config.get("monthly_budget", API_BUDGET_LIMITS["realtor"])

    # --- Monthly Comparison (previous month, same day range) ---
    today = date.today()
    current_day = today.day
    first_of_month = today.replace(day=1)

    if today.month == 1:
        prev_month_start = date(today.year - 1, 12, 1)
    else:
        prev_month_start = date(today.year, today.month - 1, 1)
    prev_month_end_day = min(current_day, calendar.monthrange(prev_month_start.year, prev_month_start.month)[1])
    prev_month_end = date(prev_month_start.year, prev_month_start.month, prev_month_end_day) + timedelta(days=1)

    zillow_prev = get_api_call_count_for_period("zillow", prev_month_start, prev_month_end)
    realtor_prev = get_api_call_count_for_period("realtor", prev_month_start, prev_month_end)

    sources = [
        _build_budget_data(
            "Zillow", "zillow", zillow_calls, API_BUDGET_LIMITS["zillow"],
            zillow_daily, zillow_last_10, zillow_config, zillow_key_ok,
            prev_month_calls=zillow_prev,
        ),
        _build_budget_data(
            "Realtor.com", "realtor", realtor_calls, realtor_budget,
            realtor_daily, realtor_last_10, realtor_config, realtor_key_ok,
            prev_month_calls=realtor_prev,
        ),
    ]

    # --- 7-Day Success Rate (all sources combined) ---
    success_rate_7d = get_api_success_rate_by_day(7)

    # Month labels
    current_month_label = today.strftime("%b %Y")
    prev_month_label = prev_month_start.strftime("%b %Y")

    # Timestamp for page header (portable — no %-d)
    now = datetime.now(timezone.utc)
    now_str = f"{now.strftime('%b')} {now.day}, {now.strftime('%Y %I:%M %p')}"

    return templates.TemplateResponse(
        request,
        "admin/api-usage.html",
        context={
            "active_page": "api-usage",
            "sources": sources,
            "success_rate_7d": success_rate_7d,
            "current_day_of_month": current_day,
            "current_month_label": current_month_label,
            "prev_month_label": prev_month_label,
            "now_str": now_str,
        },
    )


@router.get("/notifications")
async def admin_notifications(request: Request):
    """Notification history and delivery statistics."""
    stats = get_notification_stats()
    total = stats["total"]
    success_rate = stats["success_rate"]
    today_count = stats["today_count"]
    failed = total - int(total * success_rate / 100) if total > 0 else 0

    # Daily data
    daily_data = get_notifications_by_day(30)

    # History
    history = get_notification_history(100)
    formatted_history = []
    for entry in history:
        formatted_history.append({
            "sent_at": _format_datetime(entry.get("sent_at")),
            "channel": entry.get("channel", "—"),
            "recipient": entry.get("recipient", "—"),
            "listing_count": entry.get("listing_count", 0),
            "success": entry.get("success", False),
        })

    # SMTP credential status check (mirrors API key check on api-usage page)
    smtp_password_env = os.environ.get("SMTP_PASSWORD", "").strip()
    try:
        config = load_config()
    except FileNotFoundError:
        config = {}
    smtp_password_cfg = config.get("email", {}).get("sender_password", "").strip()
    smtp_configured = bool(smtp_password_env or smtp_password_cfg)

    # WhatsApp credential status check
    whatsapp_api_token = os.environ.get("WHATSAPP_API_TOKEN", "").strip()
    whatsapp_phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    whatsapp_configured = bool(whatsapp_api_token and whatsapp_phone_id)

    return templates.TemplateResponse(
        request,
        "admin/notifications.html",
        context={
            "active_page": "notifications",
            "total": total,
            "today_count": today_count,
            "success_rate": success_rate,
            "failed": failed,
            "daily_data": daily_data,
            "history": formatted_history,
            "smtp_configured": smtp_configured,
            "whatsapp_configured": whatsapp_configured,
        },
    )


@router.get("/settings")
async def admin_settings(request: Request):
    """Settings page with read-only config display."""
    email_settings = get_email_settings()
    whatsapp_settings = get_whatsapp_settings()

    try:
        config = load_config()
    except FileNotFoundError:
        config = {}

    email_cfg = config.get("email", {})
    whatsapp_cfg = config.get("whatsapp", {})
    zillow_cfg = config.get("zillow_api", {})
    realtor_cfg = config.get("realtor_api", {})
    schedule_cfg = config.get("schedule", {})
    search_cfg = config.get("search", {})
    filters_cfg = config.get("filters", {})
    notif_schedule = config.get("notification_schedule", {})

    config_sections = {
        "Search": {
            "City": search_cfg.get("city", "Not configured"),
            "State": search_cfg.get("state", "N/A"),
            "ZIP Codes": ", ".join(search_cfg.get("zip_codes", [])),
        },
        "Filters": {
            "Price Range": f"${filters_cfg.get('min_price', 'N/A'):,}–${filters_cfg.get('max_price', 'N/A'):,}",
            "Bedrooms": f"{filters_cfg.get('min_bedrooms', 'N/A')}–{filters_cfg.get('max_bedrooms', 'N/A')}",
            "Property Types": ", ".join(filters_cfg.get("property_types", [])),
        },
        "Schedule": {
            "Scrape Interval": f"Every {schedule_cfg.get('interval_hours', 'N/A')} hours",
            "Notification Hours": ", ".join(str(h) for h in notif_schedule.get("hours", [])),
            "Timezone": notif_schedule.get("timezone", "N/A"),
        },
        "Email": {
            "Enabled": "Yes" if email_cfg.get("enabled") else "No",
            "SMTP Server": email_cfg.get("smtp_server", "Not configured"),
            "SMTP Port": str(email_cfg.get("smtp_port", "N/A")),
            "Sender": email_cfg.get("sender_email", "Not configured"),
            "Recipient": email_cfg.get("recipient_email", "Not configured"),
        },
        "WhatsApp": {
            "Enabled": "Yes" if whatsapp_cfg.get("enabled") else "No",
            "Recipient Phone": whatsapp_cfg.get("recipient_phone", "Not configured") or "Not configured",
        },
        "Zillow API": {
            "API Host": zillow_cfg.get("rapidapi_host", "Not configured"),
            "Budget Limit": f"{API_BUDGET_LIMITS['zillow']} requests/month",
        },
        "Realtor.com API": {
            "API Host": realtor_cfg.get("rapidapi_host", "Not configured"),
            "Budget Limit": f"{realtor_cfg.get('monthly_budget', API_BUDGET_LIMITS['realtor'])} requests/month",
            "Budget Threshold": str(realtor_cfg.get("budget_threshold", 90)),
            "Enabled": "Yes" if realtor_cfg.get("enabled", True) else "No",
        },
    }

    return templates.TemplateResponse(
        request,
        "admin/settings.html",
        context={
            "active_page": "settings",
            "config_sections": config_sections,
            "email_settings": email_settings,
            "whatsapp_settings": whatsapp_settings,
        },
    )
