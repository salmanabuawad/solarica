# Deploy to solarica.wavelync.com

## How to deploy (quick)

| Command | What it does |
|--------|----------------|
| `npm run deploy:server` | Build frontend and deploy to nginx root only |
| `npm run deploy:server:all` | Build frontend, deploy frontend, then deploy backend (one confirmation) |
| `npm run deploy:backend` | Deploy backend only (no frontend build) |

**Backend-only after frontend:** Use `npm run deploy:backend` when you only changed backend code.
You'll see the deploy target (server, path, app URL); type `y` to confirm.

**Skip the confirmation prompt (e.g. scripts):**
```powershell
$env:DEPLOY_SKIP_CONFIRM = "1"; npm run deploy:server
$env:DEPLOY_SKIP_CONFIRM = "1"; npm run deploy:server:all
```

**What gets deployed:** Frontend: build then upload `frontend/dist/` via SCP to nginx root. Backend (when using `deploy:server:all` or `deploy:backend`): upload `backend/` then rsync, pip install, restart service. Live app: **https://solarica.wavelync.com/**

**Requirements:** SSH access (key-based or password). Default: `root@185.229.226.37`.

---

- **App URL:** https://solarica.wavelync.com/
- **SSH host:** `185.229.226.37` (override with `$env:DEPLOY_HOST`)
- **SSH user:** `root` (override with `$env:DEPLOY_USER`)
- **Frontend path:** `/opt/solarica/frontend/dist` (override: `$env:DEPLOY_PATH`)
- **Backend path:** `/opt/solarica` (override: `$env:BACKEND_REMOTE_PATH`)
- **Systemd service:** `solarica-backend`
- **Backend port:** `8010`
- **Venv:** `/opt/solarica/venv`

## Server setup (first time)

On the server (`root@185.229.226.37`):

1. **Create directories:**
   ```bash
   mkdir -p /var/www/solarica
   mkdir -p /home/solarica/app/backend
   ```

2. **Nginx config:** Copy `deploy/nginx/solarica.conf` to `/etc/nginx/sites-available/solarica` and symlink:
   ```bash
   ln -s /etc/nginx/sites-available/solarica /etc/nginx/sites-enabled/
   nginx -t && systemctl reload nginx
   ```

3. **Backend systemd service:** Create `/etc/systemd/system/solarica.service`:
   ```ini
   [Unit]
   Description=Solarica Parsing Engine API
   After=network.target

   [Service]
   WorkingDirectory=/home/solarica/app/backend
   ExecStart=/home/solarica/app/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```
   ```bash
   cd /home/solarica/app/backend
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   systemctl daemon-reload
   systemctl enable solarica
   systemctl start solarica
   ```

4. **SSL (Let's Encrypt):**
   ```bash
   certbot --nginx -d solarica.wavelync.com
   ```

## Environment variables (all optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `DEPLOY_HOST` | `185.229.226.37` | SSH host |
| `DEPLOY_USER` | `root` | SSH user |
| `DEPLOY_PATH` | `/opt/solarica/frontend/dist` | Frontend nginx root |
| `BACKEND_REMOTE_PATH` | `/opt/solarica` | Backend app root |
| `DEPLOY_APP_URL` | `https://solarica.wavelync.com/` | Shown in success message only |
| `DEPLOY_SKIP_CONFIRM` | (unset) | Set to `1` to skip "Deploy? [y/N]" |

## Notes

- Do not commit passwords. Set credentials only in your session.
- Frontend deploy replaces the contents of the nginx path with the new `dist/` contents.
- Backend deploy rsyncs `backend/` into `$BACKEND_REMOTE_PATH/backend/`, pip installs via `/opt/solarica/venv`, then restarts the `solarica-backend` systemd service.
- After deploy, hard-refresh (Ctrl+Shift+R) in the browser to load the new frontend.
