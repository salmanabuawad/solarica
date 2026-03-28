@echo off
echo Removing Solarica Connector Windows Service...

net session >nul 2>&1
if errorlevel 1 (
    echo Run as Administrator.
    pause
    exit /b 1
)

sc stop SolaricaConnector >nul 2>&1
timeout /t 3 /nobreak >nul
sc delete SolaricaConnector
echo Service removed.
pause
