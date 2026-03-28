from fastapi import APIRouter
from app.api.v1.routes import auth, sites, projects, design_files, validation, progress, inventory, tests, maintenance, rules

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(sites.router, prefix="/sites", tags=["sites"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(design_files.router, prefix="/design-files", tags=["design-files"])
api_router.include_router(validation.router, prefix="/validation", tags=["validation"])
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["inventory"])
api_router.include_router(tests.router, prefix="/tests", tags=["tests"])
api_router.include_router(maintenance.router, prefix="/maintenance", tags=["maintenance"])
api_router.include_router(rules.router, prefix="/validation-rules", tags=["validation-rules"])
