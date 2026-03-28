# DNS Setup + Full Deployment Guide — solarica.wavelync.com

## 1 — DNS record (add at your DNS provider)

Log into the control panel for the **wavelync.com** zone and create:

| Type | Name | Value | TTL |
|------|------|-------|-----|
| **A** | `solarica` | `185.229.226.37` | 300 |

This creates `solarica.wavelync.com → 185.229.226.37`.

> Same server as `pmc.wavelync.com`. Nginx on that server will route
> requests for `solarica.wavelync.com` to the Solarica backend on port 8013,
> completely separate from PMC on port 8011/8012.

Verify propagation (run from your laptop, takes 1–10 min after save):
```
nslookup solarica.wavelync.com
# or
dig solarica.wavelync.com +short
# expected: 185.229.226.37
```

---

## 2 — Pre-flight on your laptop

```powershell
# 1. Copy credentials template
cp deploy-credentials.local.ps1.example deploy-credentials.local.ps1

# 2. Fill in passwords in deploy-credentials.local.ps1:
#    $env:SOLARICA_UNIX_PASSWORD = "KortexDigital1342#"
#    $env:SOLARICA_DB_PASSWORD   = "solarica1342#"

# 3. Create the server .env (do this once manually after first deploy):
#    SSH in and run:
#    cp /home/solarica/app/backend/.env.server.example \
#       /home/solarica/app/backend/.env
#    nano /home/solarica/app/backend/.env
#    # Fill in SECRET_KEY with a fresh random value
```

---

## 3 — First-time full setup

```powershell
# From C:\Solarica in PowerShell:

# Step A: Create Linux user, init DB, deploy app + nginx (HTTP only)
./deploy-solarica.ps1 -SetupUser -InitializeDatabase -DeployNginx

# Verify HTTP works:
# http://solarica.wavelync.com/api/health  → {"status": "ok"}

# Step B: Enable TLS (only after DNS is live + HTTP works)
./deploy-solarica.ps1 -RunCertbot
```

---

## 4 — Code-only updates (after first setup)

```powershell
# Both frontend + backend
./deploy-solarica.ps1

# Frontend only
./deploy-solarica-frontend.ps1

# Backend only
./deploy-solarica-backend.ps1
```

---

## 5 — What gets created on the server

| Resource | Value |
|----------|-------|
| Linux user | `solarica` |
| Linux password | `KortexDigital1342#` |
| Sudo | Yes (group `sudo`) |
| Home | `/home/solarica` |
| App root | `/home/solarica/app` |
| Backend code | `/home/solarica/app/backend` |
| Python venv | `/home/solarica/app/venv` |
| Backend .env | `/home/solarica/app/backend/.env` |
| Frontend static | `/var/www/solarica` |
| systemd unit | `/etc/systemd/system/solarica.service` |
| Uvicorn port | `127.0.0.1:8013` |
| Nginx vhost | `/etc/nginx/sites-available/solarica.wavelync.com` |
| PostgreSQL DB | `solarica` |
| PostgreSQL user | `solarica` |
| DB password | `solarica1342#` |
| DB schema | `public` |

---

## 6 — Useful server commands

```bash
# SSH into server
ssh root@185.229.226.37

# Check service status
systemctl status solarica

# Tail logs
journalctl -u solarica -f

# Test API (from server)
curl -s http://127.0.0.1:8013/api/health

# Test through nginx
curl -sI https://solarica.wavelync.com/api/health

# Postgres — connect as solarica
sudo -u postgres psql -U solarica -d solarica

# List all databases (confirm solarica exists)
sudo -u postgres psql -c '\l'

# Restart service
sudo systemctl restart solarica

# After .env changes
sudo systemctl restart solarica
```

---

## 7 — Troubleshooting

| Symptom | Fix |
|---------|-----|
| `502 Bad Gateway` | Solarica service not running — `systemctl status solarica` |
| `curl: could not resolve host` | DNS not propagated yet — wait or check A record |
| `certbot` fails | DNS must resolve before certbot; run `-RunCertbot` after DNS is live |
| Database connection error | Check `/home/solarica/app/backend/.env` — DATABASE_URL must URL-encode `#` as `%23` |
| Permission denied on import_data | `chown solarica:solarica /home/solarica/app/backend/import_data` |
