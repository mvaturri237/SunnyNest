#!/usr/bin/env bash
# uninstall-service.sh — Removes all SunnyNest Launch Agents
#
# This script:
#   1. Unloads all agents with launchctl
#   2. Removes all plists from ~/Library/LaunchAgents/

set -euo pipefail

# All plist files to manage
PLISTS=(
    "com.sunnynest.dashboard"
    "com.sunnynest.backoffice"
    "com.sunnynest.log-rotate"
    "com.sunnynest.scraper"
    "com.sunnynest.notify-am"
    "com.sunnynest.notify-pm"
)

echo "🏠 SunnyNest — Service Uninstaller"
echo "=============================================="
echo ""

# 1. Unload all agents
echo "⏹️  Unloading Launch Agents..."
for plist in "${PLISTS[@]}"; do
    dst="${HOME}/Library/LaunchAgents/${plist}.plist"
    if launchctl list | grep -q "${plist}"; then
        launchctl unload "${dst}" 2>/dev/null || true
        echo "   ✅ ${plist} unloaded"
    else
        echo "   ℹ️  ${plist} is not currently loaded"
    fi
done
echo ""

# 2. Remove all plists
echo "🗑️  Removing plists from ~/Library/LaunchAgents/..."
for plist in "${PLISTS[@]}"; do
    dst="${HOME}/Library/LaunchAgents/${plist}.plist"
    if [ -f "${dst}" ]; then
        rm "${dst}"
        echo "   ✅ ${dst} removed"
    else
        echo "   ℹ️  ${plist}.plist not found (already removed)"
    fi
done
echo ""

echo "=============================================="
echo "✅ SunnyNest services uninstalled!"
echo ""
echo "ℹ️  Log files in /tmp/sunnynest/ were NOT removed."
echo "   To remove them: rm -rf /tmp/sunnynest/"
