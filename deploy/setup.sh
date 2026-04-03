#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Solarica — Server Setup Script
# Tested on: Ubuntu 22.04 / 24.04, Debian 12
#
# Usage:
#   1. Copy the whole Solarica_OM project to the server (see deploy.sh)
#   2. SSH in and run:  sudo bash /opt/solarica/deploy/setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

APP_DIR="/opt/solarica"
APP_USER="solarica"
PYTHON="python3"
VENV="$APP_DIR/venv"
FRONTEND_DIST="$APP_DIR/frontend/dist"

echo "═══════════════════════════════════════════"
echo "  Solarica — Server Setup"
echo "═══════════════════════════════════════════"

# ── 1. System packages ────────────────────────────────────────────
echo "→ Installing system packages…"
apt-get update -qq
apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    postgresql postgresql-contrib \
    nginx \
    nodejs npm \
    build-essential libpq-dev curl git

# ── 2. Create app user ────────────────────────────────────────────
if ! id "$APP_USER" &>/dev/null; then
    echo "→ Creating system user '$APP_USER'…"
    useradd --system --shell /bin/bash --home "$APP_DIR" "$APP_USER"
fi

# ── 3. PostgreSQL setup ───────────────────────────────────────────
echo "→ Configuring PostgreSQL…"
systemctl enable postgresql --now

# Load env for DB credentials
if [[ -f "$APP_DIR/.env" ]]; then
    set -a; source "$APP_DIR/.env"; set +a
fi

DB_USER="${POSTGRES_USER:-solarica}"
DB_PASS="${POSTGRES_PASSWORD:-solarica}"
DB_NAME="${POSTGRES_DB:-solarica}"

sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" \
    | grep -q 1 || sudo -u postgres psql -c \
    "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" \
    | grep -q 1 || sudo -u postgres psql -c \
    "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

# Run schema (idempotent — uses IF NOT EXISTS)
sudo -u postgres psql "$DB_NAME" < "$APP_DIR/database/solarica_schema.sql"
echo "   Database ready."

# ── 4. Python virtualenv + deps ───────────────────────────────────
echo "→ Setting up Python virtualenv…"
$PYTHON -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$APP_DIR/backend/requirements.txt"
echo "   Python deps installed."

# ── 5. Build frontend ─────────────────────────────────────────────
echo "→ Building frontend…"
cd "$APP_DIR/frontend"
npm ci --silent
npm run build
echo "   Frontend built → $FRONTEND_DIST"

# ── 6. Write .env if missing ──────────────────────────────────────
if [[ ! -f "$APP_DIR/.env" ]]; then
    echo "→ Generating .env from .env.example…"
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s|replace_with_generated_secret|$SECRET|g" "$APP_DIR/.env"
    echo "   ⚠  Edit $APP_DIR/.env and set POSTGRES_PASSWORD and other values."
fi

# ── 7. Systemd service ────────────────────────────────────────────
echo "→ Installing systemd service…"
cp "$APP_DIR/deploy/solarica-backend.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable solarica-backend
systemctl restart solarica-backend
echo "   Backend service started."

# ── 8. Nginx ──────────────────────────────────────────────────────
echo "→ Configuring Nginx…"

# Detect domain or use server IP
DOMAIN="${SOLARICA_DOMAIN:-_}"

sed "s|__APP_DIR__|$APP_DIR|g; s|__DOMAIN__|$DOMAIN|g" \
    "$APP_DIR/deploy/nginx.conf" \
    > /etc/nginx/sites-available/solarica

ln -sf /etc/nginx/sites-available/solarica /etc/nginx/sites-enabled/solarica
rm -f /etc/nginx/sites-enabled/default

nginx -t
systemctl enable nginx
systemctl restart nginx
echo "   Nginx configured."

# ── 9. Permissions ────────────────────────────────────────────────
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# ── Done ──────────────────────────────────────────────────────────
SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "═══════════════════════════════════════════"
echo "  ✓  Solarica is running!"
echo "     http://$SERVER_IP"
echo "═══════════════════════════════════════════"
echo ""
echo "  Next steps:"
echo "  • Edit $APP_DIR/.env  (set POSTGRES_PASSWORD, SECRET_KEY)"
echo "  • sudo systemctl restart solarica-backend"
echo "  • For HTTPS: sudo bash $APP_DIR/deploy/ssl.sh yourdomain.com"
echo ""
