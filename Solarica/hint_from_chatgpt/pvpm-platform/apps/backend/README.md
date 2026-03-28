# Backend API

## Run
```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 9000
```
