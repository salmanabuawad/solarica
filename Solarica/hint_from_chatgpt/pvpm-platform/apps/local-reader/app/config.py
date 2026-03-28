from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    pvpm_driver: str = Field(default='mock', alias='PVPM_DRIVER')
    backend_base_url: str = Field(default='http://localhost:9000', alias='BACKEND_BASE_URL')
    local_db_path: str = Field(default='./data/local_reader.db', alias='LOCAL_DB_PATH')
    serial_baud_rate: int = Field(default=115200, alias='SERIAL_BAUD_RATE')
    serial_timeout_seconds: int = Field(default=3, alias='SERIAL_TIMEOUT_SECONDS')
    log_level: str = Field(default='INFO', alias='LOG_LEVEL')

    @property
    def local_db_file(self) -> Path:
        return Path(self.local_db_path).resolve()

settings = Settings()
