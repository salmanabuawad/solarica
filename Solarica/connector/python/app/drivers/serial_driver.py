"""
Serial Direct Driver
====================
Reads measurements directly from a PVPM 1540X over USB/serial (FTDI COM port).

The PVPM 1540X uses a proprietary serial protocol. When the device is placed
in Transfer Mode (press the Transfer button on the device), it streams
measurement files in the SUI binary format over the COM port.

This driver:
  1. Opens the COM port and waits for the device to stream SUI data
  2. Detects SUI file headers in the byte stream (UIKennNFile\\n\\r\\x1a)
  3. Captures complete SUI files from the stream
  4. Parses them using the same SUI parser as the vendor_export driver

The device must be placed in Transfer Mode by the operator. The driver
will try multiple baud rates automatically to find the correct one.
"""

from __future__ import annotations

import io
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import serial
import serial.tools.list_ports


# SUI file magic headers (try all known versions)
_SUI_HEADERS = [
    b"UIKenn0File\n\r\x1a",  # real device files from PVPM 1540X use version 0
    b"UIKenn1File\n\r\x1a",
    b"UIKenn2File\n\r\x1a",
    b"UIKenn3File\n\r\x1a",
    b"UIKenn4File\n\r\x1a",
    b"UIKenn5File\n\r\x1a",
    b"UIKenn6File\n\r\x1a",
]
_SUI_HEADER_MAGIC = b"UIKenn"

# Baud rates to probe (most likely first based on device type)
_BAUD_RATES = [115200, 57600, 38400, 19200, 9600]

# Inter-byte timeout — if no data for this long, assume file transfer complete
_FILE_END_TIMEOUT = 2.0   # seconds
_CONNECT_TIMEOUT  = 30.0  # seconds to wait for Transfer Mode signal


class SerialDirectDriver:
    """
    Reads measurement files directly from a PVPM 1540X via serial/USB.
    Place the device in Transfer Mode to start streaming SUI files.
    """

    def __init__(self) -> None:
        self.connected    = False
        self.port: Optional[str] = None
        self.last_error: Optional[str] = None
        self._baud: Optional[int] = None
        self._device_model: Optional[str] = None
        self._device_serial: Optional[str] = None
        self._transfer_detected = False
        self._captured: list[bytes] = []   # raw SUI file bytes captured
        self._lock = threading.Lock()

    # ── Status ────────────────────────────────────────────────────────────────

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

    def list_ports(self) -> list[dict]:
        ports = []
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").strip()
            mfr  = (p.manufacturer or "").lower()
            # Highlight FTDI ports (PVPM uses FTDI FT232R)
            is_pvpm = "ftdi" in mfr or "usb serial" in desc.lower()
            ports.append({
                "name": p.device,
                "description": f"{desc} {'← PVPM device' if is_pvpm else ''}".strip(),
            })
        return ports

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self, port: str) -> dict:
        self.port         = port
        self.connected    = True
        self._transfer_detected = False
        self._captured    = []
        self.last_error   = None

        # Try to open the port to verify it exists
        baud = self._probe_baud(port)
        if baud:
            self._baud = baud
            self.last_error = None
        else:
            self._baud = 115200  # default, will be confirmed on first transfer
            self.last_error = (
                "Port opened. Press Transfer on the PVPM device to start data streaming."
            )

        return self.detect()

    def disconnect(self) -> None:
        self.connected          = False
        self.port               = None
        self._baud              = None
        self._transfer_detected = False
        self._captured          = []
        self.last_error         = None

    def is_transfer_mode(self) -> bool:
        return self._transfer_detected

    def fetch_device_info(self) -> dict:
        return self.detect()

    # ── Measurement capture ───────────────────────────────────────────────────

    def fetch_measurements(self) -> list[dict]:
        """
        Open the COM port and wait for the PVPM to stream SUI files.
        The operator must press the Transfer button on the device.
        Tries each baud rate until SUI data is detected.
        """
        if not self.port:
            raise RuntimeError("Not connected to any port.")

        results: list[dict] = []

        for baud in ([self._baud] if self._baud else _BAUD_RATES):
            files = self._capture_sui_stream(self.port, baud)
            if files:
                self._baud = baud
                self._transfer_detected = True
                for raw in files:
                    parsed = _parse_sui_bytes(raw)
                    if parsed:
                        results.append(parsed)
                        with self._lock:
                            self._captured.append(raw)
                self.last_error = None
                return results

        # No data received
        self._transfer_detected = False
        self.last_error = (
            f"No data received on {self.port}. "
            "Make sure the PVPM is in Transfer Mode (press Transfer on device) "
            "and the USB cable is connected."
        )
        return results

    def list_files(self) -> list[dict]:
        """List files captured so far from the serial stream."""
        files = []
        with self._lock:
            for i, raw in enumerate(self._captured):
                meta = _extract_sui_meta(raw)
                files.append({
                    "name": f"capture_{i+1:03d}.sui",
                    "size": len(raw),
                    "modified": meta.get("measuredAt", datetime.now(timezone.utc).isoformat()),
                    "type": "sui",
                    **{k: v for k, v in meta.items() if k != "measuredAt"},
                    **({"measuredAt": meta["measuredAt"]} if "measuredAt" in meta else {}),
                })
        return files

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _probe_baud(self, port: str) -> Optional[int]:
        """Try opening the port briefly at each baud rate to confirm it exists."""
        for baud in _BAUD_RATES:
            try:
                with serial.Serial(port, baud, timeout=0.2) as s:
                    s.reset_input_buffer()
                    # Just confirm it opens cleanly
                    return baud  # Return first working baud (we'll auto-detect on transfer)
            except serial.SerialException:
                continue
        return None

    def _capture_sui_stream(self, port: str, baud: int) -> list[bytes]:
        """
        Open COM port, wait up to CONNECT_TIMEOUT seconds for SUI header,
        then capture all streaming SUI files.
        Returns list of raw SUI file byte strings.
        """
        captured_files: list[bytes] = []
        buf = bytearray()

        try:
            with serial.Serial(port, baud, timeout=0.1, bytesize=8,
                               parity='N', stopbits=1) as s:
                s.reset_input_buffer()

                # Phase 1: wait for first SUI header byte ('U' from "UIKenn")
                deadline = time.time() + _CONNECT_TIMEOUT
                print(f"[Serial] Waiting for Transfer Mode on {port} at {baud} baud...")

                while time.time() < deadline:
                    chunk = s.read(256)
                    if chunk:
                        buf.extend(chunk)
                        if _SUI_HEADER_MAGIC in buf:
                            break
                else:
                    return []   # timed out, no data

                # Phase 2: capture complete SUI files from the stream
                last_data = time.time()
                while True:
                    chunk = s.read(256)
                    if chunk:
                        buf.extend(chunk)
                        last_data = time.time()
                    elif time.time() - last_data > _FILE_END_TIMEOUT:
                        break  # No new data — transfer complete

                print(f"[Serial] Received {len(buf)} bytes at baud {baud}")

        except serial.SerialException as exc:
            print(f"[Serial] Port error at baud {baud}: {exc}")
            return []

        # Split buffer into individual SUI files
        captured_files = _split_sui_stream(bytes(buf))
        print(f"[Serial] Extracted {len(captured_files)} SUI file(s)")
        return captured_files


