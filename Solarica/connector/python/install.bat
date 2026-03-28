@echo off
setlocal
echo ============================================================
echo  Solarica Python Connector - Windows Installer
echo ============================================================
echo.

REM Check Python is available
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.11+ from https://python.org
    pause
    exit /b 1
)

python --version

echo.
echo [1/4] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/4] Installing dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip -q
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    pause
    exit /b 1
)

echo [3/4] Creating data and watch folders...
if not exist data   mkdir data
if not exist import_watch mkdir import_watch

echo [4/4] Creating .env configuration...
if not exist .env (
    copy .env.example .env >nul
    echo   .env created from .env.example — edit it before running.
) else (
    echo   .env already exists, skipping.
)

echo.
echo ============================================================
echo  Installation complete!
echo.
echo  Next steps:
echo    1. Open .env and set PVPM_DRIVER (vendor_export recommended)
echo    2. If using vendor_export, set WATCH_FOLDER to the folder
echo       where the PVPM Transfer software exports files.
echo    3. Run: start.bat
echo ============================================================
pause
endlocal
