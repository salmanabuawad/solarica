"""
Electrical and site metadata extraction from Nextracker construction + ramming PDFs.

Read-only scan — designed to NOT touch the pier/tracker extraction pipeline.
All returned values can be None if not found.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import fitz


def _next_nonempty(lines: list, start_idx: int, max_lookahead: int = 4) -> Optional[str]:
    for j in range(start_idx + 1, min(start_idx + 1 + max_lookahead, len(lines))):
        val = lines[j].strip()
        if val:
            return val
    return None


def _label_value(lines: list, label: str) -> Optional[str]:
    """Find a line containing the label and return the next non-empty line."""
    upper_label = label.upper()
    for i, line in enumerate(lines):
        if upper_label in line.upper():
            return _next_nonempty(lines, i)
    return None


def _to_int(s):
    if s is None:
        return None
    try:
        return int(str(s).replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _to_float(s):
    if s is None:
        return None
    try:
        return float(str(s).replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def _parse_nextracker_details(lines: list) -> dict:
    """
    Parse the NEXTRACKER DETAILS table from the construction PDF totals page.
    The table layout in extracted text is:
      NEXTRACKER DETAILS
      TYPES
      112 MOD 84 MOD
      56 MOD
      28 MOD
      EXTERIOR
      <c1> <c2> <c3> <c4>
      INTERIOR
      <c1> <c2> <c3> <c4>
      EPNS / EPN / EPS
      ...
      TOTAL
      <c1> <c2> <c3> <c4>
      GRAND TOTAL
      <value>
    """
    for i, line in enumerate(lines):
        if "NEXTRACKER DETAILS" in line.upper():
            break
    else:
        return {}

    table = {}
    positions = ("EXTERIOR", "INTERIOR", "EPNS", "EPN", "EPS", "TOTAL")
    col_names = ("112", "84", "56", "28")
    cursor = i
    for pos in positions:
        for j in range(cursor, min(len(lines), cursor + 30)):
            if lines[j].strip().upper() == pos:
                cursor = j + 1
                break
        else:
            continue
        vals = []
        while len(vals) < 4 and cursor < len(lines):
            s = lines[cursor].strip()
            cursor += 1
            if not s:
                continue
            try:
                vals.append(int(s))
            except ValueError:
                break
        if len(vals) == 4:
            table[pos] = dict(zip(col_names, vals))

    # GRAND TOTAL
    for j in range(cursor, min(len(lines), cursor + 20)):
        if "GRAND TOTAL" in lines[j].upper():
            for k in range(j + 1, min(len(lines), j + 5)):
                s = lines[k].strip()
                if s.isdigit():
                    table["grand_total"] = int(s)
                    break
            break
    return table


def _parse_pier_type_specs(pdf_doc) -> list:
    """
    Parse the pier type spec table from page 4 of the construction PDF.
    Returns a list of {pier_type, pier_type_full, zones: [{zone, size, part_no}, ...]}.

    Zones seen:
      - REMAINING AREA SLOPE 0-6.1%
      - CANAL AREA SLOPE 0-6.1%
      - SLOPE 6.1%-10%
    """
    # Look at pages 4-6 for the PIER LEGEND table
    pier_types = [
        ("HAP", "HEAVY ARRAY PIER"),
        ("HMP", "HEAVY MOTOR PIER"),
        ("SAP", "STANDARD ARRAY PIER"),
        ("SAPE", "STANDARD ARRAY PIER, EDGE"),
        ("SAPEND", "STANDARD ARRAY PIER END"),
        ("SMP", "STANDARD MOTOR PIER"),
    ]
    specs = []
    for page_idx in range(min(len(pdf_doc), 20)):
        try:
            text = pdf_doc.load_page(page_idx).get_text("text") or ""
        except Exception:
            continue
        if "PIER LEGEND" not in text.upper() or "HEAVY ARRAY PIER" not in text.upper():
            continue
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for abbr, full_name in pier_types:
            # find the line matching "HEAVY ARRAY PIER (HAP)" or similar
            for i, line in enumerate(lines):
                u = line.upper()
                if full_name in u and f"({abbr})" in u:
                    # next 6 lines should be: size1, partno1, size2, partno2, size3, partno3
                    zones_names = ["remaining_0_6.1", "canal_0_6.1", "slope_6.1_10"]
                    zones = []
                    for k, zname in enumerate(zones_names):
                        idx_size = i + 1 + k * 2
                        idx_part = i + 2 + k * 2
                        if idx_part < len(lines):
                            zones.append({
                                "zone": zname,
                                "size": lines[idx_size],
                                "part_no": lines[idx_part],
                            })
                    specs.append({
                        "pier_type": abbr,
                        "pier_type_full": full_name.title(),
                        "zones": zones,
                    })
                    break
            if len(specs) >= len(pier_types):
                return specs
        if specs:
            return specs
    return specs


def _parse_pier_spacing(pdf_doc) -> list:
    """
    Parse the PIER SPACING table from pages 30-42 of the construction PDF.
    Shows distances like 7.594m, 17.022m, 25.127m along tracker length.
    Returns a sorted list of distances in meters.
    """
    import re
    distances_m = set()
    for page_idx in range(min(len(pdf_doc), 45)):
        try:
            text = pdf_doc.load_page(page_idx).get_text("text") or ""
        except Exception:
            continue
        if "PIER SPACING" not in text.upper():
            continue
        for m in re.finditer(r"(\d{1,3}\.\d{2,3})m(?!\w)", text):
            try:
                d = float(m.group(1))
                if 1 < d < 100:
                    distances_m.add(round(d, 3))
            except ValueError:
                pass
    return sorted(distances_m)


def _parse_bill_of_materials(lines: list) -> list:
    """
    Parse the Bill of Materials table. Each entry is a QTY/NAME/PART NO triple.
    Returns a list of {qty, name, part_no, pier_count, module_count} dicts.
    Only entries that describe trackers ('module, N pier') are returned.
    """
    for i, line in enumerate(lines):
        if "BILL OF MATERIAL" in line.upper():
            break
    else:
        return []

    # Skip header lines (QTY / NAME / PART NO)
    j = i + 1
    while j < len(lines) and lines[j].strip().upper() in ("BILL OF MATERIALS", "QTY", "NAME", "PART NO", ""):
        j += 1

    rx_pier = re.compile(r"(\d+)\s*module.*?(\d+)\s*pier", re.IGNORECASE)
    entries = []
    while j < len(lines):
        s = lines[j].strip()
        if not s:
            j += 1
            continue
        # Stop at next section
        if "SYSTEM SPECIFICATION" in s.upper() or "NOTE:" in s.upper() or "BLOCK" in s.upper() and s.upper().startswith("BLOCK"):
            break
        if not s.isdigit():
            j += 1
            continue
        qty = int(s)
        name = lines[j + 1].strip() if j + 1 < len(lines) else ""
        part = lines[j + 2].strip() if j + 2 < len(lines) else ""
        entry = {"qty": qty, "name": name, "part_no": part}
        m = rx_pier.search(name)
        if m:
            entry["module_count"] = int(m.group(1))
            entry["pier_count"] = int(m.group(2))
        entries.append(entry)
        j += 3
    return entries


def _extract_from_construction(construction_pdf: str) -> dict:
    """Extract plant-wide metadata from the construction PDF title block / totals page."""
    out = {}
    if not construction_pdf or not Path(construction_pdf).exists():
        return out
    try:
        doc = fitz.open(construction_pdf)
    except Exception:
        return out
    try:
        # Scan first 3 pages for title block + totals
        pages_text = []
        for i in range(min(len(doc), 4)):
            try:
                pages_text.append(doc.load_page(i).get_text("text") or "")
            except Exception:
                pass
        full = "\n".join(pages_text)
        lines = [l for l in full.split("\n")]

        # NEXTRACKER DETAILS matrix
        tracker_matrix = _parse_nextracker_details(lines)
        if tracker_matrix:
            out["tracker_matrix"] = tracker_matrix
            if "grand_total" in tracker_matrix:
                out["expected_trackers"] = tracker_matrix["grand_total"]

        # Bill of Materials
        bom = _parse_bill_of_materials(lines)
        tracker_bom = [e for e in bom if "pier_count" in e]
        if tracker_bom:
            out["bill_of_materials"] = tracker_bom
            out["expected_piers"] = sum(e["qty"] * e["pier_count"] for e in tracker_bom)
            out["expected_modules_from_bom"] = sum(e["qty"] * e["module_count"] for e in tracker_bom)

        # Pier type specs (HAP/HMP/SAP/SAPE/SAPEND/SMP sizes + part numbers by zone)
        try:
            specs = _parse_pier_type_specs(doc)
            if specs:
                out["pier_type_specs"] = specs
        except Exception:
            pass

        # Pier spacing distances along tracker length
        try:
            spacing = _parse_pier_spacing(doc)
            if spacing:
                out["pier_spacing_m"] = spacing
        except Exception:
            pass

        # Plant totals
        out["total_output_mw"] = _to_float(_label_value(lines, "TOTAL CAPACITY [MW]"))
        out["total_strings"] = _to_int(_label_value(lines, "NUMBER OF STRINGS"))
        out["total_modules"] = _to_int(_label_value(lines, "TOTAL MODULES"))
        out["modules_per_string"] = _to_int(_label_value(lines, "MODULES PER STRING"))
        out["module_capacity_w"] = _to_int(_label_value(lines, "MODULE CAPACITY [W]"))

        # Module dimensions (LENGTH / WIDTH / PITCH) — they appear in a block
        # where each label is immediately followed by its numeric value (meters),
        # then a unit line ('m'), then imperial value ('ft'), etc. Find the LENGTH
        # block and read all three in sequence.
        for i, line in enumerate(lines):
            if line.strip() == "LENGTH":
                # Expected: LENGTH, <m>, m, <ft>, ft, WIDTH, <m>, m, <ft>, ft, PITCH, <m>, m, <ft>, ft
                window = lines[i : i + 15]
                if len(window) >= 15:
                    out["module_length_m"] = _to_float(window[1])
                    out["module_width_m"] = _to_float(window[6])
                    out["pitch_m"] = _to_float(window[11])
                break

        # Title block
        out["site_id"] = _label_value(lines, "SITE ID:")
        out["project_number"] = _label_value(lines, "PROJECT NUMBER:")
        out["nextracker_model"] = _label_value(lines, "NEXTRACKER")
        out["lat_long"] = _label_value(lines, "LAT/LONG")
        out["snow_load"] = _label_value(lines, "SNOW LOAD")
        out["wind_load"] = _label_value(lines, "WIND LOAD")
        out["review_by"] = _label_value(lines, "REVIEW BY")
        out["issue_date"] = _label_value(lines, "DATE")
    finally:
        try:
            doc.close()
        except Exception:
            pass
    return out


def _extract_from_ramming(ramming_pdf: str) -> dict:
    """
    Extract DCCB and inverter counts from the ramming/electrical PDF.

    The ramming PDF contains DCCB labels like `DCCB_<block>.<inverter>.<string>.<box>`.
    Counting unique IDs gives us:
      - dccb: number of distinct DCCB boxes
      - inverters: number of distinct block-inverter pairs
      - string_groups: number of distinct (block, inverter, string) groups
    """
    out = {}
    if not ramming_pdf or not Path(ramming_pdf).exists():
        return out
    try:
        doc = fitz.open(ramming_pdf)
    except Exception:
        return out
    try:
        text_parts = []
        for i in range(len(doc)):
            try:
                text_parts.append(doc.load_page(i).get_text("text") or "")
            except Exception:
                pass
        full = "\n".join(text_parts)

        rx_dccb = re.compile(r"DCCB_(\d+)\.(\d+)\.(\d+)\.(\d+)")
        dccb_ids = set()
        inverter_ids = set()
        string_group_ids = set()
        block_ids = set()
        for m in rx_dccb.finditer(full):
            b, inv, s, box = m.group(1), m.group(2), m.group(3), m.group(4)
            dccb_ids.add((b, inv, s, box))
            inverter_ids.add((b, inv))
            string_group_ids.add((b, inv, s))
            block_ids.add(b)

        if dccb_ids:
            out["dccb"] = len(dccb_ids)
            out["inverters"] = len(inverter_ids)
            out["string_groups"] = len(string_group_ids)
            out["blocks_in_electrical"] = len(block_ids)
    finally:
        try:
            doc.close()
        except Exception:
            pass
    return out


def extract_electrical_metadata(construction_pdf: str, ramming_pdf: Optional[str] = None) -> dict:
    """
    Combined extraction from both PDFs.

    READ-ONLY. Any parsing error in one source does not affect the other.
    Returns dict with all known fields (values may be None).
    """
    result = {
        # Plant totals (construction PDF)
        "total_output_mw": None,
        "total_strings": None,
        "total_modules": None,
        "modules_per_string": None,
        "module_capacity_w": None,
        "module_length_m": None,
        "module_width_m": None,
        "pitch_m": None,
        # Electrical counts (ramming PDF)
        "inverters": None,
        "dccb": None,
        "string_groups": None,
        "blocks_in_electrical": None,
        # Site info (construction PDF title block)
        "site_id": None,
        "project_number": None,
        "nextracker_model": None,
        "lat_long": None,
        "snow_load": None,
        "wind_load": None,
        "review_by": None,
        "issue_date": None,
        # Validation targets (from construction PDF tables)
        "expected_trackers": None,
        "expected_piers": None,
        "expected_modules_from_bom": None,
        "tracker_matrix": None,
        "bill_of_materials": None,
        "pier_type_specs": None,
        "pier_spacing_m": None,
        "_extracted": False,
    }

    try:
        cons = _extract_from_construction(construction_pdf)
        for k, v in cons.items():
            if v is not None:
                result[k] = v
    except Exception:
        pass

    if ramming_pdf:
        try:
            ram = _extract_from_ramming(ramming_pdf)
            for k, v in ram.items():
                if v is not None:
                    result[k] = v
        except Exception:
            pass

    if any(v is not None for k, v in result.items() if not k.startswith("_")):
        result["_extracted"] = True

    return result
