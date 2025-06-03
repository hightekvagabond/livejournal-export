#!/usr/bin/env bash
# run_backup.sh – LiveJournal full backup via Docker
# Place at repo root (livejournal-export/run_backup.sh)
# chmod +x run_backup.sh

# NOTE: This script is the main entry point for Docker-based backups. It expects all code to be in src/.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKERFILE="$PROJECT_ROOT/Dockerfile"
DOCKER_CONTEXT="$PROJECT_ROOT"
REQUIREMENTS_FILE="$PROJECT_ROOT/requirements.txt"

# Tag image with current Git commit hash
GIT_COMMIT=$(git -C "$PROJECT_ROOT" rev-parse --short=12 HEAD)
IMAGE_NAME="ljexport:${GIT_COMMIT}"

# -----------------------------------------------------------------------------
usage() {
  cat <<EOF
Usage: $0 [--dest DIR] [--start YYYY-MM] [--end YYYY-MM] [--clear] [--debug LEVEL] [--no-bw-auto] [--run-tests]   or   $0 DIR

Options
  -d, --dest DIR     Host directory where the archive will be written
  -s, --start MONTH  Start month (YYYY-MM) for export (optional, overrides default)
  -e, --end MONTH    End month (YYYY-MM) for export (optional, overrides default)
  --clear            Delete all contents of the destination folder before backup (for testing),
                    and remove all Docker images/containers with ljexport:* to avoid caching issues
  --debug LEVEL      Set debug level (0=quiet, 1=info, 2=verbose, 3=debug)
  --no-bw-auto       Don't automatically select the only LiveJournal credential from Bitwarden
  --run-tests        Run unit tests before starting the backup
  -h, --help         Show this help and exit
EOF
  exit 1
}

# 0. Parse CLI arguments ------------------------------------------------------
BACKUP_DIR_CLI=""
START_MONTH=""
END_MONTH=""
CLEAR_DEST=0
DEBUG_LEVEL=0
BW_AUTO_SELECT=1  # Default to true
RUN_TESTS=0      # Default to false
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--dest) BACKUP_DIR_CLI="$2"; shift 2 ;;
    -s|--start) START_MONTH="$2"; shift 2 ;;
    -e|--end) END_MONTH="$2"; shift 2 ;;
    --clear) CLEAR_DEST=1; shift ;;
    --debug) DEBUG_LEVEL="$2"; shift 2 ;;
    --no-bw-auto) BW_AUTO_SELECT=0; shift ;;
    --run-tests) RUN_TESTS=1; shift ;;
    -h|--help) usage ;;
    --) shift; break ;;
    -*)
      echo "Unknown option: $1"; usage ;;
    *)  BACKUP_DIR_CLI="$1"; shift ;;
  esac
done

# 1. Load .env ---------------------------------------------------------------
ENV_FILE="$PROJECT_ROOT/.env"
if [[ -f "$ENV_FILE" ]]; then
  echo "Loading environment from $ENV_FILE"
  # shellcheck source=/dev/null
  source "$ENV_FILE"
else
  echo "No .env file found at $ENV_FILE - using defaults and CLI arguments"
fi

# Precedence: CLI > .env > prompt
LJ_USER="${LJ_USER:-}"
LJ_PASS="${LJ_PASS:-}"
DEST="${DEST:-}" # DEST is the main output directory
START="${START:-}" # Start month (YYYY-MM)
END="${END:-}"     # End month (YYYY-MM)
FORMAT="${FORMAT:-json}"
CLEAR="${CLEAR:-false}"
DEBUG_LEVEL="${DEBUG_LEVEL:-0}"
RUN_TESTS="${RUN_TESTS:-false}"

# Handle BW_AUTO_SELECT from .env if not set by CLI
if [[ -n "${BW_AUTO_SELECT:-}" ]]; then
  if [[ "$BW_AUTO_SELECT" == "true" ]]; then
    BW_AUTO_SELECT=1
  elif [[ "$BW_AUTO_SELECT" == "false" ]]; then
    BW_AUTO_SELECT=0
  fi
fi

# Handle RUN_TESTS from .env if not set by CLI
if [[ -n "${RUN_TESTS:-}" ]]; then
  if [[ "$RUN_TESTS" == "true" ]]; then
    RUN_TESTS=1
  elif [[ "$RUN_TESTS" == "false" ]]; then
    RUN_TESTS=0
  fi
fi

# Auto-enable tests if debug level is 3
if [[ $DEBUG_LEVEL -eq 3 ]]; then
  RUN_TESTS=1
fi

