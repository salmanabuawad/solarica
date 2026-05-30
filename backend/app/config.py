from pathlib import Path
import os

APP_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = APP_ROOT.parent
DATABASE_URL = os.getenv("DATABASE_URL", "mysql://solarica:solarica@127.0.0.1:3306/solarica")
PROJECTS_ROOT = (BACKEND_ROOT / "data" / "projects").resolve()
PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
