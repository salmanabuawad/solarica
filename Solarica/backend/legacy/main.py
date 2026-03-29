"""
IVCurve - PVPM 1540X Data Ingestion & Analysis API
Python FastAPI backend for photovoltaic I-V curve data
"""

from contextlib import asynccontextmanager
from pathlib import Path

import traceback
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import measurements, import_data, analysis, sites, pvpm_import, auth, preferences, string_scan
from config import settings
from database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    init_db()
    if settings.watch_import_folder:
        try:
            from services.file_watcher import start_file_watcher, stop_file_watcher
            start_file_watcher()
        except ImportError:
            pass  # watchdog not installed, skip file watching
    yield
    if settings.watch_import_folder:
        try:
            from services.file_watcher import stop_file_watcher
            stop_file_watcher()
        except ImportError:
            pass


app = FastAPI(
    title="IVCurve API",
    description="PVPM 1540X I-V Curve Data Ingestion and Analysis",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(measurements.router, prefix="/api/measurements", tags=["measurements"])
app.include_router(import_data.router, prefix="/api/import", tags=["import"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(sites.router, prefix="/api/sites", tags=["sites"])
# v1 PVPM connector routes (camelCase format from connector/local-reader)
app.include_router(pvpm_import.router, prefix="/api/v1/import", tags=["pvpm-import"])
# Auth / RBAC
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
# User preferences
app.include_router(preferences.router, prefix="/api/preferences", tags=["preferences"])
# String scan
app.include_router(string_scan.router, prefix="/api", tags=["string-scan"])

# Create import folder if it doesn't exist
Path(settings.import_folder).mkdir(parents=True, exist_ok=True)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "ivcurve-api"}
