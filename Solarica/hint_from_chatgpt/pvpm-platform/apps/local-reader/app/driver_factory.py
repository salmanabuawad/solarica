from .config import settings
from .drivers.mock_driver import MockDriver
from .drivers.serial_driver import SerialDirectDriver
from .drivers.vendor_export_driver import VendorExportDriver

_driver = None

def get_driver():
    global _driver
    if _driver is not None:
        return _driver
    match settings.pvpm_driver:
        case 'serial':
            _driver = SerialDirectDriver()
        case 'vendor_export':
            _driver = VendorExportDriver()
        case _:
            _driver = MockDriver()
    return _driver
