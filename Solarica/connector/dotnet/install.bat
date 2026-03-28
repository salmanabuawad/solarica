@echo off
setlocal EnableDelayedExpansion
echo ============================================================
echo  Solarica .NET Connector - Windows Installer
echo ============================================================
echo.

REM Must run as admin to install Windows Service
net session >nul 2>&1
if errorlevel 1 (
    echo  This script needs Administrator privileges to install a Windows Service.
    echo  Right-click install.bat and choose "Run as administrator".
    pause
    exit /b 1
)

REM Check dotnet is available
where dotnet >nul 2>&1
if errorlevel 1 (
    echo ERROR: .NET 8 SDK not found.
    echo Install from: https://dotnet.microsoft.com/download/dotnet/8.0
    pause
    exit /b 1
)
dotnet --version

echo.
echo [1/3] Publishing self-contained Windows executable...
set "SCRIPT_DIR=%~dp0"
dotnet publish "%SCRIPT_DIR%SolaricaConnector\SolaricaConnector.csproj" -c Release -r win-x64 --self-contained true -o "%SCRIPT_DIR%dist" --nologo -v quiet
if errorlevel 1 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo [2/3] Creating data folder...
if not exist "%SCRIPT_DIR%dist\data" mkdir "%SCRIPT_DIR%dist\data"

echo [3/3] Installing Windows Service...
set "EXE_PATH=%SCRIPT_DIR%dist\SolaricaConnector.exe"

sc query SolaricaConnector >nul 2>&1
if not errorlevel 1 (
    echo   Service already exists — stopping and deleting old version...
    sc stop SolaricaConnector >nul 2>&1
    timeout /t 3 /nobreak >nul
    sc delete SolaricaConnector >nul 2>&1
    timeout /t 2 /nobreak >nul
)

sc create SolaricaConnector binPath="%EXE_PATH%" start=auto DisplayName="Solarica Connector"
sc description SolaricaConnector "Solarica Local Connector - bridges PVPM 1540X device to the Solarica cloud app"
sc start SolaricaConnector

echo.
echo ============================================================
echo  Installation complete!
echo.
echo  The service is now running on  http://127.0.0.1:8765
echo  To change settings, edit dist\appsettings.json and restart:
echo    sc stop SolaricaConnector
echo    sc start SolaricaConnector
echo.
echo  To uninstall:  run uninstall.bat (as Administrator)
echo ============================================================
pause
endlocal
