#!/usr/bin/env python3
"""
Unified solar PDF/DXF design parser (Qunitra + Hamadiya layouts).

Extracts strings, metadata, simple layout, design validation, and BOS/device labels.
Used by Solarica string-scan endpoints. CLI: ``run`` | ``step`` | ``frontend`` subcommands.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
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
TOKEN_RE = re.compile(r"[A-Za-z0-9_.+\-/°]+")
FLOAT_COORDS_RE = re.compile(r"(\d{1,2}\.\d+)\s*[Nn]\s+(\d{1,3}\.\d+)\s*[Ee]")
CAPACITY_KWP_RE = re.compile(r"Plant System Rating\s*[-:]\s*([\d,]+(?:\.\d+)?)\s*kW[pP]", re.I)
SYSTEM_CAPACITY_MW_RE = re.compile(r"System Capacity\s*[-:]\s*([\d,]+(?:\.\d+)?)\s*MW", re.I)
MODULES_TOTAL_RE = re.compile(r"Number of Modules\s*[-:]\s*([\d,]+)", re.I)
MODULES_PER_STRING_RE = re.compile(r"(\d+)\s*/\s*String", re.I)
QUNITRA_NAME_RE = re.compile(r"Qunitra-?FPV", re.I)
HAMADIYA_NAME_RE = re.compile(r"Hamadiya", re.I)
COUNTRY_RE = re.compile(r"Country\s*[-:]\s*([A-Za-z]+)", re.I)
REGION_RE = re.compile(r"Region\s*/\s*Province\s*[-:]\s*([A-Za-z]+)", re.I)
JINKO_610_RE = re.compile(r"TYPE\s+JKM615N66-HL4M-BDV\s*-\s*([\d,]+)", re.I)
JINKO_620_RE = re.compile(r"TYPE\s+JKM620N66-HL4M-BDV\s*-\s*([\d,]+)", re.I)
QUN_INVERTERS_RE = re.compile(r"String Inverter\s*[-:]\s*(\d+)\s*[Xx]\s*SG350HX", re.I)
QUN_BATT_RE = re.compile(r"Battery Storage\s*[-:]\s*(\d+)\s*[Xx]\s*SUNGROW\s*ST5015kWh", re.I)
QUN_PCS_RE = re.compile(r"PCS\s*[-:]\s*(\d+)\s*[Xx]\s*SUNGROW\s*MVS5140-LV", re.I)
QUN_MV_RE = re.compile(r"MVS SKID\s*[-:]\s*(\d+)\s*[Xx]\s*SUNGROW\s*MVS6400-LV", re.I)
HAM_MODULE_MODEL_RE = re.compile(r"Type of Module\s*/\s*Power\s*[-:]\s*(.+?580Wp)", re.I)
HAM_INVERTER_COUNT_RE = re.compile(r"Strings Inverters\s*[-:]\s*(\d+)\s*[Xx]\s*SUN\s*2000-330KTL", re.I)
HAM_BESS_TYPE_RE = re.compile(r"BESS type\s*[-:]\s*(\d+)\s*[Xx]\s*([\d.]+MWh.*?)\s*BESS", re.I)
HAM_BESS_KWH_RE = re.compile(r"BESS kWh BoL\s*[-:]\s*([\d,]+)\s*kWh", re.I)
HAM_BESS_INV_RE = re.compile(
    r"BESS INV\s*[-:]\s*(\d+)\s*[Xx]\s*\(\s*INV\+MV Trafo\s*\)\s*-\s*SMA\s*([\d.]+MVA)", re.I
)
HAM_TRANSFORMERS_RE = re.compile(r"Transformer/\s*Stands\s*[-:]\s*(\d+)\s*[Xx]\s*([\d,]+)kVA", re.I)
TRACKER_HINT_RE = re.compile(r"Rotation\s*-\s*\+\-?60\s*deg", re.I)
FLOATING_HINT_RE = re.compile(r"\bFPV\b", re.I)

# Device label patterns (drawing / BOS)
PTZ_RE = re.compile(r"^PTZ[-\s]?\d+$", re.I)
RADAR_RE = re.compile(r"RADAR", re.I)
CAB_RE = re.compile(r"^CAB[-\s]?\d+", re.I)
BESS_LABEL_RE = re.compile(r"^BESS\s+\d+\.\d+$", re.I)
MVS5140_LABEL_RE = re.compile(r"^MVS5140(?:-\d+)?$", re.I)
MVS6400_LABEL_RE = re.compile(r"^MVS6400(?:-\d+)?$", re.I)
MVPS_RE = re.compile(r"^MVPS-\d+$", re.I)
SCADA_RE = re.compile(r"^SCADA$", re.I)
PLC_RE = re.compile(r"^PLC$", re.I)
RMU_RE = re.compile(r"^RMU$", re.I)
ICB_RE = re.compile(r"^ICB.*$", re.I)
AUX_RE = re.compile(r"^AUX$", re.I)
BOARD_RE = re.compile(r"^Board$", re.I)
TRAFO_RE = re.compile(r"^TRAFO$", re.I)
TRANSFORMER_RE = re.compile(r"^Transformer", re.I)
WEATHER_RE = re.compile(r"^W\.S$", re.I)
POA_RE = re.compile(r"^POA$", re.I)
DISCONNECTOR_RE = re.compile(r"^Disconnector$", re.I)
INVERTER_WORD_RE = re.compile(r"^Inverter$", re.I)


@dataclass
class TextItem:
    text: str
    source_file: str
    page: int = 1
    x: Optional[float] = None
    y: Optional[float] = None
    page_width: Optional[float] = None
    page_height: Optional[float] = None


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
    page_width: Optional[float] = None
    page_height: Optional[float] = None

    @property
    def inverter_id(self) -> str:
        if self.site_pattern == "hamadiya":
            return f"{self.station}.{self.block_or_station}.{self.inverter}"
        return f"{self.station}.{self.inverter}"


def extract_pdf_items(path: Path) -> List[TextItem]:
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is required for PDF parsing")
    items: List[TextItem] = []
    with pdfplumber.open(str(path)) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            pw, ph = float(page.width), float(page.height)
            words = page.extract_words() or []
            if words:
                for w in words:
                    txt = (w.get("text") or "").strip()
                    if txt:
                        items.append(
                            TextItem(
                                txt,
                                path.name,
                                page_idx,
                                float(w.get("x0", 0.0)),
                                float(w.get("top", 0.0)),
                                pw,
                                ph,
                            )
                        )
            else:
                txt = page.extract_text() or ""
                for token in TOKEN_RE.findall(txt):
                    items.append(TextItem(token, path.name, page_idx, page_width=pw, page_height=ph))
    return items


def _ascii_dxf_scan(content: str, path: Path) -> List[TextItem]:
    return [
        TextItem(token, path.name)
        for token in TOKEN_RE.findall(content)
        if "." in token or token.startswith("S") or token.isalpha()
    ]


def extract_dxf_items(path: Path) -> List[TextItem]:
    if ezdxf is None:
        return _ascii_dxf_scan(path.read_text(encoding="utf-8", errors="ignore"), path)
    items: List[TextItem] = []
    try:
        doc = ezdxf.readfile(str(path))
        msp = doc.modelspace()
        for e in msp:
            t = e.dxftype()
            if t in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
                text = (getattr(e, "text", "") if t == "MTEXT" else getattr(e.dxf, "text", "")) or ""
                text = text.strip()
                if not text:
                    continue
                try:
                    ins = e.dxf.insert
                    x, y = float(ins[0]), float(ins[1])
                except Exception:
                    x = y = None
                for token in TOKEN_RE.findall(text):
                    items.append(TextItem(token, path.name, 1, x, y))
            elif t == "INSERT":
                for attrib in getattr(e, "attribs", []):
                    text = (attrib.dxf.text or "").strip()
                    if not text:
                        continue
                    try:
                        ins = attrib.dxf.insert
                        x, y = float(ins[0]), float(ins[1])
                    except Exception:
                        x = y = None
                    for token in TOKEN_RE.findall(text):
                        items.append(TextItem(token, path.name, 1, x, y))
        if items:
            return items
    except Exception:
        pass
    return _ascii_dxf_scan(path.read_text(encoding="utf-8", errors="ignore"), path)


def extract_items_from_file(path: Path) -> List[TextItem]:
    if path.suffix.lower() == ".pdf":
        return extract_pdf_items(path)
    if path.suffix.lower() == ".dxf":
        return extract_dxf_items(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def extract_joined_text(path: Path) -> str:
    """Space-joined tokens from the unified extractor (pattern detection, previews)."""
    return " ".join(i.text for i in extract_items_from_file(path))


def detect_site_pattern(items: List[TextItem]) -> str:
    qun = sum(1 for i in items if QUNITRA_STRING_RE.match(i.text))
    ham = sum(1 for i in items if HAMADIYA_STRING_RE.match(i.text))
    if qun == 0 and ham == 0:
        return "unknown"
    return "qunitra" if qun >= ham else "hamadiya"


def parse_valid_string(item: TextItem, pattern: str) -> Optional[ValidStringOccurrence]:
    if pattern == "qunitra":
        m = QUNITRA_STRING_RE.match(item.text)
        if not m:
            return None
        st, inv, s = map(int, m.groups())
        return ValidStringOccurrence(
            item.text,
            "qunitra",
            st,
            None,
            inv,
            s,
            item.source_file,
            item.page,
            item.x,
            item.y,
            item.page_width,
            item.page_height,
        )
    if pattern == "hamadiya":
        m = HAMADIYA_STRING_RE.match(item.text)
        if not m:
            return None
        st, block, inv, s = map(int, m.groups())
        return ValidStringOccurrence(
            item.text,
            "hamadiya",
            st,
            block,
            inv,
            s,
            item.source_file,
            item.page,
            item.x,
            item.y,
            item.page_width,
            item.page_height,
        )
    return None


def compute_metadata_warnings(metadata: Dict[str, object]) -> List[str]:
    warnings: List[str] = []
    design = metadata.get("design", {}) or {}
    d = design.get("plant_system_rating_kwp")
    c = design.get("calculated_dc_power_kwp")
    m = design.get("system_capacity_mw")
    if d is not None and c is not None and abs(float(d) - float(c)) > 0.5:
        warnings.append("Declared plant system rating differs from module-count calculation")
    if d is not None and m is not None and abs(float(d) / 1000 - float(m)) > 0.05:
        warnings.append("System capacity and plant system rating are not the same value")
    return warnings


def parse_project_metadata(items: List[TextItem], pattern: str) -> Dict[str, object]:
    joined = " ".join(i.text for i in items)
    site_name = (
        "Qunitra-FPV" if QUNITRA_NAME_RE.search(joined) else "Hamadiya" if HAMADIYA_NAME_RE.search(joined) else None
    )
    country = COUNTRY_RE.search(joined)
    region = REGION_RE.search(joined)
    coords = FLOAT_COORDS_RE.search(joined)
    design: Dict[str, object] = {}
    m = CAPACITY_KWP_RE.search(joined)
    if m:
        design["plant_system_rating_kwp"] = float(m.group(1).replace(",", ""))
    m = SYSTEM_CAPACITY_MW_RE.search(joined)
    if m:
        design["system_capacity_mw"] = float(m.group(1).replace(",", ""))
    m = MODULES_TOTAL_RE.search(joined)
    if m:
        design["modules_total"] = int(m.group(1).replace(",", ""))
    m = MODULES_PER_STRING_RE.search(joined)
    if m:
        design["modules_per_string_declared"] = int(m.group(1))
    installation: Dict[str, object] = {
        "primary_type": None,
        "mounting_type": None,
        "has_trackers": False,
        "confidence": None,
    }
    if FLOATING_HINT_RE.search(joined) or (site_name and "FPV" in site_name):
        installation.update(
            {"primary_type": "floating", "mounting_type": "fpv", "has_trackers": False, "confidence": 0.9}
        )
    if TRACKER_HINT_RE.search(joined):
        installation.update(
            {
                "primary_type": "utility_scale",
                "mounting_type": "single_axis_tracker",
                "has_trackers": True,
                "confidence": 0.93,
            }
        )
    if pattern == "qunitra":
        m610 = JINKO_610_RE.search(joined)
        m620 = JINKO_620_RE.search(joined)
        q610 = int(m610.group(1).replace(",", "")) if m610 else None
        q620 = int(m620.group(1).replace(",", "")) if m620 else None
        if q610 is not None or q620 is not None:
            models: List[Dict[str, object]] = []
            calc = 0.0
            if q610 is not None:
                models.append({"model": "JKM615N66-HL4M-BDV", "quantity": q610, "power_w": 610})
                calc += q610 * 610 / 1000
            if q620 is not None:
                models.append({"model": "JKM620N66-HL4M-BDV", "quantity": q620, "power_w": 620})
                calc += q620 * 620 / 1000
            design["module_models"] = models
            design["calculated_dc_power_kwp"] = round(calc, 4)
        m2 = QUN_INVERTERS_RE.search(joined)
        if m2:
            design["string_inverter_count"] = int(m2.group(1))
            design["string_inverter_model"] = "SG350HX"
        m2 = QUN_BATT_RE.search(joined)
        if m2:
            design["battery_count"] = int(m2.group(1))
            design["battery_model"] = "ST5015kWh"
        m2 = QUN_PCS_RE.search(joined)
        if m2:
            design["pcs_count"] = int(m2.group(1))
            design["pcs_model"] = "MVS5140-LV"
        m2 = QUN_MV_RE.search(joined)
        if m2:
            design["mv_skid_count"] = int(m2.group(1))
            design["mv_skid_model"] = "MVS6400-LV"
    elif pattern == "hamadiya":
        m2 = HAM_MODULE_MODEL_RE.search(joined)
        if m2:
            design["module_model"] = " ".join(m2.group(1).split())
        m2 = HAM_INVERTER_COUNT_RE.search(joined)
        if m2:
            design["string_inverter_count"] = int(m2.group(1))
            design["string_inverter_model"] = "SUN2000-330KTL"
        m2 = HAM_BESS_TYPE_RE.search(joined)
        if m2:
            design["battery_container_count"] = int(m2.group(1))
            design["battery_container_model"] = m2.group(2).strip()
        m2 = HAM_BESS_KWH_RE.search(joined)
        if m2:
            design["storage_capacity_kwh"] = int(m2.group(1).replace(",", ""))
        m2 = HAM_BESS_INV_RE.search(joined)
        if m2:
            design["bess_inv_count"] = int(m2.group(1))
            design["bess_inv_model"] = f"SMA {m2.group(2)}"
        m2 = HAM_TRANSFORMERS_RE.search(joined)
        if m2:
            design["transformer_count"] = int(m2.group(1))
            design["transformer_rating_kva"] = int(m2.group(2).replace(",", ""))
        if "modules_total" in design and "module_model" in design:
            pw_m = re.search(r"(\d+)\s*Wp", str(design["module_model"]), re.I)
            if pw_m:
                pw = int(pw_m.group(1))
                design["module_power_w"] = pw
                design["calculated_dc_power_kwp"] = round(float(design["modules_total"]) * pw / 1000, 4)

    metadata: Dict[str, object] = {
        "site_name": site_name,
        "country": country.group(1).upper() if country else None,
        "region": region.group(1).upper() if region else None,
        "coordinates": {"lat": float(coords.group(1)), "lon": float(coords.group(2))} if coords else None,
        "installation": installation,
        "design": design,
    }
    metadata["metadata_warnings"] = compute_metadata_warnings(metadata)
    return metadata


def extract_inverter_ids(items: List[TextItem], pattern: str, occs: List[ValidStringOccurrence]) -> List[str]:
    if pattern == "hamadiya":
        return sorted({o.inverter_id for o in occs}, key=lambda s: tuple(int(p) for p in s.split(".")))
    out = {o.inverter_id for o in occs}
    for item in items:
        m = QUNITRA_INVERTER_RE.fullmatch(item.text)
        if m:
            out.add(f"{int(m.group(1))}.{int(m.group(2))}")
    return sorted(out, key=lambda s: tuple(int(p) for p in s.split(".")))


def infer_expected_string_counts(
    items: List[TextItem], pattern: str, inverter_ids: List[str], per_inv: Dict[str, set]
) -> Dict[str, int]:
    expected: Dict[str, int] = {inv: max(nums) for inv, nums in per_inv.items() if nums}
    if pattern == "qunitra":
        for inv_id in inverter_ids:
            if inv_id in expected:
                continue
            st, inv = map(int, inv_id.split("."))
            if st == 1:
                if 1 <= inv <= 7:
                    expected[inv_id] = 21
                elif 8 <= inv <= 12:
                    expected[inv_id] = 20
                elif 13 <= inv <= 16:
                    expected[inv_id] = 21
                elif inv == 17:
                    expected[inv_id] = 22
            elif st == 2:
                if 1 <= inv <= 7:
                    expected[inv_id] = 21
                elif 8 <= inv <= 12:
                    expected[inv_id] = 20
                elif 13 <= inv <= 17:
                    expected[inv_id] = 22
    return expected


def infer_mppt_mapping(string_numbers: List[int], inverter_model: Optional[str]) -> Dict[str, object]:
    if not string_numbers:
        return {"mapping_mode": "none", "mppts": []}
    if inverter_model == "SG350HX":
        mppts: List[Dict[str, object]] = []
        idx = 0
        for n in range(1, 13):
            mppts.append({"mppt": n, "strings": string_numbers[idx : idx + 2]})
            idx += 2
        return {"mapping_mode": "sg350hx_default", "mppts": mppts}
    buckets: List[List[int]] = [[] for _ in range(min(6, max(1, math.ceil(len(string_numbers) / 2))))]
    for i, s in enumerate(string_numbers):
        buckets[i % len(buckets)].append(s)
    return {"mapping_mode": "generic_balanced", "mppts": [{"mppt": i + 1, "strings": b} for i, b in enumerate(buckets)]}


def compute_bbox_norm(
    points: List[Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]],
) -> Optional[Dict[str, float]]:
    clean = [(x, y, pw, ph) for x, y, pw, ph in points if x is not None and y is not None and pw and ph]
    if not clean:
        return None
    xs = [x / pw for x, _, pw, _ in clean]
    ys = [y / ph for _, y, _, ph in clean]
    return {"x": round(min(xs), 6), "y": round(min(ys), 6), "w": round(max(xs) - min(xs), 6), "h": round(max(ys) - min(ys), 6)}


def same_area_rule(points: List[Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]]) -> Dict[str, object]:
    clean = [(x, y) for x, y, _, _ in points if x is not None and y is not None]
    if len(clean) < 2:
        return {"status": "not_enough_geometry", "same_area": None, "cluster_count": None}
    xs = [p[0] for p in clean]
    ys = [p[1] for p in clean]
    spread = max(max(xs) - min(xs), max(ys) - min(ys))
    dists: List[float] = []
    for i, (x1, y1) in enumerate(clean):
        nearest: Optional[float] = None
        for j, (x2, y2) in enumerate(clean):
            if i == j:
                continue
            d = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
            nearest = d if nearest is None else min(nearest, d)
        if nearest is not None:
            dists.append(nearest)
    median_nn = statistics.median(dists) if dists else 0.0
    same = True if median_nn == 0 else spread <= 12 * median_nn
    return {
        "status": "ok" if same else "warning_split_area",
        "same_area": same,
        "cluster_count": 1 if same else 2,
    }


def build_simple_layout(per_occ: Dict[str, List[ValidStringOccurrence]]) -> Dict[str, object]:
    pages: Dict[int, Dict[str, List]] = defaultdict(lambda: {"inverters": [], "strings": []})
    for inv_id, occs in per_occ.items():
        page = occs[0].page if occs else 1
        points = [(o.x, o.y, o.page_width, o.page_height) for o in occs]
        bbox = compute_bbox_norm(points)
        if bbox:
            pages[page]["inverters"].append({"id": inv_id, "shape": "rectangle", **bbox})
        for o in occs:
            if o.x is not None and o.y is not None and o.page_width and o.page_height:
                pages[o.page]["strings"].append(
                    {
                        "id": o.raw,
                        "shape": "rectangle",
                        "x": round(o.x / o.page_width, 6),
                        "y": round(o.y / o.page_height, 6),
                        "w": 0.002,
                        "h": 0.008,
                        "inverter_id": inv_id,
                    }
                )
    return {
        "coordinate_system": "page_normalized_top_left",
        "pages": [{"page_number": p, **data} for p, data in sorted(pages.items())],
    }


def _pv_module_display_model(design: Dict[str, object]) -> Optional[str]:
    mm = design.get("module_model")
    if isinstance(mm, str) and mm.strip():
        return mm.strip()
    mmodels = design.get("module_models")
    if not isinstance(mmodels, list) or not mmodels:
        return None
    powers: set[int] = set()
    for m in mmodels:
        if isinstance(m, dict) and m.get("power_w") is not None:
            try:
                powers.add(int(m["power_w"]))
            except (TypeError, ValueError):
                pass
    if powers == {610, 620}:
        return "mixed Jinko 610/620W"
    if len(mmodels) == 1 and isinstance(mmodels[0], dict):
        mod = mmodels[0].get("model")
        pw = mmodels[0].get("power_w")
        if mod and pw:
            return f"{mod} ({pw} Wp)"
        return str(mod) if mod else None
    return "mixed PV modules"


def _device_row(
    category: str,
    quantity: int,
    source: str,
    *,
    model: Optional[str] = None,
) -> Dict[str, object]:
    row: Dict[str, object] = {"category": category, "quantity": quantity, "source": source}
    if model is not None:
        row["model"] = model
    return row


def extract_devices(
    items: List[TextItem],
    metadata: Dict[str, object],
    inverter_ids: List[str],
) -> Dict[str, object]:
    _ = inverter_ids
    joined = " ".join(i.text for i in items)
    token_counts = Counter(i.text for i in items)
    devices: List[Dict[str, object]] = []
    design = metadata.get("design", {}) or {}

    if design.get("string_inverter_count"):
        devices.append(
            _device_row(
                "string_inverter",
                int(design["string_inverter_count"]),
                "project_metadata",
                model=str(design["string_inverter_model"])
                if design.get("string_inverter_model")
                else None,
            )
        )
    if design.get("battery_count"):
        devices.append(
            _device_row(
                "battery_container",
                int(design["battery_count"]),
                "project_metadata",
                model=str(design["battery_model"]) if design.get("battery_model") else None,
            )
        )
    if design.get("pcs_count"):
        devices.append(
            _device_row(
                "pcs",
                int(design["pcs_count"]),
                "project_metadata",
                model=str(design["pcs_model"]) if design.get("pcs_model") else None,
            )
        )
    if design.get("mv_skid_count"):
        devices.append(
            _device_row(
                "mv_skid",
                int(design["mv_skid_count"]),
                "project_metadata",
                model=str(design["mv_skid_model"]) if design.get("mv_skid_model") else None,
            )
        )
    if design.get("transformer_count"):
        tr_model = (
            f"{design.get('transformer_rating_kva')}kVA transformer"
            if design.get("transformer_rating_kva")
            else None
        )
        devices.append(
            _device_row(
                "transformer",
                int(design["transformer_count"]),
                "project_metadata",
                model=tr_model,
            )
        )
    if design.get("bess_inv_count"):
        devices.append(
            _device_row(
                "bess_inverter",
                int(design["bess_inv_count"]),
                "project_metadata",
                model=str(design["bess_inv_model"]) if design.get("bess_inv_model") else None,
            )
        )
    if design.get("modules_total"):
        pm = _pv_module_display_model(design)
        devices.append(
            _device_row(
                "pv_module",
                int(design["modules_total"]),
                "project_metadata",
                model=pm,
            )
        )

    ptz = sum(token_counts[t] for t in token_counts if PTZ_RE.match(t))
    if ptz:
        devices.append(_device_row("ptz_camera", ptz, "drawing_labels"))
    radar = sum(token_counts[t] for t in token_counts if RADAR_RE.search(t) or CAB_RE.search(t))
    if radar:
        devices.append(_device_row("radar_cabinet", radar, "drawing_labels"))
    bess_labels = sum(token_counts[t] for t in token_counts if BESS_LABEL_RE.match(t))
    if bess_labels:
        devices.append(_device_row("bess_block_label", bess_labels, "drawing_labels"))
    mvs5140_labels = sum(token_counts[t] for t in token_counts if MVS5140_LABEL_RE.match(t))
    if mvs5140_labels:
        devices.append(_device_row("pcs_label", mvs5140_labels, "drawing_labels", model="MVS5140"))
    mvs6400_labels = sum(token_counts[t] for t in token_counts if MVS6400_LABEL_RE.match(t))
    if mvs6400_labels:
        devices.append(_device_row("mv_skid_label", mvs6400_labels, "drawing_labels", model="MVS6400"))
    mvps_labels = sum(token_counts[t] for t in token_counts if MVPS_RE.match(t))
    if mvps_labels:
        devices.append(_device_row("mv_power_station", mvps_labels, "drawing_labels"))
    if any(SCADA_RE.match(t) for t in token_counts):
        devices.append(_device_row("scada", 1, "drawing_labels"))
    if any(PLC_RE.match(t) for t in token_counts):
        devices.append(_device_row("plc", 1, "drawing_labels"))
    if any(RMU_RE.match(t) for t in token_counts):
        devices.append(_device_row("rmu", 1, "drawing_labels"))
    if any(ICB_RE.match(t) for t in token_counts):
        devices.append(
            _device_row(
                "icb_area",
                sum(token_counts[t] for t in token_counts if ICB_RE.match(t)),
                "drawing_labels",
            )
        )
    if any(AUX_RE.match(t) for t in token_counts):
        devices.append(
            _device_row(
                "aux",
                sum(token_counts[t] for t in token_counts if AUX_RE.match(t)),
                "drawing_labels",
            )
        )
    if any(BOARD_RE.match(t) for t in token_counts):
        devices.append(
            _device_row(
                "board",
                sum(token_counts[t] for t in token_counts if BOARD_RE.match(t)),
                "drawing_labels",
            )
        )
    if any(TRAFO_RE.match(t) for t in token_counts) or any(TRANSFORMER_RE.match(t) for t in token_counts):
        devices.append(_device_row("trafo", 1, "drawing_labels"))
    if "MV" in joined and "Room" in joined:
        devices.append(_device_row("mv_room", 1, "drawing_labels"))
    if any(POA_RE.match(t) for t in token_counts):
        devices.append(
            _device_row(
                "poa_sensor",
                sum(token_counts[t] for t in token_counts if POA_RE.match(t)),
                "drawing_labels",
            )
        )
    if any(WEATHER_RE.match(t) for t in token_counts):
        devices.append(
            _device_row(
                "weather_station",
                sum(token_counts[t] for t in token_counts if WEATHER_RE.match(t)),
                "drawing_labels",
            )
        )
    if any(DISCONNECTOR_RE.match(t) for t in token_counts):
        devices.append(
            _device_row(
                "disconnector_symbol",
                sum(token_counts[t] for t in token_counts if DISCONNECTOR_RE.match(t)),
                "drawing_labels",
            )
        )
    if any(INVERTER_WORD_RE.match(t) for t in token_counts):
        devices.append(
            _device_row(
                "inverter_symbol",
                sum(token_counts[t] for t in token_counts if INVERTER_WORD_RE.match(t)),
                "drawing_labels",
            )
        )

    categories: Dict[str, int] = defaultdict(int)
    for d in devices:
        categories[str(d["category"])] += int(d.get("quantity") or 0)

    return {
        "devices": devices,
        "device_summary": dict(sorted(categories.items())),
    }


def validate_output(metadata: Dict[str, object], valid_total: int) -> Dict[str, object]:
    design = metadata.get("design", {}) or {}
    result: Dict[str, object] = {
        "declared_dc_power_kwp": design.get("plant_system_rating_kwp"),
        "calculated_dc_power_kwp": design.get("calculated_dc_power_kwp"),
        "declared_modules": design.get("modules_total"),
        "declared_modules_per_string": design.get("modules_per_string_declared"),
        "calculated_strings": valid_total,
        "power_match": None,
        "strings_match": None,
        "status": "unknown",
        "warnings": [],
    }
    if result["declared_dc_power_kwp"] is not None and result["calculated_dc_power_kwp"] is not None:
        result["power_match"] = abs(float(result["declared_dc_power_kwp"]) - float(result["calculated_dc_power_kwp"])) <= 0.5
    if result["declared_modules"] is not None and result["declared_modules_per_string"] is not None:
        ds = int(result["declared_modules"]) / int(result["declared_modules_per_string"])
        result["declared_strings"] = ds
        result["strings_match"] = abs(ds - valid_total) < 0.001
    pm, sm = result.get("power_match"), result.get("strings_match")
    if pm is True and sm is True:
        result["status"] = "ok"
    elif pm is False or sm is False:
        result["status"] = "mismatch"
    else:
        result["status"] = "partial"
    return result


def build_compact_parse_report(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Human-oriented slice matching the documented parse preview shape
    (metadata, summary, devices, strings without large example lists, slim per-inverter, core validation flags).
    """
    dv = report.get("design_validation") or {}
    dv_out = {
        "power_match": dv.get("power_match"),
        "strings_match": dv.get("strings_match"),
        "status": dv.get("status"),
    }
    str_b = report.get("strings") or {}
    strings_out: Dict[str, Any] = {
        "valid_total": str_b.get("valid_total"),
        "invalid_total": str_b.get("invalid_total"),
        "invalid_examples": list(str_b.get("invalid_examples") or []),
    }
    per_full = report.get("per_inverter") or {}
    per_out: Dict[str, Any] = {}
    for inv_id, v in per_full.items():
        if not isinstance(v, dict):
            continue
        slim: Dict[str, Any] = {
            "expected_count": v.get("expected_count"),
            "string_count": v.get("string_count"),
        }
        if v.get("missing"):
            slim["missing"] = v["missing"]
        if v.get("duplicates"):
            slim["duplicates"] = v["duplicates"]
        sp = v.get("spatial") or {}
        slim["spatial"] = {"status": sp.get("status"), "same_area": sp.get("same_area")}
        per_out[inv_id] = slim
    return {
        "project_metadata": report.get("project_metadata"),
        "summary": report.get("summary"),
        "devices": report.get("devices"),
        "device_summary": report.get("device_summary"),
        "duplicates": report.get("duplicates"),
        "missing": report.get("missing"),
        "strings": strings_out,
        "per_inverter": per_out,
        "design_validation": dv_out,
    }


