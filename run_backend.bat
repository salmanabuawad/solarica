@echo off
cd /d %~dp0\backend
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
