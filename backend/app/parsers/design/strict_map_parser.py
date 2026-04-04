#!/usr/bin/env python3
"""
Strict solar map parser for PDF and DXF.

Rules:
- Each site has exactly one valid string pattern.
- For Qunitra-style labels, only `S.<station>.<inverter>.<string>` is valid.
- Non-matching labels such as `2.2.2.5.1A` are INVALID, not aliases.
- Duplicate detection is based only on exact valid string occurrences.
- Missing strings are computed after global merge per inverter.
- Supports PDF text extraction and DXF text extraction.

CLI (repo layout):
  python -m app.parsers.design.strict_map_parser file1.pdf --json-out report.json

Python API:
  from app.parsers.design.strict_map_parser import parse_files, to_frontend_parse_report
  raw = parse_files([Path("a.pdf")])
  ui = to_frontend_parse_report(raw, site_name="Qunitra-FPV", country="Israel", region="North",
                                lat=33.13062, lon=35.81224)

Also importable for FastAPI routes or subprocess wrappers.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Optional dependencies
try:
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover
    pdfplumber = None

try:
    import ezdxf  # type: ignore
except Exception:  # pragma: no cover
    ezdxf = None


QUNITRA_STRING_RE = re.compile(r"^S\.(\d+)\.(\d+)\.(\d+)$")
HAMADIYA_STRING_RE = re.compile(r"^S(\d+)\.(\d+)\.(\d+)\.(\d+)$")
QUNITRA_INVERTER_RE = re.compile(r"(?<![\d.])(\d+)\.(\d+)(?![\d.])")

TOKEN_RE = re.compile(r"[A-Za-z0-9_.-]+")


@dataclass
class TextItem:
    text: str
    source_file: str
    page: int = 1
    x: Optional[float] = None
    y: Optional[float] = None


@dataclass
class ValidStringOccurrence:
    raw: str
    site_pattern: str
    station: int
    block_or_station: Optional[int]
    inverter: int
    string_no: int
    source_file: str
    page: int
    x: Optional[float]
    y: Optional[float]

    @property
    def inverter_id(self) -> str:
        if self.site_pattern == "hamadiya":
            return f"{self.station}.{self.block_or_station}.{self.inverter}"
        return f"{self.station}.{self.inverter}"


def extract_pdf_items(path: Path) -> List[TextItem]:
    items: List[TextItem] = []
    if pdfplumber is None:
        return items
    with pdfplumber.open(str(path)) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            try:
                words = page.extract_words() or []
                for w in words:
                    txt = (w.get("text") or "").strip()
                    if txt:
                        items.append(
                            TextItem(
                                text=txt,
                                source_file=path.name,
                                page=page_idx,
                                x=float(w.get("x0", 0.0)),
                                y=float(w.get("top", 0.0)),
                            )
                        )
            except Exception:
                txt = page.extract_text() or ""
                for token in TOKEN_RE.findall(txt):
                    items.append(TextItem(text=token, source_file=path.name, page=page_idx))
    return items


def _ascii_dxf_scan(content: str, path: Path) -> List[TextItem]:
    items: List[TextItem] = []
    for token in TOKEN_RE.findall(content):
        if "." in token or token.startswith("S"):
            items.append(TextItem(text=token, source_file=path.name, page=1))
    return items


def _dxf_entity_text(entity: Any) -> str:
    dxftype = entity.dxftype()
    if dxftype == "MTEXT":
        plain = getattr(entity, "plain_text", None)
        if callable(plain):
            return (plain() or "").strip()
        return (getattr(entity, "text", None) or "").strip()
    return (entity.dxf.text or "").strip()


def extract_dxf_items(path: Path) -> List[TextItem]:
    items: List[TextItem] = []
    if ezdxf is not None:
        try:
            doc = ezdxf.readfile(str(path))
            msp = doc.modelspace()
            for e in msp:
                dxftype = e.dxftype()
                if dxftype in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
                    text = _dxf_entity_text(e) if dxftype == "MTEXT" else (e.dxf.text or "").strip()
                    if text:
                        try:
                            insert = e.dxf.insert
                            x, y = float(insert[0]), float(insert[1])
                        except Exception:
                            x = y = None
                        for token in TOKEN_RE.findall(text):
                            items.append(TextItem(token, path.name, 1, x, y))
                elif dxftype == "INSERT":
                    for attrib in getattr(e, "attribs", []):
                        text = (attrib.dxf.text or "").strip()
                        if text:
                            try:
                                insert = attrib.dxf.insert
                                x, y = float(insert[0]), float(insert[1])
                            except Exception:
                                x = y = None
                            for token in TOKEN_RE.findall(text):
                                items.append(TextItem(token, path.name, 1, x, y))
            if items:
                return items
        except Exception:
            pass

    content = path.read_text(encoding="utf-8", errors="ignore")
    return _ascii_dxf_scan(content, path)


def extract_items_from_file(path: Path) -> List[TextItem]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_pdf_items(path)
    if suffix == ".dxf":
        return extract_dxf_items(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def detect_site_pattern(items: List[TextItem]) -> str:
    qunitra_hits = 0
    hamadiya_hits = 0
    for item in items:
        if QUNITRA_STRING_RE.match(item.text):
            qunitra_hits += 1
        if HAMADIYA_STRING_RE.match(item.text):
            hamadiya_hits += 1
    if qunitra_hits == 0 and hamadiya_hits == 0:
        return "unknown"
    return "qunitra" if qunitra_hits >= hamadiya_hits else "hamadiya"


def parse_valid_string(item: TextItem, pattern: str) -> Optional[ValidStringOccurrence]:
    if pattern == "qunitra":
        m = QUNITRA_STRING_RE.match(item.text)
        if not m:
            return None
        st, inv, s = map(int, m.groups())
        return ValidStringOccurrence(
            raw=item.text,
            site_pattern="qunitra",
            station=st,
            block_or_station=None,
            inverter=inv,
            string_no=s,
            source_file=item.source_file,
            page=item.page,
            x=item.x,
            y=item.y,
        )
    if pattern == "hamadiya":
        m = HAMADIYA_STRING_RE.match(item.text)
        if not m:
            return None
        st, block, inv, s = map(int, m.groups())
        return ValidStringOccurrence(
            raw=item.text,
            site_pattern="hamadiya",
            station=st,
            block_or_station=block,
            inverter=inv,
            string_no=s,
            source_file=item.source_file,
            page=item.page,
            x=item.x,
            y=item.y,
        )
    return None


def extract_inverter_ids(items: List[TextItem], pattern: str) -> List[str]:
    out: set[str] = set()
    if pattern == "qunitra":
        for item in items:
            token = item.text
            m = QUNITRA_INVERTER_RE.fullmatch(token)
            if m:
                out.add(f"{int(m.group(1))}.{int(m.group(2))}")
    return sorted(out, key=lambda s: tuple(int(p) for p in s.split(".")))


def compute_bbox(points: List[Tuple[float, float]]) -> Optional[Dict[str, float]]:
    clean = [(x, y) for x, y in points if x is not None and y is not None]
    if not clean:
        return None
    xs = [p[0] for p in clean]
    ys = [p[1] for p in clean]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    return {"x": min_x, "y": min_y, "w": max_x - min_x, "h": max_y - min_y}


def same_area_rule(points: List[Tuple[float, Optional[float]]], threshold_multiplier: float = 3.0) -> Dict[str, Any]:
    clean = [(x, y) for x, y in points if x is not None and y is not None]
    if len(clean) < 2:
        return {"status": "not_enough_geometry", "same_area": None, "cluster_count": None}

    xs = [p[0] for p in clean]
    ys = [p[1] for p in clean]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)

    clean_sorted = sorted(clean)
    dists: List[float] = []
    for i, (x1, y1) in enumerate(clean_sorted):
        nearest: Optional[float] = None
        for j, (x2, y2) in enumerate(clean_sorted):
            if i == j:
                continue
            d = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
            nearest = d if nearest is None else min(nearest, d)
        if nearest is not None:
            dists.append(nearest)
    median_nn = sorted(dists)[len(dists) // 2] if dists else 0.0
    spread = max(width, height)

    if median_nn == 0:
        same_area = True
    else:
        same_area = spread <= threshold_multiplier * median_nn * max(3, len(clean) ** 0.5)

    return {
        "status": "ok" if same_area else "failed_split_area",
        "same_area": same_area,
        "cluster_count": 1 if same_area else 2,
        "bbox": compute_bbox(clean),
    }


def parse_files(paths: List[Path]) -> Dict[str, Any]:
    items: List[TextItem] = []
    for p in paths:
        items.extend(extract_items_from_file(p))

    site_pattern = detect_site_pattern(items)

    valid_occurrences: List[ValidStringOccurrence] = []
    invalid_labels: List[str] = []
    for item in items:
        occ = parse_valid_string(item, site_pattern)
        if occ is not None:
            valid_occurrences.append(occ)
        else:
            if item.text.startswith("S") or "." in item.text:
                invalid_labels.append(item.text)

    exact_duplicate_counts = {
        s: c for s, c in Counter(o.raw for o in valid_occurrences).items() if c > 1
    }

    unique_valid_strings = sorted({o.raw for o in valid_occurrences})
    invalid_unique = sorted(set(invalid_labels))

    per_inverter_numbers: Dict[str, set] = defaultdict(set)
    per_inverter_points: Dict[str, List[Tuple[Optional[float], Optional[float]]]] = defaultdict(list)
    for o in valid_occurrences:
        per_inverter_numbers[o.inverter_id].add(o.string_no)
        per_inverter_points[o.inverter_id].append((o.x, o.y))

    per_inverter: Dict[str, Any] = {}
    for inv_id in sorted(per_inverter_numbers.keys(), key=lambda s: tuple(int(p) for p in s.split("."))):
        nums = sorted(per_inverter_numbers[inv_id])
        expected = list(range(1, max(nums) + 1)) if nums else []
        missing = [n for n in expected if n not in per_inverter_numbers[inv_id]]
        duplicates_for_inverter = sorted(
            {
                o.raw
                for o in valid_occurrences
                if o.inverter_id == inv_id and exact_duplicate_counts.get(o.raw)
            }
        )
        spatial = same_area_rule(per_inverter_points[inv_id])
        per_inverter[inv_id] = {
            "string_count": len(nums),
            "strings": nums,
            "missing": missing,
            "duplicates": duplicates_for_inverter,
            "spatial": spatial,
        }

    inv_ids_list = (
        extract_inverter_ids(items, site_pattern) if site_pattern == "qunitra" else sorted(per_inverter.keys())
    )

    return {
        "site_pattern": site_pattern,
        "summary": {
            "valid_total": len(set(unique_valid_strings)),
            "invalid_total": len(invalid_unique),
            "exact_duplicates_total": len(exact_duplicate_counts),
            "inverters_total": len(per_inverter),
        },
        "inverters": inv_ids_list,
        "strings": {
            "valid_total": len(set(unique_valid_strings)),
            "valid_examples": unique_valid_strings[:10],
            "invalid_total": len(invalid_unique),
            "invalid_examples": invalid_unique[:50],
        },
        "duplicates": exact_duplicate_counts,
        "missing": {inv_id: data["missing"] for inv_id, data in per_inverter.items() if data["missing"]},
        "per_inverter": per_inverter,
        "db_ui_export": {
            "site_pattern": site_pattern,
            "inverters": [{"id": inv_id, **data} for inv_id, data in per_inverter.items()],
            "valid_strings": unique_valid_strings,
            "invalid_strings": invalid_unique,
        },
    }


def to_frontend_parse_report(
    report: Dict[str, Any],
    *,
    site_name: Optional[str] = None,
    installation_type: Optional[str] = None,
    country: Optional[str] = None,
    region: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    include_engine_report: bool = False,
) -> Dict[str, Any]:
    """
    Map `parse_files` output to the compact JSON shape consumed by the Solarica frontend
    (see StructuredParseReport + extractStructuredParseReport).
    """
    site_pattern = report.get("site_pattern") or "unknown"
    patterns: Dict[str, Any] = {
        "mode": "strict_single_pattern",
    }
    if site_pattern == "qunitra":
        patterns["valid_string_pattern"] = "S.<station>.<inverter>.<string>"
        patterns["valid_inverter_pattern"] = "<station>.<inverter>"
    elif site_pattern == "hamadiya":
        patterns["valid_string_pattern"] = "S<station>.<block>.<inverter>.<string>"
        patterns["valid_inverter_pattern"] = "<station>.<block>.<inverter>"
    else:
        patterns["valid_string_pattern"] = None
        patterns["valid_inverter_pattern"] = None

    strings_block = report.get("strings") or {}
    summary = report.get("summary") or {}
    dup_raw = report.get("duplicates") or {}
    missing = {k: v for k, v in (report.get("missing") or {}).items() if v}
    inv_list = list(report.get("inverters") or [])

    invalid_n = int(strings_block.get("invalid_total", summary.get("invalid_total", 0)))
    missing_any = bool(missing)
    dup_any = bool(dup_raw)
    per = report.get("per_inverter") or {}
    spatial_failed = any(
        isinstance(v, dict) and (v.get("spatial") or {}).get("status") == "failed_split_area"
        for v in per.values()
    )
    not_enough = any(
        isinstance(v, dict) and (v.get("spatial") or {}).get("status") == "not_enough_geometry"
        for v in per.values()
    )

    if spatial_failed:
        spatial_status = "failed"
        spatial_reason = "String labels for at least one inverter span disjoint drawing areas."
    elif not_enough or not per:
        spatial_status = "pending"
        spatial_reason = "needs coordinate clustering from PDF/DXF"
    else:
        spatial_status = "ok"
        spatial_reason = None

    final_status = "ok"
    if invalid_n or missing_any or dup_any or site_pattern == "unknown":
        final_status = "needs_cleanup"

    site: Dict[str, Any] = {}
    if site_name:
        site["name"] = site_name
    if installation_type:
        site["installation_type"] = installation_type
    if country:
        site["country"] = country
    if region:
        site["region"] = region
    if lat is not None or lon is not None:
        site["coordinates"] = {"lat": lat, "lon": lon}

    out: Dict[str, Any] = {
        "site": site,
        "patterns": patterns,
        "inverters": {
            "total": len(inv_list),
            "present": inv_list,
            "status": "ok" if inv_list and site_pattern != "unknown" else ("unknown" if site_pattern == "unknown" else "ok"),
        },
        "strings": {
            "valid_total": strings_block.get("valid_total", summary.get("valid_total")),
            "invalid_total": invalid_n,
            "invalid_examples": strings_block.get("invalid_examples", [])[:20],
        },
        "duplicates": {"exact": dup_raw} if dup_raw else {"exact": {}},
        "missing": missing,
        "spatial_validation": {
            "status": spatial_status,
            "reason": spatial_reason,
        },
        "final_status": final_status,
    }
    if include_engine_report:
        out["strict_engine_report"] = report
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict solar PDF/DXF parser")
    parser.add_argument("files", nargs="+", help="PDF and/or DXF files")
    parser.add_argument("--json-out", help="Write JSON report to this file")
    parser.add_argument(
        "--frontend-shape",
        action="store_true",
        help="Emit Solarica UI parse-summary shape (site / patterns / strings / â€¦)",
    )
    parser.add_argument(
        "--include-engine-report",
        action="store_true",
        help="With --frontend-shape, nest full engine JSON under strict_engine_report",
    )
    args = parser.parse_args()

    paths = [Path(p) for p in args.files]
    engine_report = parse_files(paths)
    if args.frontend_shape:
        output = to_frontend_parse_report(
            engine_report,
            include_engine_report=args.include_engine_report,
        )
    else:
        output = engine_report

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(f"Wrote {out_path}", file=sys.stderr)
    else:
        print(json.dumps(output, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
