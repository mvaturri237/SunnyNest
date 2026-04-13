"""SunnyNest Backoffice — Admin dashboard for operational monitoring.

A separate Streamlit app (port 8502) providing:
- Dashboard with KPI cards and summary charts
- Listing Analytics with price trends and source breakdown
- API Usage monitoring with budget tracking
- Notification history and statistics
- Settings management for email notifications

Phases 1–3 — read-only analytics + settings management.
"""

from __future__ import annotations

import calendar
import html
import logging
import re
from datetime import date, datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.database import (
    get_api_call_count,
    get_api_calls_by_day,
    get_avg_price_by_period,
    get_batch_price_changes,
    get_data_freshness,
    get_listing_inventory_timeline,
    get_listing_stats,
    get_notification_history,
    get_notification_stats,
    get_notifications_by_day,
    get_price_distribution,
    get_recent_api_calls,
    get_session,
    get_source_counts,
    get_source_counts_with_inactive,
    get_today_notification_count,
    init_db,
)
from src.models import Listing
from src.utils import get_email_settings, load_config, sqft_to_sqm, update_email_settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger("sunnynest.backoffice")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BUDGET_LIMIT = 500  # Zillow RapidAPI free tier: 500 requests/month

# ---------------------------------------------------------------------------
# Page configuration (must be the first Streamlit command)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SunnyNest Admin",
    page_icon="🏠",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Initialise database
# ---------------------------------------------------------------------------

init_db()

# ---------------------------------------------------------------------------
# Custom CSS — Dark theme matching the mockup
# ---------------------------------------------------------------------------

