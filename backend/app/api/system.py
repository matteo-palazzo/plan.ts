from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import authenticated
from app.config import APP_VERSION, get_settings
from app.db import engine, get_db
from app.schemas import BackupInfo, BackupStatus, SettingsOut, TelegramStatus
from app.services import backup, notifications, tasks
from app.services.photos import SUPPORTED_FORMATS

router = APIRouter(tags=["sistema"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse({"status": "error", "database": "unreachable"}, status_code=503)
    return {"status": "ok", "database": "ok", "version": APP_VERSION}


@router.get("/settings", response_model=SettingsOut, dependencies=authenticated)
def app_settings():
    settings = get_settings()
    return SettingsOut(
        version=APP_VERSION,
        timezone=settings.tz,
        dashboard_days=min(settings.dashboard_days, tasks.GENERATION_HORIZON_DAYS),
        photo_max_mb=settings.photo_max_mb,
        photos_per_entry=settings.photos_per_entry,
        photo_formats=sorted(SUPPORTED_FORMATS),
        notify_time=settings.notify_time,
        telegram=TelegramStatus(enabled=settings.telegram_enabled, configured=settings.telegram_configured),
        backup_schedule=settings.backup_schedule,
        backup_retention_days=settings.backup_retention_days,
    )


@router.post("/settings/telegram/test", status_code=status.HTTP_204_NO_CONTENT, dependencies=authenticated)
def telegram_test():
    try:
        notifications.send_test_message()
    except notifications.TelegramError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from None


def _backup_status() -> BackupStatus:
    current = backup.read_status()
    return BackupStatus(
        last_run_at=current.get("last_run_at"),
        last_success_at=current.get("last_success_at"),
        last_result=current.get("last_result"),
        last_error=current.get("last_error"),
        last_file=current.get("last_file"),
        backups=[BackupInfo(**{k: v for k, v in item.items() if k != "path"}) for item in backup.list_backups()],
    )


@router.get("/backups", response_model=BackupStatus, dependencies=authenticated)
def backup_status():
    return _backup_status()


@router.post("/backups", response_model=BackupStatus, dependencies=authenticated)
def run_backup():
    try:
        backup.create_backup(engine)
    except Exception:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Backup non riuscito: controlla lo stato e i log") from None
    return _backup_status()
