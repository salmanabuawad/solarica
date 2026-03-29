"""
Serial Direct Driver
====================
Direct USB access to PVPM via FTDI COM port.

What this driver does:
- Enumerates FTDI / USB-Serial ports
- Auto-detects the most likely PVPM port
- Connects directly to the COM port
- Waits for the operator to put the device into Transfer Mode
- Captures one or more SUI files from the serial byte stream
- Parses each SUI into the connector's measurement schema

Important:
- This is direct USB/serial access.
- It does not depend on PVPMdisp / Curvealyzer.
- The PVPM still needs to be switched into Transfer Mode by the operator.
"""

from __future__ import annotations

import io
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import serial
import serial.tools.list_ports

from ..config import settings

# Try to use the backend's richer parser if available
PROJECT_ROOT = Path(__file__).resolve().parents[4]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

try:
    from app.parsers.pvpm.parser_v4_1 import parse_sui_bytes as _rich_parse_sui_bytes  # type: ignore
except Exception:
    _rich_parse_sui_bytes = None

_SUI_HEADERS = [
    b"UIKenn0File\n\r\x1a",
    b"UIKenn1File\n\r\x1a",
    b"UIKenn2File\n\r\x1a",
    b"UIKenn3File\n\r\x1a",
    b"UIKenn4File\n\r\x1a",
    b"UIKenn5File\n\r\x1a",
    b"UIKenn6File\n\r\x1a",
]
_SUI_HEADER_MAGIC = b"UIKenn"

# Probe most common FTDI / serial rates first.
_BAUD_RATES = [115200, 57600, 38400, 19200, 9600]

_FILE_END_TIMEOUT = 2.0
_CONNECT_TIMEOUT = 20.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode_tail_timestamp(raw: bytes) -> str | None:
    import re
    tail = raw[-200:].decode("latin-1", errors="ignore")
    match = re.search(r"(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2})", tail)
    if not match:
        return None
    date_str = match.group(1).strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y  %H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def _curve_points_from_rich(parsed: dict) -> list[dict]:
    pts = parsed.get("curve", {}).get("points", [])
    out = []
    for idx, p in enumerate(pts):
        out.append(
            {
                "pointIndex": idx,
                "voltageV": p.get("u_v"),
                "currentA": p.get("i_a"),
            }
        )
    return out


