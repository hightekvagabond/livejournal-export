#!/usr/bin/env bash
# lj_full_backup.sh – runs inside the container
# Needs: LJ_USER  LJ_PASS   (exported by run_backup.sh)
# Optional: DEST  (target dir, default /backup)
# 
# NOTE: This script is now in src/ and is not used directly in the Docker workflow. The main entry point is run_backup.sh in the project root.
# All code is commented for clarity for junior developers.

set -euo pipefail

# Ensure output is not buffered
export PYTHONUNBUFFERED=1

echo "=== Starting lj_full_backup.sh ==="
echo "Current directory: $(pwd)"
echo "Environment variables:"
echo "LJ_USER: ${LJ_USER:-not set}"
echo "DEST: ${DEST:-/backup}"
echo "START_MONTH: ${START_MONTH:-1999-01}"
echo "END_MONTH: ${END_MONTH:-$(date -u +%Y-%m)}"
echo "PYTHONUNBUFFERED: ${PYTHONUNBUFFERED:-not set}"
echo "RUN_TESTS: ${RUN_TESTS:-false}"
echo "=== Environment check complete ==="

########################################
# 0. Validate env vars
########################################
: "${LJ_USER?Need LJ_USER env var (LiveJournal username)}"
: "${LJ_PASS?Need LJ_PASS env var (LiveJournal password / app-password)}"

DEST="${DEST:-/backup}"

########################################
# 1. Run tests if requested
########################################
if [[ "${RUN_TESTS:-false}" == "true" || "${RUN_TESTS:-0}" == "1" ]]; then
  echo "=== Running unit tests ==="
  cd /opt/livejournal-export/src
  # Create a temporary __init__.py if it doesn't exist
  touch __init__.py
  # Run tests with src directory in PYTHONPATH
  PYTHONPATH=/opt/livejournal-export/src python3 -m unittest discover -v tests
  TEST_RESULT=$?
  if [ $TEST_RESULT -ne 0 ]; then
    echo "Error: Unit tests failed"
    exit 1
  fi
  echo "=== All tests passed ==="
  cd /opt/livejournal-export
fi

########################################
# 2. Directory prep
########################################
echo "=== Creating directories ==="
mkdir -p "$DEST/batch-downloads" "$DEST/images" "$DEST/posts"
echo "Directories created successfully"

########################################
# 3. Date range (full history)
########################################
START_MONTH="${START_MONTH:-1999-01}" # earliest plausible LJ month
END_MONTH="${END_MONTH:-$(date -u +%Y-%m)}"          # current month (UTC)
echo "=== Date range: $START_MONTH to $END_MONTH ==="

########################################
# 4. Posts + comments + friend groups → JSON
########################################
echo "=== Starting export.py ==="
python /opt/livejournal-export/src/export.py \
  --username "$LJ_USER" \
  --password "$LJ_PASS" \
  --start    "$START_MONTH" \
  --end      "$END_MONTH" \
  --format   json \
  --dest     "$DEST"
echo "=== export.py completed ==="

########################################
# 5. Images: download & rewrite <img src>
########################################
echo "=== Starting grab_images.py ==="
python /opt/livejournal-export/src/grab_images.py "$DEST"
echo "=== grab_images.py completed ==="

echo "=== lj_full_backup.sh completed successfully ==="

# No legacy cleanup needed; assume blank folder for each run.