def run_full(paths: List[Path]) -> Dict[str, Any]:
    items: List[TextItem] = []
    for p in paths:
        items.extend(extract_items_from_file(p))
    pattern = detect_site_pattern(items)
    metadata = parse_project_metadata(items, pattern)
    valid_occ: List[ValidStringOccurrence] = []
    invalid: List[str] = []
    for item in items:
        occ = parse_valid_string(item, pattern)
        if occ:
            valid_occ.append(occ)
        elif item.text.startswith("S") or "." in item.text:
            invalid.append(item.text)
    exact_dups = {k: v for k, v in Counter(o.raw for o in valid_occ).items() if v > 1}
    unique_valid = sorted({o.raw for o in valid_occ})
    per_inv_nums: Dict[str, set] = defaultdict(set)
    per_inv_occ: Dict[str, List[ValidStringOccurrence]] = defaultdict(list)
    for o in valid_occ:
        per_inv_nums[o.inverter_id].add(o.string_no)
        per_inv_occ[o.inverter_id].append(o)
    inverter_ids = extract_inverter_ids(items, pattern, valid_occ)
    expected = infer_expected_string_counts(items, pattern, inverter_ids, per_inv_nums)
    inv_model = (metadata.get("design", {}) or {}).get("string_inverter_model")
    per_inverter: Dict[str, Any] = {}
    for inv_id in inverter_ids:
        nums = sorted(per_inv_nums.get(inv_id, set()))
        expected_count = expected.get(inv_id)
        expected_numbers = (
            list(range(1, expected_count + 1))
            if expected_count is not None
            else list(range(1, max(nums) + 1)) if nums else []
        )
        missing = [n for n in expected_numbers if n not in set(nums)]
        dups = sorted({o.raw for o in per_inv_occ.get(inv_id, []) if o.raw in exact_dups})
        occs = per_inv_occ.get(inv_id, [])
        points = [(o.x, o.y, o.page_width, o.page_height) for o in occs]
        area = same_area_rule(points)
        per_inverter[inv_id] = {
            "expected_count": expected_count,
            "string_count": len(nums),
            "strings": nums,
            "missing": missing,
            "duplicates": dups,
            "mppt_mapping": infer_mppt_mapping(nums, inv_model if isinstance(inv_model, str) else None),
            "spatial": {**area, "bbox_norm": compute_bbox_norm(points)},
            "invalid_labels_related": [],
        }

    devices_block = extract_devices(items, metadata, inverter_ids)

    full: Dict[str, Any] = {
        "project_metadata": metadata,
        "naming_patterns": {
            "string_pattern": "S.<station>.<inverter>.<string>"
            if pattern == "qunitra"
            else "S<station>.<block>.<inverter>.<string>"
            if pattern == "hamadiya"
            else None,
            "inverter_pattern": "<station>.<inverter>"
            if pattern == "qunitra"
            else "<station>.<block>.<inverter>"
            if pattern == "hamadiya"
            else None,
            "strict_single_pattern": True,
        },
        "summary": {
            "site_pattern": pattern,
            "inverters_total": len(inverter_ids),
            "valid_total": len(unique_valid),
            "invalid_total": len(invalid),
            "exact_duplicates_total": len(exact_dups),
            "missing_strings_total": sum(len(v["missing"]) for v in per_inverter.values()),
            "device_categories_total": len(devices_block["device_summary"]),
        },
        "inverters": inverter_ids,
        "strings": {
            "valid_total": len(unique_valid),
            "valid_examples": unique_valid[:20],
            "invalid_total": len(invalid),
            "invalid_examples": sorted(set(invalid))[:100],
        },
        "devices": devices_block["devices"],
        "device_summary": devices_block["device_summary"],
        "duplicates": exact_dups,
        "missing": {inv_id: data["missing"] for inv_id, data in per_inverter.items() if data["missing"]},
        "per_inverter": per_inverter,
        "design_validation": validate_output(metadata, len(unique_valid)),
        "simple_layout": build_simple_layout(per_inv_occ),
        "db_ui_export": {
            "project_metadata": metadata,
            "inverters": [{"id": inv_id, **data} for inv_id, data in per_inverter.items()],
            "valid_strings": unique_valid,
            "invalid_strings": sorted(set(invalid)),
            "devices": devices_block["devices"],
            "device_summary": devices_block["device_summary"],
        },
    }
    full["compact"] = build_compact_parse_report(full)
    return full


