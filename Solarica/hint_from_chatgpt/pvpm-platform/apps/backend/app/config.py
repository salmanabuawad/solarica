from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    database_url: str = Field(default='postgresql+psycopg://postgres:postgres@localhost:5432/pvpm', alias='DATABASE_URL')
    jwt_secret: str = Field(default='change-me', alias='JWT_SECRET')
    log_level: str = Field(default='INFO', alias='LOG_LEVEL')

settings = Settings()
