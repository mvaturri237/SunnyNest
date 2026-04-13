#!/usr/bin/env bash
# start-dashboard.sh — Activates the venv and starts the FastAPI dashboard via uvicorn
# Starts the FastAPI dashboard (for manual use; launchd plist invokes uvicorn directly)

set -euo pipefail

PROJECT_DIR="/Users/mvaturri/Documents/zillow"
VENV_DIR="${PROJECT_DIR}/.venv"

cd "${PROJECT_DIR}"

# Activate virtual environment
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

# Start FastAPI via uvicorn on port 8000
exec uvicorn web.main:app --host 127.0.0.1 --port 8000
