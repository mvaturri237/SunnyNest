"""FastAPI application factory for the SunnyNest dashboard.

Note: Scheduling is handled by macOS launchd agents (com.sunnynest.scraper,
com.sunnynest.notify-am, com.sunnynest.notify-pm). This web server is a
pure HTTP server with no background scheduling. See plans/scheduler-fix.md.
"""

from __future__ import annotations

# Load .env BEFORE any other imports that may read env vars
from dotenv import load_dotenv

load_dotenv()  # reads .env from project root (if present)

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.database import init_db
from src.utils import load_config
from web.routes import admin, dashboard, listings
from web.routes import actions, api

logger = logging.getLogger("rental_finder.web")

# ---------------------------------------------------------------------------
# Startup environment validation
# ---------------------------------------------------------------------------


def _validate_environment() -> None:
    """Check for required/recommended environment variables at startup.

    Logs clear WARNING-level messages for any missing credentials so
    operators can spot configuration issues immediately after a restart.
    Does **not** crash the app — all warnings are advisory.
    """
    has_warnings = False

    # --- RAPIDAPI_KEY (Zillow scraper) ---
    if not os.environ.get("RAPIDAPI_KEY"):
        logger.warning(
            "⚠️  RAPIDAPI_KEY is not set — Zillow scraper will be disabled. "
            "Set it in .env or as an environment variable."
        )
        has_warnings = True

    # --- SMTP_PASSWORD (email notifications) ---
    if not os.environ.get("SMTP_PASSWORD"):
        # Only warn if email is actually enabled in config
        try:
            config = load_config()
            email_enabled = config.get("email", {}).get("enabled", False)
        except FileNotFoundError:
            email_enabled = False

        if email_enabled:
            logger.warning(
                "⚠️  SMTP_PASSWORD is not set — email notifications will fail. "
                "Set it in .env or as an environment variable."
            )
            has_warnings = True

    # --- REALTOR_RAPIDAPI_KEY (Realtor.com scraper) ---
    realtor_key = os.environ.get("REALTOR_RAPIDAPI_KEY") or os.environ.get("RAPIDAPI_KEY")
    if not realtor_key:
        try:
            config = load_config()
            realtor_enabled = config.get("realtor_api", {}).get("enabled", True)
        except FileNotFoundError:
            realtor_enabled = True
        if realtor_enabled:
            logger.warning(
                "⚠️  REALTOR_RAPIDAPI_KEY is not set (and RAPIDAPI_KEY fallback is also missing) "
                "— Realtor.com scraper will be disabled. "
                "Set it in .env or as an environment variable."
            )
            has_warnings = True

    # --- NOTIFICATION_RECIPIENT (optional, falls back to config.yaml) ---
    if not os.environ.get("NOTIFICATION_RECIPIENT"):
        logger.info(
            "ℹ️  NOTIFICATION_RECIPIENT is not set — falling back to "
            "recipient_email in config.yaml."
        )

    if not has_warnings:
        logger.info(
            "✅ Environment validation passed — all credentials configured."
        )


# ---------------------------------------------------------------------------
# Lifespan — runs on startup/shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the database on startup.

    Note: Background scheduling has been moved to launchd agents.
    The manual sync button (POST /admin/sync) still works — it calls
    ScraperOrchestrator directly, not through a scheduler.
    """
    # Ensure DB tables exist
    init_db()
    logger.info("Database initialised.")

    # Validate environment before starting services
    _validate_environment()

    logger.info(
        "FastAPI web server ready (pure HTTP — scheduling via launchd)."
    )

    yield  # Application is running

    logger.info("FastAPI web server shutting down.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SunnyNest",
    description="Rental listing aggregator dashboard",
    lifespan=lifespan,
)

# Mount static files
_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# Include routers
app.include_router(dashboard.router)
app.include_router(listings.router)
app.include_router(api.router)
app.include_router(actions.router)
app.include_router(admin.router)
