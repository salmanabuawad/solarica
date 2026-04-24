from __future__ import annotations

from pathlib import Path

from app.system_artifacts import ensure_system_json_cache
from app.utils import read_json


def _read_manifest_inputs(project_dir: Path) -> dict:
    mf = project_dir / "manifest.json"
    if not mf.exists():
        return {}
    try:
        data = read_json(mf)
    except Exception:
        return {}
    return data.get("inputs", {}) if isinstance(data, dict) else {}


def infer_ramming_pdf_path(project_dir: Path) -> str | None:
    # Preferred: project manifest (inputs used to generate core artifacts).
    inputs = _read_manifest_inputs(project_dir)
    ramming = inputs.get("ramming_pdf")
    if ramming and Path(ramming).exists():
        return str(ramming)

    # Fallback: if system_sources.json exists, use the stored path.
    src = project_dir / "system_cache" / "system_sources.json"
    if src.exists():
        try:
            data = read_json(src)
            p = (data.get("ramming_pdf") or {}).get("path") if isinstance(data, dict) else None
            if p and Path(p).exists():
                return str(p)
        except Exception:
            pass

    return None


def ensure_vector_piers_json(
    *,
    project_dir: Path,
    ramming_pdf_path: str,
    page_index: int = 0,
) -> Path:
    out = project_dir / "piers_vector_labeled.json"
    if out.exists():
        return out

    # Create the vector pier JSON only once; later queries use the JSON.
    from app.pier_scan import export_labeled_pier_json, extract_vector_labeled_piers

    result = extract_vector_labeled_piers(ramming_pdf_path, page_index=page_index)
    export_labeled_pier_json(str(out), result)
    return out


def ensure_system_cache(
    *,
    project_dir: Path,
    cache_dir: Path | None = None,
    legend_image_path: str | None = None,
    tesseract_exe: str | None = None,
    force: bool = False,
) -> dict:
    cache_dir = cache_dir or (project_dir / "system_cache")

    ramming_pdf = infer_ramming_pdf_path(project_dir)
    if not ramming_pdf:
        raise FileNotFoundError(
            "Could not infer ramming PDF path. Build the project artifacts with a manifest.json, "
            "or build the system cache once so system_sources.json exists."
        )

    # Use the ramming page index from summary.json if available, else 0.
    page_index = 0
    summary_path = project_dir / "summary.json"
    if summary_path.exists():
        try:
            summary = read_json(summary_path)
            page_index = int(summary.get("ramming_page_index_used", 0))
        except Exception:
            page_index = 0

    vector_json = ensure_vector_piers_json(project_dir=project_dir, ramming_pdf_path=ramming_pdf, page_index=page_index)

    rebuilt = ensure_system_json_cache(
        cache_dir=cache_dir,
        vector_json_path=str(vector_json),
        ramming_pdf_path=ramming_pdf,
        legend_image_path=legend_image_path,
        tesseract_exe=tesseract_exe,
        force=force,
    )
    return {
        "rebuilt": bool(rebuilt),
        "cache_dir": str(cache_dir),
        "vector_json": str(vector_json),
        "ramming_pdf": str(ramming_pdf),
        "page_index": int(page_index),
    }


def export_system_excel_from_cache(
    *,
    project_id: str,
    project_dir: Path,
    cache_dir: Path | None = None,
    out_path: Path | None = None,
) -> dict:
    """
    Create an xlsx under the project's artifacts folder, using the JSON cache only.
    """
    cache_dir = cache_dir or (project_dir / "system_cache")
    out_path = out_path or (project_dir / f"{project_id}_full_system.xlsx")

    from app.system_artifacts import export_excel_from_cache

    export_excel_from_cache(cache_dir=cache_dir, out_xlsx=out_path)
    return {
        "xlsx_path": str(out_path),
        "xlsx_filename": out_path.name,
    }