st.markdown(
    """<style>
/* Import Inter font */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* Apply Inter font globally */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
}

/* Hide Streamlit's deploy button, hamburger menu */
.stDeployButton { display: none !important; }
[data-testid="stAppDeployButton"] { display: none !important; }
[data-testid="stMainMenu"] { display: none !important; }
[data-testid="stToolbarActions"] { display: none !important; }
/* Do NOT hide stHeader — it contains the sidebar expand button */

/* Hide stray Streamlit status/progress bars between sections */
[data-testid="stStatusWidget"] { display: none !important; }
.stProgress { display: none !important; }

/* Tighter top padding */
.block-container { padding-top: 1.5rem !important; }

/* Chart section titles */
.chart-title {
    font-size: 15px !important;
    font-weight: 700 !important;
    color: #e0e0e0 !important;
    margin-bottom: 8px !important;
}

/* Metric card styling */
[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
    padding: 16px 20px;
    transition: all 0.15s ease;
}
[data-testid="stMetric"]:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(37, 99, 235, 0.30);
}
[data-testid="stMetricLabel"] {
    font-size: 13px !important;
    font-weight: 500 !important;
    color: #888 !important;
}
[data-testid="stMetricValue"] {
    font-size: 28px !important;
    font-weight: 800 !important;
    letter-spacing: -0.5px !important;
}

/* Sidebar BACKOFFICE label */
.backoffice-label {
    font-size: 10px;
    font-weight: 600;
    color: #3b82f6;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-top: 2px;
}

/* Chart container styling */
.chart-container {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 12px;
    padding: 20px;
}

/* Config display styling */
.config-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    font-size: 13px;
}
.config-key { color: #888; }
.config-value { color: #ccc; font-weight: 500; }

/* Budget gauge status badges */
.gauge-status {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 12px;
}
.gauge-green { color: #22c55e; background: rgba(22, 163, 74, 0.15); }
.gauge-amber { color: #f59e0b; background: rgba(217, 119, 6, 0.15); }
.gauge-red { color: #ef4444; background: rgba(220, 38, 38, 0.15); }
</style>""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Plotly theme defaults (dark, matching mockup)
# ---------------------------------------------------------------------------

_PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#ccc"),
    margin=dict(l=40, r=20, t=30, b=40),
    xaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.06)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.06)"),
)


# ---------------------------------------------------------------------------
# Helper: relative time formatting
# ---------------------------------------------------------------------------


def _relative_time(dt: datetime | None) -> str:
    """Format a datetime as a human-readable relative time string."""
    if dt is None:
        return "No data"

    # Ensure dt is timezone-aware (assume UTC if naive)
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


# ---------------------------------------------------------------------------
# Page: Dashboard
# ---------------------------------------------------------------------------


def page_dashboard() -> None:
    """Render the Dashboard page with KPI cards and summary charts."""
    st.title("📊 Dashboard")
    st.caption("Operational overview of the SunnyNest rental aggregator")

    # --- Fetch data ---
    stats = get_listing_stats()
    api_calls = get_api_call_count("zillow")
    notif_count = get_today_notification_count()
    freshness = get_data_freshness()

    # --- KPI Cards Row ---
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    with k1:
        st.metric("Active Listings", f"{stats['total']:,}")
    with k2:
        avg_price = stats["avg_price"]
        st.metric("Avg Rent", f"${avg_price:,.0f}" if avg_price else "$0")
    with k3:
        st.metric("New Today", stats["new_today"])
    with k4:
        pct = (api_calls / API_BUDGET_LIMIT * 100) if API_BUDGET_LIMIT else 0
        st.metric("API Calls (Month)", f"{api_calls}/{API_BUDGET_LIMIT}")
        # Color-coded progress bar
        if pct < 60:
            color = "#16a34a"
        elif pct < 80:
            color = "#d97706"
        else:
            color = "#dc2626"
        st.markdown(
            f'<div style="width:100%; height:6px; background:rgba(255,255,255,0.08); '
            f'border-radius:3px; overflow:hidden; margin-top:-8px;">'
            f'<div style="width:{min(pct, 100):.0f}%; height:100%; '
            f'background:{color}; border-radius:3px;"></div></div>',
            unsafe_allow_html=True,
        )
    with k5:
        st.metric("Notifications", notif_count)
    with k6:
        st.metric("Freshness", _relative_time(freshness))

    st.markdown("")  # spacer

    # --- Charts Row ---
    c1, c2, c3 = st.columns(3)

    # Chart 1: Listings by Source (donut)
    with c1:
        st.markdown('<p class="chart-title">Listings by Source</p>', unsafe_allow_html=True)
        source_counts = get_source_counts({})
        if source_counts:
            labels = list(source_counts.keys())
            values = list(source_counts.values())
            if len(labels) == 1:
                # Single source — show a styled info card instead of a one-slice donut
                src_name = labels[0].capitalize()
                st.markdown(
                    f'<div style="text-align:center; padding:40px 0;">'
                    f'<div style="font-size:48px; font-weight:800; color:#3b82f6;">{values[0]}</div>'
                    f'<div style="font-size:14px; color:#888; margin-top:8px;">'
                    f'Single source: {src_name}</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                colors = ["#3b82f6", "#8b5cf6", "#14b8a6", "#f97316", "#ec4899"]
                fig = go.Figure(
                    data=[
                        go.Pie(
                            labels=labels,
                            values=values,
                            hole=0.55,
                            marker=dict(colors=colors[: len(labels)]),
                            textinfo="label+value",
                            textfont=dict(size=12),
                            hovertemplate="%{label}: %{value} listings<extra></extra>",
                        )
                    ]
                )
                fig.update_layout(
                    **_PLOTLY_LAYOUT,
                    showlegend=False,
                    height=280,
                )
                st.plotly_chart(fig, width="stretch")
        else:
            st.info("No listing data available.")

    # Chart 2: API Usage This Month (bar)
    with c2:
        st.markdown('<p class="chart-title">API Usage This Month</p>', unsafe_allow_html=True)
        daily_calls = get_api_calls_by_day("zillow")
        if daily_calls:
            df_api = pd.DataFrame(daily_calls)
            fig = go.Figure(
                data=[
                    go.Bar(
                        x=df_api["date"],
                        y=df_api["count"],
                        marker_color="#3b82f6",
                        hovertemplate="Date: %{x}<br>Calls: %{y}<extra></extra>",
                    )
                ]
            )
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                xaxis_title="",
                yaxis_title="API Calls",
                height=280,
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No API call data for this month.")

    # Chart 3: Price Distribution (histogram)
    with c3:
        st.markdown('<p class="chart-title">Price Distribution</p>', unsafe_allow_html=True)
        # Use lightweight price-only query (not full ORM objects)
        prices = get_price_distribution(include_inactive=False)
        if prices:
            fig = go.Figure(
                data=[
                    go.Histogram(
                        x=prices,
                        nbinsx=15,
                        marker_color="#8b5cf6",
                        hovertemplate="Price: $%{x:,.0f}<br>Count: %{y}<extra></extra>",
                    )
                ]
            )
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                xaxis_title="Monthly Rent ($)",
                yaxis_title="Count",
                height=280,
            )
            fig.update_xaxes(tickformat="$,.0f")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No listing price data available.")


# ---------------------------------------------------------------------------
# Page: API Usage
# ---------------------------------------------------------------------------


def page_api_usage() -> None:
    """Render the API Usage page with budget tracking and call log."""
    st.title("🔑 API Usage")
    st.caption("Zillow RapidAPI budget monitoring and call history")

    # --- Load config ---
    try:
        config = load_config()
    except FileNotFoundError:
        config = {}

    zillow_config = config.get("zillow_api", {})
    schedule_config = config.get("schedule", {})

    # --- Fetch data ---
    api_calls = get_api_call_count("zillow")
    daily_calls = get_api_calls_by_day("zillow")
    recent_calls = get_recent_api_calls("zillow", 50)

    # --- Budget Gauge ---
    pct = (api_calls / API_BUDGET_LIMIT * 100) if API_BUDGET_LIMIT else 0

    if pct < 60:
        gauge_color = "#16a34a"
        status_class = "gauge-green"
        status_text = "✓ Within budget"
    elif pct < 80:
        gauge_color = "#d97706"
        status_class = "gauge-amber"
        status_text = "⚠ Approaching limit"
    else:
        gauge_color = "#dc2626"
        status_class = "gauge-red"
        status_text = "⚠ Near limit"

    gauge_col, projection_col = st.columns([1, 1])

    with gauge_col:
        st.markdown('<p class="chart-title">Budget Usage</p>', unsafe_allow_html=True)
        # Plotly gauge chart
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=api_calls,
                number=dict(suffix=f" / {API_BUDGET_LIMIT}", font=dict(size=28)),
                gauge=dict(
                    axis=dict(range=[0, API_BUDGET_LIMIT], tickwidth=1, tickcolor="#444"),
                    bar=dict(color=gauge_color),
                    bgcolor="rgba(255,255,255,0.05)",
                    borderwidth=0,
                    steps=[
                        dict(range=[0, API_BUDGET_LIMIT * 0.6], color="rgba(22,163,74,0.08)"),
                        dict(range=[API_BUDGET_LIMIT * 0.6, API_BUDGET_LIMIT * 0.8], color="rgba(217,119,6,0.08)"),
                        dict(range=[API_BUDGET_LIMIT * 0.8, API_BUDGET_LIMIT], color="rgba(220,38,38,0.08)"),
                    ],
                    threshold=dict(
                        line=dict(color="#dc2626", width=2),
                        thickness=0.8,
                        value=API_BUDGET_LIMIT,
                    ),
                ),
            )
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", color="#ccc"),
            margin=dict(l=30, r=30, t=40, b=10),
            height=250,
        )
        st.plotly_chart(fig, width="stretch")

        # Status badge
        st.markdown(
            f'<div style="text-align:center;">'
            f'<span class="gauge-status {status_class}">{status_text}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # --- Budget Projection ---
    with projection_col:
        st.markdown('<p class="chart-title">Budget Projection</p>', unsafe_allow_html=True)
        today = date.today()
        first_of_month = today.replace(day=1)
        days_elapsed = (today - first_of_month).days + 1  # include today
        days_in_month = calendar.monthrange(today.year, today.month)[1]

        if days_elapsed > 0:
            projected = int((api_calls / days_elapsed) * days_in_month)
        else:
            projected = api_calls

        remaining = API_BUDGET_LIMIT - api_calls
        daily_avg = api_calls / days_elapsed if days_elapsed > 0 else 0
        days_remaining = days_in_month - days_elapsed

        proj_col1, proj_col2 = st.columns(2)
        with proj_col1:
            st.metric("Projected Total", f"{projected:,}")
            st.metric("Daily Average", f"{daily_avg:.1f}")
        with proj_col2:
            st.metric("Remaining Budget", f"{remaining:,}")
            st.metric("Days Left", f"{days_remaining}")

        if projected > API_BUDGET_LIMIT:
            st.warning(
                f"⚠️ **Budget Alert**: At the current rate ({daily_avg:.1f} calls/day), "
                f"you're projected to use **{projected:,}** calls this month, "
                f"exceeding the {API_BUDGET_LIMIT} limit by **{projected - API_BUDGET_LIMIT:,}**."
            )
        else:
            st.success(
                f"✅ On track — projected **{projected:,}** / {API_BUDGET_LIMIT} calls this month."
            )

    st.markdown("")  # spacer

    # --- Daily Usage Chart ---
    st.markdown('<p class="chart-title">Daily Usage (Current Month)</p>', unsafe_allow_html=True)
    if daily_calls:
        df_daily = pd.DataFrame(daily_calls)
        fig = go.Figure(
            data=[
                go.Bar(
                    x=df_daily["date"],
                    y=df_daily["count"],
                    marker_color="#3b82f6",
                    hovertemplate="Date: %{x}<br>Calls: %{y}<extra></extra>",
                )
            ]
        )
        fig.update_layout(
            **_PLOTLY_LAYOUT,
            xaxis_title="",
            yaxis_title="API Calls",
            height=280,
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No API call data for this month.")

    st.markdown("")  # spacer

    # --- Call Log Table ---
    st.markdown('<p class="chart-title">Recent API Calls</p>', unsafe_allow_html=True)
    if recent_calls:
        df_log = pd.DataFrame(recent_calls)
        df_log.columns = ["Called At", "Endpoint", "Status Code"]
        st.dataframe(
            df_log,
            hide_index=True,
            height=400,
        )
    else:
        st.info("No API call records found.")

    st.markdown("")  # spacer

    # --- Config Display ---
    st.markdown('<p class="chart-title">API Configuration</p>', unsafe_allow_html=True)
    config_items = {
        "API Host": zillow_config.get("rapidapi_host", "Not configured"),
        "Budget Limit": f"{API_BUDGET_LIMIT} requests/month",
        "Scrape Frequency": f"Every {schedule_config.get('interval_hours', 'N/A')} hours",
    }
    for key, value in config_items.items():
        st.markdown(
            f'<div class="config-row">'
            f'<span class="config-key">{html.escape(str(key))}</span>'
            f'<span class="config-value">{html.escape(str(value))}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Page: Listing Analytics
# ---------------------------------------------------------------------------


def page_analytics() -> None:
    """Render the Listing Analytics page with price trends and source breakdown."""
    st.title("📈 Listing Analytics")
    st.caption("Price trends, source breakdown, and inventory analysis")

    # --- Active/All toggle ---
    include_inactive = st.toggle("Include inactive listings", value=False)

    st.markdown("")  # spacer

    # --- Price Trends Over Time ---
    st.markdown('<p class="chart-title">Price Trends Over Time</p>', unsafe_allow_html=True)

    trend_col1, trend_col2 = st.columns([3, 1])
    with trend_col2:
        bedroom_options = [1, 2, 3, 4, 5]
        selected_bedrooms = st.multiselect(
            "Bedrooms",
            options=bedroom_options,
            default=[3, 4],
            key="analytics_bedrooms",
        )
        period = st.radio(
            "Period",
            options=["monthly", "weekly"],
            horizontal=True,
            key="analytics_period",
        )

    with trend_col1:
        if selected_bedrooms:
            trend_data = get_avg_price_by_period(selected_bedrooms, period)
            if trend_data:
                df_trend = pd.DataFrame(trend_data)
                fig = go.Figure()
                colors = ["#3b82f6", "#8b5cf6", "#14b8a6", "#f97316", "#ec4899"]
                for i, br in enumerate(sorted(selected_bedrooms)):
                    br_data = df_trend[df_trend["bedrooms"] == br]
                    if not br_data.empty:
                        fig.add_trace(
                            go.Scatter(
                                x=br_data["period_label"],
                                y=br_data["avg_price"],
                                mode="lines+markers",
                                name=f"{br} BR",
                                line=dict(color=colors[i % len(colors)], width=2),
                                hovertemplate=(
                                    "Period: %{x}<br>"
                                    "Avg Rent: $%{y:,.0f}<br>"
                                    f"Bedrooms: {br}<extra></extra>"
                                ),
                            )
                        )
                fig.update_layout(
                    **_PLOTLY_LAYOUT,
                    xaxis_title="",
                    yaxis_title="Avg Monthly Rent ($)",
                    height=320,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                )
                fig.update_yaxes(tickformat="$,.0f")
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("No price trend data available for the selected bedrooms.")
        else:
            st.info("Select at least one bedroom count to see price trends.")

    st.markdown("")  # spacer

    # --- Price Distribution & Source Breakdown ---
    dist_col, source_col = st.columns(2)

    with dist_col:
        st.markdown('<p class="chart-title">Price Distribution</p>', unsafe_allow_html=True)
        prices = get_price_distribution(include_inactive=include_inactive)
        if prices:
            fig = go.Figure(
                data=[
                    go.Histogram(
                        x=prices,
                        nbinsx=20,
                        marker_color="#8b5cf6",
                        hovertemplate="Price: $%{x:,.0f}<br>Count: %{y}<extra></extra>",
                    )
                ]
            )
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                xaxis_title="Monthly Rent ($)",
                yaxis_title="Count",
                height=300,
            )
            fig.update_xaxes(tickformat="$,.0f")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No listing price data available.")

    with source_col:
        st.markdown('<p class="chart-title">Source Breakdown (Active vs Inactive)</p>', unsafe_allow_html=True)
        source_data = get_source_counts_with_inactive()
        if source_data:
            sources = sorted(source_data.keys())
            active_counts = [source_data[s]["active"] for s in sources]
            inactive_counts = [source_data[s]["inactive"] for s in sources]
            fig = go.Figure(
                data=[
                    go.Bar(
                        name="Active",
                        x=sources,
                        y=active_counts,
                        marker_color="#3b82f6",
                        hovertemplate="Source: %{x}<br>Active: %{y}<extra></extra>",
                    ),
                    go.Bar(
                        name="Inactive",
                        x=sources,
                        y=inactive_counts,
                        marker_color="#6b7280",
                        hovertemplate="Source: %{x}<br>Inactive: %{y}<extra></extra>",
                    ),
                ]
            )
            fig.update_layout(
                **_PLOTLY_LAYOUT,
                barmode="stack",
                xaxis_title="",
                yaxis_title="Listings",
                height=300,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No source data available.")

    st.markdown("")  # spacer

    # --- Listings Inventory Timeline ---
    st.markdown('<p class="chart-title">Listings Inventory Timeline</p>', unsafe_allow_html=True)
    timeline_data = get_listing_inventory_timeline()
    if timeline_data:
        df_timeline = pd.DataFrame(timeline_data)
        fig = go.Figure(
            data=[
                go.Scatter(
                    x=df_timeline["date"],
                    y=df_timeline["count"],
                    mode="lines+markers",
                    line=dict(color="#14b8a6", width=2),
                    fill="tozeroy",
                    fillcolor="rgba(20, 184, 166, 0.1)",
                    hovertemplate="Date: %{x}<br>Total Listings: %{y}<extra></extra>",
                )
            ]
        )
        fig.update_layout(
            **_PLOTLY_LAYOUT,
            xaxis_title="",
            yaxis_title="Cumulative Listings",
            height=300,
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No inventory timeline data available.")

    st.markdown("")  # spacer

    # --- Price Changes Summary ---
    st.markdown('<p class="chart-title">Price Changes Summary</p>', unsafe_allow_html=True)
    with get_session() as session:
        listing_query = session.query(Listing.id, Listing.address, Listing.sqft).filter(
            Listing.is_active == True,  # noqa: E712
            Listing.price.isnot(None),
        )
        listings_for_changes = listing_query.all()
        listing_ids = [row.id for row in listings_for_changes]
        listing_info = {row.id: {"address": row.address, "sqft": row.sqft} for row in listings_for_changes}

    if listing_ids:
        price_changes = get_batch_price_changes(listing_ids)
        # Filter to only listings with actual price changes
        changed = {
            lid: data
            for lid, data in price_changes.items()
            if data["price_change"] != 0
        }
        if changed:
            rows = []
            for lid, data in changed.items():
                info = listing_info.get(lid, {})
                address = info.get("address", "Unknown")
                sqft_val = info.get("sqft")
                if sqft_val:
                    area_str = f"{sqft_val:,} sqft ({sqft_to_sqm(sqft_val):,.0f} m²)"
                else:
                    area_str = "N/A"
                change = data["price_change"]
                direction = "📈" if change > 0 else "📉"
                rows.append({
                    "Address": address,
                    "Old Price": f"${data['first_price']:,.0f}",
                    "New Price": f"${data['current_price']:,.0f}",
                    "Change": f"{direction} ${abs(change):,.0f}",
                    "Area": area_str,
                })
            df_changes = pd.DataFrame(rows)
            st.dataframe(df_changes, hide_index=True, height=300)
        else:
            st.info("No price changes detected across listings.")
    else:
        st.info("No listings available for price change analysis.")


# ---------------------------------------------------------------------------
# Page: Notifications
# ---------------------------------------------------------------------------


def page_notifications() -> None:
    """Render the Notifications page with send history and statistics."""
    st.title("🔔 Notifications")
    st.caption("Notification history and delivery statistics")

    # --- Summary KPI Cards ---
    stats = get_notification_stats()
    total = stats["total"]
    success_rate = stats["success_rate"]
    today_count = stats["today_count"]
    failed = total - int(total * success_rate / 100) if total > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Total Sent", f"{total:,}")
    with k2:
        st.metric("Sent Today", f"{today_count:,}")
    with k3:
        st.metric("Success Rate", f"{success_rate:.1f}%")
    with k4:
        st.metric("Failed", f"{failed:,}")

    st.markdown("")  # spacer

    # --- Daily Send Chart ---
    st.markdown('<p class="chart-title">Daily Notifications (Last 30 Days)</p>', unsafe_allow_html=True)
    daily_data = get_notifications_by_day(30)
    if daily_data:
        df_daily = pd.DataFrame(daily_data)
        fig = go.Figure(
            data=[
                go.Bar(
                    x=df_daily["date"],
                    y=df_daily["success_count"],
                    name="Successful",
                    marker_color="#22c55e",
                    hovertemplate="Date: %{x}<br>Successful: %{y}<extra></extra>",
                ),
                go.Bar(
                    x=df_daily["date"],
                    y=df_daily["count"] - df_daily["success_count"],
                    name="Failed",
                    marker_color="#ef4444",
                    hovertemplate="Date: %{x}<br>Failed: %{y}<extra></extra>",
                ),
            ]
        )
        fig.update_layout(
            **_PLOTLY_LAYOUT,
            barmode="stack",
            xaxis_title="",
            yaxis_title="Notifications",
            height=300,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No notification data for the last 30 days.")

    st.markdown("")  # spacer

    # --- Notification History Table ---
    st.markdown('<p class="chart-title">Notification History</p>', unsafe_allow_html=True)
    history = get_notification_history(100)
    if history:
        df_hist = pd.DataFrame(history)
        df_hist.columns = ["Timestamp", "Channel", "Recipient", "Listings", "Status"]
        # Convert boolean status to readable text
        df_hist["Status"] = df_hist["Status"].map({True: "✅ Success", False: "❌ Failed"})
        st.dataframe(df_hist, hide_index=True, height=400)
    else:
        st.info("No notification records found.")


# ---------------------------------------------------------------------------
# Page: Settings
# ---------------------------------------------------------------------------


def page_settings() -> None:
    """Render the Settings page for notification and system configuration."""
    st.title("⚙️ Settings")
    st.caption("Manage notification settings and view system configuration")

    # --- Notification Settings ---
    st.markdown('<p class="chart-title">Notification Settings</p>', unsafe_allow_html=True)

    email_settings = get_email_settings()

    with st.form("email_settings_form"):
        enabled = st.toggle(
            "Enable email notifications",
            value=email_settings["enabled"],
        )
        recipient = st.text_input(
            "Recipient email",
            value=email_settings["recipient_email"],
        )
        submitted = st.form_submit_button("Save Settings", type="primary")

        if submitted:
            if recipient and not re.match(r"^[^@]+@[^@]+\.[^@]+$", recipient):
                st.error("❌ Invalid email format. Please enter a valid email address.")
            elif not recipient:
                st.error("❌ Recipient email cannot be empty.")
            else:
                try:
                    update_email_settings(enabled=enabled, recipient_email=recipient)
                    st.success("✅ Settings saved successfully!")
                except Exception as e:
                    st.error(f"❌ Failed to save settings: {e}")

    st.markdown("")  # spacer

    # --- Current Configuration (read-only) ---
    st.markdown('<p class="chart-title">Current Configuration</p>', unsafe_allow_html=True)

    try:
        config = load_config()
    except FileNotFoundError:
        config = {}

    email_cfg = config.get("email", {})
    zillow_cfg = config.get("zillow_api", {})
    schedule_cfg = config.get("schedule", {})

    config_items = {
        "SMTP Server": email_cfg.get("smtp_server", "Not configured"),
        "SMTP Port": str(email_cfg.get("smtp_port", "N/A")),
        "Sender Email": email_cfg.get("sender_email", "Not configured"),
        "API Host": zillow_cfg.get("rapidapi_host", "Not configured"),
        "Budget Limit": f"{API_BUDGET_LIMIT} requests/month",
        "Scrape Frequency": f"Every {schedule_cfg.get('interval_hours', 'N/A')} hours",
    }

    for key, value in config_items.items():
        st.markdown(
            f'<div class="config-row">'
            f'<span class="config-key">{html.escape(str(key))}</span>'
            f'<span class="config-value">{html.escape(str(value))}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")  # spacer
    st.info(
        "🔒 SMTP password and API key are managed via environment variables "
        "(`SMTP_PASSWORD`, `RAPIDAPI_KEY`). They are not displayed here for security."
    )


# ---------------------------------------------------------------------------
# Sidebar & Navigation
# ---------------------------------------------------------------------------

# Sidebar branding
st.sidebar.markdown("## 🏠 SunnyNest")
st.sidebar.markdown('<span class="backoffice-label">BACKOFFICE</span>', unsafe_allow_html=True)

# Navigation using st.navigation
pages = st.navigation(
    [
        st.Page(page_dashboard, title="Dashboard", icon="📊"),
        st.Page(page_analytics, title="Analytics", icon="📈"),
        st.Page(page_api_usage, title="API Usage", icon="🔑"),
        st.Page(page_notifications, title="Notifications", icon="🔔"),
        st.Page(page_settings, title="Settings", icon="⚙️"),
    ]
)

# Footer link back to main dashboard (fixed at bottom of sidebar)
st.sidebar.markdown(
    '<div style="position: fixed; bottom: 20px; left: 20px;">'
    '<a href="http://sunnynest:8000" target="_blank" '
    'style="color: #6b7280; font-size: 12px; text-decoration: none;">'
    '← User Dashboard</a></div>',
    unsafe_allow_html=True,
)

# Run the selected page
pages.run()
