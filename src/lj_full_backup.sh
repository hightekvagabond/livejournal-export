#!/usr/bin/env bash
# lj_full_backup.sh – runs inside the container
# Needs: LJ_USER  LJ_PASS   (exported by run_backup.sh)
# Optional: DEST  (target dir, default /backup)
# 
# NOTE: This script is now in src/ and is not used directly in the Docker workflow. The main entry point is run_backup.sh in the project root.
# All code is commented for clarity for junior developers.

set -euo pipefail

########################################
# 0. Validate env vars
########################################
: "${LJ_USER?Need LJ_USER env var (LiveJournal username)}"
: "${LJ_PASS?Need LJ_PASS env var (LiveJournal password / app-password)}"

DEST="${DEST:-/backup}"

########################################
# 1. Directory prep
########################################
mkdir -p "$DEST/batch-downloads" "$DEST/images" "$DEST/posts"

########################################
# 2. Date range (full history)
########################################
START_MONTH="${START_MONTH:-1999-01}" # earliest plausible LJ month
END_MONTH="${END_MONTH:-$(date -u +%Y-%m)}"          # current month (UTC)

########################################
# 3. Posts + comments + friend groups → JSON
########################################
python /opt/livejournal-export/src/export.py \
  --username "$LJ_USER" \
  --password "$LJ_PASS" \
  --start    "$START_MONTH" \
  --end      "$END_MONTH" \
  --format   json \
  --dest     "$DEST"

########################################
# 4. Images: download & rewrite <img src>
########################################
python /opt/livejournal-export/src/grab_images.py "$DEST"

# No legacy cleanup needed; assume blank folder for each run.