def _best_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _parse_sui_bytes(raw: bytes, port: str) -> Optional[dict]:
    """Convert one full SUI file into the connector's Measurement schema."""
    if not any(raw.startswith(h) for h in _SUI_HEADERS):
        return None

    if _rich_parse_sui_bytes is not None:
        try:
            parsed = _rich_parse_sui_bytes(
                raw,
                "serial_capture.sui",
                master_row=None,
                sidecar_xls=None,
                include_curve=True,
                include_ascii=False,
            )
            measured_at = (
                parsed.get("normalized", {}).get("timestamp")
                or parsed.get("measurement_from_sui", {}).get("timestamp_text")
            )
            if measured_at and isinstance(measured_at, str):
                # normalize dd.mm.yyyy hh:mm:ss if needed
                for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y  %H:%M:%S"):
                    try:
                        measured_at = datetime.strptime(measured_at, fmt).replace(tzinfo=timezone.utc).isoformat()
                        break
                    except Exception:
                        pass
            if not measured_at:
                measured_at = _decode_tail_timestamp(raw) or _now_iso()

            return {
                "id": uuid.uuid4().hex,
                "externalMeasurementKey": _best_text(
                    parsed.get("device", {}).get("model_serial"),
                    parsed.get("measurement_from_sui", {}).get("timestamp_text"),
                ),
                "measuredAt": measured_at,
                "customer": None,
                "installation": _best_text(
                    parsed.get("normalized", {}).get("site_name"),
                    parsed.get("raw_sui_labels", {}).get("site_label_raw"),
                ),
                "stringNo": _best_text(
                    parsed.get("normalized", {}).get("part_name"),
                    parsed.get("raw_sui_labels", {}).get("string_label_raw"),
                ),
                "moduleType": _best_text(
                    parsed.get("normalized", {}).get("module_part_number"),
                    parsed.get("module_reference_from_sui", {}).get("part_number_raw"),
                ),
                "moduleReference": _best_text(parsed.get("module_reference_from_sui", {}).get("manufacturer")),
                "modulesSeries": None,
                "modulesParallel": None,
                "nominalPowerW": parsed.get("module_reference_from_sui", {}).get("pmax_stc"),
                "ppkWp": parsed.get("derived_from_curve", {}).get("pmax_w"),
                "rsOhm": None,
                "rpOhm": None,
                "vocV": parsed.get("derived_from_curve", {}).get("voc_v"),
                "iscA": parsed.get("derived_from_curve", {}).get("isc_a"),
                "vpmaxV": parsed.get("derived_from_curve", {}).get("vmp_v"),
                "ipmaxA": parsed.get("derived_from_curve", {}).get("imp_a"),
                "ffPercent": parsed.get("derived_from_curve", {}).get("fill_factor"),
                "sweepDurationMs": None,
                "irradianceWM2": None,
                "sensorTempC": None,
                "moduleTempC": None,
                "irradianceSensorType": parsed.get("sensor", {}).get("type"),
                "irradianceSensorSerial": parsed.get("sensor", {}).get("name"),
                "importSource": f"serial:{port}",
                "syncStatus": "unsynced",
                "notes": "Direct USB serial capture from PVPM Transfer Mode",
                "rawPayloadJson": parsed,
                "curvePoints": _curve_points_from_rich(parsed),
            }
        except Exception:
            pass

    # Fallback if rich parser is unavailable
    return {
        "id": uuid.uuid4().hex,
        "externalMeasurementKey": f"{port}:{uuid.uuid4().hex[:8]}",
        "measuredAt": _decode_tail_timestamp(raw) or _now_iso(),
        "customer": None,
        "installation": None,
        "stringNo": None,
        "moduleType": None,
        "moduleReference": None,
        "modulesSeries": None,
        "modulesParallel": None,
        "nominalPowerW": None,
        "ppkWp": None,
        "rsOhm": None,
        "rpOhm": None,
        "vocV": None,
        "iscA": None,
        "vpmaxV": None,
        "ipmaxA": None,
        "ffPercent": None,
        "sweepDurationMs": None,
        "irradianceWM2": None,
        "sensorTempC": None,
        "moduleTempC": None,
        "irradianceSensorType": None,
        "irradianceSensorSerial": None,
        "importSource": f"serial:{port}",
        "syncStatus": "unsynced",
        "notes": "Fallback serial capture; rich SUI parser unavailable",
        "rawPayloadJson": {"size": len(raw)},
        "curvePoints": [],
    }


