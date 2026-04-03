from fastapi import HTTPException
from app.schemas.project import ProjectCreate

# Seed demo projects — always available after server restart
_SEED = [
    {"id": 1, "name": "Solar Farm Alpha",   "customer_name": "GreenEnergy SA",    "site_name": "Alentejo North",  "project_type": "utility",      "description": "100 MW utility-scale PV farm",           "phase": "implementation", "progress_percent": 62.0},
    {"id": 2, "name": "Rooftop Porto B2B",  "customer_name": "Logistics Hub Lda", "site_name": "Porto Industrial","project_type": "commercial",   "description": "Industrial rooftop, 450 kWp",             "phase": "commissioning",  "progress_percent": 88.0},
    {"id": 3, "name": "Rural Mini-Grid",    "customer_name": "Cooperativa Sol",   "site_name": "Évora Rural",     "project_type": "mini-grid",    "description": "Off-grid community solar + storage",      "phase": "testing",        "progress_percent": 75.0},
    {"id": 4, "name": "Hospital Canopy",    "customer_name": "NHS Regional",      "site_name": "Lisbon Central",  "project_type": "commercial",   "description": "Carport canopy + EV charging 120 kWp",    "phase": "design",         "progress_percent": 15.0},
    {"id": 5, "name": "Agrivoltaic Demo",   "customer_name": "AgriSun Coop",      "site_name": "Beja Fields",     "project_type": "agrivoltaic",  "description": "Dual-use solar + crops pilot 2 MWp",      "phase": "validation",     "progress_percent": 38.0},
]


class ProjectService:
    def __init__(self):
        self._items = [dict(s) for s in _SEED]
        self._id = len(_SEED) + 1

    def _find(self, project_id: int):
        item = next((x for x in self._items if x["id"] == project_id), None)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
        return item

    def create(self, payload: ProjectCreate):
        item = payload.model_dump()
        item.update({"id": self._id, "phase": "design", "progress_percent": 0.0})
        self._items.append(item)
        self._id += 1
        return item

    def list_all(self):
        return self._items

    def get(self, project_id: int):
        return self._find(project_id)

    def update_phase(self, project_id: int, phase: str):
        item = self._find(project_id)
        item["phase"] = phase
        return item

    def validate_design(self, project_id: int):
        self._find(project_id)          # confirm exists — raises 404 if not
        return {
            "status": "warning",
            "issues": [
                {
                    "severity": "warning",
                    "asset_type": "string",
                    "asset_ref": "S.2.7.4",
                    "issue_type": "missing_sequence",
                    "message": "Detected possible missing sequence before S.2.7.4",
                }
            ],
        }
