"""
Vendor Export Driver
====================
Reads measurements from files exported by the PVPM Transfer software.

The PVPM 1540X can operate in "Transfer Mode" where it streams saved
measurements to the vendor Windows application, which writes them as
.XLS / .XLSX / .CSV / .TXT / .SUI files to a user-configured export folder.

This driver watches that folder for new or modified files and parses
them into the connector's canonical Measurement schema.

Vendor driver (USB) installation is SEPARATE from this connector.
This driver only reads the files that the vendor software produces.
"""

from __future__ import annotations

import csv
import io
import re
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..config import settings


# ---------------------------------------------------------------------------
# Minimal inline parser for PVPM export files
# Supports CSV, tab-delimited ASCII, and native .SUI binary format.
# XLS/XLSX require openpyxl/xlrd (optional).
# ---------------------------------------------------------------------------

_COLUMN_MAP: dict[str, str] = {
    # Canonical name → connector field
    "ppk": "ppkWp",
    "ppeak": "ppkWp",
    "p_peak": "ppkWp",
    "rs": "rsOhm",
    "rp": "rpOhm",
    "voc": "vocV",
    "isc": "iscA",
    "vpmax": "vpmaxV",
    "vmp": "vpmaxV",
    "ipmax": "ipmaxA",
    "imp": "ipmaxA",
    "ff": "ffPercent",
    "fill_factor": "ffPercent",
    "eeff": "irradianceWM2",
    "irradiance": "irradianceWM2",
    "e_eff": "irradianceWM2",
    "tmod": "moduleTempC",
    "t_mod": "moduleTempC",
    "tcell": "sensorTempC",
    "t_cell": "sensorTempC",
    "customer": "customer",
    "module_type": "moduleType",
    "module type": "moduleType",
    "string_no": "stringNo",
    "string no": "stringNo",
    "remarks": "notes",
    "device_serial": "externalMeasurementKey",
    "measured_at": "measuredAt",
    "date": "measuredAt",
    "time": "_time",
}

_FLOAT_FIELDS = {
    "ppkWp", "rsOhm", "rpOhm", "vocV", "iscA", "vpmaxV", "ipmaxA",
    "ffPercent", "irradianceWM2", "moduleTempC", "sensorTempC",
}

# SUI binary file magic headers (UIKennNFile\n\r\x1a)
_SUI_HEADERS = (
    b"UIKenn0File\n\r\x1a",  # real device files from PVPM 1540X use version 0
    b"UIKenn1File\n\r\x1a",
    b"UIKenn2File\n\r\x1a",
    b"UIKenn3File\n\r\x1a",
    b"UIKenn4File\n\r\x1a",
    b"UIKenn5File\n\r\x1a",
    b"UIKenn6File\n\r\x1a",
)

# Well-known PVPM data directories (checked in order for auto-detection)
_PVPM_DATA_DIRS = [
    Path.home() / "Documents" / "PVPMdisp" / "Samples",
    Path.home() / "Documents" / "PVPM_Export",
    Path.home() / "Documents" / "PVPMdisp",
    Path("C:/Users/Public/Documents/PVPM_Export"),
]


def _read_pvpmdisp_ini() -> dict:
    """Read PVPMdisp.INI from AppData to get EXPDIR, PORTNAME etc."""
    ini_path = (
        Path.home() / "AppData" / "Roaming" / "PV-Engineering" / "PVPMdisp" / "PVPMdisp.INI"
    )
    result: dict = {}
    if not ini_path.exists():
        return result
    try:
        import configparser
        cfg = configparser.RawConfigParser()
        cfg.read(str(ini_path), encoding="latin-1")
        for section in cfg.sections():
            for key, val in cfg.items(section):
                result[key.upper()] = val.strip()
    except Exception:
        pass
    return result


