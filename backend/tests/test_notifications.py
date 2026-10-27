from datetime import date

import httpx
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.models import NotificationLog, NotificationStatus, NotifyMode, Plant, PlantStatus, Recurrence
from app.services import notifications, tasks


class FakeClient:
    def __init__(self, fail: bool = False):
        self.messages: list[str] = []
        self.fail = fail

    def send(self, text: str) -> None:
        if self.fail:
            raise notifications.TelegramError("Telegram ha risposto 502")
        self.messages.append(text)


@pytest.fixture
def telegram(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "notify_time", "08:00")
    return FakeClient()


def make(db, plant, notify=NotifyMode.BOTH, **values):
    data = {"name": "Innaffiare", "recurrence": Recurrence.ONCE, "start_date": date(2026, 3, 11), "notify": notify}
    return tasks.create_task(db, plant, data | values)


def logs(db):
    db.expire_all()
    return list(db.scalars(select(NotificationLog).order_by(NotificationLog.id)))


def test_day_before_reminder(db, plant, at, telegram):
    at("2026-03-01 07:00")
    make(db, plant, notify=NotifyMode.DAY_BEFORE)
    result = notifications.run_reminders(db, telegram, at("2026-03-10 08:05"))
    assert result.sent == 1
    assert "Da fare domani" in telegram.messages[0] and "Ginepro: Innaffiare" in telegram.messages[0]
    assert [(log.reminder, log.status) for log in logs(db)] == [("day_before", NotificationStatus.SENT)]

    notifications.run_reminders(db, telegram, at("2026-03-11 08:05"))
    assert len(telegram.messages) == 1


def test_day_of_reminder(db, plant, at, telegram):
    at("2026-03-01 07:00")
    make(db, plant, notify=NotifyMode.DAY_OF)
    notifications.run_reminders(db, telegram, at("2026-03-10 09:00"))
    assert telegram.messages == []
    notifications.run_reminders(db, telegram, at("2026-03-11 08:00"))
    assert "Da fare oggi" in telegram.messages[0]


def test_both_reminders_and_no_duplicates_after_restart(db, plant, at, telegram):
    at("2026-03-01 07:00")
    make(db, plant)
    notifications.run_reminders(db, telegram, at("2026-03-10 08:00"))
    notifications.run_reminders(db, telegram, at("2026-03-10 12:00"))
    restarted = FakeClient()
    notifications.run_reminders(db, restarted, at("2026-03-10 18:00"))
    notifications.run_reminders(db, restarted, at("2026-03-11 08:00"))
    notifications.run_reminders(db, restarted, at("2026-03-11 20:00"))
    assert len(telegram.messages) == 1
    assert len(restarted.messages) == 1 and "Da fare oggi" in restarted.messages[0]
    assert [log.reminder for log in logs(db)] == ["day_before", "day_of"]


def test_day_before_is_calendar_based_not_24h(db, plant, at, telegram):
    at("2026-03-01 07:00")
    make(db, plant, notify=NotifyMode.DAY_BEFORE)
    notifications.run_reminders(db, telegram, at("2026-03-09 23:30"))
    assert telegram.messages == []
    notifications.run_reminders(db, telegram, at("2026-03-10 23:30"))
    assert len(telegram.messages) == 1


def test_respects_per_task_setting(db, plant, at, telegram):
    at("2026-03-01 07:00")
    make(db, plant, notify=NotifyMode.NONE, name="Silenzioso")
    make(db, plant, notify=NotifyMode.DAY_OF, name="Solo giorno")
    notifications.run_reminders(db, telegram, at("2026-03-10 08:00"))
    assert telegram.messages == []
    notifications.run_reminders(db, telegram, at("2026-03-11 08:00"))
    assert "Solo giorno" in telegram.messages[0] and "Silenzioso" not in telegram.messages[0]


