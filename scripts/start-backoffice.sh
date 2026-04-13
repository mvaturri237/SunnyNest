#!/usr/bin/env bash
# start-backoffice.sh — Activates the venv and starts the Streamlit backoffice
# Used by the launchd Launch Agent (com.sunnynest.backoffice.plist)

set -euo pipefail

PROJECT_DIR="/Users/mvaturri/Documents/zillow"
VENV_DIR="${PROJECT_DIR}/.venv"

cd "${PROJECT_DIR}"

# Activate virtual environment
# shellcheck source=/dev/null
source "${VENV_DIR}/bin/activate"

# Start Streamlit in headless mode on port 8502
exec streamlit run backoffice.py \
    --server.headless true \
    --server.port 8502 \
    --server.address localhost
