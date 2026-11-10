"""Streamlit dashboard for the SunnyNest rental finder application.

Provides an interactive UI with filters, map view, card-based listings grid,
detail panel, and analytical charts for browsing rental listings in Sunnyvale, CA.
"""

from __future__ import annotations

import functools
import html
import json
import logging
import math
import pathlib
from datetime import date, datetime, timezone
from typing import Any

import folium
import streamlit as st
from streamlit_folium import st_folium

from src.database import get_batch_price_changes, get_filtered_listings, init_db, toggle_dislike, toggle_favorite
from src.models import Listing
from src.orchestrator import ScraperOrchestrator
from src.utils import load_config, setup_logging

# ---------------------------------------------------------------------------
# Helpers — cached GeoJSON loader & price-label formatter
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _load_sunnyvale_boundary() -> dict:
    """Load the accurate Sunnyvale city-boundary GeoJSON (cached)."""
    path = pathlib.Path(__file__).parent / "data" / "sunnyvale-boundary.geojson"
    with open(path) as f:
        return json.load(f)


def _format_price_label(price: float | None) -> str:
    """Format price for map pill label: $5,800 → '5.8K', $6,000 → '6K'."""
    if price is None:
        return "N/A"
    k = price / 1000
    if k == int(k):
        return f"{int(k)}K"
    return f"{k:.1f}K"


# ---------------------------------------------------------------------------
# Page configuration (must be the first Streamlit command)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SunnyNest",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom CSS — Modern Styling (compact header + inline filter bar)
# ---------------------------------------------------------------------------

