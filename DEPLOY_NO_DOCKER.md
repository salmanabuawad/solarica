# Solarica deployment without Docker

This package runs as a standard **FastAPI + PostgreSQL + Vite/React** application.

## 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 2. Frontend

```bash
cd frontend
npm ci
npm run dev
```

## 3. Production build

```bash
cd frontend
npm ci
npm run build
```

Serve `frontend/dist` with Nginx or any static web server, and reverse-proxy `/api` to the FastAPI backend.

## 4. Database

The backend creates missing ORM tables at startup. For first-time setup you can also load:

```bash
psql "$DATABASE_URL" -f database/solarica_schema.sql
```

## 5. New map engine endpoints

- `GET /api/projects/{project_id}/map/workspace`
- `POST /api/projects/{project_id}/map/bootstrap`
- `GET /api/projects/{project_id}/map/layers`
- `GET /api/projects/{project_id}/map/objects`
- `POST /api/projects/{project_id}/map/objects`
- `PATCH /api/map/objects/{object_id}`
- `POST /api/map/objects/{object_id}/link`

## 6. What is included

- persistent `map_layers`, `map_objects`, `map_object_links`
- backend map workspace bootstrap from existing project data
- frontend layered map inside **Project Details**
- object inspector and layer toggles
- tracker / floating / rooftop / fixed-tilt aware rendering
- storage-aware overlays

## 7. Kendo note

The current UI is implemented with SVG so the app works immediately.
The data contract is intentionally Kendo-ready, so a later KendoReact Map adapter can replace the renderer without changing the API.
