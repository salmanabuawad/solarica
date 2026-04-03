"""
Bootstrap seed data into the database when tables are empty.
Called during FastAPI lifespan startup.
"""
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def run_all_seeds(db: Session) -> None:
    """Run all seed functions in dependency order."""
    from app.repositories.user_repo import seed_default_users
    from app.repositories.project_repo import seed_projects
    from app.repositories.task_repo import seed_tasks
    from app.repositories.inventory_repo import seed_inventory
    from app.repositories.test_repo import seed_test_types

    try:
        seed_default_users(db)
        logger.info("Users seeded")
        seed_projects(db)
        logger.info("Projects seeded")
        seed_tasks(db)
        logger.info("Tasks seeded")
        seed_inventory(db)
        logger.info("Inventory seeded")
        seed_test_types(db)
        logger.info("Test types seeded")
        db.commit()
        logger.info("All seeds committed")
    except Exception as e:
        db.rollback()
        logger.error("Seed failed: %s", e)

    # Device inventory repository (from device_repo/device_repository/repository.json)
    try:
        from app.repositories.device_repo import seed_from_repository_json
        result = seed_from_repository_json(db)
        logger.info("Device repo seed: %s", result)
    except Exception as e:
        logger.error("Device repo seed failed: %s", e)

    # Field configuration defaults
    try:
        from app.repositories.field_config_repo import seed_defaults
        count = seed_defaults(db)
        logger.info("Field config seed: %d rows inserted", count)
    except Exception as e:
        logger.error("Field config seed failed: %s", e)
