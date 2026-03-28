# Deploy Solarica React frontend to the server.
# Builds frontend/dist, uploads via scp, moves files into /var/www/solarica.
#
# Usage (from repo root):
#   ./deploy-solarica-frontend.ps1
#
# Override targets via env vars (or deploy-credentials.local.ps1):
#   DEPLOY_HOST, DEPLOY_USER, DEPLOY_PATH, DEPLOY_APP_URL

$ErrorActionPreference = "Stop"

$credsFile = Join-Path $PSScriptRoot "deploy-credentials.local.ps1"
if (Test-Path $credsFile) { . $credsFile }

$SERVER      = if ($env:DEPLOY_HOST)     { $env:DEPLOY_HOST }     else { "185.229.226.37" }
$USER        = if ($env:DEPLOY_USER)     { $env:DEPLOY_USER }     else { "root" }
$REMOTE_PATH = if ($env:DEPLOY_PATH)     { $env:DEPLOY_PATH.TrimEnd("/") } else { "/var/www/solarica" }
$APP_URL     = if ($env:DEPLOY_APP_URL)  { $env:DEPLOY_APP_URL }  else { "https://solarica.wavelync.com/" }

Write-Host ""
Write-Host "========== SOLARICA FRONTEND DEPLOY ==========" -ForegroundColor Yellow
Write-Host "  Server:  $USER@$SERVER"
Write-Host "  Path:    $REMOTE_PATH"
Write-Host "  URL:     $APP_URL"
Write-Host "==============================================" -ForegroundColor Yellow
Write-Host ""

$frontendDir = Join-Path $PSScriptRoot "frontend"
if (-not (Test-Path $frontendDir)) {
    Write-Host "Error: frontend/ not found at $frontendDir" -ForegroundColor Red
    exit 1
}

# ── Build ────────────────────────────────────────────────────────────────────
Write-Host "[1/3] Building React app (npm run build)..." -ForegroundColor Cyan
Push-Location $frontendDir
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally { Pop-Location }

$distPath = Join-Path $frontendDir "dist"
if (-not (Test-Path $distPath)) {
    Write-Host "Error: frontend/dist not found after build." -ForegroundColor Red
    exit 1
}

# ── Upload ───────────────────────────────────────────────────────────────────
$remoteTemp = "/tmp/solarica_frontend_deploy"
Write-Host "[2/3] Uploading dist to ${USER}@${SERVER}:${remoteTemp} ..." -ForegroundColor Cyan
& scp -r $distPath "${USER}@${SERVER}:${remoteTemp}"
if ($LASTEXITCODE -ne 0) {
    Write-Host "SCP failed. Check SSH key: ssh $USER@$SERVER" -ForegroundColor Red
    exit $LASTEXITCODE
}

# ── Move into place ──────────────────────────────────────────────────────────
Write-Host "[3/3] Moving files into $REMOTE_PATH ..." -ForegroundColor Cyan
$remoteCmd = @"
set -e
mkdir -p $REMOTE_PATH
rm -rf ${REMOTE_PATH}/*
(mv ${remoteTemp}/dist/* $REMOTE_PATH/ 2>/dev/null || mv ${remoteTemp}/* $REMOTE_PATH/)
rm -rf $remoteTemp
chown -R www-data:www-data $REMOTE_PATH 2>/dev/null || true
echo frontend_deploy_done
"@
$remoteCmd = $remoteCmd -replace "`r`n", "`n" -replace "`r", "`n"
$remoteCmd | & ssh "${USER}@${SERVER}" "bash -s"
if ($LASTEXITCODE -ne 0) {
    Write-Host "SSH command failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Frontend deploy complete. $APP_URL" -ForegroundColor Green
