from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.v1.api import api_router

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

_downloads_dir = Path(__file__).parent.parent / "downloads"
_downloads_dir.mkdir(exist_ok=True)
app.mount("/downloads", StaticFiles(directory=str(_downloads_dir)), name="downloads")


@app.get("/health")
def health():
    return {"status": "ok"}
