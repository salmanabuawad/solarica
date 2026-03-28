from __future__ import annotations

from functools import lru_cache

from app.adapters.serial_adapter import SerialAdapter
from app.adapters.simulator_adapter import SimulatorAdapter
from app.config import ADAPTER_MODE
from app.services.controller import DeviceController
from app.services.session_manager import SessionManager
from app.services.storage import StorageService


@lru_cache
def get_adapter():
    if ADAPTER_MODE == "serial":
        return SerialAdapter()
    return SimulatorAdapter()


@lru_cache
def get_session_manager() -> SessionManager:
    return SessionManager()


@lru_cache
def get_storage_service() -> StorageService:
    return StorageService()


@lru_cache
def get_controller() -> DeviceController:
    return DeviceController(get_adapter(), get_session_manager(), get_storage_service())