def _get_pvpm_export_dirs() -> list[Path]:
    """Return all candidate PVPM data directories, including PVPMdisp EXPDIR."""
    dirs: list[Path] = []

    # 1. EXPDIR from PVPMdisp.INI (highest priority — this is where new files go)
    ini = _read_pvpmdisp_ini()
    expdir = ini.get("EXPDIR") or ini.get("expdir")
    if expdir:
        p = Path(expdir.rstrip("\\/"))
        if p.exists():
            dirs.append(p)

    lastdir = ini.get("LASTDIR") or ini.get("lastdir")
    if lastdir:
        p = Path(lastdir.rstrip("\\/"))
        if p.exists() and p not in dirs:
            dirs.append(p)

    # 2. Well-known fallback directories
    for d in _PVPM_DATA_DIRS:
        if d.exists() and d not in dirs:
            dirs.append(d)

    return dirs


# ---------------------------------------------------------------------------
# SUI parser  (UIKenn0File — PVPM 1540X native binary format)
# ---------------------------------------------------------------------------
# Fixed offsets discovered from real device files.
# Strings are length-prefixed (1-byte length then data bytes).
# IV curve: current array at 503, voltage array at 1475, 4-byte LE floats.
# ---------------------------------------------------------------------------

_SUI_OFF = {
    "format_version":           153,
    "device_serial":            160,
    "device_calibration_date":  175,
    "sensor_name":              233,   # string / installation identifier
    "sensor_type":              247,   # cell technology (mono/poly)
    "module_manufacturer":      300,
    "module_type":              326,
    "module_isc_stc":           396,   # float32
    "module_voc_stc":           392,   # float32
    "module_vmp_stc":           400,   # float32
    "module_imp_stc":           388,   # float32
    "module_pmax_stc":          404,   # float32
    "curve_current_start":      503,   # 110 × float32
    "curve_voltage_start":      1475,  # 130 × float32
    "label_timestamp_text":     2648,  # "DD.MM.YYYY  HH:MM:SS"
}

_LP_MAX = 120   # max plausible length-prefixed string length


def _lp_str(data: bytes, off: int) -> Optional[str]:
    """Read a length-prefixed Latin-1 string; return None on any error."""
    # skip leading null bytes
    while off < len(data) and data[off] == 0:
        off += 1
    if off >= len(data):
        return None
    ln = data[off]
    if ln == 0 or ln > _LP_MAX or off + 1 + ln > len(data):
        return None
    raw = data[off + 1: off + 1 + ln]
    return raw.decode("latin-1", errors="replace").strip() or None


def _f32(data: bytes, off: int) -> Optional[float]:
    if off + 4 > len(data):
        return None
    v = struct.unpack_from("<f", data, off)[0]
    import math as _math
    return None if not _math.isfinite(v) else v


def _extract_curve(data: bytes, start: int, count: int) -> list[float]:
    import math as _math
    out = []
    for i in range(count):
        off = start + i * 4
        if off + 4 > len(data):
            break
        v = struct.unpack_from("<f", data, off)[0]
        if _math.isfinite(v):
            out.append(v)
    # trim trailing zeros
    while out and abs(out[-1]) < 1e-12:
        out.pop()
    return out


def _derive_iv_params(voltages: list[float], currents: list[float]) -> dict:
    """Derive Isc, Voc, Ppk, Vmpp, Impp, FF from paired IV curve arrays."""
    import math as _math
    n = min(len(voltages), len(currents))
    if n < 3:
        return {}
    pts = [(voltages[i], currents[i], voltages[i] * currents[i]) for i in range(n)]

    # Isc = current at lowest voltage (first point)
    isc = currents[0]

    # Voc = voltage where current ≈ 0 (last meaningful point with i≥0)
    voc_candidates = [(v, c) for v, c, _ in pts if c >= 0]
    voc = max(v for v, _ in voc_candidates) if voc_candidates else voltages[-1]

    # Ppk = max power point
    ppk_pt = max(pts, key=lambda t: t[2])
    ppk  = ppk_pt[2]
    vmpp = ppk_pt[0]
    impp = ppk_pt[1]

    ff = (ppk / (isc * voc) * 100.0) if isc > 0 and voc > 0 else None

    return {
        "iscA":    round(isc,  4),
        "vocV":    round(voc,  4),
        "ppkWp":   round(ppk,  3),
        "vpmaxV":  round(vmpp, 4),
        "ipmaxA":  round(impp, 4),
        "ffPercent": round(ff, 2) if ff is not None else None,
    }


