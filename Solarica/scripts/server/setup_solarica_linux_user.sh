#!/usr/bin/env bash
# Create the 'solarica' Linux system user with sudo privileges.
# Run on the server as root.
#
# Usage:
#   bash setup_solarica_linux_user.sh /path/to/unix_password_file
#
# The password file must contain exactly one line: the plain-text password.
# The file is deleted after use.
set -euo pipefail

UNIX_SECRET_FILE="${1:?Usage: $0 <unix_password_file>}"
if [ ! -f "$UNIX_SECRET_FILE" ]; then
  echo "Password file not found: $UNIX_SECRET_FILE" >&2
  exit 1
fi

UNIX_USER="solarica"
UNIX_PASS="$(cat "$UNIX_SECRET_FILE" | tr -d '\r\n')"
if [ -z "$UNIX_PASS" ]; then
  echo "Empty password in $UNIX_SECRET_FILE" >&2
  exit 1
fi

# ── Create user if not present ─────────────────────────────────────────────
if id "$UNIX_USER" &>/dev/null; then
  echo "[user] '$UNIX_USER' already exists — updating password."
else
  echo "[user] Creating user '$UNIX_USER'..."
  useradd \
    --create-home \
    --shell /bin/bash \
    --comment "Solarica app user" \
    "$UNIX_USER"
fi

# ── Set password ────────────────────────────────────────────────────────────
echo "${UNIX_USER}:${UNIX_PASS}" | chpasswd
echo "[user] Password set for '$UNIX_USER'."

# ── Add to sudo group ───────────────────────────────────────────────────────
if ! groups "$UNIX_USER" | grep -q '\bsudo\b'; then
  usermod -aG sudo "$UNIX_USER"
  echo "[user] '$UNIX_USER' added to sudo group."
else
  echo "[user] '$UNIX_USER' is already in the sudo group."
fi

# ── Create app directories ──────────────────────────────────────────────────
APP_HOME="/home/${UNIX_USER}/app"
mkdir -p "${APP_HOME}/backend"
chown -R "${UNIX_USER}:${UNIX_USER}" "/home/${UNIX_USER}"
echo "[user] App directory ready: ${APP_HOME}"

# ── Secure-delete the password file ─────────────────────────────────────────
rm -f "$UNIX_SECRET_FILE"
echo "[user] Password file deleted."

echo ""
echo "Done. Linux user '${UNIX_USER}' is ready (sudo enabled)."
echo "  Home:    /home/${UNIX_USER}"
echo "  App dir: ${APP_HOME}"
echo "  Login:   ssh ${UNIX_USER}@<server>"
