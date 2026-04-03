"""
APScheduler setup for background jobs (red flag detection, etc.)
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


def _run_red_flags_job():
    """Daily job: scan all open issue transactions and raise variance flags."""
    try:
        from app.core.database import SessionLocal
        from app.repositories import inventory_repo
        db = SessionLocal()
        try:
            result = inventory_repo.run_red_flags(db)
            db.commit()
            logger.info("Red flag job completed: %s", result)
        finally:
            db.close()
    except Exception as e:
        logger.error("Red flag job failed: %s", e)


def start_scheduler():
    scheduler.add_job(
        _run_red_flags_job,
        trigger=CronTrigger(hour=6, minute=0),
        id="daily_red_flags",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("Scheduler started — daily red flag job at 06:00")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
