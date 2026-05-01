from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import PROJECTS_ROOT
from app.services import db_store


def attach_map_source_image_url(project_id: str, project_uuid: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Attach a public PNG render URL to a string-optimizer map_source.

    The frontend needs the actual drawing page as the map substrate. We render
    the authoritative PDF page once into the project artifacts folder and serve
    it through a public API route. Production nginx only proxies /api/* to the
    backend, so returning /projects/* would fall through to the frontend shell.
    """
    map_source = payload.get("map_source") or {}
    if not isinstance(map_source, dict):
        return payload

    source_file = str(map_source.get("source_file") or "")
    page_no = int(map_source.get("page") or 1)
    if not source_file:
        return payload

    files = db_store.list_project_files(project_uuid)
    match = None
    for f in files:
        storage = str(f.get("storage_path") or "")
        if f.get("filename") == source_file or Path(storage).name == source_file:
            match = f
            break
    if not match:
        return payload

    pdf_path = Path(str(match.get("storage_path") or ""))
    if not pdf_path.exists() or pdf_path.suffix.lower() != ".pdf":
        return payload

    render_dir = PROJECTS_ROOT / project_id / "map_source"
    render_dir.mkdir(parents=True, exist_ok=True)
    safe_stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in pdf_path.stem)
    out_path = render_dir / f"{safe_stem}_p{page_no:03d}.png"

    try:
        if not out_path.exists() or out_path.stat().st_mtime < pdf_path.stat().st_mtime:
            import fitz  # PyMuPDF

            with fitz.open(str(pdf_path)) as doc:
                page = doc.load_page(max(0, min(page_no - 1, len(doc) - 1)))
                zoom = 2.0
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                pix.save(str(out_path))
                map_source["image_width_px"] = pix.width
                map_source["image_height_px"] = pix.height
        map_source["image_url"] = f"/api/public/projects/{project_id}/map-source-image/{out_path.stem}"
    except Exception as exc:
        map_source["image_error"] = str(exc)

    payload["map_source"] = map_source
    return payload
