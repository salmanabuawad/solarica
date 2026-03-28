from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Driver selection: "mock" | "serial" | "vendor_export"
    pvpm_driver: str = Field(default="mock", alias="PVPM_DRIVER")

    # Cloud backend to sync measurements to
    backend_base_url: str = Field(
        default="http://localhost:8000", alias="BACKEND_BASE_URL"
    )

    # Local SQLite database for caching
    local_db_path: str = Field(
        default="./data/connector.db", alias="LOCAL_DB_PATH"
    )

    # Serial port settings
    serial_baud_rate: int = Field(default=115200, alias="SERIAL_BAUD_RATE")
    serial_timeout_seconds: int = Field(default=3, alias="SERIAL_TIMEOUT_SECONDS")

    # Vendor export driver: folder to watch for exported PVPM files
    watch_folder: str = Field(default="./import_watch", alias="WATCH_FOLDER")

    # HTTP server
    connector_port: int = Field(default=8765, alias="CONNECTOR_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @property
    def local_db_file(self) -> Path:
        return Path(self.local_db_path).resolve()

    @property
    def watch_folder_path(self) -> Path:
        return Path(self.watch_folder).resolve()


settings = Settings()
