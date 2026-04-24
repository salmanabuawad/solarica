## Deploy Notes (Nginx + FastAPI + React)

### Frontend (React + TypeScript)
Build:
```bash
cd frontend
npm install
npm run build
```

The build output is `frontend/dist/`.

### Backend (FastAPI)
Run:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Nginx
Use [`deploy/nginx/solarica.conf`](./nginx/solarica.conf) to:
- serve the React SPA
- reverse proxy `/api/*` and `/projects/*` to FastAPI

If you run Nginx locally (not Docker), change:
```nginx
server backend:8000;
```
to:
```nginx
server 127.0.0.1:8000;
```

