"""Solarica BHK Base Map Extraction Engine.

Phase 1 — PDF layer analysis & semantic classification.

The BHK CAD exports are fully vector with named optional-content / layer
groups (PyMuPDF exposes the layer name on each drawing path). This module
inspects those layers WITHOUT flattening, preserves the original layer
names, summarises the per-layer vector geometry, and classifies each layer
into a semantic category used to build the physical base map.

Phase 2 (physical base map: Site -> Rows -> Trackers -> Piers -> Panels)
lives in build_base_map().
"""
from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None


# Ordered keyword -> semantic-layer rules. First match wins; matched against
# the upper-cased CAD layer name. Order matters (specific before generic).
_LAYER_RULES: list[tuple[str, str]] = [
    ("EN-PANEL", "panels"),
    ("CCTV", "security"),
    ("CAMERA", "security"),
    ("SECURIT", "security"),
    ("PANEL", "panels"),
    ("S-PLAN-PIER", "piers"),
    ("PIER", "piers"),
    ("TRACKER", "trackers"),
    ("BE-STRING", "strings"),
    ("STRING", "strings"),
    ("OPTIM", "optimizers"),
    ("VERTICAL GRID", "physical_rows"),
    ("TRENCH", "dc_cables"),
    ("INV", "ac_cables"),
    ("MV", "mv_cables"),
    ("DC", "dc_cables"),
    ("CABLE", "dc_cables"),
    ("GROUND", "grounding"),
    ("EARTH", "grounding"),
    ("COMM", "communication"),
    ("SCADA", "communication"),
    ("FIBER", "communication"),
    ("WS", "weather"),
    ("WEATHER", "weather"),
    ("CCTV", "security"),
    ("CAMERA", "security"),
    ("SECURIT", "security"),
    ("FENCE", "boundaries"),
    ("BORDER", "boundaries"),
    ("BOUNDAR", "boundaries"),
    ("SITE", "boundaries"),
    ("TOPO", "terrain"),
    ("CONT", "terrain"),
    ("ROAD", "terrain"),
    ("GRAVEL", "terrain"),
    ("TREE", "terrain"),
    ("HYD", "terrain"),
    ("AGRO", "terrain"),
    ("DIM", "text_labels"),
    ("TXT", "text_labels"),
    ("TEXT", "text_labels"),
    ("LABEL", "text_labels"),
    ("ANNO", "text_labels"),
    ("LOGO", "text_labels"),
    ("INFO", "text_labels"),
]


def classify_layer(layer_name: str) -> tuple[str, str]:
    """Map a CAD layer name to (semantic_layer, confidence)."""
    if not layer_name:
        return "unclassified", "low"
    name = layer_name.upper()
    for kw, sem in _LAYER_RULES:
        if kw in name:
            return sem, "high"
    return "unclassified", "low"


def _rgb(color):
    if not color or len(color) < 3:
        return None
    return tuple(round(float(c), 3) for c in color[:3])