def _parse_sui_timestamp(data: bytes) -> Optional[str]:
    """Extract ISO-8601 UTC timestamp from the label block at fixed offset."""
    ts_raw = _lp_str(data, _SUI_OFF["label_timestamp_text"])
    if ts_raw:
        for fmt in ("%d.%m.%Y  %H:%M:%S", "%d.%m.%Y %H:%M:%S"):
            try:
                dt = datetime.strptime(ts_raw.strip(), fmt)
                return dt.replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                continue
    # fallback: scan tail for date pattern
    tail = data[-150:].decode("latin-1", errors="replace")
    m = re.search(r"(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2})", tail)
    if m:
        for fmt in ("%d.%m.%Y  %H:%M:%S", "%d.%m.%Y %H:%M:%S"):
            try:
                dt = datetime.strptime(m.group(1).strip(), fmt)
                return dt.replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                continue
    return None


def _parse_sui_file(path: Path) -> list[dict]:
    """Parse a PVPM native UIKenn0File .SUI binary into a measurement record."""
    data = path.read_bytes()

    if not any(data.startswith(h) for h in _SUI_HEADERS):
        return []

    # ── Metadata ──────────────────────────────────────────────────────────
    sensor_name      = _lp_str(data, _SUI_OFF["sensor_name"])       # string/installation ID
    module_mfr       = _lp_str(data, _SUI_OFF["module_manufacturer"])
    module_type      = _lp_str(data, _SUI_OFF["module_type"])
    device_serial    = _lp_str(data, _SUI_OFF["device_serial"])

    # ── IV curve → derived electrical params ──────────────────────────────
    currents = _extract_curve(data, _SUI_OFF["curve_current_start"],  110)
    voltages = _extract_curve(data, _SUI_OFF["curve_voltage_start"],  130)
    # drop leading outlier voltage if first > second (curve trim from parser)
    while len(voltages) > 5 and voltages[0] > voltages[1] + 1e-6:
        voltages = voltages[1:]

    iv_params = _derive_iv_params(voltages, currents)

    curve_points = []
    n = min(len(voltages), len(currents))
    for i in range(n):
        curve_points.append({
            "pointIndex": i,
            "voltageV":   round(voltages[i],  4),
            "currentA":   round(currents[i],  4),
        })

    # ── Timestamp ─────────────────────────────────────────────────────────
    measured_at = _parse_sui_timestamp(data)
    if not measured_at:
        mtime = path.stat().st_mtime
        measured_at = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

    # ── Build record ──────────────────────────────────────────────────────
    m: dict = {
        "id":           uuid.uuid4().hex,
        "importSource": f"vendor_export:{path.name}",
        "syncStatus":   "unsynced",
        "curvePoints":  curve_points,
        "measuredAt":   measured_at,
        "rawPayloadJson": {
            "suiFile":      path.name,
            "deviceSerial": device_serial,
            "moduleType":   module_type,
            "manufacturer": module_mfr,
            "stringId":     sensor_name,
        },
    }

    # Electrical measurements
    m.update({k: v for k, v in iv_params.items() if v is not None})

    # String / module metadata
    if sensor_name:
        m["stringNo"] = sensor_name
    if module_type:
        m["moduleType"] = module_type
    if module_mfr:
        m["customer"] = module_mfr   # manufacturer as customer until real customer field known

    return [m]


# ---------------------------------------------------------------------------
# CSV / delimited parser
# ---------------------------------------------------------------------------

