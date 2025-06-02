#!/usr/bin/env bash
# run_backup.sh – LiveJournal full backup via Docker
# Place at repo root (livejournal-export/run_backup.sh)
# chmod +x run_backup.sh

# NOTE: This script is the main entry point for Docker-based backups. It expects all code to be in src/.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKERFILE="$PROJECT_ROOT/docker/Dockerfile"
DOCKER_CONTEXT="$PROJECT_ROOT"

# Tag image with current Git commit hash
GIT_COMMIT=$(git -C "$PROJECT_ROOT" rev-parse --short=12 HEAD)
IMAGE_NAME="ljexport:${GIT_COMMIT}"

# -----------------------------------------------------------------------------
usage() {
  cat <<EOF
Usage: $0 [--dest DIR] [--start YYYY-MM] [--end YYYY-MM] [--clear]   or   $0 DIR

Options
  -d, --dest DIR     Host directory where the archive will be written
  -s, --start MONTH  Start month (YYYY-MM) for export (optional, overrides default)
  -e, --end MONTH    End month (YYYY-MM) for export (optional, overrides default)
  --clear            Delete all contents of the destination folder before backup (for testing)
  -h, --help         Show this help and exit
EOF
  exit 1
}

# 0. Parse CLI arguments ------------------------------------------------------
BACKUP_DIR_CLI=""
START_MONTH=""
END_MONTH=""
CLEAR_DEST=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--dest) BACKUP_DIR_CLI="$2"; shift 2 ;;
    -s|--start) START_MONTH="$2"; shift 2 ;;
    -e|--end) END_MONTH="$2"; shift 2 ;;
    --clear) CLEAR_DEST=1; shift ;;
    -h|--help) usage ;;
    --) shift; break ;;
    -*)
      echo "Unknown option: $1"; usage ;;
    *)  BACKUP_DIR_CLI="$1"; shift ;;
  esac
done

# 1. Load .env ---------------------------------------------------------------
[[ -f "$PROJECT_ROOT/.env" ]] && source "$PROJECT_ROOT/.env"

LJ_USER="${LJ_USER:-}"
LJ_PASS="${LJ_PASS:-}"

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
        echo "Pick a credential:"
        for i in "${!ITEMS[@]}"; do printf "  %d) %s\n" $((i+1)) "${ITEMS[$i]#*|}"; done
        printf "  %d) Cancel\n" $(( ${#ITEMS[@]} + 1 ))
        while read -rp "#? " CH && [[ ! "$CH" =~ ^[0-9]+$ ]]; do :; done
        if (( CH>=1 && CH<=${#ITEMS[@]} )); then
          BW_ID="${ITEMS[$((CH-1))]%%|*}"
          LJ_USER=$(bw get item "$BW_ID" "${BW_FLAGS[@]}" | jq -r '.login.username')
          LJ_PASS=$(bw get item "$BW_ID" "${BW_FLAGS[@]}" | jq -r '.login.password')
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
elif [[ -n "${BACKUP_DIR:-}" ]]; then
  :  # from .env
else
  DEFAULT_DIR="${PROJECT_ROOT}/backup"
  read -rp "Local directory for backup [${DEFAULT_DIR}]: " BACKUP_DIR
  BACKUP_DIR="${BACKUP_DIR:-$DEFAULT_DIR}"
fi

if [[ $CLEAR_DEST -eq 1 ]]; then
  echo "[TESTING] Clearing all contents of $BACKUP_DIR before backup..."
  rm -rf "$BACKUP_DIR"/*
fi

mkdir -p "$BACKUP_DIR/posts-json" "$BACKUP_DIR/images"

# 5. Build Docker image if tag is missing -----------------------------------
if ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
  echo "Building Docker image $IMAGE_NAME …"
  docker build -f "$DOCKERFILE" -t "$IMAGE_NAME" "$DOCKER_CONTEXT"
else
  echo "Docker image $IMAGE_NAME already exists – skipping build."
fi

# 6. Run backup --------------------------------------------------------------
echo "Running backup – output will appear in $BACKUP_DIR"
docker run --rm -it \
  -e LJ_USER="$LJ_USER" \
  -e LJ_PASS="$LJ_PASS" \
  -e START_MONTH="$START_MONTH" \
  -e END_MONTH="$END_MONTH" \
  -v "$BACKUP_DIR":/backup \
  "$IMAGE_NAME" \
  /opt/livejournal-export/src/lj_full_backup.sh

echo "✔ Done! Archive saved in $BACKUP_DIR"

