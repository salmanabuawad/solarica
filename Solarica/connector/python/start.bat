@echo off
setlocal
echo Starting Solarica Python Connector...

if not exist venv (
    echo ERROR: Virtual environment not found. Run install.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
uvicorn main:app --host 127.0.0.1 --port 8765 --reload
endlocal