class SerialDirectDriver:
    def __init__(self) -> None:
        self.connected = False
        self.port: Optional[str] = None
        self.last_error: Optional[str] = None
        self._baud: Optional[int] = None
        self._device_model: Optional[str] = "PVPM 1540X"
        self._device_serial: Optional[str] = None
        self._transfer_detected = False
        self._captured: list[bytes] = []
        self._lock = threading.Lock()

    def detect(self) -> dict:
        return {
            "connected": self.connected,
            "mode": "serial",
            "port": self.port,
            "deviceModel": self._device_model,
            "deviceSerial": self._device_serial,
            "firmwareVersion": None,
            "transferModeRequired": True,
            "transferModeDetected": self._transfer_detected,
            "lastError": self.last_error,
        }

    def _candidate_ports(self) -> list[dict]:
        items = []
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").strip()
            manu = (p.manufacturer or "").strip()
            hwid = (p.hwid or "").strip()
            desc_l = f"{desc} {manu} {hwid}".lower()
            is_ftdi = "ftdi" in desc_l or "usb serial" in desc_l or "vid:pid=0403:" in desc_l
            score = 0
            if "vid:pid=0403:" in desc_l:
                score += 4
            if "ftdi" in desc_l:
                score += 3
            if "usb serial" in desc_l:
                score += 1
            items.append(
                {
                    "name": p.device,
                    "description": desc,
                    "manufacturer": manu,
                    "hwid": hwid,
                    "isLikelyPvpm": is_ftdi,
                    "score": score,
                }
            )
        items.sort(key=lambda x: (x["isLikelyPvpm"], x["score"], x["name"]), reverse=True)
        return items

    def list_ports(self) -> list[dict]:
        return [
            {
                "name": p["name"],
                "description": f'{p["description"]} {"← likely PVPM" if p["isLikelyPvpm"] else ""}'.strip(),
            }
            for p in self._candidate_ports()
        ]

    def auto_connect(self) -> dict:
        ports = self._candidate_ports()
        likely = [p for p in ports if p["isLikelyPvpm"]]
        selected = likely[0]["name"] if likely else (ports[0]["name"] if ports else None)
        if not selected:
            self.last_error = "No serial/FTDI ports found."
            return self.detect()
        return self.connect(selected)

    def connect(self, port: str) -> dict:
        if not port or port.lower() in {"auto", "pvpm", "default"}:
            return self.auto_connect()

        self.port = port
        self.connected = True
        self._transfer_detected = False
        self._captured = []
        self.last_error = None

        baud = self._probe_baud(port)
        if baud:
            self._baud = baud
        else:
            self._baud = settings.serial_baud_rate
            self.last_error = (
                f"Connected to {port}. Press Transfer on the PVPM to start streaming SUI data."
            )
        return self.detect()

    def disconnect(self) -> None:
        self.connected = False
        self.port = None
        self._baud = None
        self._transfer_detected = False
        self._captured = []
        self.last_error = None

    def is_transfer_mode(self) -> bool:
        return self._transfer_detected

    def fetch_device_info(self) -> dict:
        return self.detect()

    def fetch_measurements(self) -> list[dict]:
        if not self.port:
            self.auto_connect()
        if not self.port:
            raise RuntimeError("No FTDI/serial port available for PVPM direct USB access.")

        results: list[dict] = []
        baud_plan = [self._baud] if self._baud else [settings.serial_baud_rate]
        for b in _BAUD_RATES:
            if b not in baud_plan:
                baud_plan.append(b)

        for baud in baud_plan:
            files = self._capture_sui_stream(self.port, baud)
            if files:
                self._baud = baud
                self._transfer_detected = True
                parsed_count = 0
                for raw in files:
                    item = _parse_sui_bytes(raw, self.port)
                    if item:
                        results.append(item)
                        parsed_count += 1
                        with self._lock:
                            self._captured.append(raw)
                self.last_error = None if parsed_count else "Captured bytes but could not parse any SUI files."
                return results

        self._transfer_detected = False
        self.last_error = (
            f"No SUI data received on {self.port}. "
            "Connect the PVPM with USB and press Transfer on the device."
        )
        return results

    def list_files(self) -> list[dict]:
        files = []
        with self._lock:
            for i, raw in enumerate(self._captured):
                files.append(
                    {
                        "name": f"capture_{i+1:03d}.sui",
                        "size": len(raw),
                        "modified": _decode_tail_timestamp(raw) or _now_iso(),
                        "type": "sui",
                    }
                )
        return files

    def _probe_baud(self, port: str) -> Optional[int]:
        for baud in [settings.serial_baud_rate] + [b for b in _BAUD_RATES if b != settings.serial_baud_rate]:
            try:
                with serial.Serial(port, baud, timeout=0.2) as s:
                    s.reset_input_buffer()
                    return baud
            except serial.SerialException:
                continue
        return None

    def _capture_sui_stream(self, port: str, baud: int) -> list[bytes]:
        buf = bytearray()
        try:
            with serial.Serial(
                port,
                baudrate=baud,
                timeout=0.1,
                bytesize=8,
                parity="N",
                stopbits=1,
            ) as s:
                s.reset_input_buffer()
                deadline = time.time() + _CONNECT_TIMEOUT
                while time.time() < deadline:
                    chunk = s.read(256)
                    if chunk:
                        buf.extend(chunk)
                        if _SUI_HEADER_MAGIC in buf:
                            break
                else:
                    return []

                last_data = time.time()
                while True:
                    chunk = s.read(256)
                    if chunk:
                        buf.extend(chunk)
                        last_data = time.time()
                    elif time.time() - last_data > _FILE_END_TIMEOUT:
                        break
        except serial.SerialException as exc:
            self.last_error = f"Serial error on {port}: {exc}"
            return []

        return _split_sui_stream(bytes(buf))


def _split_sui_stream(data: bytes) -> list[bytes]:
    files: list[bytes] = []
    pos = 0
    while pos < len(data):
        header_pos = data.find(_SUI_HEADER_MAGIC, pos)
        if header_pos < 0:
            break

        next_pos = data.find(_SUI_HEADER_MAGIC, header_pos + 8)
        if next_pos > 0:
            files.append(data[header_pos:next_pos])
            pos = next_pos
        else:
            files.append(data[header_pos:])
            break
    return [f for f in files if len(f) > 64]
