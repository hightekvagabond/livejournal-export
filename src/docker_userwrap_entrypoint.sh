#!/usr/bin/env bash
set -euo pipefail

# Get the target UID/GID from environment or default to 1000
TARGET_UID=${HOST_UID:-1000}
TARGET_GID=${HOST_GID:-1000}
TARGET_USER=appuser

# Debug: Show UID/GID/USER if DEBUG_LEVEL is 2 or higher
if [[ "${DEBUG_LEVEL:-0}" -ge 2 ]]; then
  echo "[ENTRYPOINT DEBUG] Entrypoint running as UID: $(id -u), GID: $(id -g), USER: $(id -un 2>/dev/null || echo 'unknown')"
fi

# Create group if needed
if ! grep -q ":$TARGET_GID:" /etc/group; then
  if [[ "${DEBUG_LEVEL:-0}" -ge 2 ]]; then
    echo "[ENTRYPOINT DEBUG] Creating group $TARGET_USER with GID $TARGET_GID"
  fi
  groupadd -g "$TARGET_GID" "$TARGET_USER"
fi

# Create user if needed
if ! grep -q ":$TARGET_UID:" /etc/passwd; then
  if [[ "${DEBUG_LEVEL:-0}" -ge 2 ]]; then
    echo "[ENTRYPOINT DEBUG] Creating user $TARGET_USER with UID $TARGET_UID and GID $TARGET_GID"
  fi
  useradd -m -u "$TARGET_UID" -g "$TARGET_GID" -s /bin/bash "$TARGET_USER"
fi

# Add to sudoers with no password
if [[ "${DEBUG_LEVEL:-0}" -ge 2 ]]; then
  echo "[ENTRYPOINT DEBUG] Adding $TARGET_USER to sudoers with NOPASSWD"
fi
echo "$TARGET_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/$TARGET_USER
chmod 0440 /etc/sudoers.d/$TARGET_USER

if [[ "${DEBUG_LEVEL:-0}" -ge 2 ]]; then
  echo "[ENTRYPOINT DEBUG] Switching to $TARGET_USER (UID: $TARGET_UID, GID: $TARGET_GID) and running lj_full_backup.sh"
fi

# Exec as the target user, running lj_full_backup.sh with all arguments
exec sudo -E -u "$TARGET_USER" /opt/livejournal-export/src/lj_full_backup.sh "$@"
