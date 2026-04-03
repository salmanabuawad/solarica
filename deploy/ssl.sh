#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Solarica — HTTPS setup via Let's Encrypt (Certbot)
#
# Usage:  sudo bash /opt/solarica/deploy/ssl.sh yourdomain.com
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DOMAIN="${1:-}"
if [[ -z "$DOMAIN" ]]; then
    echo "Usage: $0 <domain>"
    echo "Example: $0 solarica.yourcompany.com"
    exit 1
fi

echo "→ Installing Certbot…"
apt-get install -y -qq certbot python3-certbot-nginx

echo "→ Obtaining certificate for $DOMAIN…"
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
    --email "admin@$DOMAIN" --redirect

# Update Nginx server_name
sed -i "s|server_name _;|server_name $DOMAIN;|g" \
    /etc/nginx/sites-available/solarica

# Update CORS_ORIGINS in .env
ENV_FILE="/opt/solarica/.env"
if grep -q "^CORS_ORIGINS=" "$ENV_FILE"; then
    sed -i "s|^CORS_ORIGINS=.*|CORS_ORIGINS=https://$DOMAIN|" "$ENV_FILE"
else
    echo "CORS_ORIGINS=https://$DOMAIN" >> "$ENV_FILE"
fi

nginx -t && systemctl reload nginx
systemctl restart solarica-backend

echo ""
echo "✓ HTTPS enabled: https://$DOMAIN"
echo "  Auto-renewal is handled by certbot's systemd timer."
