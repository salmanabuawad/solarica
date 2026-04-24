from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import fitz
import numpy as np
import pandas as pd

from app.utils import read_json, save_json


PIER_LEGEND_LINE_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<code>[A-Z0-9]+)\)\s*(?P<rest>.*)$")


SYSTEM_CACHE_FILES = {
    "sources": "system_sources.json",
    "meta": "system_meta.json",
    "blocks": "system_blocks.json",
    "trackers": "system_trackers.json",
    "piers": "system_piers.json",
    "pier_type_legend": "system_pier_type_legend.json",
    "pier_type_counts": "system_pier_type_counts.json",
}


def _word_center(word):
    return (float(word[0] + word[2]) / 2.0, float(word[1] + word[3]) / 2.0)


def _parse_row_trk_anchors(words):
    anchors = []
    for idx, w in enumerate(words):
        if str(w[4]).upper() != "ROW:":
            continue

        # Typical pattern around the box:
        # ROW:, TRK:, <row_number>, <trk_number>
        window = words[idx : min(idx + 12, len(words))]
        trk_idx = None
        for j, ww in enumerate(window[1:], start=1):
            if str(ww[4]).upper() == "TRK:":
                trk_idx = j
                break
        if trk_idx is None:
            continue

        row_value = str(window[trk_idx + 1][4]) if trk_idx + 1 < len(window) else ""
        trk_value = str(window[trk_idx + 2][4]) if trk_idx + 2 < len(window) else ""

        cx, cy = _word_center(w)
        anchors.append({
            "row": row_value,
            "tracker": trk_value,
            "x": cx,
            "y": cy,
        })
    return anchors


def _parse_block_labels(words):
    blocks = []
    for w in words:
        txt = str(w[4])
        m = re.search(r"BLOCK[^0-9]*(\d+)", txt.upper())
        if not m:
            continue
        cx, cy = _word_center(w)
        blocks.append({
            "block": m.group(1),
            "x": cx,
            "y": cy,
        })
    return blocks


def _grid_index(points, cell_size):
    grid = {}
    for idx, (x, y) in enumerate(points):
        gx = int(np.floor(float(x) / float(cell_size)))
        gy = int(np.floor(float(y) / float(cell_size)))
        grid.setdefault((gx, gy), []).append(idx)
    return grid


def _nearest_by_grid(points, grid, cell_size, qx, qy, max_rings=2):
    gx = int(np.floor(float(qx) / float(cell_size)))
    gy = int(np.floor(float(qy) / float(cell_size)))
    best = None
    best_d2 = float("inf")
    for ring in range(0, max_rings + 1):
        for dx in range(-ring, ring + 1):
            for dy in range(-ring, ring + 1):
                idxs = grid.get((gx + dx, gy + dy))
                if not idxs:
                    continue
                for idx in idxs:
                    px, py = points[idx]
                    d2 = (px - qx) ** 2 + (py - qy) ** 2
                    if d2 < best_d2:
                        best_d2 = d2
                        best = idx
        if best is not None and best_d2 <= (cell_size * 0.6) ** 2:
            break
    return best, best_d2


def _estimate_axis(p1_points, p2_points):
    # Find a near P2 per P1 using a grid, then average the vector.
    cell_size = 25.0
    grid = _grid_index(p2_points, cell_size)
    vectors = []
    distances = []
    for x1, y1 in p1_points:
        idx, _ = _nearest_by_grid(p2_points, grid, cell_size, x1, y1, max_rings=2)
        if idx is None:
            continue
        x2, y2 = p2_points[idx]
        dx = x2 - x1
        dy = y2 - y1
        dist = float(np.hypot(dx, dy))
        if dist < 5.0 or dist > 30.0:
            continue
        vectors.append((dx, dy))
        distances.append(dist)
    if not vectors:
        # Fallback: assume horizontal spacing.
        return (1.0, 0.0), 10.0
    mean_dx = float(np.mean([v[0] for v in vectors]))
    mean_dy = float(np.mean([v[1] for v in vectors]))
    norm = float(np.hypot(mean_dx, mean_dy)) or 1.0
    u = (mean_dx / norm, mean_dy / norm)
    return u, float(np.mean(distances))


