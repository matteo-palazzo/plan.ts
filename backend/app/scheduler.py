import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import delete

from app.clock import now
from app.config import get_settings
from app.db import SessionLocal, engine
from app.models import UserSession
from app.services import backup, notifications, tasks

logger = logging.getLogger(__name__)


def reminders_job() -> None:
    try:
        with SessionLocal() as db:
            tasks.sync_all(db)
            notifications.run_reminders(db)
    except Exception:
        logger.exception("Errore durante l'elaborazione dei promemoria")


def backup_job() -> None:
    try:
        backup.create_backup(engine)
    except Exception:
        logger.error("Backup settimanale non riuscito: dettagli in backup-errors.log")


def cleanup_job() -> None:
    try:
        with SessionLocal() as db:
            db.execute(delete(UserSession).where(UserSession.expires_at < now()))
            db.commit()
    except Exception:
        logger.exception("Errore durante la pulizia delle sessioni scadute")


def start_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    scheduler = BackgroundScheduler(
        timezone=settings.zone, job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600}
    )
    scheduler.add_job(reminders_job, "interval", minutes=settings.notify_check_minutes, id="reminders", next_run_time=now())
    scheduler.add_job(backup_job, CronTrigger.from_crontab(settings.backup_schedule, timezone=settings.zone), id="backup")
    scheduler.add_job(cleanup_job, "cron", hour=4, minute=10, id="sessions-cleanup")
    scheduler.start()
    logger.info("Scheduler avviato (backup: %s, promemoria ogni %d minuti)", settings.backup_schedule, settings.notify_check_minutes)
    return scheduler
