# Deploy parsing_engine frontend to solarica.wavelync.com
# Default: root@185.229.226.37, path /var/www/solarica (see DEPLOY_SERVER.md)
# Override: DEPLOY_HOST, DEPLOY_USER, DEPLOY_PATH
# Skip confirmation: $env:DEPLOY_SKIP_CONFIRM = "1"

$ErrorActionPreference = "Stop"
$SERVER = if ($env:DEPLOY_HOST) { $env:DEPLOY_HOST } else { "185.229.226.37" }
$USER = if ($env:DEPLOY_USER) { $env:DEPLOY_USER } else { "root" }
$REMOTE_PATH = if ($env:DEPLOY_PATH) { $env:DEPLOY_PATH.TrimEnd("/") } else { "/opt/solarica/frontend/dist" }
$APP_URL = if ($env:DEPLOY_APP_URL) { $env:DEPLOY_APP_URL } else { "https://solarica.wavelync.com/" }

Write-Host ""
Write-Host "========== DEPLOY TARGET ==========" -ForegroundColor Yellow
Write-Host "  Server:    $USER@$SERVER"
Write-Host "  Path:      $REMOTE_PATH"
Write-Host "  App URL:   $APP_URL"
Write-Host "===================================" -ForegroundColor Yellow
Write-Host ""

if (-not $env:DEPLOY_SKIP_CONFIRM) {
    $confirm = Read-Host "Deploy to the above target? [y/N]"
    if ($confirm -notmatch '^[yY]') {
        Write-Host "Deploy cancelled." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host "Building frontend..." -ForegroundColor Cyan
Push-Location (Join-Path $PSScriptRoot "frontend")
npm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; exit $LASTEXITCODE }
Pop-Location

$distPath = Join-Path (Join-Path $PSScriptRoot "frontend") "dist"
if (-not (Test-Path $distPath)) {
    Write-Host "Error: dist folder not found at $distPath. Build failed?" -ForegroundColor Red
    exit 1
}

Write-Host "Deploying to ${USER}@${SERVER}:${REMOTE_PATH}" -ForegroundColor Cyan
$remoteTemp = "/tmp/solarica_frontend_deploy"
$scpTarget = "${USER}@${SERVER}:${remoteTemp}"
Write-Host "Uploading dist to $scpTarget ..."
& scp -r "$distPath" $scpTarget
if ($LASTEXITCODE -ne 0) {
    Write-Host "SCP failed. Ensure you have SSH key access: ssh $USER@$SERVER" -ForegroundColor Red
    exit $LASTEXITCODE
}

$remoteCmd = "mkdir -p $REMOTE_PATH && rm -rf ${REMOTE_PATH}/* && (mv ${remoteTemp}/dist/* $REMOTE_PATH/ 2>/dev/null || mv ${remoteTemp}/* $REMOTE_PATH/) && rm -rf $remoteTemp"
Write-Host "Moving files into place on server..."
& ssh "${USER}@${SERVER}" $remoteCmd
if ($LASTEXITCODE -ne 0) {
    Write-Host "SSH command failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Frontend deploy complete. App: $APP_URL" -ForegroundColor Green