def build_system_tables(vector_json_path: str, ramming_pdf_path: str):
    vector_obj = json.loads(Path(vector_json_path).read_text(encoding="utf-8"))
    piers = vector_obj["piers"]

    # Build P1 and P2 point lists for axis estimation.
    p1_points = [(float(p["x"]), float(p["y"])) for p in piers if str(p.get("label", "")).upper() == "P1"]
    p2_points = [(float(p["x"]), float(p["y"])) for p in piers if str(p.get("label", "")).upper() == "P2"]
    axis_u, step = _estimate_axis(p1_points, p2_points)
    axis_v = (-axis_u[1], axis_u[0])

    # Parse anchors and blocks from the ramming PDF text layer.
    pdf = fitz.open(ramming_pdf_path)
    try:
        page = pdf.load_page(0)
        words = page.get_text("words")
    finally:
        pdf.close()
    anchors = _parse_row_trk_anchors(words)
    blocks = _parse_block_labels(words)

    # Map each anchor to a unique nearest P1.
    p1_grid = _grid_index(p1_points, cell_size=25.0)
    anchor_to_p1 = {}
    used_p1 = set()
    for a_idx, a in enumerate(anchors):
        idx, _ = _nearest_by_grid(p1_points, p1_grid, 25.0, a["x"], a["y"], max_rings=2)
        if idx is None:
            continue
        if idx in used_p1:
            idx2, _ = _nearest_by_grid(p1_points, p1_grid, 25.0, a["x"], a["y"], max_rings=4)
            if idx2 is not None and idx2 not in used_p1:
                idx = idx2
        used_p1.add(idx)
        anchor_to_p1[a_idx] = idx

    # Map anchor -> nearest block label.
    block_points = [(b["x"], b["y"]) for b in blocks] if blocks else []
    block_grid = _grid_index(block_points, cell_size=250.0) if block_points else {}
    anchor_block = {}
    for a_idx, a in enumerate(anchors):
        if not block_points:
            anchor_block[a_idx] = ""
            continue
        b_idx, _ = _nearest_by_grid(block_points, block_grid, 250.0, a["x"], a["y"], max_rings=3)
        anchor_block[a_idx] = blocks[b_idx]["block"] if b_idx is not None else ""

    # Build P1->anchor reverse mapping.
    p1_to_anchor = {p1_idx: a_idx for a_idx, p1_idx in anchor_to_p1.items()}

    expected_offset = {f"P{k}": (k - 1) * step for k in range(1, 20)}

    pier_rows = []
    for i, p in enumerate(piers, start=1):
        label = str(p.get("label", "")).upper()
        x = float(p["x"])
        y = float(p["y"])
        pier_type = str(p.get("pier_type", "")).upper() if p.get("pier_type") is not None else ""
        off = expected_offset.get(label, 0.0)

        px = x - axis_u[0] * off
        py = y - axis_u[1] * off
        p1_idx, _ = _nearest_by_grid(p1_points, p1_grid, 25.0, px, py, max_rings=3)
        a_idx = p1_to_anchor.get(p1_idx) if p1_idx is not None else None
        if a_idx is None:
            # Fallback: choose closest anchor by Euclidean distance to predicted P1.
            best = None
            best_d2 = float("inf")
            for j, a in enumerate(anchors):
                dd2 = (a["x"] - px) ** 2 + (a["y"] - py) ** 2
                if dd2 < best_d2:
                    best_d2 = dd2
                    best = j
            a_idx = best

        row = anchors[a_idx]["row"] if a_idx is not None else ""
        tracker = anchors[a_idx]["tracker"] if a_idx is not None else ""
        block = anchor_block.get(a_idx, "") if a_idx is not None else ""

        if p1_idx is not None and p1_idx < len(p1_points):
            x1, y1 = p1_points[p1_idx]
            dx = x - x1
            dy = y - y1
            along = dx * axis_u[0] + dy * axis_u[1]
            perp = dx * axis_v[0] + dy * axis_v[1]
        else:
            along = None
            perp = None

        x_rel = p.get("x_rel")
        y_rel = p.get("y_rel")
        pier_rows.append({
            "pier_id": f"VP{i:05d}",
            "block": block,
            "row": row,
            "tracker": tracker,
            "pier_label": label,
            "pier_type": pier_type,
            "x": x,
            "y": y,
            "x_rel": float(x_rel) if x_rel is not None else None,
            "y_rel": float(y_rel) if y_rel is not None else None,
            "axis_along": along,
            "axis_perp": perp,
        })

    piers_df = pd.DataFrame(pier_rows)
    tracker_summary = (
        piers_df
        .groupby(["block", "row", "tracker"], dropna=False)["pier_type"]
        .value_counts()
        .unstack(fill_value=0)
        .reset_index()
    )
    tracker_summary["total_piers"] = (
        tracker_summary.drop(columns=["block", "row", "tracker"]).sum(axis=1)
    )
    cols = ["block", "row", "tracker", "total_piers"] + [
        c for c in tracker_summary.columns if c not in {"block", "row", "tracker", "total_piers"}
    ]
    tracker_summary = tracker_summary[cols]

    block_summary = (
        piers_df
        .groupby(["block"], dropna=False)["pier_type"]
        .value_counts()
        .unstack(fill_value=0)
        .reset_index()
    )
    block_summary["total_piers"] = block_summary.drop(columns=["block"]).sum(axis=1)
    cols = ["block", "total_piers"] + [c for c in block_summary.columns if c not in {"block", "total_piers"}]
    block_summary = block_summary[cols]

    meta = {
        "vector_json": str(vector_json_path),
        "ramming_pdf": str(ramming_pdf_path),
        "pier_count": int(len(piers_df)),
        "axis_u_x": float(axis_u[0]),
        "axis_u_y": float(axis_u[1]),
        "p_step_mean": float(step),
        "anchor_count": int(len(anchors)),
        "block_label_count": int(len(blocks)),
    }
    meta_df = pd.DataFrame([meta])
    return meta_df, block_summary, tracker_summary, piers_df