def _parse_csv_bytes(data: bytes, source_file: str) -> list[dict]:
    text = data.decode("utf-8", errors="replace")
    dialect = "excel-tab" if "\t" in text.split("\n")[0] else "excel"
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    results = []
    for row in reader:
        mapped: dict = {
            "id": uuid.uuid4().hex,
            "importSource": f"vendor_export:{source_file}",
            "syncStatus": "unsynced",
            "curvePoints": [],
            "rawPayloadJson": dict(row),
        }
        date_val: Optional[str] = None
        time_val: Optional[str] = None
        for raw_key, value in row.items():
            key = raw_key.strip().lower()
            connector_field = _COLUMN_MAP.get(key)
            if connector_field == "_time":
                time_val = value.strip()
                continue
            if connector_field == "measuredAt":
                date_val = value.strip()
                continue
            if connector_field and value.strip():
                if connector_field in _FLOAT_FIELDS:
                    try:
                        mapped[connector_field] = float(value.replace(",", "."))
                    except ValueError:
                        pass
                else:
                    mapped[connector_field] = value.strip()

        # Combine date + time if separate columns
        if date_val:
            combined = f"{date_val} {time_val}" if time_val else date_val
            for fmt in (
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d",
            ):
                try:
                    dt = datetime.strptime(combined.strip(), fmt)
                    mapped["measuredAt"] = dt.replace(tzinfo=timezone.utc).isoformat()
                    break
                except ValueError:
                    continue

        if "measuredAt" not in mapped:
            mapped["measuredAt"] = datetime.now(timezone.utc).isoformat()

        results.append(mapped)

    return results


# ---------------------------------------------------------------------------
# File routing
# ---------------------------------------------------------------------------

_TEXT_EXTS = {".csv", ".txt", ".asc", ".dat"}
_XLSX_EXTS = {".xlsx", ".xls"}
_SUI_EXT   = ".sui"
_ALL_EXTS  = _TEXT_EXTS | _XLSX_EXTS | {_SUI_EXT}


def _parse_file(path: Path) -> list[dict]:
    ext = path.suffix.lower()
    if ext in _TEXT_EXTS:
        return _parse_csv_bytes(path.read_bytes(), path.name)
    if ext == _SUI_EXT:
        return _parse_sui_file(path)
    if ext == ".xlsx":
        try:
            import openpyxl  # type: ignore[import]
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return []
            headers = [str(h).strip() if h is not None else "" for h in rows[0]]
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerows([headers] + [list(r) for r in rows[1:]])
            return _parse_csv_bytes(buf.getvalue().encode(), path.name)
        except ImportError:
            pass
    if ext == ".xls":
        try:
            import xlrd  # type: ignore[import]
            wb = xlrd.open_workbook(file_contents=path.read_bytes())
            ws = wb.sheet_by_index(0)
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerows([ws.row_values(r) for r in range(ws.nrows)])
            return _parse_csv_bytes(buf.getvalue().encode(), path.name)
        except ImportError:
            pass
    return []


def _file_info(path: Path) -> dict:
    """Build a file-listing entry for a measurement file."""
    stat = path.stat()
    entry: dict = {
        "name": path.name,
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "type": path.suffix.lower().lstrip("."),
    }
    if path.suffix.lower() == _SUI_EXT:
        try:
            data = path.read_bytes()
            if any(data.startswith(h) for h in _SUI_HEADERS):
                meta = _extract_sui_metadata(data)
                for k in ("stringNo", "customer", "moduleType", "measuredAt",
                          "moduleCount", "externalMeasurementKey"):
                    if k in meta:
                        entry[k] = meta[k]
        except Exception:
            pass
    return entry


# ---------------------------------------------------------------------------
# Driver class
# ---------------------------------------------------------------------------

