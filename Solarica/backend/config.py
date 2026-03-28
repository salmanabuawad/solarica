from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ─────────────────────────────────────────────────────────────
    # In Docker: set via DATABASE_URL env var (composed by docker-compose.yml)
    database_url: str = "postgresql://postgres:postgres@localhost:5432/ivcare"

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key: str = "dev-secret-key"
    access_token_expire_minutes: int = 480  # 8 hours

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Accepts a JSON list OR a comma-separated string via the CORS_ORIGINS env var.
    # Defaults include localhost dev servers AND the Docker nginx origin (port 80).
    cors_origins: list[str] = [
        "http://localhost",
        "http://localhost:80",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Accept JSON list or comma-separated string from env."""
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Try JSON first ("["http://x", "http://y"]")
            stripped = v.strip()
            if stripped.startswith("["):
                import json
                return json.loads(stripped)
            # Fall back to comma-separated
            return [o.strip() for o in stripped.split(",") if o.strip()]
        return v

    # ── Import folder ────────────────────────────────────────────────────────
    import_folder: str = "import_data"
    import_folder_path: Path = Path("import_data")
    watch_import_folder: bool = False

    @property
    def IMPORT_FOLDER(self) -> str:
        return str(
            self.import_folder_path.resolve()
            if self.import_folder_path
            else self.import_folder
        )

    @property
    def WATCH_IMPORT_FOLDER(self) -> bool:
        return self.watch_import_folder

    @property
    def CORS_ORIGINS(self) -> list[str]:
        return self.cors_origins

    class Config:
        env_file = ".env"


settings = Settings()
