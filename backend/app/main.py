from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, branding, projects, tasks, measurements, inventory, mobile
from app.api.routes.companies import router as companies_router
from app.api.routes.security import router as security_router
from app.api.routes.project_files import router as project_files_router
from app.api.routes.task_attachments import router as task_attachments_router
from app.api.routes.warehouse import router as warehouse_router
from app.api.routes.audit import router as audit_router
from app.api.routes.string_scan import router as string_scan_router
from app.api.routes.testing import router as testing_router
from app.api.routes.topology import router as topology_router
from app.api.routes.device_inventory import router as device_inventory_router
from app.api.routes.solar_catalog import router as solar_catalog_router
from app.api.routes.field_config import router as field_config_router
from app.core.config import get_settings
from app.core.database import engine, SessionLocal, ensure_schema_patches
from app.core.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    # Create all tables (idempotent — only creates missing ones)
    try:
        from app.core.database import Base
        import app.models  # noqa: F401 — registers all ORM models
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error("DB table creation failed: %s", e)

    try:
        ensure_schema_patches()
    except Exception as e:
        logger.error("Schema patches failed: %s", e)

    # Seed default data
    try:
        from app.db.seed import run_all_seeds
        db = SessionLocal()
        try:
            run_all_seeds(db)
        finally:
            db.close()
    except Exception as e:
        logger.error("Seed failed: %s", e)

    # Start background scheduler
    try:
        start_scheduler()
    except Exception as e:
        logger.error("Scheduler failed to start: %s", e)

    yield  # ── Application running ───────────────────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────────────
    stop_scheduler()


app = FastAPI(
    title="Solarica API",
    version="2.0.0",
    description="Solarica — From Design to Operation",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,               prefix="/api/auth",        tags=["auth"])
app.include_router(companies_router,          prefix="/api",             tags=["companies"])
app.include_router(branding.router,           prefix="/api/branding",    tags=["branding"])
app.include_router(projects.router,           prefix="/api/projects",    tags=["projects"])
app.include_router(tasks.router,              prefix="/api/tasks",       tags=["tasks"])
app.include_router(task_attachments_router,   prefix="/api/tasks",       tags=["task-attachments"])
app.include_router(measurements.router,       prefix="/api/measurements",tags=["measurements"])
app.include_router(inventory.router,          prefix="/api/inventory",   tags=["inventory"])
app.include_router(warehouse_router,          prefix="/api/warehouse",   tags=["warehouse"])
app.include_router(mobile.router,             prefix="/api/mobile",      tags=["mobile"])
app.include_router(security_router,           prefix="/api/security",    tags=["security"])
app.include_router(project_files_router,      prefix="/api/projects",    tags=["project-files"])
app.include_router(audit_router,              prefix="/api/audit",       tags=["audit"])
app.include_router(string_scan_router,        prefix="/api/projects",    tags=["string-scan"])
app.include_router(testing_router,            prefix="/api/projects",    tags=["testing"])
app.include_router(topology_router,           prefix="/api",             tags=["topology"])
app.include_router(device_inventory_router,   prefix="/api/device-inventory", tags=["device-inventory"])
app.include_router(solar_catalog_router,      prefix="/api/solar-catalog",    tags=["solar-catalog"])
app.include_router(field_config_router,       prefix="/api/field-configs",    tags=["field-configs"])


@app.get("/health")
def health():
    return {"ok": True, "version": "2.0.0"}
