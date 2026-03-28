from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.schemas import DeviceInfo


class PVPMAdapter(ABC):
    @abstractmethod
    def detect_device(self) -> DeviceInfo:
        raise NotImplementedError

    @abstractmethod
    def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def apply_metadata(self, site_name: str | None, part_name: str | None, module_part_number: str | None) -> bool:
        raise NotImplementedError

    @abstractmethod
    def trigger_measurement(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def fetch_result(self) -> dict[str, Any]:
        raise NotImplementedError