# ---------------------------------------------------------------------------
# SUI stream splitter — handles one or more SUI files concatenated in a stream
# ---------------------------------------------------------------------------

def _split_sui_stream(data: bytes) -> list[bytes]:
    """Split a byte stream containing one or more concatenated SUI files."""
    files: list[bytes] = []
    pos = 0
    while pos < len(data):
        # Find next SUI header
        header_pos = -1
        for hdr in _SUI_HEADERS:
            idx = data.find(hdr[:6], pos)  # search for "UIKenn"
            if idx >= 0:
                # Verify full header
                for h in _SUI_HEADERS:
                    if data[idx:idx+len(h)] == h:
                        header_pos = idx
                        break
                if header_pos >= 0:
                    break

        if header_pos < 0:
            break  # No more SUI files

        # Find start of next SUI file (to determine end of current)
        next_pos = -1
        for h in _SUI_HEADERS:
            idx = data.find(h[:6], header_pos + 16)
            if idx >= 0 and (next_pos < 0 or idx < next_pos):
                next_pos = idx

        if next_pos > 0:
            files.append(data[header_pos:next_pos])
            pos = next_pos
        else:
            files.append(data[header_pos:])
            break

    return [f for f in files if len(f) > 50]  # filter out tiny fragments


# ---------------------------------------------------------------------------
# SUI metadata parser (shared logic with vendor_export_driver)
# ---------------------------------------------------------------------------

def _extract_sui_meta(data: bytes) -> dict:
    """Extract metadata from SUI binary data."""
    import re
    meta: dict = {}

    kunde_idx = data.find(b"Kunde:")
    if kunde_idx != -1:
        block_start = data.rfind(b"\x00\x00\x00\x00", 0, kunde_idx)
        block_start = block_start + 4 if block_start != -1 else kunde_idx
        block = data[block_start:kunde_idx + 400].decode("latin-1", errors="replace")
        lines = block.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped and "stringNo" not in meta:
                meta["stringNo"] = stripped
                break
        for line in lines:
            line = line.strip()
            if line.startswith("Kunde:"):
                meta["customer"] = line[6:].strip()
            elif line.startswith("Modultyp:"):
                meta["moduleType"] = line[9:].strip()
            elif "Module im String" in line:
                parts = line.split()
                if parts and parts[0].isdigit():
                    meta["moduleCount"] = int(parts[0])

    tail_text = data[-100:].decode("latin-1", errors="replace")
    date_match = re.search(r"(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2})", tail_text)
    if date_match:
        date_str = date_match.group(1).strip()
        for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y  %H:%M:%S"):
            try:
                dt = datetime.strptime(date_str, fmt)
                meta["measuredAt"] = dt.replace(tzinfo=timezone.utc).isoformat()
                break
            except ValueError:
                continue

    pvpm_match = re.search(rb"((?:PVPM|VPM)\w+)", data[-300:])
    if pvpm_match:
        meta["externalMeasurementKey"] = pvpm_match.group(1).decode("latin-1")

    return meta


def _parse_sui_bytes(data: bytes) -> Optional[dict]:
    """Parse a complete SUI file from raw bytes into a measurement dict."""
    if not any(data.startswith(h) for h in _SUI_HEADERS):
        return None

    meta = _extract_sui_meta(data)
    measured_at = meta.get("measuredAt") or datetime.now(timezone.utc).isoformat()

    return {
        "id": uuid.uuid4().hex,
        "importSource": "serial:COM",
        "syncStatus": "unsynced",
        "curvePoints": [],
        "measuredAt": measured_at,
        "rawPayloadJson": {"source": "serial_transfer", **meta},
        **{k: v for k, v in meta.items()
           if k in ("stringNo", "customer", "moduleType", "externalMeasurementKey")},
    }
