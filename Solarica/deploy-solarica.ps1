# Full Solarica deployment script.
# Reads from C:\Solarica  — does NOT modify mahsani_hashmal.
# Targets server 185.229.226.37 running the same host as pmc.wavelync.com.
#
# Solarica specifics vs PMC:
#   Linux user:  solarica  (sudo, pass: KortexDigital1342#)
#   DB user/DB:  solarica / solarica  (pass: solarica1342#)
#   postgres SA: postgres             (pass: postgres1342  — override with POSTGRES_SUPERUSER_PASSWORD)
#   Uvicorn:     127.0.0.1:8013
#   Static:      /var/www/solarica
#   systemd:     solarica.service
#   Domain:      solarica.wavelync.com
#
# Usage (from C:\Solarica in PowerShell):
#
#   First-time full setup:
#     ./deploy-solarica.ps1 -SetupUser -InitializeDatabase -DeployNginx
#
#   Code update only (no DB / user changes):
#     ./deploy-solarica.ps1
#
#   Database init only (no app deploy):
#     ./deploy-solarica.ps1 -InitializeDatabaseOnly
#
#   Enable TLS after DNS is live:
#     ./deploy-solarica.ps1 -RunCertbot
#
# Prerequisites:
#   1. SSH key installed for root@185.229.226.37
#   2. Copy deploy-credentials.local.ps1.example → deploy-credentials.local.ps1 and fill in passwords
#   3. Create backend/.env on the server (use backend/.env.server.example)
#   4. DNS A record: solarica.wavelync.com → 185.229.226.37 (needed for certbot)

param(
    [switch] $SetupUser,             # Create Linux user 'solarica' with sudo
    [switch] $InitializeDatabase,    # Create Postgres role + DB 'solarica'
    [switch] $InitializeDatabaseOnly,# DB init only (skip app deploy)
    [switch] $DeployNginx,           # Upload + enable nginx vhost
    [switch] $RunCertbot,            # Run certbot for TLS (requires DNS to be live)
    [switch] $SkipFrontend,          # Skip frontend build + upload
    [switch] $SkipBackend            # Skip backend upload + restart
)

$ErrorActionPreference = "Stop"

$credsFile = Join-Path $PSScriptRoot "deploy-credentials.local.ps1"
if (Test-Path $credsFile) {
    Write-Host "[deploy] Loaded deploy-credentials.local.ps1" -ForegroundColor DarkGray
    . $credsFile
}

# ── Targets ──────────────────────────────────────────────────────────────────
$SERVER      = if ($env:DEPLOY_HOST)            { $env:DEPLOY_HOST }            else { "185.229.226.37" }
$USER        = if ($env:DEPLOY_USER)            { $env:DEPLOY_USER }            else { "root" }
$REMOTE_APP  = if ($env:BACKEND_REMOTE_PATH)    { $env:BACKEND_REMOTE_PATH.TrimEnd("/") } else { "/home/solarica/app" }
$REMOTE_PATH = if ($env:DEPLOY_PATH)            { $env:DEPLOY_PATH.TrimEnd("/") }         else { "/var/www/solarica" }
$APP_URL     = if ($env:DEPLOY_APP_URL)         { $env:DEPLOY_APP_URL }                   else { "https://solarica.wavelync.com/" }
$DOMAIN      = "solarica.wavelync.com"
$remoteTmp   = "/tmp/solarica_setup_$(Get-Random)"

$setupScript  = Join-Path $PSScriptRoot "scripts\server\setup_solarica_linux_user.sh"
$initDbScript = Join-Path $PSScriptRoot "scripts\server\init_solarica_postgres.sh"
$serviceFile  = Join-Path $PSScriptRoot "scripts\systemd\solarica.service"
$nginxConf    = Join-Path $PSScriptRoot "nginx\solarica.wavelync.com.conf"

Write-Host ""
Write-Host "============ SOLARICA FULL DEPLOY ============" -ForegroundColor Yellow
Write-Host "  Server:        $USER@$SERVER"
Write-Host "  Frontend:      $REMOTE_PATH"
Write-Host "  Backend:       $REMOTE_APP/backend"
Write-Host "  Setup user:    $SetupUser"
Write-Host "  Init DB:       $(if ($InitializeDatabaseOnly) { 'DB only' } elseif ($InitializeDatabase) { 'Yes' } else { 'No' })"
Write-Host "  Deploy nginx:  $DeployNginx"
Write-Host "  Run certbot:   $RunCertbot"
Write-Host "  App URL:       $APP_URL"
Write-Host "==============================================" -ForegroundColor Yellow
Write-Host ""

