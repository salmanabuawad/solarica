from __future__ import annotations

class VendorExportDriver:
    def __init__(self) -> None:
        self.connected = False
        self.port = None

    def detect(self) -> dict:
        return {
            "connected": self.connected,
            "mode": "vendor_export",
            "port": self.port,
            "deviceModel": None,
            "deviceSerial": None,
            "firmwareVersion": None,
            "transferModeRequired": True,
            "transferModeDetected": False,
            "lastError": "Export parser not implemented yet.",
        }

    def list_ports(self) -> list[dict]:
        return [{"name": "EXPORT", "description": "Vendor export directory monitor"}]

    def connect(self, port: str) -> dict:
        self.connected = True
        self.port = port
        return self.detect()

    def disconnect(self) -> None:
        self.connected = False
        self.port = None

    def is_transfer_mode(self) -> bool:
        return False

    def fetch_device_info(self) -> dict:
        return self.detect()

    def fetch_measurements(self) -> list[dict]:
        raise NotImplementedError("Vendor export parser not implemented yet.")