# 2. Pull creds from Bitwarden (same logic as before) ------------------------
if [[ -z "$LJ_USER" || -z "$LJ_PASS" ]]; then
  if command -v bw >/dev/null 2>&1 && command -v jq >/dev/null 2>&1; then
    echo "Bitwarden CLI detected."
    BW_FLAGS=()
    [[ -n "${BW_SESSION:-}" ]] && BW_FLAGS+=(--session "$BW_SESSION")
    if [[ "$(bw status "${BW_FLAGS[@]}" 2>/dev/null | jq -r .status)" == "unlocked" ]]; then
      echo 'Searching Bitwarden for items containing "livejournal" …'
      mapfile -t ITEMS < <(
        bw list items --search livejournal "${BW_FLAGS[@]}" |
        jq -r '.[] | (.id + "|" + .name + (if .login.username then " ["+.login.username+"]" else "" end))'
      )
      if ((${#ITEMS[@]})); then
        if [[ ${#ITEMS[@]} -eq 1 && $BW_AUTO_SELECT -eq 1 ]]; then
          echo "Found 1 LiveJournal credential:"
          printf "  1) %s\n" "${ITEMS[0]#*|}"
          echo "Auto-selecting the only credential..."
          BW_ID="${ITEMS[0]%%|*}"
          LJ_USER=$(bw get item "$BW_ID" "${BW_FLAGS[@]}" | jq -r '.login.username')
          LJ_PASS=$(bw get item "$BW_ID" "${BW_FLAGS[@]}" | jq -r '.login.password')
          echo "Using LiveJournal username: $LJ_USER"
        else
          echo "Found ${#ITEMS[@]} LiveJournal credentials:"
          echo "Pick a credential:"
          for i in "${!ITEMS[@]}"; do printf "  %d) %s\n" $((i+1)) "${ITEMS[$i]#*|}"; done
          printf "  %d) Cancel\n" $(( ${#ITEMS[@]} + 1 ))
          while read -rp "#? " CH && [[ ! "$CH" =~ ^[0-9]+$ ]]; do :; done
          if (( CH>=1 && CH<=${#ITEMS[@]} )); then
            BW_ID="${ITEMS[$((CH-1))]%%|*}"
            LJ_USER=$(bw get item "$BW_ID" "${BW_FLAGS[@]}" | jq -r '.login.username')
            LJ_PASS=$(bw get item "$BW_ID" "${BW_FLAGS[@]}" | jq -r '.login.password')
            echo "Using LiveJournal username: $LJ_USER"
          fi
        fi
      fi
    fi
  fi
fi

# 3. Final interactive fallback ---------------------------------------------
[[ -z "$LJ_USER" ]] && read -rp "LiveJournal username: " LJ_USER
[[ -z "$LJ_PASS" ]] && { read -rsp "LiveJournal password (app-password if 2-FA): " LJ_PASS; echo; }

# 4. Resolve backup directory ------------------------------------------------
if [[ -n "$BACKUP_DIR_CLI" ]]; then
  BACKUP_DIR="$BACKUP_DIR_CLI"
elif [[ -n "$DEST" ]]; then
  BACKUP_DIR="$DEST"
else
  DEFAULT_DIR="${PROJECT_ROOT}/backup"
  read -rp "Local directory for backup [${DEFAULT_DIR}]: " BACKUP_DIR
  BACKUP_DIR="${BACKUP_DIR:-$DEFAULT_DIR}"
fi

# 5. Date range and format from CLI or .env ----------------------------------
if [[ -n "$START_MONTH" ]]; then
  START="$START_MONTH"
fi
if [[ -n "$END_MONTH" ]]; then
  END="$END_MONTH"
fi

# 6. Clear destination if requested ------------------------------------------
if [[ "$CLEAR" == "true" || $CLEAR_DEST -eq 1 ]]; then
  echo "[TESTING] Clearing all contents of $BACKUP_DIR before backup..."
  rm -rf "$BACKUP_DIR"/*
  echo "[TESTING] Removing all Docker images with ljexport:* ..."
  if ! docker ps -a --filter ancestor=ljexport --format '{{.ID}}' | xargs -r docker rm; then
    echo "Warning: Failed to remove some Docker containers"
  fi
  echo "[TESTING] Done Removing all Docker containers with ljexport:* ..."
  if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep '^ljexport:' | xargs -r docker rmi -f; then
    echo "Warning: Failed to remove some Docker images"
  fi
  echo "[TESTING] Done Removing all Docker images with ljexport:* ..."
fi

mkdir -p "$BACKUP_DIR"
echo "[TESTING] Done creating $BACKUP_DIR"

# 7. Build Docker image if tag is missing -----------------------------------
if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  echo "Building Docker image $IMAGE_NAME …"
  if ! docker build -f "$DOCKERFILE" -t "$IMAGE_NAME" "$DOCKER_CONTEXT"; then
    echo "Error: Failed to build Docker image"
    exit 1
  fi
else
  echo "Docker image $IMAGE_NAME already exists – skipping build."
fi

# 8. Run backup --------------------------------------------------------------
echo "Running backup – output will appear in $BACKUP_DIR"
echo "Note: Inside the container, $BACKUP_DIR is mounted as /backup"

# Ensure Python output is not buffered
export PYTHONUNBUFFERED=1

# Run Docker with proper output handling
if ! docker run --rm -it \
  -e LJ_USER="$LJ_USER" \
  -e LJ_PASS="$LJ_PASS" \
  -e START_MONTH="$START" \
  -e END_MONTH="$END" \
  -e FORMAT="$FORMAT" \
  -e DEBUG_LEVEL="$DEBUG_LEVEL" \
  -e PYTHONUNBUFFERED=1 \
  -e RUN_TESTS="$RUN_TESTS" \
  -v "$BACKUP_DIR":/backup \
  "$IMAGE_NAME" \
  /opt/livejournal-export/src/lj_full_backup.sh 2>&1 | while IFS= read -r line; do
    # Remove any carriage returns and ensure proper line endings
    printf '%s\n' "$line"
  done; then
  echo "Error: Docker run failed"
  exit 1
fi

echo "✔ Done! Archive saved in $BACKUP_DIR"

# 9. Show results if debug level is 3 -----------------------------------------------
if [[ $DEBUG_LEVEL -eq 3 ]]; then
  echo -e "\n📊 Backup contents summary:"
  find "$BACKUP_DIR" -type d -print0 | while IFS= read -r -d '' d; do
    echo "$d:"
    n=$(find "$d" -maxdepth 1 -type f | wc -l)
    find "$d" -maxdepth 1 -type f | head -n 5
    [ "$n" -gt 5 ] && echo "... ($((n-5)) more files)"
  done
fi

