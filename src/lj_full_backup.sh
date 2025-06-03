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

if [[ "${DEBUG_LEVEL:-0}" -ge 2 ]]; then
  echo "[LJ_FULL_BACKUP DEBUG] Running as UID: $(id -u), GID: $(id -g), USER: $(id -un 2>/dev/null || echo 'unknown')"
fi

# Attempt to chown /backup and working directory if we have sudo/root
if command -v sudo >/dev/null 2>&1; then
  echo "[DEBUG] Attempting to chown /backup and working dir to current UID/GID using sudo..."
  sudo chown -R $(id -u):$(id -g) /backup || echo "[WARN] Failed to chown /backup"
  sudo chown -R $(id -u):$(id -g) . || echo "[WARN] Failed to chown working directory"
elif [ "$(id -u)" = "0" ]; then
  echo "[DEBUG] Running as root, chowning /backup and working dir..."
  chown -R 1000:1000 /backup || echo "[WARN] Failed to chown /backup"
  chown -R 1000:1000 . || echo "[WARN] Failed to chown working directory"
else
  echo "[DEBUG] Not root and no sudo, skipping chown."
fi

########################################
# 0. Validate env vars
########################################
: "${LJ_USER?Need LJ_USER env var (LiveJournal username)}"
: "${LJ_PASS?Need LJ_PASS env var (LiveJournal password / app-password)}"

DEST="${DEST:-/backup}"

# Early debug: check working directory and DEST before any tests or writes
if [[ "${DEBUG_LEVEL:-0}" -ge 2 ]]; then
  echo "[DEBUG] Early check: Working directory: $(pwd)"
  ls -ld . || echo "[DEBUG] Could not stat current working directory"
  echo "[DEBUG] Early check: DEST: ${DEST:-/backup}"
  ls -ld "${DEST:-/backup}" || echo "[DEBUG] Could not stat DEST (${DEST:-/backup})"
fi

########################################
# 1. Run tests if requested
########################################
if [[ "${RUN_TESTS:-false}" == "true" || "${RUN_TESTS:-0}" == "1" ]]; then
  echo "=== Running unit tests ==="
  mkdir -p "$DEST/tmp"
  # Create a temporary __init__.py in /backup/tmp instead of the codebase
  touch "$DEST/tmp/__init__.py"
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
if [[ "${DEBUG_LEVEL:-0}" -ge 2 ]]; then
  echo "[DEBUG] Checking ownership and permissions of DEST: $DEST"
  ls -ld "$DEST" || echo "[DEBUG] Could not stat $DEST"
  echo "[DEBUG] Listing first 10 files in $DEST (if any):"
  ls -l "$DEST" | head -n 10 || echo "[DEBUG] Could not list $DEST"
fi
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

