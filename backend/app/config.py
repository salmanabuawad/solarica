from pathlib import Path
import os

APP_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = APP_ROOT.parent
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/solarica_local")
PROJECTS_ROOT = (BACKEND_ROOT / "data" / "projects").resolve()
PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
