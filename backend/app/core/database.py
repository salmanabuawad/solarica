import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def ensure_schema_patches() -> None:
    """
    Idempotent DDL for existing DBs that predate new ORM columns.
    create_all() does not ALTER existing tables, so new columns must be added here.
    """
    if engine.dialect.name != "postgresql":
        return
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'projects' AND column_name = 'is_active'
                    """
                )
            ).first()
            if row is None:
                conn.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE"
                    )
                )
                logger.info("Schema patch: added projects.is_active")
            else:
                logger.debug("Schema patch: projects.is_active already present")
    except Exception as e:
        logger.warning("Schema patch projects.is_active failed: %s", e)

    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'projects' AND column_name = 'scan_analytics_json'
                    """
                )
            ).first()
            if row is None:
                conn.execute(
                    text(
                        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS scan_analytics_json JSONB"
                    )
                )
                logger.info("Schema patch: added projects.scan_analytics_json")
            else:
                logger.debug("Schema patch: projects.scan_analytics_json already present")
    except Exception as e:
        logger.warning("Schema patch projects.scan_analytics_json failed: %s", e)

    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'projects' AND column_name = 'string_pattern'
                    """
                )
            ).first()
            if row is None:
                conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS string_pattern VARCHAR(64)"))
                logger.info("Schema patch: added projects.string_pattern")
            else:
                logger.debug("Schema patch: projects.string_pattern already present")
    except Exception as e:
        logger.warning("Schema patch projects.string_pattern failed: %s", e)


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
