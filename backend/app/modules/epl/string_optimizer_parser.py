from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .optional_assets_parser import (
    agro_pv_features,
    build_optional_asset_issues,
    parse_optional_assets,
    prepare_optional_asset_map_data,
)

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None


STRING_ZONE_RE = re.compile(r"\b(10|11)\s+STRINGS\b", re.IGNORECASE)
OPTIMIZER_ID_RE = re.compile(r"(?<![\w.])(\d+)\.(\d+)\.(\d+)(?![\w.])")
STRING_ID_RE = re.compile(r"(?<![\w.])(\d+)\.(\d+)\.(\d+)\.(\d+)(?![\w.])")
SOLAREDGE_330_RE = re.compile(r"\bSOLAREDGE\s*330\s*kW\b", re.IGNORECASE)
ICB_RE = re.compile(r"\b(?:BE[-\s]?)?ICB[-\s]?\d(?:\.\d)?\b", re.IGNORECASE)
BESS_RE = re.compile(r"\bBESS(?:[-\s]?[A-Za-z0-9.]+)?\b", re.IGNORECASE)
PCS_RE = re.compile(r"\bPCS(?:[-\s]?[A-Za-z0-9.]+)?\b", re.IGNORECASE)


def _read_pdf_blocks(pdf_path: str | Path) -> tuple[str, list[dict[str, Any]]]:
    """Return merged page text and positioned text blocks.

    We use blocks, not OCR. Coordinates are PDF page points and can later be
    transformed to the map overlay the same way piers/trackers are.
    """
    if fitz is None:
        return "", []
    text_parts: list[str] = []
    blocks: list[dict[str, Any]] = []
    try:
        with fitz.open(str(pdf_path)) as doc:
            for page_no, page in enumerate(doc, start=1):
                rect = page.rect
                page_text = page.get_text("text") or ""
                text_parts.append(page_text)
                for b in page.get_text("blocks") or []:
                    if len(b) < 5:
                        continue
                    x0, y0, x1, y1, txt = b[:5]
                    if not isinstance(txt, str) or not txt.strip():
                        continue
                    blocks.append({
                        "source_file": Path(pdf_path).name,
                        "page": page_no,
                        "x": round(float(x0), 2),
                        "y": round(float(y0), 2),
                        "x1": round(float(x1), 2),
                        "y1": round(float(y1), 2),
                        "page_width": round(float(rect.width), 2),
                        "page_height": round(float(rect.height), 2),
                        "text": txt.strip().replace("\n", " "),
                    })
    except Exception:
        return "", []
    return "\n".join(text_parts), blocks


def _extract_int_near_keywords(text: str, keywords: list[str], max_value: int = 200000) -> int | None:
    """Best-effort metadata extractor.

    Looks for numbers close to words like modules / optimizers / strings.
    """
    if not text:
        return None
    compact = re.sub(r"\s+", " ", text)
    candidates: list[int] = []
    for kw in keywords:
        # number before keyword OR keyword before number within a small window
        for m in re.finditer(rf"(\d[\d,\.]*)\s*(?:[A-Za-z0-9 /\-]{{0,30}})?{kw}", compact, re.IGNORECASE):
            n = _to_int(m.group(1))
            if n and 0 < n <= max_value:
                candidates.append(n)
        for m in re.finditer(rf"{kw}(?:[A-Za-z0-9 /\-:]{{0,60}})?(\d[\d,\.]*)", compact, re.IGNORECASE):
            n = _to_int(m.group(1))
            if n and 0 < n <= max_value:
                candidates.append(n)
    if not candidates:
        return None
    # The project-wide metadata is usually the largest meaningful number
    # for modules / optimizers and 288-ish for strings.
    return max(candidates)


def _to_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(str(value).replace(",", "").replace(".", ""))
    except Exception:
        return None


def _search_metadata_number(text: str, patterns: list[str]) -> int | None:
    for p in patterns:
        m = re.search(p, text or "", re.IGNORECASE | re.DOTALL)
        if m:
            n = _to_int(m.group(1))
            if n:
                return n
    return None


def _extract_metadata(all_text: str) -> dict[str, Any]:
    """Extract BHK/SolarEdge string-optimizer metadata when present.

    BHK drawings expose the project totals in the Color Map as:
      Number of Modules - 12672
      No° of optimizers H1300 - 6336
      Number of STRINGS - 288

    We use exact label patterns first, then derive ratios from totals.
    """
    total_modules = _search_metadata_number(all_text, [
        r"Number\s+of\s+Modules\s*[-:]\s*(\d[\d,\.]*)",
        r"Modules\s*[-:]\s*(\d[\d,\.]*)",
    ])
    total_optimizers = _search_metadata_number(all_text, [
        r"No[°º]?\s*of\s+optimizers\s+H1300\s*[-:]\s*(\d[\d,\.]*)",
        r"optimizers?\s+H1300\s*[-:]\s*(\d[\d,\.]*)",
        r"optimizers?\s*[-:]\s*(\d[\d,\.]*)",
    ])
    total_strings = _search_metadata_number(all_text, [
        r"Number\s+of\s+STRINGS\s*[-:]\s*(\d[\d,\.]*)",
    ])

    modules_per_string = None
    optimizers_per_string = None

    # Optional explicit connection pattern, when available.
    m = re.search(r"\b(\d{1,3})\s*[-/]?\s*String\s*/\s*(\d{1,3})\s*[-/]?\s*OP\b", all_text or "", re.IGNORECASE)
    if m:
        modules_per_string = int(m.group(1))
        optimizers_per_string = int(m.group(2))

    # Derive from totals. This is the reliable BHK relation:
    # 12672 modules / 288 strings = 44 modules/string
    # 6336 optimizers / 288 strings = 22 optimizers/string
    if total_strings:
        if total_modules and total_modules % total_strings == 0:
            modules_per_string = total_modules // total_strings
        if total_optimizers and total_optimizers % total_strings == 0:
            optimizers_per_string = total_optimizers // total_strings

    # BHK/SolarEdge safe defaults only when the drawings clearly show the
    # optimizer system but one ratio was not explicitly extractable.
    if modules_per_string is None and total_modules == 12672 and total_strings == 288:
        modules_per_string = 44
    if optimizers_per_string is None and total_optimizers == 6336 and total_strings == 288:
        optimizers_per_string = 22

    modules_per_optimizer = None
    if modules_per_string and optimizers_per_string and modules_per_string % optimizers_per_string == 0:
        modules_per_optimizer = modules_per_string // optimizers_per_string

    return {
        "expected_strings": total_strings,
        "expected_modules": total_modules,
        "expected_optimizers": total_optimizers,
        "modules_per_string": modules_per_string,
        "optimizers_per_string": optimizers_per_string,
        "modules_per_optimizer": modules_per_optimizer,
        "inverter_mentions_solaredge_330kw": len(SOLAREDGE_330_RE.findall(all_text or "")),
    }