def parse_files(paths: List[Path]) -> Dict[str, Any]:
    """Backward-compatible alias for :func:`run_full`."""
    return run_full(paths)


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
    site_pattern = (report.get("summary") or {}).get("site_pattern") or report.get("site_pattern") or "unknown"
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
        isinstance(v, dict)
        and (v.get("spatial") or {}).get("status") in ("failed_split_area", "warning_split_area")
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


def cmd_run(args: argparse.Namespace) -> int:
    report = run_full([Path(p) for p in args.files])
    out_obj: Dict[str, Any] = report["compact"] if getattr(args, "compact", False) else report
    text = json.dumps(out_obj, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
        print(f"Wrote {args.json_out}", file=sys.stderr)
    else:
        print(text)
    return 0


def cmd_step(args: argparse.Namespace) -> int:
    report = run_full([Path(p) for p in args.files])
    mapping: Dict[str, Any] = {
        "metadata": report["project_metadata"],
        "strings": {
            "summary": report["summary"],
            "strings": report["strings"],
            "duplicates": report["duplicates"],
            "missing": report["missing"],
        },
        "inverters": {"inverters": report["inverters"], "per_inverter": report["per_inverter"]},
        "layout": report["simple_layout"],
        "devices": {"devices": report["devices"], "device_summary": report["device_summary"]},
        "validation": report["design_validation"],
        "compact": report["compact"],
        "full": report,
    }
    out = mapping.get(args.step.lower(), report)
    text = json.dumps(out, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
        print(f"Wrote {args.json_out}", file=sys.stderr)
    else:
        print(text)
    return 0


def cmd_frontend(args: argparse.Namespace) -> int:
    """Solarica UI summary JSON (optional --include-engine-report)."""
    report = run_full([Path(p) for p in args.files])
    output = to_frontend_parse_report(report, include_engine_report=args.include_engine_report)
    text = json.dumps(output, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
        print(f"Wrote {args.json_out}", file=sys.stderr)
    else:
        print(text)
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Strict solar PDF/DXF parser with device extraction")
    sub = p.add_subparsers(dest="command", required=True)
    pr = sub.add_parser("run", help="Full JSON report (use --compact for documented preview shape)")
    pr.add_argument("files", nargs="+")
    pr.add_argument("--json-out")
    pr.add_argument(
        "--compact",
        action="store_true",
        help="Emit only the compact block (sample preview: slim strings, per_inverter, design_validation)",
    )
    pr.set_defaults(func=cmd_run)
    ps = sub.add_parser("step", help="Emit one slice of the report")
    ps.add_argument(
        "--step",
        required=True,
        choices=["metadata", "strings", "inverters", "layout", "devices", "validation", "compact", "full"],
    )
    ps.add_argument("files", nargs="+")
    ps.add_argument("--json-out")
    ps.set_defaults(func=cmd_step)
    pf = sub.add_parser("frontend", help="Frontend StructuredParseReport shape")
    pf.add_argument("files", nargs="+")
    pf.add_argument("--json-out")
    pf.add_argument(
        "--include-engine-report",
        action="store_true",
        help="Include full run_full JSON under strict_engine_report",
    )
    pf.set_defaults(func=cmd_frontend)
    return p


def main() -> int:
    argv = list(sys.argv[1:])
    if len(argv) >= 2 and argv[0] == "-m":
        argv = argv[2:]
    if argv and argv[0] not in ("run", "step", "frontend"):
        argv = ["run", *argv]
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())
