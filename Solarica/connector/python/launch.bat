@echo off
title Solarica Connector
cd /d "%~dp0"

if not exist venv (
    echo ERROR: Run install.bat first.
    pause & exit /b 1
)

echo Starting Solarica Connector...
start "" /B venv\Scripts\uvicorn main:app --host 127.0.0.1 --port 8765

timeout /t 2 /nobreak >nul

set CHROME=
for %%P in (
    "%ProgramFiles%\Google\Chrome\Application\chrome.exe"
    "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
    "%LocalAppData%\Google\Chrome\Application\chrome.exe"
) do if exist %%P set CHROME=%%P

if defined CHROME (
    start "" %CHROME% --app=http://127.0.0.1:8765 --window-size=1100,720 --window-position=100,80
) else (
    start "" "http://127.0.0.1:8765"
)