def analyze_pdf_layers(pdf_path: str | Path) -> dict[str, Any]:
    """Phase 1: per-layer vector summary + semantic classification.

    Returns a dict with status, the OCG names declared in the PDF, and a
    list of per-layer records (preserving original names).
    """
    path = Path(pdf_path)
    if fitz is None:
        return {"source_file": path.name, "status": "pymupdf_unavailable", "layers": []}
    if not path.exists():
        return {"source_file": path.name, "status": "file_not_found", "layers": []}
    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        return {"source_file": path.name, "status": "open_failed", "reason": str(exc), "layers": []}

    # Declared optional-content groups (named CAD layers), if any.
    try:
        ocgs = doc.get_ocgs() or {}
        ocg_names = sorted({str(v.get("name")) for v in ocgs.values() if v.get("name")})
    except Exception:
        ocg_names = []

    page = doc[0]
    page_rect = page.rect
    drawings = page.get_drawings()

    # Aggregate geometry per layer name.
    agg: dict[str, dict[str, Any]] = {}
    for d in drawings:
        layer = str(d.get("layer") or "(no layer)")
        rec = agg.setdefault(layer, {
            "paths": 0, "lines": 0, "curves": 0, "rects": 0,
            "colors": Counter(), "bbox": [math.inf, math.inf, -math.inf, -math.inf],
        })
        rec["paths"] += 1
        items = d.get("items") or []
        rec["lines"] += sum(1 for it in items if it[0] == "l")
        rec["curves"] += sum(1 for it in items if it[0] == "c")
        rec["rects"] += sum(1 for it in items if it[0] in ("re", "qu"))
        c = _rgb(d.get("color")) or _rgb(d.get("fill"))
        if c is not None:
            rec["colors"][c] += 1
        r = d.get("rect")
        if r:
            bb = rec["bbox"]
            bb[0] = min(bb[0], r.x0); bb[1] = min(bb[1], r.y0)
            bb[2] = max(bb[2], r.x1); bb[3] = max(bb[3], r.y1)

    flattened = len(drawings) == 0

    layers: list[dict[str, Any]] = []
    for name, rec in sorted(agg.items(), key=lambda kv: -kv[1]["paths"]):
        sem, conf = classify_layer(name)
        bb = rec["bbox"]
        bbox = None if bb[0] == math.inf else [round(v, 1) for v in bb]
        layers.append({
            "source_file": path.name,
            "page": 1,
            "pdf_layer": name,
            "semantic_layer": sem,
            "confidence": conf,
            "geometry": {
                "paths": rec["paths"],
                "line_segments": rec["lines"],
                "curve_segments": rec["curves"],
                "rect_fills": rec["rects"],
                "bbox": bbox,
                "dominant_colors": [list(c) for c, _ in rec["colors"].most_common(3)],
            },
        })

    doc.close()
    return {
        "source_file": path.name,
        "status": "flattened_no_vector_layers" if flattened else "ok",
        "page_size": [round(page_rect.width, 1), round(page_rect.height, 1)],
        "declared_ocgs": ocg_names,
        "drawing_paths_total": len(drawings),
        "layer_count": len(layers),
        "layers": layers,
    }


# Files expected by the spec; used to emit warnings for missing inputs.
EXPECTED_BHK_FILES = {
    "E_10": "color map / overview",
    "E_11.1": "AGRO-PV structural context",
    "E_20": "electrical cable plan (electrical overlay, later)",
    "E_30": "communication plan",
    "E_40": "cable trench plan",
    "E_41": "panels plan (PRIMARY physical base map)",
    "E_50": "grounding layout plan",
}


def _file_code(name: str) -> str | None:
    m = re.search(r"E_(\d+(?:\.\d+)?)", name)
    return f"E_{m.group(1)}" if m else None


def analyze_layers_across_files(pdf_paths: list[str | Path]) -> dict[str, Any]:
    """Phase 1 over a set of BHK PDFs, with input-completeness warnings."""
    reports = [analyze_pdf_layers(p) for p in pdf_paths]
    present_codes = {c for c in (_file_code(Path(p).name) for p in pdf_paths) if c}
    warnings: list[dict[str, str]] = []
    for code, purpose in EXPECTED_BHK_FILES.items():
        if code not in present_codes:
            warnings.append({"code": "missing_input_file", "detail": f"{code} ({purpose}) not provided", "severity": "warning"})
    for r in reports:
        if r["status"] == "flattened_no_vector_layers":
            warnings.append({"code": "pdf_layers_not_accessible", "detail": f"{r['source_file']} has no vector layers (flattened) - CV fallback required", "severity": "error"})
    return {"files": reports, "warnings": warnings}


# ----------------------------------------------------------------------------
# Phase 2 — physical base map: Site -> Rows -> Trackers -> Piers -> Panels
# ----------------------------------------------------------------------------

