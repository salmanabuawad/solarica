$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Starting backend..." -ForegroundColor Cyan
Push-Location (Join-Path $root "backend")
if (!(Test-Path ".venv")) {
  python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt | Out-Host

$backend = Start-Process -PassThru -WindowStyle Normal -FilePath ".\\.venv\\Scripts\\python.exe" -ArgumentList @(
  "-m","uvicorn","app.main:app","--reload","--port","8000"
)
Pop-Location

Write-Host "Starting frontend..." -ForegroundColor Cyan
Push-Location (Join-Path $root "frontend")
if (!(Test-Path "node_modules")) {
  npm install | Out-Host
}
$frontend = Start-Process -PassThru -WindowStyle Normal -FilePath "npm.cmd" -ArgumentList @("run","dev")
Pop-Location

Write-Host "Backend PID: $($backend.Id)  Frontend PID: $($frontend.Id)" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor Yellow

try {
  Wait-Process -Id $frontend.Id
} finally {
  if (!$backend.HasExited) { Stop-Process -Id $backend.Id -Force }
}

