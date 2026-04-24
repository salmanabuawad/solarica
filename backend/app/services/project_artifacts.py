from __future__ import annotations

import datetime as _dt
from pathlib import Path

from app.parser import run_pipeline
from app.site_profiles import load_site_profile
from app.utils import read_json, save_json


CORE_ARTIFACT_FILES = (
    "summary.json",
    "blocks.json",
    "trackers.json",
    "piers.json",
    "zoom_targets.json",
    "drawing_bundles.json",
)


def manifest_path(project_dir: Path) -> Path:
    return project_dir / "manifest.json"


def write_manifest(
    project_dir: Path,
    *,
    project_id: str,
    construction_pdf: str,
    ramming_pdf: str,
    overlay_image: str,
    site_profile: str = "auto",
    profile_config: str | None = None,
) -> Path:
    project_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "project_id": project_id,
        "created_at": _dt.datetime.now(tz=_dt.timezone.utc).isoformat(),
        "inputs": {
            "construction_pdf": str(construction_pdf),
            "ramming_pdf": str(ramming_pdf),
            "overlay_image": str(overlay_image),
        },
        "profile": {
            "site_profile": str(site_profile),
            "profile_config": str(profile_config) if profile_config else "",
        },
    }
    out = manifest_path(project_dir)
    save_json(out, payload)
    return out


def load_manifest(project_dir: Path) -> dict:
    return read_json(manifest_path(project_dir))


def artifacts_missing(project_dir: Path, required_files=CORE_ARTIFACT_FILES) -> list[str]:
    missing = []
    for name in required_files:
        if not (project_dir / name).exists():
            missing.append(name)
    return missing


def build_project_from_manifest(project_dir: Path) -> dict:
    """
    (Re)build core JSON artifacts into `project_dir` using `manifest.json`.
    This is intentionally deterministic: it always regenerates all core artifacts.
    """
    mf = load_manifest(project_dir)
    inputs = mf.get("inputs", {})
    profile_info = mf.get("profile", {})

    construction_pdf = inputs.get("construction_pdf")
    ramming_pdf = inputs.get("ramming_pdf")
    overlay_image = inputs.get("overlay_image")
    if not (construction_pdf and ramming_pdf and overlay_image):
        raise RuntimeError("manifest.json is missing required input paths (construction_pdf, ramming_pdf, overlay_image)")

    profile = load_site_profile(
        profile_name=profile_info.get("site_profile") or "auto",
        input_paths=[construction_pdf, ramming_pdf, overlay_image],
        config_path=(profile_info.get("profile_config") or None),
    )
    return run_pipeline(construction_pdf, ramming_pdf, overlay_image, str(project_dir), profile)


def ensure_project_artifacts(project_dir: Path, *, required_files=CORE_ARTIFACT_FILES) -> bool:
    """
    Ensure required JSON artifacts exist.

    Returns True if a rebuild was performed, False if everything was already present.
    """
    missing = artifacts_missing(project_dir, required_files=required_files)
    if not missing:
        return False

    mf = manifest_path(project_dir)
    if not mf.exists():
        raise FileNotFoundError(
            f"Missing artifacts ({', '.join(missing)}) and no manifest.json present to rebuild."
        )

    build_project_from_manifest(project_dir)
    return True

