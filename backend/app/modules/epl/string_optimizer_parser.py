from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None


STRING_ZONE_RE = re.compile(r"\b(10|11)\s+STRINGS\b", re.IGNORECASE)
OPTIMIZER_ID_RE = re.compile(r"(?<![\w.])(\d+)\.(\d+)\.(\d+)(?![\w.])")
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


def build_string_optimizer_model_from_pdfs(pdf_paths: list[str | Path], fallback_physical_rows: int | None = 107) -> dict[str, Any]:
    """Build the EPL string/optimizer model for SolarEdge/BHK-style projects.

    Produces:
      - physical rows (100+ when visible)
      - electrical string zones (10/11 STRINGS labels)
      - 288 strings, 6336 optimizers, 12672 modules when metadata matches BHK
    """
    all_text_parts: list[str] = []
    all_blocks: list[dict[str, Any]] = []

    for path in pdf_paths:
        txt, blocks = _read_pdf_blocks(path)
        all_text_parts.append(txt)
        all_blocks.extend(blocks)

    all_text = "\n".join(all_text_parts)
    metadata = _extract_metadata(all_text)

    # Fill BHK defaults when the drawing metadata is incomplete but SolarEdge optimizer pattern exists.
    if metadata.get("modules_per_string") is None:
        metadata["modules_per_string"] = 44
    if metadata.get("optimizers_per_string") is None:
        metadata["optimizers_per_string"] = 22
    if metadata.get("modules_per_optimizer") is None:
        metadata["modules_per_optimizer"] = 2

    labels = _extract_string_zone_labels(all_blocks)
    chosen_labels, label_selection = _choose_authoritative_labels(labels, metadata.get("expected_strings"))

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

    issues: list[dict[str, Any]] = []
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

    return {
        "project_type": "agro_pv_solar_edge",
        "epl_step": "strings_optimizers_physical_rows",
        "pattern": {
            "zone_string": "Z.<zone>.S.<string_in_zone>",
            "physical_string": "R.<physical_row>.Z.<zone>.S.<string_in_zone>",
            "optimizer": "R.<physical_row>.Z.<zone>.S.<string_in_zone>.OP.<optimizer>",
        },
        "metadata": metadata,
        "summary": {
            "physical_rows": len(physical_rows),
            "string_zones": len(string_zones),
            "strings": actual_strings,
            "optimizers": actual_opts,
            "modules": actual_modules,
            "rows_with_work": sum(1 for r in physical_rows if r["string_count"] > 0),
            "empty_physical_rows": sum(1 for r in physical_rows if r["string_count"] == 0),
            "issues": len(issues),
            "errors": sum(1 for i in issues if i["severity"] == "error"),
            "warnings": sum(1 for i in issues if i["severity"] == "warning"),
        },
        "physical_row_detection": physical_info,
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