def _extract_string_zone_labels(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels: list[dict[str, Any]] = []
    for b in blocks:
        for m in STRING_ZONE_RE.finditer(b.get("text", "")):
            labels.append({
                "label": m.group(0).upper(),
                "string_count": int(m.group(1)),
                "source_file": b.get("source_file"),
                "page": b.get("page"),
                "x": b.get("x"),
                "y": b.get("y"),
                "x1": b.get("x1"),
                "y1": b.get("y1"),
                "page_width": b.get("page_width"),
                "page_height": b.get("page_height"),
                "text_block": (b.get("text") or "")[:240],
            })
    return labels


def _choose_authoritative_labels(labels: list[dict[str, Any]], expected_strings: int | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Pick the string-zone label set to use for reconstruction.

    For BHK, the Electrical Cable Plan contains 27 labels whose sum is 288.
    Panels Plan has extra/repeated labels, so it is a reference layer only.
    """
    by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in labels:
        by_file[str(item.get("source_file") or "unknown")].append(item)

    candidates: list[dict[str, Any]] = []
    for file_name, items in by_file.items():
        s = sum(int(i["string_count"]) for i in items)
        candidates.append({
            "source_file": file_name,
            "label_count": len(items),
            "string_sum": s,
            "distribution": dict(Counter(int(i["string_count"]) for i in items)),
            "matches_expected": expected_strings is not None and s == expected_strings,
            "electrical_priority": 1 if "electrical" in file_name.lower() or "_e_20" in file_name.lower() else 0,
        })

    if not candidates:
        return [], {"candidates": [], "selected": None}

    # Prefer an exact match to metadata, then Electrical Cable Plan, then largest label count.
    candidates_sorted = sorted(
        candidates,
        key=lambda c: (
            1 if c["matches_expected"] else 0,
            c["electrical_priority"],
            c["label_count"],
            c["string_sum"],
        ),
        reverse=True,
    )
    selected = candidates_sorted[0]
    chosen = sorted(by_file[selected["source_file"]], key=lambda d: (float(d.get("y") or 0), float(d.get("x") or 0)))
    return chosen, {"candidates": candidates_sorted, "selected": selected}


def _infer_physical_row_count(all_text: str, default: int | None = None) -> dict[str, Any]:
    """Infer physical row count from visible row-number sequences.

    BHK drawings show long visual sequences such as 1..107. Instead of
    treating every standalone number as a row, we scan the text order and
    look for the longest consecutive sequence beginning at 1.
    """
    tokens = [
        int(m.group(0))
        for m in re.finditer(r"(?<![\w.])(?:[1-9]\d?|1\d\d|200)(?![\w.])", all_text or "")
    ]

    best: list[int] = []
    current: list[int] = []
    for n in tokens:
        if n == 1:
            current = [1]
        elif current and n == current[-1] + 1:
            current.append(n)
            if len(current) > len(best):
                best = current.copy()
        elif current and n == current[-1]:
            # Some PDF text layers duplicate labels; ignore same-number repeats.
            continue
        else:
            current = []

    if len(best) >= 20:
        row_count = best[-1]
        method = "longest_consecutive_visible_row_sequence"
    else:
        row_count = default
        method = "fallback_default"

    return {
        "physical_row_count": row_count,
        "method": method,
        "sequence_length": len(best),
        "sequence_end": best[-1] if best else None,
        "sequence_start": best[0] if best else None,
    }

def _zone_row_ranges(zone_count: int, physical_row_count: int | None) -> list[list[int]]:
    if not physical_row_count or zone_count <= 0:
        return [[] for _ in range(zone_count)]

    ranges: list[list[int]] = []
    start = 1
    # Even distribution, preserving total row count.
    for i in range(zone_count):
        end = round((i + 1) * physical_row_count / zone_count)
        rows = list(range(start, end + 1))
        ranges.append(rows)
        start = end + 1
    return ranges


def _distribute_strings_across_rows(string_count: int, physical_rows: list[int]) -> list[tuple[int | None, int]]:
    """Return [(physical_row, local_string_index_in_row), ...] for a zone."""
    if not physical_rows:
        return [(None, i) for i in range(1, string_count + 1)]
    out: list[tuple[int | None, int]] = []
    # Balanced 10/11 strings across 3-4 rows, e.g. 11 -> 3,3,3,2.
    base = string_count // len(physical_rows)
    rem = string_count % len(physical_rows)
    for idx, row in enumerate(physical_rows):
        n = base + (1 if idx < rem else 0)
        for local in range(1, n + 1):
            out.append((row, local))
    return out


def _is_bhk_electrical_plan(path: str | Path) -> bool:
    name = Path(path).name.lower()
    return (
        ("bhk" in name or "electrical" in name)
        and ("e_20" in name or "electrical cable plan" in name or "electrical_cable_plan" in name)
    )


def _is_panels_plan(path: str | Path) -> bool:
    name = Path(path).name.lower()
    return "panels plan" in name or "panels_plan" in name or "_e_41" in name or "e_41" in name


def _read_pdf_words(pdf_path: str | Path) -> list[dict[str, Any]]:
    if fitz is None:
        return []
    words: list[dict[str, Any]] = []
    try:
        with fitz.open(str(pdf_path)) as doc:
            for page_no, page in enumerate(doc, start=1):
                rect = page.rect
                for w in page.get_text("words") or []:
                    if len(w) < 5:
                        continue
                    x0, y0, x1, y1, text = w[:5]
                    if not str(text).strip():
                        continue
                    words.append({
                        "source_file": Path(pdf_path).name,
                        "page": page_no,
                        "x": round(float(x0), 2),
                        "y": round(float(y0), 2),
                        "x1": round(float(x1), 2),
                        "y1": round(float(y1), 2),
                        "page_width": round(float(rect.width), 2),
                        "page_height": round(float(rect.height), 2),
                        "text": str(text).strip(),
                    })
    except Exception:
        return []
    return words


def _center(item: dict[str, Any]) -> tuple[float, float]:
    return (
        (float(item.get("x") or 0) + float(item.get("x1") or 0)) / 2,
        (float(item.get("y") or 0) + float(item.get("y1") or 0)) / 2,
    )


def _nearest_item(item: dict[str, Any], candidates: list[dict[str, Any]], *, max_distance: float | None = None) -> dict[str, Any] | None:
    if not candidates:
        return None
    x, y = _center(item)
    best = min(candidates, key=lambda cand: ((x - _center(cand)[0]) ** 2 + (y - _center(cand)[1]) ** 2))
    if max_distance is not None:
        bx, by = _center(best)
        if math.hypot(x - bx, y - by) > max_distance:
            return None
    return best


def _zone_id_sort_key(zone_id: str) -> tuple[int, ...]:
    return tuple(int(part) for part in str(zone_id).split(".") if part.isdigit())


def _extract_visible_row_numbers(page_words: list[dict[str, Any]], string_count_words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        w for w in page_words
        if re.fullmatch(r"\d{1,3}", str(w.get("text") or ""))
        and 1 <= int(str(w.get("text"))) <= 250
    ]
    if not candidates:
        return []
    # BHK row numbers sit in the same upper detail band as the string-count
    # labels; use that y-window to avoid BOM notes and panel numbers.
    if string_count_words:
        min_y = min(float(w.get("y") or 0) for w in string_count_words) - 80
        max_y = max(float(w.get("y") or 0) for w in string_count_words) + 80
        candidates = [w for w in candidates if min_y <= float(w.get("y") or 0) <= max_y]
    by_num: dict[int, dict[str, Any]] = {}
    for w in candidates:
        n = int(str(w.get("text")))
        old = by_num.get(n)
        if old is None or float(w.get("x") or 0) < float(old.get("x") or 0):
            by_num[n] = w
    rows = [by_num[n] for n in sorted(by_num)]
    # Keep only the first visible consecutive run from 1.
    out: list[dict[str, Any]] = []
    expected = 1
    for w in rows:
        n = int(str(w.get("text")))
        if n == expected:
            out.append(w)
            expected += 1
        elif n > expected and expected > 20:
            break
    return out


def _nearest_visible_row_for_label(item: dict[str, Any], row_words: list[dict[str, Any]]) -> tuple[int | None, float | None]:
    if not row_words:
        return None, None
    _, cy = _center(item)
    nearest = min(row_words, key=lambda row: abs(_center(row)[1] - cy))
    try:
        return int(nearest["text"]), round(abs(_center(nearest)[1] - cy), 2)
    except Exception:
        return None, None


def _extract_bhk_electrical_geometry(pdf_paths: list[str | Path]) -> dict[str, Any]:
    electrical_paths = [p for p in pdf_paths if _is_bhk_electrical_plan(p)]
    if not electrical_paths:
        return {"status": "missing_electrical_plan", "physical_rows": [], "string_zones": [], "strings": [], "issues": [], "map_source": None}
    words = _read_pdf_words(electrical_paths[0])
    page_words = [w for w in words if int(w.get("page") or 0) == 1]
    string_words = [w for w in page_words if STRING_ID_RE.fullmatch(str(w.get("text") or ""))]
    zone_words = [
        w for w in page_words
        if OPTIMIZER_ID_RE.fullmatch(str(w.get("text") or ""))
        and not STRING_ID_RE.fullmatch(str(w.get("text") or ""))
    ]
    string_count_words = [
        w for w in page_words
        if re.fullmatch(r"(?:10|11)", str(w.get("text") or ""))
        and any(
            str(other.get("text") or "").upper() == "STRINGS"
            and abs(float(other.get("y") or 0) - float(w.get("y") or 0)) < 8
            and 0 < float(other.get("x") or 0) - float(w.get("x") or 0) < 80
            for other in page_words
        )
    ]
    row_words = _extract_visible_row_numbers(page_words, string_count_words)

    strings_by_zone: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for word in sorted(string_words, key=lambda w: (str(w["text"]), float(w.get("y") or 0), float(w.get("x") or 0))):
        label = str(word["text"])
        parts = label.split(".")
        zone_id = ".".join(parts[:3])
        strings_by_zone[zone_id].append({
            "id": label,
            "zone_id": zone_id,
            "string_in_zone": int(parts[3]),
            "source_file": word.get("source_file"),
            "page": word.get("page"),
            "x": word.get("x"),
            "y": word.get("y"),
            "x1": word.get("x1"),
            "y1": word.get("y1"),
            "page_width": word.get("page_width"),
            "page_height": word.get("page_height"),
            "geometry_source": "visible_four_part_pdf_label",
        })

    zone_words_by_label = {str(w.get("text")): w for w in zone_words}
    string_zones: list[dict[str, Any]] = []
    strings_flat: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for zone_index, zone_id in enumerate(sorted(strings_by_zone, key=_zone_id_sort_key), start=1):
        zone_strings = sorted(strings_by_zone[zone_id], key=lambda s: int(s["string_in_zone"]))
        zone_word = zone_words_by_label.get(zone_id) or _nearest_item(zone_strings[0], zone_words, max_distance=140)
        count_word = _nearest_item(zone_word or zone_strings[0], string_count_words, max_distance=90)
        declared_count = int(count_word["text"]) if count_word and str(count_word.get("text")).isdigit() else None
        if declared_count is not None and declared_count != len(zone_strings):
            issues.append({"severity": "error", "type": "bhk_zone_string_count_mismatch", "zone_id": zone_id, "declared": declared_count, "actual": len(zone_strings)})
        zone_payload = {
            "zone": zone_index,
            "zone_id": zone_id,
            "string_count": len(zone_strings),
            "declared_string_count": declared_count,
            "physical_rows": [],
            "source": {
                "label": zone_id,
                "source_file": (zone_word or zone_strings[0]).get("source_file"),
                "page": (zone_word or zone_strings[0]).get("page"),
                "x": (zone_word or zone_strings[0]).get("x"),
                "y": (zone_word or zone_strings[0]).get("y"),
                "x1": (zone_word or zone_strings[0]).get("x1"),
                "y1": (zone_word or zone_strings[0]).get("y1"),
                "page_width": (zone_word or zone_strings[0]).get("page_width"),
                "page_height": (zone_word or zone_strings[0]).get("page_height"),
                "geometry_source": "visible_three_part_pdf_label",
            },
            "strings": [],
        }
        for string_item in zone_strings:
            string_row, row_distance = _nearest_visible_row_for_label(string_item, row_words)
            s_obj = {
                **string_item,
                "zone": zone_index,
                "physical_row": string_row,
                "physical_row_distance_pt": row_distance,
                "row_assignment_source": "nearest_visible_row_number_y_coordinate",
                "global_string_index": len(strings_flat) + 1,
                "raw_label": string_item["id"],
                "optimizer_count": None,
                "module_count": None,
            }
            zone_payload["strings"].append(s_obj)
            strings_flat.append(s_obj)
        zone_rows = sorted({int(s["physical_row"]) for s in zone_payload["strings"] if isinstance(s.get("physical_row"), int)})
        zone_payload["physical_rows"] = zone_rows
        string_zones.append(zone_payload)

    map_source = None
    if page_words:
        first = page_words[0]
        map_source = {
            "source_file": first.get("source_file"),
            "page": first.get("page"),
            "page_width": first.get("page_width"),
            "page_height": first.get("page_height"),
            "coordinate_frame": "pdf_points",
            "base_map": "vector",
        }
    return {
        "source": "bhk_electrical_geometry",
        "status": "ok" if strings_flat else "no_visible_string_labels",
        "source_file": Path(electrical_paths[0]).name,
        "physical_rows": [
            {
                "physical_row": int(w["text"]),
                "raw_label": str(w["text"]),
                "source_file": w.get("source_file"),
                "page": w.get("page"),
                "x": w.get("x"),
                "y": w.get("y"),
                "x1": w.get("x1"),
                "y1": w.get("y1"),
                "page_width": w.get("page_width"),
                "page_height": w.get("page_height"),
                "geometry_source": "visible_row_number",
            }
            for w in row_words
        ],
        "string_zones": string_zones,
        "strings": strings_flat,
        "issues": issues,
        "map_source": map_source,
        "panel_numbering_rule": {"source": "user_rule", "starts_from": "south"},
    }


def _extract_panel_map_geometry(pdf_paths: list[str | Path]) -> dict[str, Any]:
    if fitz is None:
        return {"source": "panel_plan_geometry", "status": "pymupdf_unavailable", "panel_rows": [], "site_border": []}
    panel_paths = [p for p in pdf_paths if _is_panels_plan(p)]
    if not panel_paths:
        return {"source": "panel_plan_geometry", "status": "missing_panels_plan", "panel_rows": [], "site_border": []}
    panel_rows: list[dict[str, Any]] = []
    panel_rects: list[dict[str, Any]] = []
    try:
        with fitz.open(str(panel_paths[0])) as doc:
            page = doc[0]
            rect = page.rect
            for drawing in page.get_drawings():
                color = drawing.get("color")
                layer = str(drawing.get("layer") or "")
                drawing_rect = drawing.get("rect")
                items = drawing.get("items") or []
                if "EN-PANEL" in layer and drawing_rect and len(items) == 1 and items[0][0] == "qu":
                    width = abs(float(drawing_rect.x1) - float(drawing_rect.x0))
                    height = abs(float(drawing_rect.y1) - float(drawing_rect.y0))
                    if 4.5 <= width <= 7.2 and 9.0 <= height <= 12.2:
                        panel_rects.append({
                            "x": round(float(drawing_rect.x0), 2),
                            "y": round(float(drawing_rect.y0), 2),
                            "x1": round(float(drawing_rect.x1), 2),
                            "y1": round(float(drawing_rect.y1), 2),
                            "cx": round((float(drawing_rect.x0) + float(drawing_rect.x1)) / 2, 2),
                            "cy": round((float(drawing_rect.y0) + float(drawing_rect.y1)) / 2, 2),
                            "source_layer": layer,
                        })
                if not color or "BE-Vertical Grid" not in layer:
                    continue
                if not all(abs(float(color[i]) - 0.50196) < 0.012 for i in range(3)):
                    continue
                for item in items:
                    if not item or item[0] != "l":
                        continue
                    p0, p1 = item[1], item[2]
                    length = math.hypot(float(p1.x) - float(p0.x), float(p1.y) - float(p0.y))
                    if length < 120:
                        continue
                    north, south = (p0, p1) if float(p0.x) >= float(p1.x) else (p1, p0)
                    panel_rows.append({
                        "id": f"panel-row-{len(panel_rows) + 1}",
                        "source_file": Path(panel_paths[0]).name,
                        "page": 1,
                        "x0": round(float(p0.x), 2),
                        "y0": round(float(p0.y), 2),
                        "x1": round(float(p1.x), 2),
                        "y1": round(float(p1.y), 2),
                        "north_x": round(float(north.x), 2),
                        "north_y": round(float(north.y), 2),
                        "south_x": round(float(south.x), 2),
                        "south_y": round(float(south.y), 2),
                        "length": round(length, 2),
                        "page_width": round(float(rect.width), 2),
                        "page_height": round(float(rect.height), 2),
                        "geometry_source": "bhk_e41_gray_be_vertical_grid",
                    })
    except Exception as exc:
        return {"source": "panel_plan_geometry", "status": "extract_failed", "error": str(exc), "panel_rows": [], "site_border": []}
    panel_rows.sort(key=lambda row: (float(row["north_y"]) + float(row["south_y"])) / 2)
    for idx, row in enumerate(panel_rows, start=1):
        row["id"] = f"panel-row-{idx}"

    assigned_panels: list[list[tuple[float, float, dict[str, Any]]]] = [[] for _ in panel_rows]
    for panel in panel_rects:
        best: tuple[float, int, float] | None = None
        px = float(panel["cx"])
        py = float(panel["cy"])
        for idx, row in enumerate(panel_rows):
            sx = float(row["south_x"])
            sy = float(row["south_y"])
            nx = float(row["north_x"])
            ny = float(row["north_y"])
            dx = nx - sx
            dy = ny - sy
            denom = dx * dx + dy * dy or 1.0
            t = ((px - sx) * dx + (py - sy) * dy) / denom
            if t < -0.08 or t > 1.08:
                continue
            qx = sx + dx * t
            qy = sy + dy * t
            dist = math.hypot(px - qx, py - qy)
            if best is None or dist < best[0]:
                best = (dist, idx, t)
        if best and best[0] <= 10.0:
            assigned_panels[best[1]].append((best[2], best[0], panel))

    for row, panels in zip(panel_rows, assigned_panels):
        ordered = sorted(panels, key=lambda item: item[0])
        row_panels = []
        for panel_no, (t, dist, panel) in enumerate(ordered, start=1):
            row_panels.append({
                "panel": panel_no,
                "t": round(float(t), 6),
                "x": panel["x"],
                "y": panel["y"],
                "x1": panel["x1"],
                "y1": panel["y1"],
                "cx": panel["cx"],
                "cy": panel["cy"],
                "row_distance": round(float(dist), 3),
            })
        row["panel_count"] = len(row_panels)
        row["panels"] = row_panels
        row["panel_numbering"] = "south_to_north"

    north_chain = [{"x": r["north_x"], "y": r["north_y"]} for r in panel_rows]
    south_chain = [{"x": r["south_x"], "y": r["south_y"]} for r in reversed(panel_rows)]
    site_border = north_chain + south_chain
    if site_border:
        site_border.append(site_border[0])
    return {
        "source": "panel_plan_geometry",
        "status": "ok" if panel_rows else "no_gray_panel_rows",
        "source_file": Path(panel_paths[0]).name,
        "panel_rows": panel_rows,
        "site_border": site_border,
        "panel_rectangles": len(panel_rects),
        "assigned_panel_rectangles": sum(int(row.get("panel_count") or 0) for row in panel_rows),
    }


def _extract_typical_string_detail(pdf_paths: list[str | Path]) -> dict[str, Any]:
    if fitz is None:
        return {"status": "unavailable", "reason": "pymupdf_not_available"}
    electrical_paths = [Path(p) for p in pdf_paths if _is_bhk_electrical_plan(p)]
    if not electrical_paths:
        return {"status": "not_detected", "reason": "electrical_file_not_found"}
    try:
        with fitz.open(str(electrical_paths[0])) as doc:
            words = doc[0].get_text("words") or []
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}
    detail_words = []
    for w in words:
        if len(w) < 5:
            continue
        x0, y0, x1, y1, text = w[:5]
        x = float(x0); y = float(y0)
        if 1950 <= x <= 2250 and 350 <= y <= 2700:
            detail_words.append({"text": str(text), "x": x, "y": y, "x1": float(x1), "y1": float(y1)})
    h_entries = []
    visible_panel_numbers: list[int] = []
    for word in detail_words:
        if re.fullmatch(r"\d{1,2}", word["text"]):
            number = int(word["text"])
            if 1 <= number <= 60:
                visible_panel_numbers.append(number)
        m = re.fullmatch(r"H1300-(\d+)", word["text"], re.IGNORECASE)
        if not m:
            continue
        pair_index = int(m.group(1))
        nearby_numbers = []
        for num_word in detail_words:
            dx = float(word["x"]) - float(num_word["x"])
            if re.fullmatch(r"\d{1,2}", num_word["text"]) and abs(float(num_word["y"]) - float(word["y"])) <= 70 and 40 <= dx <= 130:
                nearby_numbers.append((float(num_word["y"]), int(num_word["text"])))
        panel_pair = [n for _, n in sorted(nearby_numbers)[:2]]
        if len(panel_pair) == 2:
            h_entries.append({"pair_index": pair_index, "optimizer_label": f"H1300-{pair_index}", "panel_pair": panel_pair, "x": round(float(word["x"]), 2), "y": round(float(word["y"]), 2)})
    if not h_entries:
        return {"status": "not_detected", "reason": "typical_detail_pairs_not_found"}
    by_index = {int(e["pair_index"]): e for e in h_entries}
    pair_count = max(by_index)
    max_visible_panel = max(visible_panel_numbers, default=0)
    panel_count = max(pair_count * 2, max_visible_panel if max_visible_panel % 2 == 0 else max_visible_panel - 1)
    start_words = [w for w in detail_words if str(w["text"]).lower() == "start"]
    start_index = pair_count
    if start_words:
        start_word = start_words[0]
        nearest = min(h_entries, key=lambda e: math.hypot(float(e["x"]) - float(start_word["x"]), float(e["y"]) - float(start_word["y"])))
        start_index = int(nearest["pair_index"])
    end_index = min(by_index)
    return {
        "status": "ok",
        "source": "typical_strings_wires_detail",
        "source_file": electrical_paths[0].name,
        "panel_pair_count": pair_count,
        "panel_count": panel_count,
        "visible_panel_numbers": sorted(set(visible_panel_numbers)),
        "panel_count_origin": "south",
        "panel_count_axis": "south_to_north",
        "start_pair_index": start_index,
        "start_panel_pair": by_index[start_index]["panel_pair"],
        "end_pair_index": end_index,
        "end_panel_pair": by_index[end_index]["panel_pair"],
        "pairs": [by_index[i] for i in sorted(by_index)],
    }


def _prepare_bhk_vector_map_layers(physical_rows: list[dict[str, Any]], string_zones: list[dict[str, Any]], strings_flat: list[dict[str, Any]], optional_map_data: dict[str, Any], panel_geometry: dict[str, Any]) -> dict[str, Any]:
    return {
        "physical_rows": physical_rows,
        "string_zones": string_zones,
        "strings": strings_flat,
        "panel_rows": panel_geometry.get("panel_rows") or [],
        "site_border": panel_geometry.get("site_border") or [],
        **(optional_map_data or {}),
    }


def _logical_optimizers_from_visible_strings(strings_flat: list[dict[str, Any]], opt_per_string: int, mod_per_opt: int) -> list[dict[str, Any]]:
    optimizers: list[dict[str, Any]] = []
    for string_item in strings_flat:
        string_id = str(string_item.get("id") or string_item.get("raw_label") or "")
        if not string_id:
            continue
        for op in range(1, opt_per_string + 1):
            opt_id = f"{string_id}.OP.{op}"
            optimizers.append({
                "id": opt_id,
                "string_id": string_id,
                "zone": string_item.get("zone"),
                "zone_id": string_item.get("zone_id"),
                "physical_row": string_item.get("physical_row"),
                "string_in_zone": string_item.get("string_in_zone"),
                "global_string_index": string_item.get("global_string_index"),
                "optimizer": op,
                "modules": [f"{opt_id}.M.{m}" for m in range(1, mod_per_opt + 1)],
            })
    return optimizers


def build_string_optimizer_model_from_pdfs(pdf_paths: list[str | Path], fallback_physical_rows: int | None = 107) -> dict[str, Any]:
    """Build the EPL string/optimizer model for SolarEdge/BHK-style projects.

    Produces:
      - physical rows (100+ when visible)
      - electrical string zones (10/11 STRINGS labels)
      - 288 strings, 6336 optimizers, 12672 modules when metadata matches BHK
    """
    all_text_parts: list[str] = []
    text_by_file: dict[str, str] = {}
    all_blocks: list[dict[str, Any]] = []

    for path in pdf_paths:
        txt, blocks = _read_pdf_blocks(path)
        all_text_parts.append(txt)
        text_by_file[Path(path).name] = txt
        all_blocks.extend(blocks)

    all_text = "\n".join(all_text_parts)
    metadata = _extract_metadata(all_text)
    features = agro_pv_features()
    optional_assets = parse_optional_assets(text_by_file, all_blocks)

    # Fill BHK defaults when the drawing metadata is incomplete but SolarEdge optimizer pattern exists.
    if metadata.get("modules_per_string") is None:
        metadata["modules_per_string"] = 44
    if metadata.get("optimizers_per_string") is None:
        metadata["optimizers_per_string"] = 22
    if metadata.get("modules_per_optimizer") is None:
        metadata["modules_per_optimizer"] = 2

    labels = _extract_string_zone_labels(all_blocks)
    chosen_labels, label_selection = _choose_authoritative_labels(labels, metadata.get("expected_strings"))
    bhk_geometry = _extract_bhk_electrical_geometry(pdf_paths)
    panel_geometry = _extract_panel_map_geometry(pdf_paths)
    string_detail = _extract_typical_string_detail(pdf_paths)
    metadata["string_detail"] = string_detail

    # If exact metadata was not found, use the selected zone sum.
    if metadata.get("expected_strings") is None and chosen_labels:
        metadata["expected_strings"] = sum(int(l["string_count"]) for l in chosen_labels)
    if metadata.get("expected_optimizers") is None and metadata.get("expected_strings") and metadata.get("optimizers_per_string"):
        metadata["expected_optimizers"] = metadata["expected_strings"] * metadata["optimizers_per_string"]
    if metadata.get("expected_modules") is None and metadata.get("expected_strings") and metadata.get("modules_per_string"):
        metadata["expected_modules"] = metadata["expected_strings"] * metadata["modules_per_string"]

    physical_info = _infer_physical_row_count(all_text, default=fallback_physical_rows)
    physical_row_count = physical_info.get("physical_row_count") or fallback_physical_rows

    zone_ranges = _zone_row_ranges(len(chosen_labels), physical_row_count)

    rows_by_physical: dict[int, dict[str, Any]] = {}
    string_zones: list[dict[str, Any]] = []
    strings_flat: list[dict[str, Any]] = []
    optimizers_flat: list[dict[str, Any]] = []

    global_string_index = 1
    opt_per_string = int(metadata.get("optimizers_per_string") or 22)
    mod_per_string = int(metadata.get("modules_per_string") or 44)
    mod_per_opt = int(metadata.get("modules_per_optimizer") or 2)

    for zone_idx, label in enumerate(chosen_labels, start=1):
        zone_rows = zone_ranges[zone_idx - 1] if zone_idx - 1 < len(zone_ranges) else []
        zone = {
            "zone": zone_idx,
            "string_count": int(label["string_count"]),
            "physical_rows": zone_rows,
            "source": {
                "label": label.get("label"),
                "source_file": label.get("source_file"),
                "page": label.get("page"),
                "x": label.get("x"),
                "y": label.get("y"),
                "x1": label.get("x1"),
                "y1": label.get("y1"),
                "page_width": label.get("page_width"),
                "page_height": label.get("page_height"),
            },
            "strings": [],
        }

        assignments = _distribute_strings_across_rows(int(label["string_count"]), zone_rows)
        zone_string_no = 1

        for physical_row, local_string_in_row in assignments:
            string_id = f"Z.{zone_idx}.S.{zone_string_no}"
            row_string_id = f"R.{physical_row}.Z.{zone_idx}.S.{zone_string_no}" if physical_row else string_id
            s_obj = {
                "id": row_string_id,
                "zone_string_id": string_id,
                "zone": zone_idx,
                "physical_row": physical_row,
                "string_in_zone": zone_string_no,
                "string_in_physical_row": local_string_in_row,
                "global_string_index": global_string_index,
                "optimizer_count": opt_per_string,
                "module_count": mod_per_string,
            }
            zone["strings"].append(s_obj)
            strings_flat.append(s_obj)

            if physical_row is not None:
                rows_by_physical.setdefault(physical_row, {
                    "physical_row": physical_row,
                    "zones": [],
                    "strings": [],
                    "string_count": 0,
                    "optimizer_count": 0,
                    "module_count": 0,
                })
                r = rows_by_physical[physical_row]
                if zone_idx not in r["zones"]:
                    r["zones"].append(zone_idx)
                r["strings"].append(s_obj)
                r["string_count"] += 1
                r["optimizer_count"] += opt_per_string
                r["module_count"] += mod_per_string

            for op in range(1, opt_per_string + 1):
                opt_id = f"{row_string_id}.OP.{op}"
                modules = [f"{opt_id}.M.{m}" for m in range(1, mod_per_opt + 1)]
                optimizers_flat.append({
                    "id": opt_id,
                    "zone": zone_idx,
                    "physical_row": physical_row,
                    "string_in_zone": zone_string_no,
                    "string_in_physical_row": local_string_in_row,
                    "global_string_index": global_string_index,
                    "optimizer": op,
                    "modules": modules,
                })

            global_string_index += 1
            zone_string_no += 1

        string_zones.append(zone)

    physical_rows = [rows_by_physical.get(i, {
        "physical_row": i,
        "zones": [],
        "strings": [],
        "string_count": 0,
        "optimizer_count": 0,
        "module_count": 0,
    }) for i in range(1, int(physical_row_count or 0) + 1)]

    if bhk_geometry.get("strings"):
        physical_info = {
            "physical_row_count": len(bhk_geometry.get("physical_rows") or []),
            "method": "visible_row_numbers_from_bhk_e20_geometry",
            "sequence_length": len(bhk_geometry.get("physical_rows") or []),
            "source_file": bhk_geometry.get("source_file"),
        }
        strings_flat = bhk_geometry["strings"]
        string_zones = bhk_geometry["string_zones"]
        rows_by_physical = {}
        max_panel_row = len(panel_geometry.get("panel_rows") or [])
        visible_rows = [int(r.get("physical_row") or 0) for r in bhk_geometry.get("physical_rows") or [] if int(r.get("physical_row") or 0)]
        row_count = max([max_panel_row, *visible_rows], default=len(visible_rows))
        for row in bhk_geometry.get("physical_rows") or []:
            row_no = int(row.get("physical_row") or 0)
            if not row_no:
                continue
            rows_by_physical[row_no] = {
                **row,
                "zones": [],
                "strings": [],
                "string_count": 0,
                "optimizer_count": 0,
                "module_count": 0,
            }
        for s_obj in strings_flat:
            s_obj["optimizer_count"] = opt_per_string
            s_obj["module_count"] = mod_per_string
            row_no = s_obj.get("physical_row")
            if not isinstance(row_no, int):
                continue
            row = rows_by_physical.setdefault(row_no, {
                "physical_row": row_no,
                "zones": [],
                "strings": [],
                "string_count": 0,
                "optimizer_count": 0,
                "module_count": 0,
            })
            zone_idx = s_obj.get("zone")
            if zone_idx not in row["zones"]:
                row["zones"].append(zone_idx)
            row["strings"].append(s_obj)
            row["string_count"] += 1
            row["optimizer_count"] += opt_per_string
            row["module_count"] += mod_per_string
        physical_rows = [rows_by_physical.get(i, {
            "physical_row": i,
            "zones": [],
            "strings": [],
            "string_count": 0,
            "optimizer_count": 0,
            "module_count": 0,
        }) for i in range(1, int(row_count or 0) + 1)]
        optimizers_flat = _logical_optimizers_from_visible_strings(strings_flat, opt_per_string, mod_per_opt)

    issues: list[dict[str, Any]] = list(bhk_geometry.get("issues") or [])
    expected_strings = metadata.get("expected_strings")
    expected_opts = metadata.get("expected_optimizers")
    expected_modules = metadata.get("expected_modules")
    actual_strings = len(strings_flat)
    actual_opts = len(optimizers_flat)
    actual_modules = actual_strings * mod_per_string

    if expected_strings is not None and actual_strings != int(expected_strings):
        issues.append({"severity": "error", "type": "string_count_mismatch", "expected": expected_strings, "actual": actual_strings})
    if expected_opts is not None and actual_opts != int(expected_opts):
        issues.append({"severity": "error", "type": "optimizer_count_mismatch", "expected": expected_opts, "actual": actual_opts})
    if expected_modules is not None and actual_modules != int(expected_modules):
        issues.append({"severity": "error", "type": "module_count_mismatch", "expected": expected_modules, "actual": actual_modules})
    issues.extend(build_optional_asset_issues(optional_assets, features))

    # Keep reference labels for audit, especially if panel-plan labels differ.
    all_label_by_file: dict[str, dict[str, Any]] = {}
    for source_file, items in defaultdict(list, {}).items():
        pass
    by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for l in labels:
        by_file[str(l.get("source_file"))].append(l)
    source_label_summaries = {
        file_name: {
            "label_count": len(items),
            "string_sum": sum(int(i["string_count"]) for i in items),
            "distribution": dict(Counter(int(i["string_count"]) for i in items)),
        }
        for file_name, items in sorted(by_file.items())
    }
    map_source = None
    if bhk_geometry.get("map_source"):
        map_source = bhk_geometry.get("map_source")
    elif chosen_labels:
        first = chosen_labels[0]
        map_source = {
            "source_file": first.get("source_file"),
            "page": first.get("page"),
            "page_width": first.get("page_width"),
            "page_height": first.get("page_height"),
            "coordinate_frame": "pdf_points",
            "base_map": "vector",
        }

    optional_map_data = prepare_optional_asset_map_data(optional_assets, features)
    epl_map_layers = _prepare_bhk_vector_map_layers(physical_rows, string_zones, strings_flat, optional_map_data, panel_geometry)

    return {
        "project_type": "agro_pv_solar_edge",
        "epl_step": "strings_optimizers_physical_rows",
        "features": features,
        "pattern": {
            "zone_string": "Z.<zone>.S.<string_in_zone>",
            "physical_string": "R.<physical_row>.Z.<zone>.S.<string_in_zone>",
            "optimizer": "R.<physical_row>.Z.<zone>.S.<string_in_zone>.OP.<optimizer>",
        },
        "metadata": metadata,
        "assets": {
            "required": {
                "physical_rows": len(physical_rows),
                "string_zones": len(string_zones),
                "strings": actual_strings,
                "optimizers": actual_opts,
                "modules": actual_modules,
            },
            "security_devices": optional_assets.get("security_devices", []),
            "weather_assets": optional_assets.get("weather_assets", []),
        },
        "map_data": {
            "layers": epl_map_layers,
            "optional_assets": optional_map_data,
        },
        "summary": {
            "physical_rows": len(physical_rows),
            "string_zones": len(string_zones),
            "strings": actual_strings,
            "optimizers": actual_opts,
            "modules": actual_modules,
            "security_devices": len(optional_assets.get("security_devices", [])),
            "weather_assets": len(optional_assets.get("weather_assets", [])),
            "rows_with_work": sum(1 for r in physical_rows if r["string_count"] > 0),
            "empty_physical_rows": sum(1 for r in physical_rows if r["string_count"] == 0),
            "issues": len(issues),
            "errors": sum(1 for i in issues if i["severity"] == "error"),
            "warnings": sum(1 for i in issues if i["severity"] == "warning"),
        },
        "physical_row_detection": physical_info,
        "geometry_extraction": {
            "source": bhk_geometry.get("source"),
            "status": bhk_geometry.get("status"),
            "source_file": bhk_geometry.get("source_file"),
            "visible_string_labels": len(bhk_geometry.get("strings") or []),
            "visible_string_zones": len(bhk_geometry.get("string_zones") or []),
            "visible_row_numbers": len(bhk_geometry.get("physical_rows") or []),
            "panel_base_rows": len(panel_geometry.get("panel_rows") or []),
            "panel_base_status": panel_geometry.get("status"),
            "panel_base_source_file": panel_geometry.get("source_file"),
            "string_detail_status": string_detail.get("status"),
            "string_detail_source_file": string_detail.get("source_file"),
            "base_map": "vector",
        },
        "panel_numbering_rule": bhk_geometry.get("panel_numbering_rule"),
        "map_source": map_source,
        "label_selection": label_selection,
        "source_label_summaries": source_label_summaries,
        "physical_rows": physical_rows,
        "string_zones": string_zones,
        "strings": strings_flat,
        "optimizers": optimizers_flat,
        "issues": issues,
    }


def write_string_optimizer_csvs(model: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    """Write rows/strings/optimizers CSV exports and return their paths."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows_csv = out / "physical_rows.csv"
    strings_csv = out / "strings.csv"
    optimizers_csv = out / "optimizers.csv"
    zones_csv = out / "string_zones.csv"
    issues_csv = out / "validation_issues.csv"
    model_json = out / "string_optimizer_model.json"

    model_json.write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")

    with rows_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["physical_row", "zones", "string_count", "optimizer_count", "module_count"])
        for r in model.get("physical_rows", []):
            w.writerow([r.get("physical_row"), ",".join(map(str, r.get("zones", []))), r.get("string_count"), r.get("optimizer_count"), r.get("module_count")])

    with strings_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "physical_row", "zone", "string_in_zone", "string_in_physical_row", "global_string_index", "optimizer_count", "module_count"])
        for s in model.get("strings", []):
            w.writerow([s.get("id"), s.get("physical_row"), s.get("zone"), s.get("string_in_zone"), s.get("string_in_physical_row"), s.get("global_string_index"), s.get("optimizer_count"), s.get("module_count")])

    with optimizers_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "physical_row", "zone", "string_in_zone", "string_in_physical_row", "global_string_index", "optimizer", "modules"])
        for o in model.get("optimizers", []):
            w.writerow([o.get("id"), o.get("physical_row"), o.get("zone"), o.get("string_in_zone"), o.get("string_in_physical_row"), o.get("global_string_index"), o.get("optimizer"), ",".join(o.get("modules", []))])

    with zones_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["zone", "string_count", "physical_rows", "source_file", "page", "x", "y"])
        for z in model.get("string_zones", []):
            src = z.get("source") or {}
            w.writerow([z.get("zone"), z.get("string_count"), ",".join(map(str, z.get("physical_rows", []))), src.get("source_file"), src.get("page"), src.get("x"), src.get("y")])

    with issues_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["severity", "type", "data"])
        for i in model.get("issues", []):
            w.writerow([i.get("severity"), i.get("type"), json.dumps(i, ensure_ascii=False)])

    return {
        "model_json": str(model_json),
        "physical_rows_csv": str(rows_csv),
        "strings_csv": str(strings_csv),
        "optimizers_csv": str(optimizers_csv),
        "string_zones_csv": str(zones_csv),
        "issues_csv": str(issues_csv),
    }