class VendorExportDriver:
    """
    Reads PVPM measurement files from a watched export folder.
    The vendor USB driver and Transfer software must be installed separately.
    """

    def __init__(self) -> None:
        self.connected = False
        self.port: Optional[str] = None
        self._watch_folder = settings.watch_folder_path
        self._watch_folder.mkdir(parents=True, exist_ok=True)

    # ── Detection / lifecycle ──────────────────────────────────────────────

    def detect(self) -> dict:
        has_files = self._has_measurement_files()
        return {
            "connected": self.connected,
            "mode": "vendor_export",
            "port": str(self._watch_folder),
            "deviceModel": None,
            "deviceSerial": None,
            "firmwareVersion": None,
            "transferModeRequired": True,
            "transferModeDetected": self.connected and has_files,
            "lastError": None if self.connected else (
                f"Drop exported PVPM files into: {self._watch_folder}"
            ),
        }

    def list_ports(self) -> list[dict]:
        """Return watch folder + auto-detected PVPM export directories."""
        ports = []
        seen = set()

        # Always include current watch folder first
        ports.append({
            "name": str(self._watch_folder),
            "description": "Current watch folder",
        })
        seen.add(str(self._watch_folder))

        # Add all detected PVPM directories
        for candidate in _get_pvpm_export_dirs():
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            try:
                sui_count = sum(
                    1 for f in candidate.iterdir()
                    if f.is_file() and f.suffix.lower() == _SUI_EXT
                )
                if sui_count > 0:
                    ports.append({
                        "name": key,
                        "description": f"PVPM export folder — {sui_count} .SUI file(s)",
                    })
            except Exception:
                pass
        return ports

    def connect(self, port: str) -> dict:
        import re as _re
        # If a COM port is passed (e.g. from the manager UI), redirect to
        # the PVPM export folder from PVPMdisp.INI instead of treating the
        # COM port name as a folder path (which fails on Windows).
        if port and _re.match(r"^(?:\\\\.\\)?COM\d+$", port, _re.IGNORECASE):
            ini = _read_pvpmdisp_ini()
            for key in ("EXPDIR", "LASTDIR"):
                val = ini.get(key, "").strip().rstrip("\\/")
                if val and Path(val).exists():
                    port = val
                    break
            else:
                port = str(self._watch_folder)
        folder = Path(port) if port else self._watch_folder
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # folder may already exist or be a network path
        self._watch_folder = folder
        self.connected = True
        self.port = str(folder)
        return self.detect()

    def disconnect(self) -> None:
        self.connected = False
        self.port = None

    # ── Data access ────────────────────────────────────────────────────────

    def is_transfer_mode(self) -> bool:
        return self._has_measurement_files()

    def fetch_device_info(self) -> dict:
        return self.detect()

    def fetch_measurements(self) -> list[dict]:
        all_measurements: list[dict] = []
        for path in sorted(self._watch_folder.iterdir()):
            if not path.is_file() or path.suffix.lower() not in _ALL_EXTS:
                continue
            try:
                parsed = _parse_file(path)
                all_measurements.extend(parsed)
            except Exception as exc:
                print(f"[VendorExport] Skipping {path.name}: {exc}")
        return all_measurements

    def list_files(self) -> list[dict]:
        """List all measurement files in the watch folder with metadata."""
        files = []
        try:
            for path in sorted(self._watch_folder.iterdir()):
                if path.is_file() and path.suffix.lower() in _ALL_EXTS:
                    try:
                        files.append(_file_info(path))
                    except Exception:
                        files.append({
                            "name": path.name,
                            "size": 0,
                            "modified": "",
                            "type": path.suffix.lower().lstrip("."),
                        })
        except Exception:
            pass
        return files

    # ── Helpers ────────────────────────────────────────────────────────────

    def _has_measurement_files(self) -> bool:
        try:
            return any(
                f.is_file() and f.suffix.lower() in _ALL_EXTS
                for f in self._watch_folder.iterdir()
            )
        except Exception:
            return False
