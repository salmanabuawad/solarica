from __future__ import annotations
from ..mock_data import generate_measurements

class MockDriver:
    def __init__(self) -> None:
        self.connected = False
        self.port = None

    def detect(self) -> dict:
        return {
            "connected": self.connected,
            "mode": "mock",
            "port": self.port,
            "deviceModel": "PVPM 1540X",
            "deviceSerial": "PVPM1540X-MOCK-001",
            "firmwareVersion": "mock-1.0",
            "transferModeRequired": True,
            "transferModeDetected": self.connected,
            "lastError": None,
        }

    def list_ports(self) -> list[dict]:
        return [
            {"name": "MOCK1", "description": "Mock PVPM device"},
            {"name": "MOCK2", "description": "Mock backup device"},
        ]

    def connect(self, port: str) -> dict:
        self.connected = True
        self.port = port
        return self.detect()

    def disconnect(self) -> None:
        self.connected = False
        self.port = None

    def is_transfer_mode(self) -> bool:
        return self.connected

    def fetch_device_info(self) -> dict:
        return self.detect()

    def fetch_measurements(self) -> list[dict]:
        return generate_measurements(25)