st.markdown(
    """<style>
/* Hide Streamlit's deploy button, hamburger menu, and default header/toolbar */
.stDeployButton { display: none !important; }
[data-testid="stAppDeployButton"] { display: none !important; }
.stAppDeployButton { display: none !important; }
[data-testid="stMainMenu"] { display: none !important; }
[data-testid="stToolbarActions"] { display: none !important; }
[data-testid="stHeader"] { display: none !important; }
header[data-testid="stHeader"] { display: none !important; }

/* Ultra-slim filter bar — minimal top/bottom padding */
.block-container { padding-top: 0 !important; padding-bottom: 0 !important; }

/* --- Force full-viewport height on Streamlit's container hierarchy --- */
/* Without explicit heights on every parent, child calc(100vh) won't propagate */
html, body, #root, .stApp {
    height: 100vh !important;
    overflow: hidden !important;
}
[data-testid="stMain"] {
    height: 100vh !important;
    overflow: hidden !important;
}
.block-container, [data-testid="stMainBlockContainer"] {
    height: calc(100vh - 10px) !important;
    max-height: calc(100vh - 10px) !important;
    overflow: hidden !important;
}
/* The top-level vertical block that contains filter bar + columns */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {
    height: 100% !important;
    display: flex !important;
    flex-direction: column !important;
}
/* Wrapper divs inside the top-level vertical block must participate in flex */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
    flex: 0 0 auto !important;
}
/* The wrapper containing the stColumns (split panel) takes all remaining space */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stColumns"]) {
    flex: 1 !important;
    min-height: 0 !important;
    display: flex !important;
    flex-direction: column !important;
}
/* Pass flex through the intermediate div inside the wrapper */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stColumns"]) > div {
    flex: 1 !important;
    min-height: 0 !important;
    display: flex !important;
    flex-direction: column !important;
}
/* The stColumns element itself fills remaining space */
[data-testid="stMainBlockContainer"] [data-testid="stColumns"] {
    flex: 1 !important;
    min-height: 0 !important;
}
/* Admin link — absolutely positioned so it doesn't consume layout space */
.admin-link-fixed {
    position: fixed !important;
    bottom: 4px;
    right: 12px;
    z-index: 999;
}

/* Sync badge styling */
.sync-badge {
    font-size: 0.75rem;
    color: #888;
    line-height: 1.4;
}

/* Prevent link button text from wrapping */
[data-testid="stLinkButton"] button {
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}

/* Compact listing cards */
[data-testid="stVerticalBlock"] [data-testid="stContainer"] {
    padding: 0.15rem 0.25rem !important;
    overflow: hidden;
}
/* Tighter gap inside card containers */
[data-testid="stVerticalBlock"] [data-testid="stContainer"] [data-testid="stVerticalBlock"] {
    gap: 0rem !important;
}
/* Compact buttons inside card containers (action column) */
[data-testid="stVerticalBlock"] [data-testid="stContainer"] button {
    min-height: 1.4rem !important;
    height: 1.6rem !important;
    padding: 0 0.3rem !important;
    font-size: 0.8rem !important;
    line-height: 1 !important;
}
/* Reduce horizontal gap between card columns */
[data-testid="stVerticalBlock"] [data-testid="stContainer"] [data-testid="stHorizontalBlock"] {
    gap: 0.3rem !important;
    align-items: flex-start !important;
}
/* Reduce element wrapper margins inside cards */
[data-testid="stVerticalBlock"] [data-testid="stContainer"] [data-testid="stElementContainer"] {
    margin-bottom: 0 !important;
    margin-top: 0 !important;
}
/* Card containers — stronger borders + depth + hover glow (P1.2) */
[data-testid="stVerticalBlock"] [data-testid="stContainer"] {
    border: 1px solid rgba(255, 255, 255, 0.10) !important;
    border-radius: 10px !important;
    background: rgba(255, 255, 255, 0.025) !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25) !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}
[data-testid="stVerticalBlock"] [data-testid="stContainer"]:hover {
    border-color: rgba(59, 130, 246, 0.30) !important;
    box-shadow: 0 4px 16px rgba(59, 130, 246, 0.18) !important;
    background: rgba(255, 255, 255, 0.04) !important;
}

/* Visual separator between panels */
[data-testid="stColumns"] > div:last-child {
    border-left: 1px solid rgba(250, 250, 250, 0.1);
    padding-left: 1rem;
}

/* --- Card visual hierarchy (P1.1) --- */
.card-price {
    font-size: 20px;
    font-weight: 800;
    color: #3b82f6;
    letter-spacing: -0.5px;
    margin-bottom: 0;
    line-height: 1.2;
}
.card-specs {
    font-size: 0.82rem;
    font-weight: 500;
    color: #ccc;
    margin-bottom: 0;
    line-height: 1.2;
}
.card-sqft {
    font-size: 0.75rem;
    color: #888;
    margin-bottom: 0;
    line-height: 1.2;
}

/* Compact card styling — decluttered badges (P1.4) */
.card-tag {
    display: inline-block;
    width: auto;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    margin-right: 4px;
    margin-bottom: 0;
    font-weight: 500;
    line-height: 1.4;
    white-space: nowrap;
    vertical-align: middle;
}
/* Tag row wrapper — keep badges inline as pills */
.card-tag-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
}
/* Actionable badges — tinted style */
.tag-new { background: rgba(34, 197, 94, 0.12); color: #22c55e; border: 1px solid rgba(34, 197, 94, 0.25); }
.tag-price-drop { background: rgba(34, 197, 94, 0.12); color: #22c55e; border: 1px solid rgba(34, 197, 94, 0.25); }
.tag-price-up { background: rgba(239, 68, 68, 0.12); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.25); }
/* Informational badges — outlined style (P1.4) */
.tag-pet { background: transparent; border: 1px solid rgba(25, 118, 210, 0.4); color: #64b5f6; }
.tag-ac { background: transparent; border: 1px solid rgba(2, 136, 209, 0.4); color: #4fc3f7; }
.tag-days { background: transparent; border: 1px solid rgba(255, 255, 255, 0.15); color: #999; }
.tag-available-now { background: #2e7d32; color: white; }
.tag-available-future { background: transparent; border: 1px solid rgba(21, 101, 192, 0.4); color: #64b5f6; }
/* Freshness badges — outlined style */
.tag-fresh { background: transparent; border: 1px solid rgba(67, 160, 71, 0.4); color: #81c784; }
.tag-aging { background: transparent; border: 1px solid rgba(249, 168, 37, 0.4); color: #ffd54f; }
.tag-stale { background: transparent; border: 1px solid rgba(198, 40, 40, 0.4); color: #ef9a9a; }

/* Description preview — 1-line clamp for compact cards */
.card-description {
    font-size: 0.72rem;
    color: #888;
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 1;
    -webkit-box-orient: vertical;
    overflow: hidden;
    text-overflow: ellipsis;
    margin-top: 0;
    margin-bottom: 0;
}

/* CSS title truncation */
.card-title {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
    font-weight: 600;
    font-size: 0.82rem;
    color: white;
    line-height: 1.2;
    margin-bottom: 0;
}

/* --- Ultra-slim inline filter bar --- */
/* Hide all widget labels inside the filter bar row */
[data-testid="stHorizontalBlock"]:first-of-type [data-testid="stWidgetLabel"] {
    display: none !important;
}

/* Compact selectbox widgets — pill-like rounded style (P1.5) */
[data-testid="stHorizontalBlock"]:first-of-type [data-testid="stSelectbox"] > div > div {
    min-height: 2.2rem !important;
    padding: 0.2rem 0.5rem !important;
    font-size: 0.85rem !important;
    border-radius: 9999px !important;
}

/* Reset button — more prominent (P1.5) */
[data-testid="stHorizontalBlock"]:first-of-type button {
    min-height: 2.2rem !important;
    font-size: 1.1rem !important;
    padding: 0 0.5rem !important;
    border-radius: 6px !important;
}

/* Align filter bar items vertically centered, tight gap */
[data-testid="stHorizontalBlock"]:first-of-type {
    align-items: center;
    gap: 0.3rem;
}

/* Remove vertical margins on selectboxes in filter bar */
[data-testid="stHorizontalBlock"]:first-of-type [data-testid="stSelectbox"] {
    margin-top: -0.5rem;
    margin-bottom: -0.5rem;
}

/* Reduce gap between filter bar and content below */
[data-testid="stHorizontalBlock"]:first-of-type {
    margin-bottom: -0.3rem !important;
}

/* Eliminate extra vertical spacing between Streamlit blocks */
[data-testid="stVerticalBlockBorderWrapper"] {
    padding-top: 0 !important;
    margin-top: 0 !important;
}

/* Add breathing room between filter bar and split-panel columns row;
   both panels (listings + map) start at the same vertical position. */
[data-testid="stColumns"] {
    margin-top: 0.2rem !important;
    padding-top: 0 !important;
}

/* Placeholder image for listings without photos */
.placeholder-img {
    background: linear-gradient(135deg, #667eea, #764ba2);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    border-radius: 6px;
    height: 140px;
    width: 100%;
}

/* Listing thumbnail — fills its Streamlit column, fixed height */
.listing-img-wrapper {
    position: relative;
    width: 100%;
    height: 140px;
    overflow: hidden;
    border-radius: 8px;
}

.listing-img-wrapper img {
    width: 100%;
    height: 140px;
    object-fit: cover;
    display: block;
}

/* Overlay action icons on the image */
.img-overlay-actions {
    position: absolute;
    top: 6px;
    right: 6px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    z-index: 10;
}

.overlay-btn {
    background: rgba(0, 0, 0, 0.45);
    color: white;
    border: none;
    border-radius: 50%;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
    cursor: default;
    opacity: 0.7;
    transition: opacity 0.2s ease;
    text-decoration: none;
}

.overlay-btn:hover {
    opacity: 1;
    background: rgba(0, 0, 0, 0.7);
}

.overlay-btn.active {
    opacity: 1;
    background: rgba(0, 0, 0, 0.6);
}

/* Remove top padding from both panels so listings and map align */
[data-testid="stColumn"] > div:first-child {
    padding-top: 0 !important;
}

/* Eliminate extra gap above the listings column (left side) */
[data-testid="stColumn"]:first-child {
    padding-top: 0 !important;
    margin-top: 0 !important;
}
[data-testid="stColumn"]:first-child > div:first-child > [data-testid="stVerticalBlockBorderWrapper"] {
    padding-top: 0 !important;
    margin-top: 0 !important;
}
/* Only collapse gap on the TOP-LEVEL vertical block inside the left column,
   not on nested blocks inside listing cards (which need their internal spacing). */
[data-testid="stColumn"]:first-child > div:first-child > [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] {
    gap: 0.1rem !important;
}

/* --- Full-viewport split panel (listings + map) --- */
/* The columns row fits the viewport; align-items: stretch makes both columns the same height */
[data-testid="stColumns"]:has([data-testid="stColumn"]) {
    height: calc(100vh - 100px) !important;
    max-height: calc(100vh - 100px) !important;
    align-items: stretch !important;
    overflow: hidden !important;
}
/* Both columns constrained to viewport */
[data-testid="stColumns"] > [data-testid="stColumn"] {
    height: calc(100vh - 100px) !important;
    max-height: calc(100vh - 100px) !important;
    overflow: hidden !important;
}
/* Left panel (listings): scrollable within the viewport height */
[data-testid="stColumns"] > [data-testid="stColumn"]:first-child > div:first-child {
    height: calc(100vh - 100px) !important;
    max-height: calc(100vh - 100px) !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
}
/* Right panel (map): constrained to viewport height */
[data-testid="stColumns"] > [data-testid="stColumn"]:last-child > div:first-child {
    height: calc(100vh - 100px) !important;
    max-height: calc(100vh - 100px) !important;
    overflow: hidden !important;
}
/* Make the folium map iframe fit its container */
[data-testid="stColumns"] > [data-testid="stColumn"]:last-child iframe {
    height: calc(100vh - 110px) !important;
    max-height: calc(100vh - 110px) !important;
}

/* --- Collapse empty Streamlit container wrappers in left panel --- */
/* Remove padding/margin from empty wrapper divs that create blank space */
[data-testid="stColumn"]:first-child [data-testid="stVerticalBlockBorderWrapper"] {
    padding: 0 !important;
    margin: 0 !important;
}
/* Collapse empty elements (Streamlit injects empty divs as spacers) */
[data-testid="stColumn"]:first-child > div:first-child > [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"]:empty,
[data-testid="stColumn"]:first-child > div:first-child > [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] > div:empty {
    display: none !important;
}
/* Collapse empty stElementContainer wrappers (e.g., from conditional buttons not rendered) */
[data-testid="stColumn"]:first-child [data-testid="stElementContainer"]:has(> div:empty),
[data-testid="stColumn"]:first-child [data-testid="stElementContainer"]:empty {
    display: none !important;
}
/* Remove gap above the main stColumns row (the split panel).
   Target ONLY the direct top-level vertical block, not nested ones inside cards. */
[data-testid="stMain"] > div > [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"] {
    gap: 0 !important;
}

/* --- Zillow pill link button styling --- */
.zillow-pill-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 10px;
    border: 1px solid rgba(59, 130, 246, 0.3);
    border-radius: 20px;
    text-decoration: none !important;
    font-size: 0.72rem;
    font-weight: 500;
    color: #3b82f6 !important;
    background: rgba(59, 130, 246, 0.12);
    transition: all 0.2s ease;
    cursor: pointer;
    vertical-align: middle;
    width: fit-content !important;
    max-width: fit-content !important;
    margin-left: auto;
}
.zillow-pill-link:hover {
    background: rgba(59, 130, 246, 0.2);
    border-color: rgba(59, 130, 246, 0.5);
    color: #60a5fa !important;
}
.zillow-pill-link img {
    width: 14px;
    height: 14px;
    border-radius: 2px;
}

/* --- Action column buttons — small and subtle (narrow 3rd column) --- */
[data-testid="stVerticalBlock"] [data-testid="stContainer"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child button {
    min-height: 1.4rem !important;
    height: 1.6rem !important;
    padding: 0 0.3rem !important;
    font-size: 0.8rem !important;
    line-height: 1 !important;
    background: transparent !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    opacity: 0.6;
}
[data-testid="stVerticalBlock"] [data-testid="stContainer"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child button:hover {
    opacity: 1 !important;
    border-color: rgba(59, 130, 246, 0.4) !important;
}

/* Align detail text to top of card */
.card-price {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

/* Card detail wrapper — center text vertically with small gaps */
.card-detail-wrapper {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 4px;
    height: 140px;
    padding: 0;
}
</style>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

setup_logging()
logger = logging.getLogger("rental_finder.dashboard")

# ---------------------------------------------------------------------------
# Startup: initialise database & scheduler (once per session)
# ---------------------------------------------------------------------------

init_db()

# NOTE: Background scheduling has been moved to macOS launchd agents
# (com.sunnynest.scraper, com.sunnynest.notify-am, com.sunnynest.notify-pm).
# The ScrapeScheduler is no longer started from the Streamlit dashboard.
# See plans/scheduler-fix.md for details.

# Load config for default filter values
try:
    _config = load_config()
except FileNotFoundError:
    _config = {}

_filter_cfg = _config.get("filters", {})

# ---------------------------------------------------------------------------
# Header — SunnyNest branded logo + Horizontal Filter Bar (Zillow-style)
# ---------------------------------------------------------------------------


def _relative_time(dt_val: datetime | None) -> str:
    """Return a human-friendly relative time string like '2m ago', '1h ago'.

    Handles both timezone-aware and timezone-naive datetime inputs.
    Naive datetimes are assumed to be UTC.
    """
    if dt_val is None:
        return "Never"
    now = datetime.now(timezone.utc)
    # Handle both aware and naive datetimes
    if dt_val.tzinfo is None:
        # Assume naive datetimes are UTC
        dt_val = dt_val.replace(tzinfo=timezone.utc)
    else:
        # Convert aware datetimes to UTC for comparison
        dt_val = dt_val.astimezone(timezone.utc)
    delta = now - dt_val
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "Just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


# Single row: Logo + all primary filters + reset + sync button
_logo_col, _price_col, _bed_col, _bath_col, _src_col, _view_col, _sort_col, _reset_col, _sync_col = st.columns(
    [1.5, 1.2, 0.9, 0.9, 0.9, 0.9, 1.1, 0.3, 0.7]
)

with _logo_col:
    st.markdown(
        '<div style="display:flex; align-items:center; gap:8px; margin-bottom:0;">'
        '<span style="font-size:1.5rem;">🏠</span>'
        '<span style="font-size:1.4rem; font-weight:800; '
        'background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); '
        '-webkit-background-clip:text; -webkit-text-fill-color:transparent; '
        "font-family:'Inter','Segoe UI',sans-serif; letter-spacing:-0.5px;\">"
        'SunnyNest</span>'
        '</div>',
        unsafe_allow_html=True,
    )

# Price range selectbox — Zillow-style pre-built ranges
_price_options: dict[str, tuple[int, int]] = {
    "Any Price": (0, 10000),
    "$3K-$4K": (3000, 4000),
    "$4K-$5K": (4000, 5000),
    "$5K-$6K": (5000, 6000),
    "$5K-$6.5K": (5000, 6500),
    "$5K-$7K": (5000, 7000),
    "$5K-$7.5K": (5000, 7500),
    "$6K-$7K": (6000, 7000),
    "$6K-$8K": (6000, 8000),
    "$7K-$10K": (7000, 10000),
}
# "Custom Range" is a sentinel — not in the dict, handled separately
_price_option_keys = list(_price_options.keys()) + ["Custom Range"]

# Determine default price key from config
_cfg_min_price = int(_filter_cfg.get("min_price", 5000))
_cfg_max_price = int(_filter_cfg.get("max_price", 7500))
_price_default_key = "$5K-$7.5K"
for _pk, _pv in _price_options.items():
    if _pv == (_cfg_min_price, _cfg_max_price):
        _price_default_key = _pk
        break

with _price_col:
    _price_choice: str = st.selectbox(
        "💰 Price",
        options=_price_option_keys,
        index=_price_option_keys.index(_price_default_key),
        label_visibility="collapsed",
        key="price_selectbox",
    )

# Initialise custom range session state with sensible defaults
if "custom_price_min" not in st.session_state:
    st.session_state["custom_price_min"] = 0
if "custom_price_max" not in st.session_state:
    st.session_state["custom_price_max"] = 15000

# Resolve price_range: use custom inputs when "Custom Range" is selected
if _price_choice == "Custom Range":
    _cpr_col1, _cpr_col2 = st.columns(2)
    with _cpr_col1:
        _custom_min = st.number_input(
            "Min Price ($)",
            min_value=0,
            max_value=50000,
            value=st.session_state["custom_price_min"],
            step=100,
            key="custom_price_min",
        )
    with _cpr_col2:
        _custom_max = st.number_input(
            "Max Price ($)",
            min_value=0,
            max_value=50000,
            value=st.session_state["custom_price_max"],
            step=100,
            key="custom_price_max",
        )
    # Guard against min > max — swap silently
    if _custom_min > _custom_max:
        _custom_min, _custom_max = _custom_max, _custom_min
    price_range: tuple[int, int] = (_custom_min, _custom_max)
else:
    price_range: tuple[int, int] = _price_options[_price_choice]

with _bed_col:
    # Selectbox approach: map user-friendly labels to the list format
    # that _build_filters() expects for bedrooms_selected
    _bed_options: dict[str, list[str]] = {
        "🛏 Any": [],
        "🛏 1+": ["1", "2", "3", "4", "5+"],
        "🛏 2+": ["2", "3", "4", "5+"],
        "🛏 3+": ["3", "4", "5+"],
        "🛏 4+": ["4", "5+"],
        "🛏 3-4": ["3", "4"],
    }
    # Determine default key from config
    _min_bed = _filter_cfg.get("min_bedrooms")
    _max_bed = _filter_cfg.get("max_bedrooms")
    _bed_default_key = "🛏 3-4"  # fallback matching original default of ["3","4"]
    if _min_bed is not None and _max_bed is not None:
        # Try to match config range to a preset key
        _cfg_beds: list[str] = []
        for _opt in ["1", "2", "3", "4", "5+"]:
            _val = 5 if _opt == "5+" else int(_opt)
            if _min_bed <= _val <= _max_bed:
                _cfg_beds.append(_opt)
        # Find matching key
        for _k, _v in _bed_options.items():
            if _v == _cfg_beds:
                _bed_default_key = _k
                break

    _bed_choice: str = st.selectbox(
        "🛏 Beds",
        options=list(_bed_options.keys()),
        index=list(_bed_options.keys()).index(_bed_default_key),
        label_visibility="collapsed",
        key="bed_selectbox",
    )
    bedrooms_selected: list[str] = _bed_options[_bed_choice]

with _bath_col:
    _bath_options: dict[str, list[str]] = {
        "🚿 Any": [],
        "🚿 1+": ["1", "1.5", "2", "2.5", "3", "3.5", "4+"],
        "🚿 2+": ["2", "2.5", "3", "3.5", "4+"],
        "🚿 3+": ["3", "3.5", "4+"],
    }
    _bath_choice: str = st.selectbox(
        "🚿 Baths",
        options=list(_bath_options.keys()),
        index=0,
        label_visibility="collapsed",
        key="bath_selectbox",
    )
    bathrooms_selected: list[str] = _bath_options[_bath_choice]

with _src_col:
    _source_options: dict[str, str] = {
        "📡 All": "All",
        "📡 Zillow": "Zillow",
        "📡 Craigslist": "Craigslist",
    }
    _source_choice: str = st.selectbox(
        "📡 Source",
        options=list(_source_options.keys()),
        index=0,
        label_visibility="collapsed",
        key="source_filter_radio",
    )
    source_filter: str = _source_options[_source_choice]

with _view_col:
    _view_options: dict[str, str] = {
        "👁️ Default": "Default",
        "⭐ Favorites": "Favorites",
        "📋 All": "All",
    }
    _view_choice: str = st.selectbox(
        "⭐ View",
        options=list(_view_options.keys()),
        index=0,
        label_visibility="collapsed",
        key="view_filter_radio",
    )
    view_filter: str = _view_options[_view_choice]

with _sort_col:
    _sort_options: dict[str, str] = {
        "📊 Newest First": "Newest First",
        "📊 Price: Low → High": "Price: Low → High",
        "📊 Price: High → Low": "Price: High → Low",
        "📊 Largest (sqft)": "Largest (sqft)",
        "📊 Most Bedrooms": "Most Bedrooms",
    }
    _sort_choice_bar: str = st.selectbox(
        "📊 Sort",
        options=list(_sort_options.keys()),
        index=0,
        label_visibility="collapsed",
        key="sort_select",
    )

with _reset_col:
    if st.button("✕", key="reset_filters_btn", help="Reset all filters"):
        # Clear all filter-related session state keys
        _filter_keys = [
            "price_selectbox", "bed_selectbox", "bath_selectbox",
            "source_filter_radio", "view_filter_radio",
            "sort_select", "listing_page",
            "custom_price_min", "custom_price_max", "last_disliked",
        ]
        for _fk in _filter_keys:
            if _fk in st.session_state:
                del st.session_state[_fk]
        st.rerun()

with _sync_col:
    # Manual sync — scheduling is handled by launchd agents
    _last_run = st.session_state.get("last_manual_sync")
    _sync_label = f"🔄 {_relative_time(_last_run)}"
    if st.button(
        _sync_label,
        key="sync_now_btn",
        help=f"Last manual sync: {_last_run.strftime('%Y-%m-%d %H:%M') if _last_run else 'Never'}\nScheduled syncs run via launchd\nClick to sync now",
    ):
        with st.spinner("Syncing…"):
            _orch = ScraperOrchestrator()
            _summary = _orch.run_sync_blocking()
        st.session_state["last_manual_sync"] = datetime.now(timezone.utc)
        st.success(
            f"✅ {_summary['new_listings']} new, "
            f"{_summary['updated_listings']} updated, "
            f"{_summary['errors']} errors"
        )
        st.rerun()

# Advanced filter defaults (widgets removed — no filtering applied)
min_sqft: int | None = 0
max_sqft: int | None = 0
pet_friendly_opt: str = "Any"
parking_opt: str = "Any"
laundry_opt: str = "Any"
ac_opt: str = "Any"
furnished_opt: str = "Any"
school_district_opt: str = "Any"
neighborhood_input: str = ""

# ---------------------------------------------------------------------------
# Build filter dictionary for database query
# ---------------------------------------------------------------------------


def _build_filters() -> dict[str, Any]:
    """Construct the filter dict from widget values."""
    filters: dict[str, Any] = {
        "min_price": price_range[0],
        "max_price": price_range[1],
        "is_active": True,
    }

    # Bedrooms — convert selected labels to numeric range
    if bedrooms_selected:
        bed_values: list[int] = []
        for b in bedrooms_selected:
            bed_values.append(5 if b == "5+" else int(b))
        filters["min_bedrooms"] = min(bed_values)
        filters["max_bedrooms"] = max(bed_values)

    # Bathrooms — convert selected labels to numeric range
    if bathrooms_selected:
        bath_values: list[float] = []
        for b in bathrooms_selected:
            bath_values.append(4.0 if b == "4+" else float(b))
        filters["min_bathrooms"] = min(bath_values)
        filters["max_bathrooms"] = max(bath_values)

    # Source — extract the base name (strip count suffix if present)
    _source_base = source_filter.split(" (")[0] if " (" in source_filter else source_filter
    if _source_base != "All":
        filters["source"] = _source_base.lower()

    # View filter — favorite / dislike logic
    if view_filter == "Favorites":
        filters["is_favorite"] = True
    elif view_filter == "Default":
        filters["exclude_disliked"] = True
    # "All" view: no favorite/dislike filtering

    # Square footage
    if min_sqft and min_sqft > 0:
        filters["min_sqft"] = min_sqft
    if max_sqft and max_sqft > 0:
        filters["max_sqft"] = max_sqft

    # Boolean / text amenities
    if pet_friendly_opt == "Yes":
        filters["pet_friendly"] = True
    elif pet_friendly_opt == "No":
        filters["pet_friendly"] = False

    if parking_opt != "Any":
        parking_val = parking_opt.lower()
        if parking_val == "none":
            parking_val = None  # type: ignore[assignment]
        filters["parking"] = parking_val

    if laundry_opt != "Any":
        laundry_val = laundry_opt.lower()
        if laundry_val == "none":
            laundry_val = None  # type: ignore[assignment]
        filters["laundry"] = laundry_val

    if ac_opt == "Yes":
        filters["ac"] = True
    elif ac_opt == "No":
        filters["ac"] = False

    if furnished_opt == "Yes":
        filters["furnished"] = True
    elif furnished_opt == "No":
        filters["furnished"] = False

    if school_district_opt != "Any":
        filters["school_district"] = school_district_opt

    if neighborhood_input.strip():
        filters["neighborhood"] = neighborhood_input.strip()

    return filters


filters = _build_filters()
_raw_listings: list[Listing] = get_filtered_listings(filters)

# ---------------------------------------------------------------------------
# Deduplicate listings — collapse identical posts (same title, price, beds,
# baths, address) that were posted multiple times with different post IDs.
# ---------------------------------------------------------------------------


def _deduplicate_listings(items: list[Listing]) -> list[Listing]:
    """Remove duplicate listings based on content similarity."""
    seen: set[tuple] = set()
    unique: list[Listing] = []
    for item in items:
        key = (
            (item.title or "").lower().strip(),
            item.price,
            item.bedrooms,
            item.bathrooms,
            (item.address or "").lower().strip(),
        )
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


listings: list[Listing] = _deduplicate_listings(_raw_listings)


# ---------------------------------------------------------------------------
# Helper: parse image_urls JSON string
# ---------------------------------------------------------------------------


def _parse_image_urls(raw: str | None) -> list[str]:
    """Parse a JSON-encoded image URL list, returning an empty list on failure.

    Only URLs starting with ``http://`` or ``https://`` are included to
    prevent injection via ``javascript:`` or ``data:`` URIs.
    """
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [
                str(u) for u in parsed
                if isinstance(u, str) and u.startswith(("http://", "https://"))
            ]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


# (Sync controls + API counter moved to bottom of main dashboard)

# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------

if not listings:
    st.info(
        "📭 No listings yet. Click **'🔄 Sync'** to start scraping!",
        icon="ℹ️",
    )
    st.stop()

# ---------------------------------------------------------------------------
# Constants for listings panel
# ---------------------------------------------------------------------------

CARDS_PER_PAGE = 6

# Vendor logo URLs for source badge icons (use Google favicon proxy for reliability)
_SOURCE_LOGOS: dict[str, str] = {
    "zillow": "https://www.google.com/s2/favicons?domain=zillow.com&sz=64",
    "craigslist": "https://www.google.com/s2/favicons?domain=craigslist.org&sz=64",
}

# ---------------------------------------------------------------------------
# Split Panel — Listings (left 40%) + Map (right 60%)
# ---------------------------------------------------------------------------

_panel_left, _panel_right = st.columns([2, 3])

# ---- Left panel: Scrollable listing cards ----
with _panel_left:
    # Read sort choice from session state (widget rendered in filter bar above)
    _sort_key = st.session_state.get("sort_select", "📊 Newest First")
    sort_option = _sort_options.get(_sort_key, "Newest First")

    # Apply selected sort
    if sort_option == "Newest First":
        sorted_listings: list[Listing] = sorted(listings, key=lambda l: l.listed_date or (l.first_seen.date() if l.first_seen else date.min), reverse=True)
    elif sort_option == "Price: Low → High":
        sorted_listings = sorted(listings, key=lambda l: l.price if l.price is not None else float('inf'))
    elif sort_option == "Price: High → Low":
        sorted_listings = sorted(listings, key=lambda l: l.price if l.price is not None else 0, reverse=True)
    elif sort_option == "Largest (sqft)":
        sorted_listings = sorted(listings, key=lambda l: l.sqft if l.sqft is not None else 0, reverse=True)
    elif sort_option == "Most Bedrooms":
        sorted_listings = sorted(listings, key=lambda l: l.bedrooms if l.bedrooms is not None else 0, reverse=True)
    else:
        sorted_listings = sorted(listings, key=lambda l: l.first_seen or datetime.min, reverse=True)

    # Initialise pagination state
    if "listing_page" not in st.session_state:
        st.session_state["listing_page"] = 0

    total_pages = max(1, math.ceil(len(sorted_listings) / CARDS_PER_PAGE))

    # Clamp current page to valid range
    if st.session_state["listing_page"] >= total_pages:
        st.session_state["listing_page"] = total_pages - 1
    if st.session_state["listing_page"] < 0:
        st.session_state["listing_page"] = 0

    current_page: int = st.session_state["listing_page"]
    start_idx = current_page * CARDS_PER_PAGE
    end_idx = start_idx + CARDS_PER_PAGE
    page_listings = sorted_listings[start_idx:end_idx]

    # Load price change data for visible listings (batch query to avoid N+1)
    _page_listing_ids = [l.id for l in page_listings]
    _price_changes = get_batch_price_changes(_page_listing_ids)

    # Undo last dislike button (compact, above the listing container)
    if st.session_state.get("last_disliked") is not None:
        if st.button("↩ Undo dislike", key="undo_dislike_btn", help="Restore the last disliked listing"):
            _undo_id = st.session_state["last_disliked"]
            toggle_dislike(_undo_id)
            st.session_state["last_disliked"] = None
            st.toast("↩ Listing restored!")
            st.rerun()

    with st.container(height=600):
      for listing in page_listings:
        with st.container(border=True):
            # Horizontal layout: thumbnail (left) + details (right)
            _thumb_col, _detail_col = st.columns([2.5, 5.6])

            with _thumb_col:
                # Thumbnail image with faded overlay icons
                _card_images = _parse_image_urls(listing.image_urls)

                # Determine overlay icon variants based on state
                _fav_icon = "★" if listing.is_favorite else "☆"
                _fav_cls = "overlay-btn active" if listing.is_favorite else "overlay-btn"
                _dis_icon = "👎" if listing.is_disliked else "👎🏻"
                _dis_cls = "overlay-btn active" if listing.is_disliked else "overlay-btn"

                _overlay_html = (
                    f'<div class="img-overlay-actions">'
                    f'<span class="{_fav_cls}">{_fav_icon}</span>'
                    f'<span class="{_dis_cls}">{_dis_icon}</span>'
                    f'</div>'
                )

                if _card_images:
                    _safe_img_url = html.escape(_card_images[0], quote=True)
                    _img_html = (
                        f'<div class="listing-img-wrapper">'
                        f'<img src="{_safe_img_url}" alt="Listing photo">'
                        f'{_overlay_html}'
                        f'</div>'
                    )
                else:
                    # Styled placeholder with property type icon
                    _prop_type = (listing.property_type or "").lower()
                    _placeholder_icon = "🏢" if _prop_type == "apartment" else "🏠"
                    _img_html = (
                        f'<div class="listing-img-wrapper">'
                        f'<div class="placeholder-img">{_placeholder_icon}</div>'
                        f'{_overlay_html}'
                        f'</div>'
                    )
                st.markdown(_img_html, unsafe_allow_html=True)

            with _detail_col:
                # Build compact card HTML — all text in a single markdown call
                _card_html_parts: list[str] = []

                # Price + Title on same line
                _price_str = f"${listing.price:,.0f}/mo" if listing.price is not None else "Price N/A"
                _price_color = "#3b82f6" if listing.price is not None else "#999"
                title = html.escape(listing.title or "Rental Listing")
                _card_html_parts.append(
                    f'<div style="display:flex; align-items:baseline; gap:6px;">'
                    f'<span class="card-price" style="color:{_price_color};">{_price_str}</span>'
                    f'<span class="card-title" style="flex:1; min-width:0;">{title}</span>'
                    f'</div>'
                )

                # Beds · Baths · Sqft on one line
                _specs_parts: list[str] = []
                if listing.bedrooms is not None:
                    _specs_parts.append(f"{listing.bedrooms} bed")
                if listing.bathrooms is not None:
                    _specs_parts.append(f"{listing.bathrooms:g} bath")
                if listing.sqft is not None:
                    _sqm_str = f" ({listing.sqm:.0f} m²)" if listing.sqm else ""
                    _specs_parts.append(f"{listing.sqft:,} sqft{_sqm_str}")
                if _specs_parts:
                    _card_html_parts.append(f'<div class="card-specs">{" · ".join(_specs_parts)}</div>')

                # --- Status tag badges (pill row) — max 3 visible (P1.4) ---
                _tag_list: list[str] = []

                # "New" tag — listed within last 3 days
                _posted_date = listing.listed_date or (listing.first_seen.date() if listing.first_seen else None)
                if _posted_date is not None:
                    _days_since_posted = (date.today() - _posted_date).days
                    if _days_since_posted <= 3:
                        _tag_list.append('<span class="card-tag tag-new">New</span>')

                # Price change tags (high priority — always shown)
                _pc = _price_changes.get(listing.id)
                if _pc and _pc["price_change"] != 0:
                    _change = _pc["price_change"]
                    if _change < 0:
                        _tag_list.insert(0, f'<span class="card-tag tag-price-drop">🔻 -${abs(_change):,.0f}</span>')
                    else:
                        _tag_list.insert(0, f'<span class="card-tag tag-price-up">🔺 +${_change:,.0f}</span>')

                # Available date badge
                if listing.available_date is not None:
                    try:
                        if isinstance(listing.available_date, date):
                            _avail_date = listing.available_date
                        else:
                            _avail_str = str(listing.available_date).strip()
                            _avail_date = None
                            for _fmt in ("%Y-%m-%d", "%B %d", "%b %d", "%m/%d/%Y", "%m-%d-%Y"):
                                try:
                                    _avail_date = datetime.strptime(_avail_str, _fmt).date()
                                    break
                                except ValueError:
                                    continue
                            if _avail_date is None:
                                raise ValueError(f"Cannot parse date: {_avail_str}")
                        if _avail_date <= date.today():
                            _tag_list.append('<span class="card-tag tag-available-now">🏠 Now</span>')
                        else:
                            _avail_fmt = _avail_date.strftime("%b %-d")
                            _tag_list.append(f'<span class="card-tag tag-available-future">🏠 {_avail_fmt}</span>')
                    except (ValueError, TypeError):
                        pass

                # Pet-friendly tag — always shown when applicable (important info)
                if listing.pet_friendly:
                    _tag_list.append('<span class="card-tag tag-pet">🐕 Dog Friendly</span>')
                # Lower-priority tags — only if under 3 badges (P1.4)
                if len(_tag_list) < 3 and listing.ac:
                    _tag_list.append('<span class="card-tag tag-ac">❄️ AC</span>')

                # Days on market indicator — lower priority (P1.4)
                if len(_tag_list) < 3 and _posted_date is not None:
                    _dom_days = (date.today() - _posted_date).days
                    if _dom_days == 0:
                        _dom_label = "Today"
                        _dom_css = "tag-fresh"
                    elif _dom_days == 1:
                        _dom_label = "1d ago"
                        _dom_css = "tag-fresh"
                    elif _dom_days <= 3:
                        _dom_label = f"{_dom_days}d ago"
                        _dom_css = "tag-fresh"
                    elif _dom_days <= 14:
                        _dom_label = f"{_dom_days}d ago"
                        _dom_css = "tag-aging"
                    else:
                        _dom_weeks = _dom_days // 7
                        if _dom_weeks <= 8:
                            _dom_label = f"{_dom_weeks}w ago"
                        else:
                            _dom_label = f"{_dom_days}d ago"
                        _dom_css = "tag-stale"
                    _tag_list.append(f'<span class="card-tag {_dom_css}">{_dom_label}</span>')

                # Build source pill links for ALL sources (multi-source support)
                _source_pills_html = ""
                _source_records = getattr(listing, "sources", None) or []
                if _source_records:
                    for _src_record in _source_records:
                        _src_url = _src_record.url or ""
                        if _src_url and _src_url.startswith(("http://", "https://")):
                            _safe_src_url = html.escape(_src_url, quote=True)
                            _src_name_lower = (_src_record.source or "").lower()
                            _logo_url = _SOURCE_LOGOS.get(_src_name_lower)
                            _src_label = html.escape((_src_record.source or "Link").capitalize())
                            if _logo_url:
                                _source_pills_html += (
                                    f'<a href="{_safe_src_url}" target="_blank" class="zillow-pill-link">'
                                    f'<img src="{html.escape(_logo_url, quote=True)}"> {_src_label}</a> '
                                )
                            else:
                                _source_pills_html += (
                                    f'<a href="{_safe_src_url}" target="_blank" class="zillow-pill-link">'
                                    f'↗ {_src_label}</a> '
                                )
                else:
                    # Fallback to legacy single-source fields
                    _listing_url = listing.url or ""
                    if _listing_url and _listing_url.startswith(("http://", "https://")):
                        _safe_listing_url = html.escape(_listing_url, quote=True)
                        _view_source = (listing.source or "").lower()
                        _link_logo_url = _SOURCE_LOGOS.get(_view_source)
                        _source_name = html.escape((listing.source or "Link").capitalize())
                        if _link_logo_url:
                            _source_pills_html = (
                                f'<a href="{_safe_listing_url}" target="_blank" class="zillow-pill-link">'
                                f'<img src="{html.escape(_link_logo_url, quote=True)}"> {_source_name}</a>'
                            )
                        else:
                            _source_pills_html = (
                                f'<a href="{_safe_listing_url}" target="_blank" class="zillow-pill-link">↗ {_source_name}</a>'
                            )

                # Add badges + source pills to HTML (same row)
                if _tag_list or _source_pills_html:
                    _card_html_parts.append(f'<div class="card-tag-row">{"".join(_tag_list[:3])}{_source_pills_html}</div>')

                # Location line (compact)
                _loc_parts: list[str] = []
                if listing.neighborhood:
                    _loc_parts.append(html.escape(listing.neighborhood))
                if listing.school_district:
                    _loc_parts.append(html.escape(listing.school_district))
                if _loc_parts:
                    _card_html_parts.append(
                        f'<div style="font-size:0.72rem; color:#777; line-height:1.2; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">'
                        f'{"  ·  ".join(_loc_parts)}</div>'
                    )

                # Render all detail HTML in one call to minimize Streamlit element overhead
                st.markdown(f'<div class="card-detail-wrapper">{"".join(_card_html_parts)}</div>', unsafe_allow_html=True)

    # Pagination row (inside left panel, outside scroll area)
    if total_pages > 1:
        prev_col, page_col, next_col = st.columns([1, 2, 1])
        with prev_col:
            if st.button("⬅ Previous", disabled=(current_page == 0), key="page_prev"):
                st.session_state["listing_page"] = current_page - 1
                st.session_state["last_disliked"] = None  # clear undo on page change
                st.rerun()
        with page_col:
            _total_listing_count = len(sorted_listings)
            st.markdown(
                f"<div style='text-align:center; padding-top:0.35rem; font-size:0.9rem;'>"
                f"Page {current_page + 1} of {total_pages} · {_total_listing_count} listings"
                f"<br><span style='font-size:0.7rem; color:#666;'>← → to navigate pages</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with next_col:
            if st.button("Next ➡", disabled=(current_page >= total_pages - 1), key="page_next"):
                st.session_state["listing_page"] = current_page + 1
                st.session_state["last_disliked"] = None  # clear undo on page change
                st.rerun()

        # Keyboard shortcuts — inject JS to click Previous/Next on arrow key press
        st.markdown(
            """
            <script>
            (function() {
                // Avoid duplicate listeners across Streamlit reruns
                if (window._sunnyNestKeyNav) return;
                window._sunnyNestKeyNav = true;

                document.addEventListener('keydown', function(e) {
                    // Skip if user is typing in an input, textarea, or select
                    var tag = (e.target.tagName || '').toLowerCase();
                    if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
                    if (e.target.isContentEditable) return;

                    if (e.key === 'ArrowLeft') {
                        // Find and click the "Previous" button
                        var buttons = window.parent.document.querySelectorAll('button');
                        for (var i = 0; i < buttons.length; i++) {
                            if (buttons[i].textContent.includes('Previous') && !buttons[i].disabled) {
                                buttons[i].click();
                                e.preventDefault();
                                break;
                            }
                        }
                    } else if (e.key === 'ArrowRight') {
                        // Find and click the "Next" button
                        var buttons = window.parent.document.querySelectorAll('button');
                        for (var i = 0; i < buttons.length; i++) {
                            if (buttons[i].textContent.includes('Next') && !buttons[i].disabled) {
                                buttons[i].click();
                                e.preventDefault();
                                break;
                            }
                        }
                    }
                });
            })();
            </script>
            """,
            unsafe_allow_html=True,
        )

# ---- Right panel: Map ----
with _panel_right:
    map_center: list[float] = [37.3688, -122.0363]
    # Disable scroll-wheel zoom so page scrolling isn't captured by the map.
    # Users can still zoom via +/- buttons or double-click.
    m = folium.Map(location=map_center, zoom_start=13, scrollWheelZoom=False, tiles="OpenStreetMap")

    # --- Scroll-wheel zoom guidance overlay ---
    # Inject JS that shows "Use Ctrl+Scroll to zoom" (or ⌘+Scroll on Mac)
    # when the user tries to scroll on the map without the modifier key.
    scroll_zoom_hint_js = """
    <script>
    (function() {
        // Wait for the map container to be available in the DOM
        function attachScrollHint() {
            var mapContainer = document.querySelector('.folium-map');
            if (!mapContainer) {
                // Retry — Folium iframe may not be ready yet
                setTimeout(attachScrollHint, 500);
                return;
            }
            // Create the overlay element
            var overlay = document.createElement('div');
            overlay.id = 'scroll-zoom-hint';
            var isMac = /Mac|iPod|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
            overlay.textContent = isMac ? '⌘ + Scroll to zoom' : 'Ctrl + Scroll to zoom';
            overlay.style.cssText = 'background:rgba(0,0,0,0.7);color:white;font-size:14px;'
                + 'text-align:center;padding:20px;border-radius:8px;position:absolute;'
                + 'top:50%;left:50%;transform:translate(-50%,-50%);z-index:1000;'
                + 'pointer-events:none;opacity:0;transition:opacity 0.3s ease;'
                + 'font-family:-apple-system,BlinkMacSystemFont,sans-serif;';
            mapContainer.style.position = 'relative';
            mapContainer.appendChild(overlay);

            var hideTimer = null;
            mapContainer.addEventListener('wheel', function(e) {
                // If Ctrl/Meta is held, the map handles zoom — don't show hint
                if (e.ctrlKey || e.metaKey) return;
                overlay.style.opacity = '1';
                if (hideTimer) clearTimeout(hideTimer);
                hideTimer = setTimeout(function() {
                    overlay.style.opacity = '0';
                }, 2000);
            }, {passive: true});
        }
        // Kick off after a short delay to let Folium render
        setTimeout(attachScrollHint, 800);
    })();
    </script>
    """
    m.get_root().html.add_child(folium.Element(scroll_zoom_hint_js))

    # Sunnyvale city boundary — accurate GeoJSON (515-point polygon)
    boundary_geojson = _load_sunnyvale_boundary()
    folium.GeoJson(
        boundary_geojson,
        style_function=lambda feature: {
            "color": "#1a73e8",
            "weight": 2,
            "fillColor": "#4285f4",
            "fillOpacity": 0.12,
            "dashArray": "",
        },
        name="Sunnyvale City Limits",
    ).add_to(m)

    # --- Marker overlap handling ---
    # Collect listings with valid coordinates, then offset overlapping markers
    # so stacked price pills remain readable.
    _PROXIMITY_THRESHOLD = 0.001  # ~111 m — markers closer than this are "overlapping"
    _OFFSET_STEP = 0.0008         # ~89 m vertical offset per stacked marker

    geo_listings: list[Listing] = [
        l for l in listings
        if l.latitude is not None and l.longitude is not None
    ]

    # Group by proximity: assign each listing to a cluster of nearby markers
    marker_positions: list[tuple[float, float]] = []  # final (lat, lng) per listing
    used_clusters: list[list[int]] = []  # each cluster is a list of indices

    for idx, listing in enumerate(geo_listings):
        lat, lng = listing.latitude, listing.longitude  # type: ignore[assignment]
        # Find if this listing belongs to an existing cluster
        placed = False
        for cluster in used_clusters:
            ref_idx = cluster[0]
            ref_lat = geo_listings[ref_idx].latitude  # type: ignore[union-attr]
            ref_lng = geo_listings[ref_idx].longitude  # type: ignore[union-attr]
            if (abs(lat - ref_lat) < _PROXIMITY_THRESHOLD
                    and abs(lng - ref_lng) < _PROXIMITY_THRESHOLD):
                # Offset vertically based on position within cluster
                offset_idx = len(cluster)
                adjusted_lat = lat + offset_idx * _OFFSET_STEP
                marker_positions.append((adjusted_lat, lng))
                cluster.append(idx)
                placed = True
                break
        if not placed:
            marker_positions.append((lat, lng))
            used_clusters.append([idx])

    for idx, listing in enumerate(geo_listings):
        adj_lat, adj_lng = marker_positions[idx]

        # Build popup HTML (escape user-controlled data to prevent XSS)
        popup_title = html.escape(listing.title or "Rental Listing")
        popup_price = html.escape(f"${listing.price:,.0f}/mo" if listing.price else "N/A")
        popup_beds = html.escape(f"{listing.bedrooms} bed" if listing.bedrooms else "")
        popup_sqft = html.escape(f"{listing.sqft:,} sqft ({listing.sqm:.0f} m²)" if listing.sqft else "")

        # Build source links for popup (multi-source support)
        _popup_source_links = ""
        _popup_sources = getattr(listing, "sources", None) or []
        if _popup_sources:
            for _ps in _popup_sources:
                _ps_url = _ps.url or "#"
                _ps_safe_url = html.escape(
                    _ps_url if _ps_url.startswith(("http://", "https://")) else "#",
                    quote=True,
                )
                _ps_label = html.escape((_ps.source or "Link").capitalize())
                _popup_source_links += (
                    f'<a href="{_ps_safe_url}" target="_blank" style="color:#1a73e8; margin-right:8px;">'
                    f'{_ps_label} ↗</a>'
                )
        else:
            # Fallback to legacy single-source field
            raw_url = listing.url or "#"
            popup_url = html.escape(
                raw_url if raw_url.startswith(("http://", "https://")) else "#",
                quote=True,
            )
            _popup_source_links = f'<a href="{popup_url}" target="_blank" style="color:#1a73e8;">View Listing ↗</a>'

        popup_html = f"""
        <div style="min-width:200px; background:#ffffff; color:#333333; border-radius:8px; padding:12px;">
            <b style="color:#111111;">{popup_title}</b><br>
            <span style="font-size:1.1em; color:#2563eb; font-weight:bold;">{popup_price}</span><br>
            <span style="color:#555;">{popup_beds}
            {' · ' + popup_sqft if popup_sqft else ''}</span><br>
            {_popup_source_links}
        </div>
        """

        price_label = _format_price_label(listing.price)

        pill_html = f'''
        <div style="
            background-color: #3b82f6;
            color: white;
            font-size: 11px;
            font-weight: bold;
            padding: 3px 8px;
            border-radius: 12px;
            white-space: nowrap;
            text-align: center;
            box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
            position: relative;
            cursor: pointer;
        ">{price_label}</div>
        '''

        folium.Marker(
            location=[adj_lat, adj_lng],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.DivIcon(
                html=pill_html,
                icon_size=(50, 24),
                icon_anchor=(25, 12),
                class_name="price-pill-marker",
            ),
        ).add_to(m)

    st_folium(m, height=800, use_container_width=True)

# --- Admin link (fixed-position — does not consume layout space) ---
st.markdown(
    '<div class="admin-link-fixed">'
    '<a href="http://localhost:8502" target="_blank" '
    'style="color: #4b5563; font-size: 11px; text-decoration: none; opacity: 0.6;">'
    'Admin →</a></div>',
    unsafe_allow_html=True,
)
