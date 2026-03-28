from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    app_name: str = Field(default="Solar EPC Platform", alias="APP_NAME")
    app_env: str = Field(default="local", alias="APP_ENV")
    secret_key: str = Field(default="change-me", alias="SECRET_KEY")
    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")
    upload_dir: str = Field(default="/app/uploads", alias="UPLOAD_DIR")
    access_token_expire_minutes: int = Field(default=480, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    cors_origins_raw: str = Field(default="http://localhost:5173", alias="CORS_ORIGINS")

    @property
    def cors_origins(self) -> List[str]:
        return [item.strip() for item in self.cors_origins_raw.split(",") if item.strip()]

    class Config:
        env_file = ".env"


settings = Settings()