# ── 1. Create Linux user 'solarica' ──────────────────────────────────────────
if ($SetupUser) {
    if (-not (Test-Path $setupScript)) {
        Write-Host "Missing $setupScript" -ForegroundColor Red; exit 1
    }
    $unixPass = $env:SOLARICA_UNIX_PASSWORD
    if (-not $unixPass) {
        Write-Host "Set SOLARICA_UNIX_PASSWORD in deploy-credentials.local.ps1" -ForegroundColor Red; exit 1
    }
    $localUnixSecret = [System.IO.Path]::GetTempFileName()
    try {
        [System.IO.File]::WriteAllText($localUnixSecret, $unixPass, [System.Text.UTF8Encoding]::new($false))
        Write-Host "[1] Setting up Linux user 'solarica' on server..." -ForegroundColor Cyan
        & ssh "${USER}@${SERVER}" "mkdir -p $remoteTmp && chmod 700 $remoteTmp"
        & scp $setupScript "${USER}@${SERVER}:${remoteTmp}/setup_solarica_linux_user.sh"
        & scp $localUnixSecret "${USER}@${SERVER}:${remoteTmp}/unix_secret"
        & ssh "${USER}@${SERVER}" "chmod +x ${remoteTmp}/setup_solarica_linux_user.sh && chmod 600 ${remoteTmp}/unix_secret && bash ${remoteTmp}/setup_solarica_linux_user.sh ${remoteTmp}/unix_secret"
        if ($LASTEXITCODE -ne 0) { Write-Host "User setup failed." -ForegroundColor Red; exit $LASTEXITCODE }
        Write-Host "[1] Linux user 'solarica' ready." -ForegroundColor Green
    } finally {
        Remove-Item -Force $localUnixSecret -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "[1] Skipping Linux user setup (-SetupUser not passed)." -ForegroundColor DarkGray
}

# ── 2. Postgres init ─────────────────────────────────────────────────────────
if ($InitializeDatabase -or $InitializeDatabaseOnly) {
    if (-not (Test-Path $initDbScript)) {
        Write-Host "Missing $initDbScript" -ForegroundColor Red; exit 1
    }
    $dbPass = $env:SOLARICA_DB_PASSWORD
    if (-not $dbPass) {
        Write-Host "Set SOLARICA_DB_PASSWORD in deploy-credentials.local.ps1" -ForegroundColor Red; exit 1
    }
    Write-Host "[2] Ensuring PostgreSQL is running on server..." -ForegroundColor DarkGray
    & ssh "${USER}@${SERVER}" 'for u in postgresql@16-main postgresql@15-main postgresql@14-main; do systemctl start "$u" 2>/dev/null || true; done; true'

    $localDbSecret = [System.IO.Path]::GetTempFileName()
    try {
        [System.IO.File]::WriteAllText($localDbSecret, $dbPass, [System.Text.UTF8Encoding]::new($false))
        Write-Host "[2] Initialising Postgres database 'solarica'..." -ForegroundColor Cyan
        & ssh "${USER}@${SERVER}" "mkdir -p $remoteTmp && chmod 700 $remoteTmp"
        & scp $initDbScript "${USER}@${SERVER}:${remoteTmp}/init_solarica_postgres.sh"
        & scp $localDbSecret "${USER}@${SERVER}:${remoteTmp}/db_secret"
        $pgSuperPw = if ($env:POSTGRES_SUPERUSER_PASSWORD) { $env:POSTGRES_SUPERUSER_PASSWORD } else { "postgres1342" }
        & ssh "${USER}@${SERVER}" "chmod +x ${remoteTmp}/init_solarica_postgres.sh && chmod 600 ${remoteTmp}/db_secret && SOLARICA_DB_NAME=solarica SOLARICA_DB_USER=solarica POSTGRES_SUPERUSER_PASSWORD='$pgSuperPw' bash ${remoteTmp}/init_solarica_postgres.sh ${remoteTmp}/db_secret && rm -rf $remoteTmp"
        if ($LASTEXITCODE -ne 0) { Write-Host "DB init failed." -ForegroundColor Red; exit $LASTEXITCODE }
        Write-Host "[2] Database 'solarica' ready." -ForegroundColor Green
        Write-Host "     DATABASE_URL=postgresql://solarica:<pass>@127.0.0.1:5432/solarica" -ForegroundColor DarkYellow
    } finally {
        Remove-Item -Force $localDbSecret -ErrorAction SilentlyContinue
    }

    if ($InitializeDatabaseOnly) {
        Write-Host ""
        Write-Host "DB-only mode. Create backend/.env on the server, then:" -ForegroundColor Green
        Write-Host "  ./deploy-solarica.ps1   (to deploy app code)" -ForegroundColor DarkGray
        exit 0
    }
} else {
    Write-Host "[2] Skipping DB init." -ForegroundColor DarkGray
}

# ── 3. Install systemd service ────────────────────────────────────────────────
Write-Host "[3] Installing systemd service unit..." -ForegroundColor Cyan
if (Test-Path $serviceFile) {
    & scp $serviceFile "${USER}@${SERVER}:/tmp/solarica.service"
    & ssh "${USER}@${SERVER}" "cp /tmp/solarica.service /etc/systemd/system/solarica.service && systemctl daemon-reload && systemctl enable solarica && rm /tmp/solarica.service"
    if ($LASTEXITCODE -ne 0) { Write-Host "systemd install failed." -ForegroundColor Red; exit $LASTEXITCODE }
    Write-Host "[3] solarica.service installed and enabled." -ForegroundColor Green
} else {
    Write-Host "[3] Skipping: $serviceFile not found." -ForegroundColor DarkGray
}

# ── 4. Frontend deploy ────────────────────────────────────────────────────────
if (-not $SkipFrontend) {
    Write-Host "[4] Deploying frontend..." -ForegroundColor Cyan
    $env:DEPLOY_HOST    = $SERVER
    $env:DEPLOY_USER    = $USER
    $env:DEPLOY_PATH    = $REMOTE_PATH
    $env:DEPLOY_APP_URL = $APP_URL
    & "$PSScriptRoot\deploy-solarica-frontend.ps1"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "[4] Skipping frontend (-SkipFrontend)." -ForegroundColor DarkGray
}

# ── 5. Backend deploy ─────────────────────────────────────────────────────────
if (-not $SkipBackend) {
    Write-Host "[5] Deploying backend..." -ForegroundColor Cyan
    $env:DEPLOY_HOST            = $SERVER
    $env:DEPLOY_USER            = $USER
    $env:BACKEND_REMOTE_PATH    = $REMOTE_APP
    $env:DEPLOY_BACKEND_CHOWN   = "solarica:solarica"
    $env:DEPLOY_SYSTEMD_RESTART = "solarica"
    & "$PSScriptRoot\deploy-solarica-backend.ps1"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} else {
    Write-Host "[5] Skipping backend (-SkipBackend)." -ForegroundColor DarkGray
}

# ── 6. Nginx vhost ────────────────────────────────────────────────────────────
if ($DeployNginx) {
    Write-Host "[6] Deploying nginx vhost for $DOMAIN ..." -ForegroundColor Cyan
    if (-not (Test-Path $nginxConf)) {
        Write-Host "Missing $nginxConf" -ForegroundColor Red; exit 1
    }
    & scp $nginxConf "${USER}@${SERVER}:/tmp/solarica.wavelync.com.conf"
    $nginxCmd = @"
set -e
cp /tmp/solarica.wavelync.com.conf /etc/nginx/sites-available/solarica.wavelync.com
ln -sf /etc/nginx/sites-available/solarica.wavelync.com \
       /etc/nginx/sites-enabled/solarica.wavelync.com
nginx -t
systemctl reload nginx
echo nginx_reload_ok
"@
    $nginxCmd = $nginxCmd -replace "`r`n", "`n"
    $nginxCmd | & ssh "${USER}@${SERVER}" "bash -s"
    if ($LASTEXITCODE -ne 0) { Write-Host "nginx config failed." -ForegroundColor Red; exit $LASTEXITCODE }
    Write-Host "[6] nginx vhost live: http://$DOMAIN" -ForegroundColor Green
} else {
    Write-Host "[6] Skipping nginx deploy (-DeployNginx not passed)." -ForegroundColor DarkGray
}

# ── 7. Certbot TLS ───────────────────────────────────────────────────────────
if ($RunCertbot) {
    Write-Host "[7] Running certbot for $DOMAIN ..." -ForegroundColor Cyan
    & ssh "${USER}@${SERVER}" "certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@wavelync.com"
    if ($LASTEXITCODE -ne 0) { Write-Host "certbot failed - check DNS propagation." -ForegroundColor Red; exit $LASTEXITCODE }
    Write-Host "[7] TLS certificate installed. $APP_URL is live." -ForegroundColor Green
} else {
    Write-Host "[7] Skipping certbot (-RunCertbot not passed)." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Solarica deploy finished." -ForegroundColor Green
Write-Host "  App:    $APP_URL" -ForegroundColor Cyan
Write-Host "  Health: curl -s https://$DOMAIN/api/health" -ForegroundColor DarkGray
Write-Host "  Logs:   ssh $USER@$SERVER 'journalctl -u solarica -f'" -ForegroundColor DarkGray
