# Deploy Solarica FastAPI backend to the server.
# Uploads backend/, creates/updates venv, installs requirements, restarts systemd.
#
# Usage (from repo root):
#   ./deploy-solarica-backend.ps1
#
# Override targets via env vars (or deploy-credentials.local.ps1):
#   DEPLOY_HOST, DEPLOY_USER, BACKEND_REMOTE_PATH,
#   DEPLOY_SYSTEMD_RESTART, DEPLOY_BACKEND_CHOWN

$ErrorActionPreference = "Stop"

$credsFile = Join-Path $PSScriptRoot "deploy-credentials.local.ps1"
if (Test-Path $credsFile) { . $credsFile }

$SERVER      = if ($env:DEPLOY_HOST)            { $env:DEPLOY_HOST }            else { "185.229.226.37" }
$USER        = if ($env:DEPLOY_USER)            { $env:DEPLOY_USER }            else { "root" }
$REMOTE_APP  = if ($env:BACKEND_REMOTE_PATH)    { $env:BACKEND_REMOTE_PATH.TrimEnd("/") } else { "/home/solarica/app" }
$ChownSpec   = if ($env:DEPLOY_BACKEND_CHOWN)   { $env:DEPLOY_BACKEND_CHOWN }   else { "solarica:solarica" }
$RestartUnits = if ($env:DEPLOY_SYSTEMD_RESTART) { $env:DEPLOY_SYSTEMD_RESTART } else { "solarica" }
$REMOTE_TEMP = "/tmp/solarica_backend_deploy"

Write-Host ""
Write-Host "========== SOLARICA BACKEND DEPLOY ==========" -ForegroundColor Yellow
Write-Host "  Server:          $USER@$SERVER"
Write-Host "  App path:        $REMOTE_APP/backend"
Write-Host "  systemd restart: $RestartUnits"
Write-Host "  chown:           $ChownSpec"
Write-Host "=============================================" -ForegroundColor Yellow
Write-Host ""

$backendPath = Join-Path $PSScriptRoot "backend"
if (-not (Test-Path $backendPath)) {
    Write-Host "Error: backend/ not found at $backendPath" -ForegroundColor Red
    exit 1
}

# ── Upload ───────────────────────────────────────────────────────────────────
Write-Host "[1/3] Uploading backend to ${USER}@${SERVER}:${REMOTE_TEMP} ..." -ForegroundColor Cyan
& scp -r "$backendPath" "${USER}@${SERVER}:${REMOTE_TEMP}"
if ($LASTEXITCODE -ne 0) {
    Write-Host "SCP failed. Check SSH key: ssh $USER@$SERVER" -ForegroundColor Red
    exit $LASTEXITCODE
}

# ── Restart lines ─────────────────────────────────────────────────────────────
$restartLines = foreach ($unit in ($RestartUnits -split '\s+' | Where-Object { $_.Trim() })) {
    $u = $unit.Trim()
    "sudo systemctl restart $u 2>/dev/null || sudo systemctl restart ${u}.service 2>/dev/null || echo WARNING_skip_$u"
}
$restartBlock  = ($restartLines | ForEach-Object { $_ }) -join "`n"
$chownLine     = if ($ChownSpec -and $ChownSpec -ne "skip") { "sudo chown -R $ChownSpec $REMOTE_APP/backend" } else { "true" }

# ── Sync + pip + restart (runs on server) ────────────────────────────────────
Write-Host "[2/3] Syncing to $REMOTE_APP/backend, installing deps, restarting..." -ForegroundColor Cyan
$remoteScript = @"
set -e
sudo mkdir -p $REMOTE_APP/backend
SRC=$REMOTE_TEMP/backend
if [ ! -d "`$SRC" ]; then SRC=$REMOTE_TEMP; fi
if [ ! -f "`$SRC/requirements.txt" ]; then echo ERROR_missing_requirements_txt; exit 1; fi

rsync -av --exclude=.env --exclude=.venv --exclude=venv \
  --exclude=__pycache__ --exclude='*.pyc' \
  --exclude=import_data \
  "`$SRC/" $REMOTE_APP/backend/
rm -rf $REMOTE_TEMP

cd $REMOTE_APP/backend

# ── Ensure venv exists ─────────────────────────────────────────────────────
if [ ! -x $REMOTE_APP/venv/bin/pip ]; then
  echo creating_venv
  python3 -m venv $REMOTE_APP/venv
fi
$REMOTE_APP/venv/bin/pip install -q -r requirements.txt

# ── Ensure import_data dir exists ─────────────────────────────────────────
mkdir -p $REMOTE_APP/backend/import_data

$chownLine
$restartBlock
echo backend_deploy_done
"@
$remoteScript = $remoteScript -replace "`r`n", "`n" -replace "`r", "`n"
$remoteScript | & ssh "${USER}@${SERVER}" "bash -s"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Remote script failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[3/3] Backend deploy complete." -ForegroundColor Green
Write-Host "      Health: ssh $USER@$SERVER 'curl -s http://127.0.0.1:8013/api/health'" -ForegroundColor DarkGray