def _find_tesseract_exe(explicit=None):
    if explicit:
        p = Path(explicit)
        return str(p) if p.exists() else None

    env = (Path(shutil.which("tesseract") or "") if shutil.which("tesseract") else None)
    if env and env.exists():
        return str(env)

    cand = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if cand.exists():
        return str(cand)

    return None


def _ocr_text_from_image(image_path, tesseract_exe=None, psm=6, lang="eng"):
    exe = _find_tesseract_exe(tesseract_exe)
    if not exe:
        raise RuntimeError("Tesseract not found. Install it or pass a tesseract.exe path.")

    cmd = [exe, str(image_path), "stdout", "--psm", str(psm), "-l", lang]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Tesseract failed (code {proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def parse_pier_type_legend_from_text(text: str) -> dict:
    legend = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = PIER_LEGEND_LINE_RE.match(line.upper())
        if not m:
            continue
        code = m.group("code").strip().upper()
        name = m.group("name").strip().upper()
        rest = m.group("rest").strip()
        if len(code) < 2 or len(code) > 10:
            continue
        if "PIER" not in name:
            continue
        legend[code] = {
            "pier_type": code,
            "pier_type_name": name.title(),
            "details_raw": rest,
            "source": "tesseract_ocr",
        }
    return legend


def build_pier_type_legend_df(pier_types, legend_image=None, tesseract_exe=None):
    pier_types = [str(t).upper() for t in pier_types if t]
    legend_map = {}
    if legend_image:
        text = _ocr_text_from_image(legend_image, tesseract_exe=tesseract_exe)
        legend_map = parse_pier_type_legend_from_text(text)
    rows = []
    for code in sorted(set(pier_types)):
        item = legend_map.get(code, {})
        rows.append({
            "pier_type": code,
            "pier_type_name": item.get("pier_type_name", ""),
            "details_raw": item.get("details_raw", ""),
            "source": item.get("source", ""),
        })
    return pd.DataFrame(rows)


def _source_signature(path: str) -> dict:
    p = Path(path)
    st = p.stat()
    return {"path": str(p), "mtime_ns": int(st.st_mtime_ns), "size": int(st.st_size)}


def cache_paths(cache_dir: str | Path) -> dict:
    d = Path(cache_dir)
    return {k: d / v for k, v in SYSTEM_CACHE_FILES.items()}


def ensure_system_json_cache(
    *,
    cache_dir: str | Path,
    vector_json_path: str | None = None,
    ramming_pdf_path: str | None = None,
    legend_image_path: str | None = None,
    tesseract_exe: str | None = None,
    force: bool = False,
) -> bool:
    """
    Build `system_*.json` cache once. Subsequent queries should read these JSON files.

    Rebuild triggers:
    - Any cache file missing
    - Source signature changed
    - force=True

    Returns True if a rebuild happened, False otherwise.
    """
    paths = cache_paths(cache_dir)
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    missing = [k for k, p in paths.items() if k != "sources" and not p.exists()]
    sources_changed = False
    if paths["sources"].exists():
        try:
            prev = read_json(paths["sources"])
            for key in ("vector_json", "ramming_pdf", "legend_image"):
                if key not in prev:
                    sources_changed = True
                    break
            if not sources_changed:
                # Recompute current signatures based on stored paths (if they still exist)
                for key, src_key in (("vector_json", "vector_json"), ("ramming_pdf", "ramming_pdf"), ("legend_image", "legend_image")):
                    cur_path = prev.get(src_key, {}).get("path") if isinstance(prev.get(src_key), dict) else None
                    if cur_path and Path(cur_path).exists():
                        cur_sig = _source_signature(cur_path)
                        if cur_sig != prev.get(src_key):
                            sources_changed = True
                            break
                    else:
                        # If a source disappeared, we can’t trust the cache.
                        sources_changed = True
                        break
        except Exception:
            sources_changed = True
    else:
        sources_changed = True

    if not force and not missing and not sources_changed:
        return False

    if not (vector_json_path and ramming_pdf_path):
        raise RuntimeError("To (re)build the system cache, you must provide vector_json_path and ramming_pdf_path.")

    meta_df, block_df, tracker_df, piers_df = build_system_tables(vector_json_path, ramming_pdf_path)
    legend_df = build_pier_type_legend_df(
        pier_types=piers_df.get("pier_type", []),
        legend_image=legend_image_path,
        tesseract_exe=tesseract_exe,
    )
    type_counts_df = (
        piers_df["pier_type"]
        .astype(str)
        .str.upper()
        .value_counts()
        .rename_axis("pier_type")
        .reset_index(name="count")
        .sort_values("pier_type", kind="stable")
        .reset_index(drop=True)
    )

    save_json(paths["meta"], meta_df.to_dict(orient="records")[0] if len(meta_df) else {})
    save_json(paths["blocks"], block_df.to_dict(orient="records"))
    save_json(paths["trackers"], tracker_df.to_dict(orient="records"))
    save_json(paths["piers"], piers_df.to_dict(orient="records"))
    save_json(paths["pier_type_legend"], legend_df.to_dict(orient="records"))
    save_json(paths["pier_type_counts"], type_counts_df.to_dict(orient="records"))

    sources = {
        "vector_json": _source_signature(vector_json_path),
        "ramming_pdf": _source_signature(ramming_pdf_path),
        "legend_image": _source_signature(legend_image_path) if legend_image_path and Path(legend_image_path).exists() else {},
    }
    save_json(paths["sources"], sources)
    return True


def load_system_json_cache(cache_dir: str | Path) -> dict:
    """
    Load the already-built `system_*.json` cache for fast queries (no PDF parsing).
    """
    paths = cache_paths(cache_dir)
    return {
        "sources": read_json(paths["sources"]) if paths["sources"].exists() else {},
        "meta": read_json(paths["meta"]) if paths["meta"].exists() else {},
        "blocks": read_json(paths["blocks"]) if paths["blocks"].exists() else [],
        "trackers": read_json(paths["trackers"]) if paths["trackers"].exists() else [],
        "piers": read_json(paths["piers"]) if paths["piers"].exists() else [],
        "pier_type_legend": read_json(paths["pier_type_legend"]) if paths["pier_type_legend"].exists() else [],
        "pier_type_counts": read_json(paths["pier_type_counts"]) if paths["pier_type_counts"].exists() else [],
    }


def export_excel_from_cache(*, cache_dir: str | Path, out_xlsx: str | Path) -> Path:
    """
    Export the already-built cache JSON files into a single Excel workbook.
    This does not read or parse PDFs.
    """
    data = load_system_json_cache(cache_dir)
    out_path = Path(out_xlsx)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    meta_df = pd.DataFrame([data.get("meta") or {}])
    blocks_df = pd.DataFrame(data.get("blocks") or [])
    trackers_df = pd.DataFrame(data.get("trackers") or [])
    piers_df = pd.DataFrame(data.get("piers") or [])
    legend_df = pd.DataFrame(data.get("pier_type_legend") or [])
    counts_df = pd.DataFrame(data.get("pier_type_counts") or [])

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        meta_df.to_excel(writer, sheet_name="Meta", index=False)
        blocks_df.to_excel(writer, sheet_name="Blocks", index=False)
        trackers_df.to_excel(writer, sheet_name="Trackers", index=False)
        piers_df.to_excel(writer, sheet_name="Piers", index=False)
        legend_df.to_excel(writer, sheet_name="PierTypeLegend", index=False)
        counts_df.to_excel(writer, sheet_name="PierTypeCounts", index=False)

    return out_path
