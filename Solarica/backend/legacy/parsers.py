"""Parsers for PVPM exported data: XLS, CSV, ASCII."""
import csv
import re
from pathlib import Path
from typing import Optional

from models import IVPoint, MeasurementCreate

try:
    import openpyxl
    HAS_XLSX = True
except ImportError:
    HAS_XLSX = False
try:
    import xlrd
    HAS_XLS = True
except ImportError:
    HAS_XLS = False


def parse_xlsx(filepath: Path) -> Optional[MeasurementCreate]:
    """Parse Excel (.xlsx) export from PVPM.disp."""
    if not HAS_XLSX:
        return None
    try:
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        ws = wb.active
        data = list(ws.iter_rows(values_only=True))
        wb.close()
        return _extract_measurement_from_rows(data, filepath.name)
    except Exception:
        return None


def parse_xls(filepath: Path) -> Optional[MeasurementCreate]:
    """Parse legacy Excel (.xls) via xlrd."""
    if not HAS_XLS:
        return parse_xlsx(filepath)  # fallback
    try:
        wb = xlrd.open_workbook(str(filepath))
        ws = wb.sheet_by_index(0)
        data = [ws.row_values(i) for i in range(ws.nrows)]
        return _extract_measurement_from_rows(data, filepath.name)
    except Exception:
        return None


def parse_csv(filepath: Path) -> Optional[MeasurementCreate]:
    """Parse CSV/ASCII export from PVPM.disp."""
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            data = list(reader)
        return _extract_measurement_from_rows(data, filepath.name)
    except Exception:
        return None


def parse_ascii(filepath: Path) -> Optional[MeasurementCreate]:
    """Parse ASCII text export (tab or space separated)."""
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
        data = [re.split(r"[\t,;]+", line.strip()) for line in lines if line.strip()]
        return _extract_measurement_from_rows(data, filepath.name)
    except Exception:
        return None


def _parse_float(val) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        return float(str(val).replace(",", "."))
    except ValueError:
        return None


def _extract_measurement_from_rows(rows: list, filename: str) -> Optional[MeasurementCreate]:
    """Extract measurement and I-V curve from 2D rows (header + data)."""
    if not rows:
        return None

    # Build a lookup for known column names (case-insensitive)
    header = [str(c).strip().lower() if c else "" for c in rows[0]]
    col = lambda *names: next(
        (i for i, h in enumerate(header) if h in [n.lower() for n in names]),
        None,
    )

    # Map PVPM.disp export column names
    m = MeasurementCreate(source_file=filename)

    # Common export headers from PVPM
    mapping = {
        "ppk": col("ppk", "peak power", "p_pk"),
        "rs": col("rs", "r_s", "series resistance"),
        "rp": col("rp", "r_p", "parallel resistance"),
        "voc": col("voc", "v_oc", "open circuit voltage"),
        "isc": col("isc", "i_sc", "short circuit current"),
        "vpmax": col("vpmax", "v_pmax", "upmax", "u_pmax"),
        "ipmax": col("ipmax", "i_pmax"),
        "pmax": col("pmax", "p_max"),
        "ff": col("ff", "fill factor"),
        "tmod": col("tmod", "t_mod", "module temp", "module temperature"),
        "eeff": col("eeff", "e_eff", "irradiance", "effective irradiance"),
        "voltage": col("voltage", "v", "u"),
        "current": col("current", "i"),
    }

    v_col = mapping.get("voltage")
    i_col = mapping.get("current")
    iv_curve = []
    for row in rows[1:]:
        v = _parse_float(row[v_col]) if v_col is not None and v_col < len(row) else None
        i = _parse_float(row[i_col]) if i_col is not None and i_col < len(row) else None
        if v is not None and i is not None:
            iv_curve.append(IVPoint(voltage=v, current=i))

    # Try to get scalar values from first data row or header row
    if len(rows) > 1:
        first = rows[1]
        m.ppk = _parse_float(first[col("ppk", "peak power")]) if col("ppk", "peak power") is not None else None
        m.rs = _parse_float(first[col("rs", "r_s")]) if col("rs", "r_s") is not None else None
        m.rp = _parse_float(first[col("rp", "r_p")]) if col("rp", "r_p") is not None else None
        m.voc = _parse_float(first[col("voc", "v_oc")]) if col("voc", "v_oc") is not None else None
        m.isc = _parse_float(first[col("isc", "i_sc")]) if col("isc", "i_sc") is not None else None
        m.vpmax = _parse_float(first[col("vpmax", "upmax")]) if col("vpmax", "upmax") is not None else None
        m.ipmax = _parse_float(first[col("ipmax", "i_pmax")]) if col("ipmax", "i_pmax") is not None else None
        m.pmax = _parse_float(first[col("pmax", "p_max")]) if col("pmax", "p_max") is not None else None
        m.ff = _parse_float(first[col("ff", "fill factor")]) if col("ff", "fill factor") is not None else None
        m.tmod = _parse_float(first[col("tmod", "t_mod")]) if col("tmod", "t_mod") is not None else None
        m.eeff = _parse_float(first[col("eeff", "e_eff")]) if col("eeff", "e_eff") is not None else None

    m.iv_curve = iv_curve if iv_curve else None
    return m


def parse_import_file(content: bytes, filename: str, format_hint: str = "") -> Optional[dict]:
    """
    Parse PVPM export from bytes. Returns dict for DB insert.
    Use format_hint e.g. '.xlsx', '.csv'.
    """
    import tempfile
    suffix = format_hint or Path(filename).suffix.lower()
    if not suffix.startswith("."):
        suffix = "." + suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
        tf.write(content)
        path = Path(tf.name)
    try:
        m = parse_file(path)
    finally:
        path.unlink(missing_ok=True)
    if not m:
        return None
    d = m.model_dump(exclude_none=True)
    # Map to DB columns
    out = {
        "measured_at": d.get("measured_at"),
        "device_serial": d.get("device_serial"),
        "sensor_serial": d.get("irradiance_sensor_serial"),
        "customer": d.get("remarks"),  # placeholder if PVPM exports customer elsewhere
        "module_type": None,
        "remarks": d.get("remarks"),
        "ppk": d.get("ppk"),
        "rs": d.get("rs"),
        "rp": d.get("rp"),
        "voc": d.get("voc"),
        "isc": d.get("isc"),
        "vpmax": d.get("vpmax"),
        "ipmax": d.get("ipmax"),
        "pmax": d.get("pmax"),
        "fill_factor": d.get("ff"),
        "eeff": d.get("eeff"),
        "tmod": d.get("tmod"),
        "tcell": None,
        "iv_curve": [
            {"voltage": p["voltage"], "current": p["current"]} if isinstance(p, dict) else {"voltage": p.voltage, "current": p.current}
            for p in (d.get("iv_curve") or [])
        ],
    }
    return out


def parse_file(filepath: Path) -> Optional[MeasurementCreate]:
    """Auto-detect format and parse."""
    suffix = filepath.suffix.lower()
    if suffix == ".xlsx":
        return parse_xlsx(filepath)
    if suffix == ".xls":
        return parse_xls(filepath)
    if suffix == ".csv":
        return parse_csv(filepath)
    if suffix in (".txt", ".asc", ".dat"):
        return parse_ascii(filepath)
    return None
