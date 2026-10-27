import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import httpx
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import now
from app.config import Settings, get_settings
from app.models import (
    NotificationLog,
    NotificationStatus,
    NotifyMode,
    OccurrenceStatus,
    Plant,
    PlantStatus,
    ReminderKind,
    Task,
    TaskOccurrence,
    TaskStatus,
)
from app.services import tasks

logger = logging.getLogger(__name__)

REMINDER_MODES = {
    ReminderKind.DAY_OF: (NotifyMode.DAY_OF, NotifyMode.BOTH),
    ReminderKind.DAY_BEFORE: (NotifyMode.DAY_BEFORE, NotifyMode.BOTH),
}


class TelegramError(Exception):
    pass


class TelegramClient:
    def __init__(self, token: str, chat_id: str, timeout: float = 15.0):
        self._token = token
        self._chat_id = chat_id
        self._timeout = timeout

    def send(self, text: str) -> None:
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        try:
            response = httpx.post(
                url,
                json={"chat_id": self._chat_id, "text": text, "disable_web_page_preview": True},
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            raise TelegramError("Timeout nella comunicazione con Telegram") from None
        except httpx.HTTPError as exc:
            raise TelegramError(f"Errore di rete verso Telegram ({type(exc).__name__})") from None
        if response.status_code != 200:
            try:
                description = str(response.json().get("description", ""))[:150]
            except ValueError:
                description = ""
            raise TelegramError(f"Telegram ha risposto {response.status_code}: {description}".strip())


def build_client(settings: Settings | None = None) -> TelegramClient | None:
    settings = settings or get_settings()
    if not settings.telegram_configured:
        return None
    return TelegramClient(settings.telegram_bot_token.get_secret_value(), settings.telegram_chat_id)


@dataclass
class Reminder:
    log: NotificationLog
    occurrence: TaskOccurrence


@dataclass
class RunResult:
    sent: int = 0
    failed: int = 0
    skipped_reason: str | None = None


def _notify_time() -> time:
    hours, minutes = get_settings().notify_time.split(":")
    return time(int(hours), int(minutes))


def _candidates(db: Session, day: date) -> list[tuple[TaskOccurrence, ReminderKind]]:
    rows = db.scalars(
        select(TaskOccurrence)
        .join(TaskOccurrence.task)
        .join(Task.plant)
        .where(
            TaskOccurrence.status == OccurrenceStatus.PENDING,
            TaskOccurrence.due_date.in_([day, day + timedelta(days=1)]),
            Task.status == TaskStatus.ACTIVE,
            Task.notify != NotifyMode.NONE,
            Plant.status == PlantStatus.ACTIVE,
            or_(Task.suspended_until.is_(None), Task.suspended_until <= day),
        )
        .order_by(TaskOccurrence.due_date, Plant.name, Task.name)
    ).unique()
    result = []
    for occurrence in rows:
        reminder = ReminderKind.DAY_OF if occurrence.due_date == day else ReminderKind.DAY_BEFORE
        if occurrence.task.notify in REMINDER_MODES[reminder]:
            result.append((occurrence, reminder))
    return result


def _claim(db: Session, occurrence: TaskOccurrence, reminder: ReminderKind, day: date) -> NotificationLog | None:
    log = db.scalars(
        select(NotificationLog)
        .where(
            NotificationLog.occurrence_id == occurrence.id,
            NotificationLog.reminder == reminder,
            NotificationLog.due_date == occurrence.due_date,
        )
        .with_for_update()
    ).first()
    if log is None:
        log = NotificationLog(
            task_id=occurrence.task_id,
            occurrence_id=occurrence.id,
            reminder=reminder,
            due_date=occurrence.due_date,
            scheduled_for=day,
            status=NotificationStatus.SENDING,
            attempts=0,
        )
        db.add(log)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return None
        return log
    if log.status == NotificationStatus.FAILED and log.attempts < get_settings().notify_max_attempts:
        log.status = NotificationStatus.SENDING
        db.commit()
        return log
    db.commit()
    return None


def format_message(reminders: list[Reminder], day: date) -> str:
    sections = {ReminderKind.DAY_OF: "Da fare oggi", ReminderKind.DAY_BEFORE: "Da fare domani"}
    lines = ["🌿 Promemoria piante"]
    for kind, heading in sections.items():
        items = [item for item in reminders if item.log.reminder == kind]
        if not items:
            continue
        lines.append("")
        lines.append(f"{heading}:")
        for item in items:
            task = item.occurrence.task
            lines.append(f"• {task.plant.name}: {task.name}")
    return "\n".join(lines)


def run_reminders(db: Session, client: TelegramClient | None = None, moment: datetime | None = None) -> RunResult:
    settings = get_settings()
    client = client or build_client(settings)
    if client is None:
        return RunResult(skipped_reason="telegram non configurato")
    local = (moment or now()).astimezone(settings.zone)
    if local.time() < _notify_time():
        return RunResult(skipped_reason="orario di invio non ancora raggiunto")
    day = local.date()
    tasks.sync_all(db, day)

    claimed = []
    for occurrence, reminder in _candidates(db, day):
        log = _claim(db, occurrence, reminder, day)
        if log is not None:
            claimed.append(Reminder(log=log, occurrence=occurrence))
    if not claimed:
        return RunResult()

    text = format_message(claimed, day)
    try:
        client.send(text)
    except TelegramError as exc:
        for item in claimed:
            item.log.status = NotificationStatus.FAILED
            item.log.attempts += 1
            item.log.last_error = str(exc)[:255]
        db.commit()
        logger.warning("Invio promemoria Telegram fallito: %s", exc)
        return RunResult(failed=len(claimed))

    sent_at = now()
    for item in claimed:
        item.log.status = NotificationStatus.SENT
        item.log.attempts += 1
        item.log.sent_at = sent_at
        item.log.last_error = None
    db.commit()
    logger.info("Inviati %d promemoria Telegram", len(claimed))
    return RunResult(sent=len(claimed))


def send_test_message(client: TelegramClient | None = None) -> None:
    client = client or build_client()
    if client is None:
        raise TelegramError("Telegram non è configurato o è disattivato")
    client.send("🌿 Messaggio di prova: le notifiche Telegram dell'app piante funzionano.")
