#!/usr/bin/env bash
# install-service.sh — Installs the SunnyNest services as macOS Launch Agents
#
# This script:
#   1. Creates the /tmp/sunnynest/ log directory
#   2. Copies all plists to ~/Library/LaunchAgents/
#   3. Loads all agents with launchctl
#   4. Prints status information

set -euo pipefail

PROJECT_DIR="/Users/mvaturri/Documents/zillow"
LOGS_DIR="/tmp/sunnynest"

# All plist files to manage
PLISTS=(
    "com.sunnynest.dashboard"
    "com.sunnynest.backoffice"
    "com.sunnynest.log-rotate"
    "com.sunnynest.scraper"
    "com.sunnynest.notify-am"
    "com.sunnynest.notify-pm"
)

echo "🏠 SunnyNest — Service Installer"
echo "============================================"
echo ""

# 1. Create logs directory (in /tmp to avoid TCC permission issues)
echo "📁 Creating logs directory..."
mkdir -p "${LOGS_DIR}"
echo "   ✅ ${LOGS_DIR}"
echo ""

# 2. Ensure scripts are executable
echo "🔧 Making scripts executable..."
chmod +x "${PROJECT_DIR}/scripts/start-dashboard.sh"
echo "   ✅ scripts/start-dashboard.sh"
chmod +x "${PROJECT_DIR}/scripts/start-backoffice.sh"
echo "   ✅ scripts/start-backoffice.sh"
chmod +x "${PROJECT_DIR}/scripts/rotate-logs.sh"
echo "   ✅ scripts/rotate-logs.sh"
echo ""

# 3. Unload existing agents if already loaded (ignore errors)
echo "♻️  Unloading existing agents..."
for plist in "${PLISTS[@]}"; do
    if launchctl list | grep -q "${plist}"; then
        launchctl unload "${HOME}/Library/LaunchAgents/${plist}.plist" 2>/dev/null || true
        echo "   ✅ ${plist} unloaded"
    fi
done
echo ""

# 4. Copy plists to LaunchAgents
echo "📋 Copying plists to ~/Library/LaunchAgents/..."
for plist in "${PLISTS[@]}"; do
    src="${PROJECT_DIR}/${plist}.plist"
    dst="${HOME}/Library/LaunchAgents/${plist}.plist"
    if [ -f "${src}" ]; then
        cp "${src}" "${dst}"
        echo "   ✅ ${dst}"
    else
        echo "   ⚠️  ${src} not found — skipping"
    fi
done
echo ""

# 5. Load the agents
echo "🚀 Loading Launch Agents..."
for plist in "${PLISTS[@]}"; do
    dst="${HOME}/Library/LaunchAgents/${plist}.plist"
    if [ -f "${dst}" ]; then
        launchctl load "${dst}"
        echo "   ✅ ${plist} loaded"
    fi
done
echo ""

# 6. Print status
echo "============================================"
echo "✅ SunnyNest services installed!"
echo ""
echo "📊 Status:"
for plist in "${PLISTS[@]}"; do
    if launchctl list | grep -q "${plist}"; then
        echo "   ${plist} — LOADED"
        launchctl list | grep "${plist}" | awk '{print "     PID: " $1 "  Status: " $2}'
    else
        echo "   ⚠️  ${plist} — may not have started yet"
    fi
done
echo ""
echo "🌐 Dashboard URL:  http://sunnynest:8000"
echo "🔧 Backoffice URL: http://localhost:8502"
echo ""
echo "📝 Log files (all in /tmp/sunnynest/):"
echo "   Dashboard:   ${LOGS_DIR}/dashboard-{stdout,stderr}.log"
echo "   Backoffice:  ${LOGS_DIR}/backoffice-{stdout,stderr}.log"
echo "   Scraper:     ${LOGS_DIR}/scraper-{stdout,stderr}.log"
echo "   Notify AM:   ${LOGS_DIR}/notify-am-{stdout,stderr}.log"
echo "   Notify PM:   ${LOGS_DIR}/notify-pm-{stdout,stderr}.log"
echo "   Log-rotate:  ${LOGS_DIR}/log-rotate-{stdout,stderr}.log"
echo ""
echo "⏰ Scheduled jobs:"
echo "   Scraper:     daily at 06:00 (com.sunnynest.scraper)"
echo "   Notify AM:   daily at 08:00 (com.sunnynest.notify-am)"
echo "   Notify PM:   daily at 20:00 (com.sunnynest.notify-pm)"
echo "   Log rotate:  weekly on Sunday (com.sunnynest.log-rotate)"
echo ""
echo "🔍 Useful commands:"
echo "   Check status:  launchctl list | grep sunnynest"
echo "   View logs:     tail -f /tmp/sunnynest/scraper-stderr.log"
echo "   Uninstall:     bash ${PROJECT_DIR}/scripts/uninstall-service.sh"
