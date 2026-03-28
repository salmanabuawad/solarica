from __future__ import annotations
import serial.tools.list_ports

class SerialDirectDriver:
    def __init__(self) -> None:
        self.connected = False
        self.port: str | None = None
        self.last_error: str | None = None

    def detect(self) -> dict:
        return {
            "connected": self.connected,
            "mode": "serial",
            "port": self.port,
            "deviceModel": None,
            "deviceSerial": None,
            "firmwareVersion": None,
            "transferModeRequired": True,
            "transferModeDetected": False,
            "lastError": self.last_error,
        }

    def list_ports(self) -> list[dict]:
        return [
            {"name": port.device, "description": port.description}
            for port in serial.tools.list_ports.comports()
        ]

    def connect(self, port: str) -> dict:
        self.connected = True
        self.port = port
        self.last_error = "Protocol not implemented yet. Use diagnostics to capture serial traffic."
        return self.detect()

    def disconnect(self) -> None:
        self.connected = False
        self.port = None

    def is_transfer_mode(self) -> bool:
        return False

    def fetch_device_info(self) -> dict:
        return self.detect()

    def fetch_measurements(self) -> list[dict]:
        raise NotImplementedError("Serial protocol not implemented yet.")
