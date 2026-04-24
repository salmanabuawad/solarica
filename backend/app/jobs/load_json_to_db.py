"""
One-shot migration: load an existing project's JSON artifacts into the database.

Usage:
    python -m app.jobs.load_json_to_db <project_id>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.config import PROJECTS_ROOT
from app.services import db_store


def _read_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_project(project_id: str) -> None:
    proj_dir = PROJECTS_ROOT / project_id
    if not proj_dir.exists():
        raise FileNotFoundError(f"No project directory at {proj_dir}")

    summary = _read_json(proj_dir / "summary.json") or {}
    blocks = _read_json(proj_dir / "blocks.json") or []
    trackers = _read_json(proj_dir / "trackers.json") or []
    piers = _read_json(proj_dir / "piers.json") or []
    drawing_bundles = _read_json(proj_dir / "drawing_bundles.json") or {}
    zoom_targets = _read_json(proj_dir / "zoom_targets.json") or {}
    plant_info_path = proj_dir / "plant_info.json"
    plant_info = _read_json(plant_info_path) or {}
    pier_statuses = _read_json(proj_dir / "pier_statuses.json") or {}

    site_profile = summary.get("site_profile")

    print(f"[{project_id}] upserting project...")
    uu = db_store.upsert_project(project_id, name=project_id, site_profile=site_profile, status="ready")
    print(f"[{project_id}] uuid={uu}")

    print(f"[{project_id}] clearing old artifacts...")
    db_store.delete_project_artifacts(uu)

    print(f"[{project_id}] loading {len(blocks)} blocks...")
    db_store.insert_blocks(uu, blocks)

    print(f"[{project_id}] loading {len(trackers)} trackers...")
    db_store.insert_trackers(uu, trackers)

    print(f"[{project_id}] loading {len(piers)} piers...")
    db_store.insert_piers(uu, piers)

    print(f"[{project_id}] loading drawing_bundles ({len(drawing_bundles)}) / zoom_targets ({len(zoom_targets)})...")
    db_store.set_drawing_bundles(uu, drawing_bundles)
    db_store.set_zoom_targets(uu, zoom_targets)

    print(f"[{project_id}] saving metadata (summary + plant_info)...")
    db_store.set_project_metadata(uu, summary, plant_info)

    if pier_statuses:
        print(f"[{project_id}] loading {len(pier_statuses)} pier statuses...")
        for pier_code, status in pier_statuses.items():
            try:
                db_store.set_pier_status(uu, pier_code, status)
            except Exception as e:
                print(f"  skip {pier_code}: {e}")

    print(f"[{project_id}] done.")


def main():
    if len(sys.argv) < 2:
        print("usage: python -m app.jobs.load_json_to_db <project_id>", file=sys.stderr)
        sys.exit(1)
    for pid in sys.argv[1:]:
        load_project(pid)


if __name__ == "__main__":
    main()
