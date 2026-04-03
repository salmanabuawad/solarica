from fastapi import HTTPException
from datetime import datetime, timedelta, UTC
from app.schemas.inventory import MaterialCreate, MaterialIssueCreate

# Seed demo materials
_SEED_MATERIALS = [
    {"id": 1, "name": "PV Module 400W",        "category": "module",    "unit": "pcs", "sku": "MOD-400W",   "min_threshold": 50,  "unit_cost": 180.00},
    {"id": 2, "name": "String Inverter 25kW",  "category": "inverter",  "unit": "pcs", "sku": "INV-25KW",   "min_threshold": 2,   "unit_cost": 3200.00},
    {"id": 3, "name": "DC Cable 6mm²",         "category": "cable",     "unit": "m",   "sku": "CBL-DC6",    "min_threshold": 200, "unit_cost": 1.40},
    {"id": 4, "name": "AC Cable 16mm²",        "category": "cable",     "unit": "m",   "sku": "CBL-AC16",   "min_threshold": 100, "unit_cost": 3.20},
    {"id": 5, "name": "Mounting Rail 4.4m",    "category": "mounting",  "unit": "pcs", "sku": "MNT-RAIL44", "min_threshold": 20,  "unit_cost": 22.50},
    {"id": 6, "name": "DC Combiner Box 8-in",  "category": "electrical","unit": "pcs", "sku": "COM-DC8",    "min_threshold": 5,   "unit_cost": 420.00},
    {"id": 7, "name": "Earthing Cable 16mm²",  "category": "cable",     "unit": "m",   "sku": "CBL-GND16",  "min_threshold": 50,  "unit_cost": 2.10},
    {"id": 8, "name": "MC4 Connector pair",    "category": "connector", "unit": "pcs", "sku": "CON-MC4",    "min_threshold": 100, "unit_cost": 1.20},
]


class InventoryService:
    def __init__(self):
        self._materials = [dict(m) for m in _SEED_MATERIALS]
        self._issues = []
        self._material_id = len(_SEED_MATERIALS) + 1
        self._issue_id = 1

    def _find_material(self, material_id: int):
        item = next((m for m in self._materials if m["id"] == material_id), None)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Material {material_id} not found")
        return item

    def create_material(self, payload: MaterialCreate):
        item = payload.model_dump()
        item["id"] = self._material_id
        self._material_id += 1
        self._materials.append(item)
        return item

    def list_materials(self):
        return self._materials

    def issue_material(self, payload: MaterialIssueCreate):
        item = payload.model_dump()
        item["id"] = self._issue_id
        item["status"] = "issued"
        item["issued_at"] = datetime.now(UTC).isoformat()
        item["expected_usage_by_date"] = (datetime.now(UTC) + timedelta(days=payload.expected_usage_days)).isoformat()
        item["red_flags"] = []
        self._issue_id += 1
        self._issues.append(item)
        return item

    def list_issues(self):
        return self._issues

    def run_red_flags(self):
        now = datetime.now(UTC)
        created = []
        for issue in self._issues:
            expected = datetime.fromisoformat(issue["expected_usage_by_date"])
            total_consumed = sum(x.get("quantity_consumed", 0) for x in issue["items"])
            if now > expected and total_consumed <= 0:
                flag = {
                    "rule_type": "no_usage",
                    "severity": "high",
                    "description": "Material issued but no consumption reflected within expected usage window.",
                    "created_at": now.isoformat(),
                }
                issue["red_flags"].append(flag)
                issue["status"] = "flagged"
                created.append({"issue_id": issue["id"], "flag": flag})
        return {"created_flags": created}