def _axis(row):
    return (float(row["south_x"]), float(row["south_y"]), float(row["north_x"]), float(row["north_y"]))


def _project_t_dist(pt, row):
    """Parametric position (0=south,1=north) and perpendicular distance of a
    point relative to a row's south->north axis."""
    sx, sy, nx, ny = _axis(row)
    dx, dy = nx - sx, ny - sy
    denom = dx * dx + dy * dy or 1.0
    t = ((pt[0] - sx) * dx + (pt[1] - sy) * dy) / denom
    qx, qy = sx + dx * t, sy + dy * t
    return t, math.hypot(pt[0] - qx, pt[1] - qy)


def _assign_to_row(pt, rows, max_perp=14.0):
    best = None
    for idx, row in enumerate(rows):
        t, d = _project_t_dist(pt, row)
        if -0.1 <= t <= 1.1 and (best is None or d < best[1]):
            best = (idx, d, t)
    if best and best[1] <= max_perp:
        return best[0], best[2]
    return None, None


def build_base_map(pdf_paths: list[str | Path]) -> dict[str, Any]:
    """Reconstruct the physical base map from the E_41 panels plan.

    Hierarchy: Site -> physical rows -> trackers -> piers -> panels.
    Rows are numbered south->north (ROW_001 = south = largest PDF-Y). Panels
    and piers are numbered from the south end of each row. Trackers are
    attached to their nearest row.
    """
    from .string_optimizer_parser import _extract_panel_map_geometry, _is_panels_plan
    from .bhk_topology import load_piers

    warnings: list[dict[str, str]] = []
    panel_paths = [p for p in pdf_paths if _is_panels_plan(p)]
    if not panel_paths:
        return {"status": "missing_panels_plan", "warnings": [{"code": "missing_panels_plan", "detail": "E_41 panels plan not provided", "severity": "error"}]}
    e41 = panel_paths[0]

    geo = _extract_panel_map_geometry([e41])
    rows_raw = geo.get("panel_rows") or []
    if not rows_raw:
        return {"status": "no_rows", "warnings": [{"code": "no_physical_rows", "detail": "BE-Vertical Grid produced no rows", "severity": "error"}]}
    n_rows = len(rows_raw)

    # Orientation: no north-arrow auto-detection available, so we apply the
    # confirmed site convention (south = bottom = largest PDF-Y) and warn.
    warnings.append({
        "code": "orientation_assumed",
        "detail": "South-origin set by site convention (south = largest PDF-Y / bottom of sheet); not auto-detected from a north arrow.",
        "severity": "warning",
    })

    def south_num(internal_idx):  # 0-based internal -> south-origin row number
        return n_rows - internal_idx

    # Piers come from E_41 (S-PLAN-PIER). Tracker-N labels are drawn on the
    # electrical plan rather than E_41, so scan every provided file (all share
    # one coordinate frame) and dedupe by tracker id.
    piers_xy: list[tuple[float, float]] = []
    tracker_labels: list[dict[str, Any]] = []
    if fitz is not None:
        try:
            doc = fitz.open(str(e41))
            piers_xy = load_piers(doc[0])
            doc.close()
        except Exception as exc:
            warnings.append({"code": "pier_extract_failed", "detail": str(exc), "severity": "warning"})
        seen_trackers: set[int] = set()
        for src in [e41] + [p for p in pdf_paths if str(p) != str(e41)]:
            try:
                doc = fitz.open(str(src))
                for w in doc[0].get_text("words") or []:
                    m = re.fullmatch(r"Tracker[-\s]?(\d+)", str(w[4]).strip(), re.IGNORECASE)
                    if m:
                        num = int(m.group(1))
                        if num in seen_trackers:
                            continue
                        seen_trackers.add(num)
                        tracker_labels.append({"id": f"Tracker-{num}", "num": num,
                                               "x": (float(w[0]) + float(w[2])) / 2, "y": (float(w[1]) + float(w[3])) / 2})
                doc.close()
            except Exception:
                continue

    if not piers_xy:
        warnings.append({"code": "no_piers", "detail": "No piers extracted from S-PLAN-PIER", "severity": "warning"})
    if not tracker_labels:
        warnings.append({"code": "no_tracker_labels", "detail": "No Tracker-N labels found on E_41; tracker layer omitted", "severity": "warning"})

    # Bucket piers and trackers onto rows.
    piers_by_row: dict[int, list[tuple[float, float, float]]] = {}
    for p in piers_xy:
        idx, t = _assign_to_row(p, rows_raw)
        if idx is not None:
            piers_by_row.setdefault(idx, []).append((t, p[0], p[1]))
    trackers_by_row: dict[int, list[dict[str, Any]]] = {}
    for tl in tracker_labels:
        idx, t = _assign_to_row((tl["x"], tl["y"]), rows_raw, max_perp=40.0)
        if idx is not None:
            trackers_by_row.setdefault(idx, []).append({**tl, "t": t})

    rows_out: list[dict[str, Any]] = []
    panels_total = piers_total = trackers_total = 0
    for idx, row in enumerate(rows_raw):
        rn = south_num(idx)
        row_id = f"ROW_{rn:03d}"
        sx, sy, nx, ny = _axis(row)
        length = math.hypot(nx - sx, ny - sy)
        # Panels: already numbered south->north by the panel extractor.
        panels = sorted(row.get("panels") or [], key=lambda p: float(p.get("t", 0)))
        panel_recs = [{
            "panel_id": f"{row_id}-P{p['panel']:03d}", "panel_number": int(p["panel"]),
            "cx": p["cx"], "cy": p["cy"], "t": round(float(p["t"]), 4),
        } for p in panels]
        # Piers: south-origin numbering within the row.
        prs = sorted(piers_by_row.get(idx, []), key=lambda r: r[0])
        pier_recs = [{
            "pier_id": f"{row_id}-PIER{i+1:03d}", "pier_number": i + 1,
            "x": round(x, 2), "y": round(y, 2), "t": round(t, 4),
        } for i, (t, x, y) in enumerate(prs)]
        # Trackers attached to this row, ordered south->north.
        trs = sorted(trackers_by_row.get(idx, []), key=lambda d: d["t"])
        tracker_recs = [{"tracker_id": tl["id"], "tracker_number": tl["num"], "t": round(tl["t"], 4)} for tl in trs]

        panels_total += len(panel_recs)
        piers_total += len(pier_recs)
        trackers_total += len(tracker_recs)
        rows_out.append({
            "row_id": row_id,
            "row_number": rn,
            "geometry_polyline": [[round(sx, 2), round(sy, 2)], [round(nx, 2), round(ny, 2)]],
            "south_point": [round(sx, 2), round(sy, 2)],
            "north_point": [round(nx, 2), round(ny, 2)],
            "length": round(length, 2),
            "panel_count": len(panel_recs),
            "pier_count": len(pier_recs),
            "tracker_count": len(tracker_recs),
            "panels": panel_recs,
            "piers": pier_recs,
            "trackers": tracker_recs,
            "confidence": "high" if panel_recs else "low",
        })

    rows_out.sort(key=lambda r: r["row_number"])
    return {
        "status": "ok",
        "site": {
            "name": "BHK (Beit HaEmek)",
            "source_file": Path(e41).name,
            "coordinate_frame": "pdf_points",
            "page_size": geo.get("panel_rows") and [rows_raw[0].get("page_width"), rows_raw[0].get("page_height")],
            "panel_numbering": "south_to_north",
            "row_numbering": "south_to_north (ROW_001 = south)",
        },
        "summary": {
            "physical_rows": len(rows_out),
            "panels": panels_total,
            "piers": piers_total,
            "trackers": trackers_total,
        },
        "rows": rows_out,
        "warnings": warnings,
    }
