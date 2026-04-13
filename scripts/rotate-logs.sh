#!/usr/bin/env bash
# rotate-logs.sh — Rotates log files in the /tmp/sunnynest/ log directory
#
# For each .log file in /tmp/sunnynest/:
#   1. If the file exceeds 50 MB, archive it (gzip with date suffix) and truncate
#   2. Delete archived logs (*.log.*.gz) older than 30 days
#
# Covers: dashboard, backoffice, scraper, notify, and log-rotate logs.
# Designed to be run weekly by com.sunnynest.log-rotate.plist

set -euo pipefail

PROJECT_DIR="/Users/mvaturri/Documents/zillow"
LOGS_DIR="/tmp/sunnynest"
MAX_SIZE_BYTES=$((50 * 1024 * 1024))  # 50 MB
RETENTION_DAYS=30

echo "$(date '+%Y-%m-%d %H:%M:%S') — Log rotation started"
echo "  Logs directory: ${LOGS_DIR}"
echo "  Max size before rotation: 50 MB"
echo "  Archive retention: ${RETENTION_DAYS} days"
echo ""

if [ ! -d "${LOGS_DIR}" ]; then
    echo "  ℹ️  Logs directory does not exist. Nothing to do."
    exit 0
fi

# --- Step 1: Rotate oversized log files ---
rotated=0
for log_file in "${LOGS_DIR}"/*.log; do
    [ -f "${log_file}" ] || continue

    file_size=$(stat -f%z "${log_file}" 2>/dev/null || stat --format=%s "${log_file}" 2>/dev/null || echo 0)

    if [ "${file_size}" -gt "${MAX_SIZE_BYTES}" ]; then
        timestamp=$(date '+%Y%m%d-%H%M%S')
        archive_name="${log_file}.${timestamp}.gz"

        echo "  📦 Rotating: $(basename "${log_file}") ($(( file_size / 1024 / 1024 )) MB)"
        gzip -c "${log_file}" > "${archive_name}"
        : > "${log_file}"  # Truncate the original
        echo "     → Archived to $(basename "${archive_name}")"
        rotated=$((rotated + 1))
    else
        echo "  ✅ $(basename "${log_file}") — $(( file_size / 1024 / 1024 )) MB (under limit, skipped)"
    fi
done

echo ""
echo "  Rotated ${rotated} file(s)"
echo ""

# --- Step 2: Delete old archives ---
deleted=0
for archive in "${LOGS_DIR}"/*.log.*.gz; do
    [ -f "${archive}" ] || continue

    # Find archives older than RETENTION_DAYS
    if [ "$(find "${archive}" -mtime +${RETENTION_DAYS} -print 2>/dev/null)" ]; then
        echo "  🗑️  Deleting old archive: $(basename "${archive}")"
        rm -f "${archive}"
        deleted=$((deleted + 1))
    fi
done

echo "  Deleted ${deleted} old archive(s)"
echo ""
echo "$(date '+%Y-%m-%d %H:%M:%S') — Log rotation complete"
