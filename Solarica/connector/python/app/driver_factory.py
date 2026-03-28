from __future__ import annotations

from .config import settings
from .drivers.base import PVPMDriver

_driver_instance: PVPMDriver | None = None


def get_driver() -> PVPMDriver:
    global _driver_instance
    if _driver_instance is None:
        _driver_instance = _create_driver(settings.pvpm_driver)
    return _driver_instance


def _create_driver(name: str) -> PVPMDriver:
    name = name.lower().strip()
    if name == "mock":
        from .drivers.mock_driver import MockDriver
        return MockDriver()
    if name == "serial":
        from .drivers.serial_driver import SerialDirectDriver
        return SerialDirectDriver()
    if name in ("vendor_export", "vendor", "export"):
        from .drivers.vendor_export_driver import VendorExportDriver
        return VendorExportDriver()
    raise ValueError(
        f"Unknown PVPM driver '{name}'. Valid values: mock, serial, vendor_export"
    )