def test_no_reminder_for_suspended_or_skipped(db, plant, at, telegram):
    at("2026-03-01 07:00")
    suspended = make(db, plant, name="Sospeso")
    skipped = make(db, plant, name="Saltato")
    tasks.suspend(db, suspended, date(2026, 3, 20))
    tasks.skip(db, tasks.next_pending(db, skipped).id)
    notifications.run_reminders(db, telegram, at("2026-03-10 08:00"))
    notifications.run_reminders(db, telegram, at("2026-03-11 08:00"))
    assert telegram.messages == []


def test_no_reminder_for_completed_occurrence(db, plant, at, telegram):
    at("2026-03-01 07:00")
    task = make(db, plant)
    tasks.complete(db, tasks.next_pending(db, task).id)
    notifications.run_reminders(db, telegram, at("2026-03-10 08:00"))
    assert telegram.messages == []


def test_no_reminder_for_archived_plant(db, plant, at, telegram):
    at("2026-03-01 07:00")
    make(db, plant)
    db.get(Plant, plant.id).status = PlantStatus.ARCHIVED
    db.commit()
    notifications.run_reminders(db, telegram, at("2026-03-10 08:00"))
    notifications.run_reminders(db, telegram, at("2026-03-11 08:00"))
    assert telegram.messages == []


def test_no_backlog_after_suspension(db, plant, at, telegram):
    at("2026-03-01 07:00")
    make(
        db, plant, recurrence=Recurrence.CALENDAR, calendar_rule={"kind": "weekly", "weekdays": [0, 2, 4]},
        start_date=date(2026, 3, 1),
    )
    task = db.scalars(select(tasks.Task)).first()
    tasks.suspend(db, task, date(2026, 3, 20))
    result = notifications.run_reminders(db, telegram, at("2026-03-20 08:00"))
    assert result.sent == 1
    assert telegram.messages[0].count("•") == 1
    assert "Da fare oggi" in telegram.messages[0]


def test_failed_send_is_retried_a_limited_number_of_times(db, plant, at, monkeypatch):
    monkeypatch.setattr(get_settings(), "notify_max_attempts", 2)
    at("2026-03-01 07:00")
    make(db, plant, notify=NotifyMode.DAY_OF)
    failing = FakeClient(fail=True)
    notifications.run_reminders(db, failing, at("2026-03-11 08:00"))
    notifications.run_reminders(db, failing, at("2026-03-11 08:10"))
    notifications.run_reminders(db, failing, at("2026-03-11 08:20"))
    [log] = logs(db)
    assert log.status == NotificationStatus.FAILED and log.attempts == 2
    assert log.last_error == "Telegram ha risposto 502"


def test_retry_succeeds_after_failure(db, plant, at):
    at("2026-03-01 07:00")
    make(db, plant, notify=NotifyMode.DAY_OF)
    notifications.run_reminders(db, FakeClient(fail=True), at("2026-03-11 08:00"))
    working = FakeClient()
    notifications.run_reminders(db, working, at("2026-03-11 08:10"))
    notifications.run_reminders(db, working, at("2026-03-11 08:20"))
    assert len(working.messages) == 1
    assert logs(db)[0].status == NotificationStatus.SENT


def test_telegram_not_configured_does_nothing(db, plant, at):
    at("2026-03-01 07:00")
    make(db, plant)
    result = notifications.run_reminders(db, None, at("2026-03-11 08:00"))
    assert result.skipped_reason == "telegram non configurato"
    assert logs(db) == []


def test_client_errors_do_not_leak_token(monkeypatch):
    token = "123456:SEGRETO"

    def raise_connect_error(url, **kwargs):
        raise httpx.ConnectError(f"cannot connect to {url}")

    monkeypatch.setattr(httpx, "post", raise_connect_error)
    with pytest.raises(notifications.TelegramError) as info:
        notifications.TelegramClient(token, "42").send("ciao")
    assert token not in str(info.value)
    assert info.value.__cause__ is None

    def bad_status(url, **kwargs):
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    monkeypatch.setattr(httpx, "post", bad_status)
    with pytest.raises(notifications.TelegramError) as info:
        notifications.TelegramClient(token, "42").send("ciao")
    assert str(info.value) == "Telegram ha risposto 401: Unauthorized"
