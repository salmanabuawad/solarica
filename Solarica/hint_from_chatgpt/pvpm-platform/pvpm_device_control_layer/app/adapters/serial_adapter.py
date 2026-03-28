from __future__ import annotations

from typing import Any

from app.adapters.base import PVPMAdapter
from app.models.schemas import DeviceInfo


class SerialAdapter(PVPMAdapter):
    """
    Stub for the real device protocol.

    Replace this class with the actual serial / FTDI implementation once you have
    confirmed the command set. The public interface is already stable, so your web app
    does not need to change later.
    """

    def __init__(self) -> None:
        self._open = False

    def detect_device(self) -> DeviceInfo:
        return DeviceInfo(
            connected=False,
            transport="serial",
            port=None,
            vendor="Unknown",
            device_model=None,
            serial_number=None,
            detail="Serial adapter stub. Implement COM/FTDI detection here.",
        )

    def open(self) -> None:
        # TODO: open COM port / FTDI handle
        self._open = True

    def close(self) -> None:
        # TODO: close COM port / FTDI handle
        self._open = False

    def apply_metadata(self, site_name: str | None, part_name: str | None, module_part_number: str | None) -> bool:
        if not self._open:
            raise RuntimeError("Adapter is not open")
        # TODO: implement protocol commands, if supported by the device/software flow.
        # Return False if device cannot truly store metadata before measurement.
        return False

    def trigger_measurement(self) -> None:
        if not self._open:
            raise RuntimeError("Adapter is not open")
        # TODO: write trigger command to device.
        raise NotImplementedError("Real PVPM trigger command is not implemented yet")

    def fetch_result(self) -> dict[str, Any]:
        if not self._open:
            raise RuntimeError("Adapter is not open")
        # TODO: read raw bytes/result from device and return structured payload.
        raise NotImplementedError("Real PVPM fetch_result is not implemented yet")
