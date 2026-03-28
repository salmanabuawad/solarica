# Local Reader

## Run
```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8100
```

## Diagnostics
```bash
python -m app.tools.list_ports
python -m app.tools.seed_mock_data
```
