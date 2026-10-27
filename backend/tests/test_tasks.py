from datetime import date

import pytest
from sqlalchemy import select

from app.errors import Conflict
from app.models import DiaryEntry, DiaryKind, OccurrenceStatus, Plant, PlantStatus, Recurrence, TaskOccurrence
from app.services import tasks
from app.services.recurrence import calendar_dates, next_interval_date_after


def occurrences(db, task):
    db.expire_all()
    return list(
        db.scalars(select(TaskOccurrence).where(TaskOccurrence.task_id == task.id).order_by(TaskOccurrence.due_date))
    )


def pending_dates(db, task):
    return [o.due_date for o in occurrences(db, task) if o.status == OccurrenceStatus.PENDING]


def make(db, plant, **values):
    defaults = {"name": "Innaffiatura", "recurrence": Recurrence.ONCE, "start_date": date(2026, 3, 2)}
    return tasks.create_task(db, plant, defaults | values)


def test_monthly_rule_uses_last_day_in_short_months():
    dates = list(calendar_dates({"kind": "monthly", "day": 31}, date(2026, 1, 1), date(2026, 4, 30)))
    assert dates == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


def test_weekly_rule_yields_selected_weekdays():
    dates = list(calendar_dates({"kind": "weekly", "weekdays": [0, 4]}, date(2026, 3, 2), date(2026, 3, 13)))
    assert dates == [date(2026, 3, 2), date(2026, 3, 6), date(2026, 3, 9), date(2026, 3, 13)]


def test_next_interval_date_after_is_first_step_strictly_after():
    assert next_interval_date_after(date(2026, 3, 1), 7, date(2026, 3, 8)) == date(2026, 3, 15)
    assert next_interval_date_after(date(2026, 3, 1), 7, date(2026, 3, 20)) == date(2026, 3, 22)
    assert next_interval_date_after(date(2026, 3, 10), 7, date(2026, 3, 1)) == date(2026, 3, 17)


def test_one_off_task_has_single_occurrence_and_stops_after_completion(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant)
    assert pending_dates(db, task) == [date(2026, 3, 2)]

    at("2026-03-02 09:00")
    tasks.complete(db, occurrences(db, task)[0].id)
    tasks.sync_all(db)
    assert [o.status for o in occurrences(db, task)] == [OccurrenceStatus.COMPLETED]


def test_one_off_skip_generates_nothing_else(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant)
    tasks.skip(db, occurrences(db, task)[0].id)
    assert [o.status for o in occurrences(db, task)] == [OccurrenceStatus.SKIPPED]


def test_interval_restarts_from_actual_completion(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant, recurrence=Recurrence.INTERVAL, interval_days=14, start_date=date(2026, 3, 6))
    assert pending_dates(db, task) == [date(2026, 3, 6)]

    at("2026-03-20 18:30")
    tasks.complete(db, occurrences(db, task)[0].id)
    assert pending_dates(db, task) == [date(2026, 4, 3)]


def test_interval_completion_uses_local_date_near_midnight(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant, recurrence=Recurrence.INTERVAL, interval_days=7, start_date=date(2026, 3, 1))
    at("2026-03-01 23:30")
    tasks.complete(db, occurrences(db, task)[0].id)
    assert pending_dates(db, task) == [date(2026, 3, 8)]


def test_completion_creates_diary_entry_with_note(db, plant, at):
    at("2026-03-02 08:00")
    task = make(db, plant)
    result = tasks.complete(db, occurrences(db, task)[0].id, note="Terriccio asciutto")
    entry = db.get(DiaryEntry, result.diary_entry.id)
    assert entry.kind == DiaryKind.TASK_COMPLETION
    assert entry.title == "Innaffiatura"
    assert entry.body == "Terriccio asciutto"
    assert entry.occurrence_id == result.occurrence.id
    assert entry.occurred_at == result.occurrence.completed_at


def test_repeated_completion_is_idempotent(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant, recurrence=Recurrence.INTERVAL, interval_days=7)
    occurrence_id = occurrences(db, task)[0].id
    first = tasks.complete(db, occurrence_id)
    second = tasks.complete(db, occurrence_id)
    assert second.already_completed
    assert second.diary_entry.id == first.diary_entry.id
    assert len(occurrences(db, task)) == 2
    assert db.scalars(select(DiaryEntry)).all().__len__() == 1


def test_skipped_occurrence_cannot_be_completed(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant)
    occurrence_id = occurrences(db, task)[0].id
    tasks.skip(db, occurrence_id)
    with pytest.raises(Conflict):
        tasks.complete(db, occurrence_id)


def test_calendar_task_stays_anchored_after_late_completion(db, plant, at):
    at("2026-03-01 10:00")
    task = make(
        db, plant, recurrence=Recurrence.CALENDAR, calendar_rule={"kind": "weekly", "weekdays": [0]},
        start_date=date(2026, 3, 1),
    )
    assert pending_dates(db, task)[:3] == [date(2026, 3, 2), date(2026, 3, 9), date(2026, 3, 16)]

    at("2026-03-03 09:00")
    tasks.complete(db, occurrences(db, task)[0].id)
    assert pending_dates(db, task)[0] == date(2026, 3, 9)


def test_calendar_overdue_occurrences_remain_until_handled(db, plant, at):
    at("2026-03-01 10:00")
    task = make(
        db, plant, recurrence=Recurrence.CALENDAR, calendar_rule={"kind": "weekly", "weekdays": [3]},
        start_date=date(2026, 3, 1),
    )
    at("2026-03-20 10:00")
    tasks.sync_all(db)
    overdue = [d for d in pending_dates(db, task) if d < date(2026, 3, 20)]
    assert overdue == [date(2026, 3, 5), date(2026, 3, 12), date(2026, 3, 19)]

    first = occurrences(db, task)[0]
    tasks.skip(db, first.id)
    remaining = [d for d in pending_dates(db, task) if d < date(2026, 3, 20)]
    assert remaining == [date(2026, 3, 12), date(2026, 3, 19)]


def test_calendar_skip_keeps_next_date(db, plant, at):
    at("2026-03-01 10:00")
    task = make(
        db, plant, recurrence=Recurrence.CALENDAR, calendar_rule={"kind": "weekly", "weekdays": [3]},
        start_date=date(2026, 3, 1),
    )
    tasks.skip(db, occurrences(db, task)[0].id)
    assert occurrences(db, task)[0].status == OccurrenceStatus.SKIPPED
    assert pending_dates(db, task)[0] == date(2026, 3, 12)


def test_calendar_generation_is_limited_to_horizon_and_end_date(db, plant, at):
    at("2026-03-01 10:00")
    task = make(
        db, plant, recurrence=Recurrence.CALENDAR, calendar_rule={"kind": "monthly", "day": 15},
        start_date=date(2026, 3, 1), end_date=date(2026, 6, 30),
    )
    assert pending_dates(db, task) == [date(2026, 3, 15)]
    at("2026-05-20 10:00")
    tasks.sync_all(db)
    assert pending_dates(db, task) == [date(2026, 3, 15), date(2026, 4, 15), date(2026, 5, 15), date(2026, 6, 15)]
    at("2026-08-20 10:00")
    tasks.sync_all(db)
    assert len(pending_dates(db, task)) == 4


def test_sync_is_idempotent(db, plant, at):
    at("2026-03-01 10:00")
    task = make(
        db, plant, recurrence=Recurrence.CALENDAR, calendar_rule={"kind": "weekly", "weekdays": [0, 3]},
        start_date=date(2026, 3, 1),
    )
    before = pending_dates(db, task)
    tasks.sync_all(db)
    tasks.sync_all(db)
    assert pending_dates(db, task) == before


def test_interval_skip_without_previous_completion(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant, recurrence=Recurrence.INTERVAL, interval_days=7, start_date=date(2026, 3, 1))
    at("2026-03-01 12:00")
    tasks.skip(db, occurrences(db, task)[0].id)
    assert pending_dates(db, task) == [date(2026, 3, 8)]


def test_interval_late_skip_lands_in_future(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant, recurrence=Recurrence.INTERVAL, interval_days=7, start_date=date(2026, 3, 1))
    at("2026-03-20 12:00")
    tasks.skip(db, occurrences(db, task)[0].id)
    assert pending_dates(db, task) == [date(2026, 3, 22)]


def test_interval_skip_follows_last_completion(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant, recurrence=Recurrence.INTERVAL, interval_days=7, start_date=date(2026, 3, 1))
    tasks.complete(db, occurrences(db, task)[0].id)
    at("2026-03-08 09:00")
    pending = [o for o in occurrences(db, task) if o.status == OccurrenceStatus.PENDING][0]
    tasks.skip(db, pending.id)
    assert pending_dates(db, task) == [date(2026, 3, 15)]


def test_suspension_hides_task_and_reactivates(db, plant, at):
    at("2026-03-01 10:00")
    task = make(
        db, plant, recurrence=Recurrence.CALENDAR, calendar_rule={"kind": "weekly", "weekdays": [0]},
        start_date=date(2026, 3, 1),
    )
    tasks.suspend(db, task, date(2026, 3, 14))
    assert tasks.is_suspended(task, date(2026, 3, 5))
    assert not tasks.is_operational(task, date(2026, 3, 5))

    at("2026-03-14 07:00")
    tasks.sync_all(db)
    db.refresh(task)
    assert task.suspended_until is None
    statuses = {o.due_date: o.status for o in occurrences(db, task)}
    assert statuses[date(2026, 3, 2)] == OccurrenceStatus.SUSPENDED
    assert statuses[date(2026, 3, 9)] == OccurrenceStatus.SUSPENDED
    assert statuses[date(2026, 3, 16)] == OccurrenceStatus.PENDING


def test_suspension_keeps_previous_overdue_occurrences(db, plant, at):
    at("2026-03-01 10:00")
    task = make(
        db, plant, recurrence=Recurrence.CALENDAR, calendar_rule={"kind": "weekly", "weekdays": [0]},
        start_date=date(2026, 3, 1),
    )
    at("2026-03-04 10:00")
    tasks.suspend(db, task, date(2026, 3, 12))
    at("2026-03-12 10:00")
    tasks.sync_all(db)
    statuses = {o.due_date: o.status for o in occurrences(db, task)}
    assert statuses[date(2026, 3, 2)] == OccurrenceStatus.PENDING
    assert statuses[date(2026, 3, 9)] == OccurrenceStatus.SUSPENDED


def test_interval_due_during_suspension_moves_to_reactivation_day(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant, recurrence=Recurrence.INTERVAL, interval_days=7, start_date=date(2026, 3, 5))
    tasks.suspend(db, task, date(2026, 3, 20))
    at("2026-03-21 10:00")
    tasks.sync_all(db)
    assert pending_dates(db, task) == [date(2026, 3, 20)]


def test_early_resume(db, plant, at):
    at("2026-03-01 10:00")
    task = make(
        db, plant, recurrence=Recurrence.CALENDAR, calendar_rule={"kind": "weekly", "weekdays": [0]},
        start_date=date(2026, 3, 1),
    )
    tasks.suspend(db, task, date(2026, 4, 1))
    at("2026-03-05 10:00")
    tasks.resume(db, task)
    statuses = {o.due_date: o.status for o in occurrences(db, task)}
    assert statuses[date(2026, 3, 2)] == OccurrenceStatus.SUSPENDED
    assert statuses[date(2026, 3, 9)] == OccurrenceStatus.PENDING
    assert task.suspended_until is None


def test_recurrence_change_affects_only_future(db, plant, at):
    at("2026-03-01 10:00")
    task = make(
        db, plant, recurrence=Recurrence.CALENDAR, calendar_rule={"kind": "weekly", "weekdays": [0]},
        start_date=date(2026, 3, 1),
    )
    tasks.complete(db, occurrences(db, task)[0].id)
    at("2026-03-10 10:00")
    tasks.sync_all(db)
    tasks.update_task(db, task, {"calendar_rule": {"kind": "weekly", "weekdays": [4]}})
    items = occurrences(db, task)
    assert items[0].due_date == date(2026, 3, 2) and items[0].status == OccurrenceStatus.COMPLETED
    assert date(2026, 3, 9) in pending_dates(db, task)
    future = [d for d in pending_dates(db, task) if d >= date(2026, 3, 10)]
    assert future and all(d.weekday() == 4 for d in future)
    assert future[0] == date(2026, 3, 13)


def test_interval_change_recomputes_from_last_completion(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant, recurrence=Recurrence.INTERVAL, interval_days=7, start_date=date(2026, 3, 1))
    tasks.complete(db, occurrences(db, task)[0].id)
    tasks.update_task(db, task, {"interval_days": 3})
    assert pending_dates(db, task) == [date(2026, 3, 4)]
    assert occurrences(db, task)[0].status == OccurrenceStatus.COMPLETED


def test_switching_interval_to_calendar(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant, recurrence=Recurrence.INTERVAL, interval_days=7, start_date=date(2026, 3, 1))
    tasks.complete(db, occurrences(db, task)[0].id)
    tasks.update_task(
        db, task, {"recurrence": Recurrence.CALENDAR, "calendar_rule": {"kind": "monthly", "day": 15}}
    )
    assert pending_dates(db, task) == [date(2026, 3, 15)]
    assert task.interval_days is None


def test_reopen_interval_completion_restores_schedule_and_diary(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant, recurrence=Recurrence.INTERVAL, interval_days=7, start_date=date(2026, 3, 1))
    occurrence_id = occurrences(db, task)[0].id
    tasks.complete(db, occurrence_id)
    assert pending_dates(db, task) == [date(2026, 3, 8)]

    tasks.reopen(db, occurrence_id)
    db.commit()
    assert pending_dates(db, task) == [date(2026, 3, 1)]
    assert db.scalars(select(DiaryEntry)).all() == []


def test_reopen_only_latest_interval_occurrence(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant, recurrence=Recurrence.INTERVAL, interval_days=7, start_date=date(2026, 3, 1))
    first_id = occurrences(db, task)[0].id
    tasks.complete(db, first_id)
    second = [o for o in occurrences(db, task) if o.status == OccurrenceStatus.PENDING][0]
    tasks.complete(db, second.id)
    with pytest.raises(Conflict):
        tasks.reopen(db, first_id)


def test_reopen_calendar_completion_keeps_other_occurrences(db, plant, at):
    at("2026-03-01 10:00")
    task = make(
        db, plant, recurrence=Recurrence.CALENDAR, calendar_rule={"kind": "weekly", "weekdays": [0]},
        start_date=date(2026, 3, 1),
    )
    before = pending_dates(db, task)
    first_id = occurrences(db, task)[0].id
    tasks.complete(db, first_id)
    tasks.reopen(db, first_id)
    db.commit()
    assert pending_dates(db, task) == before


def test_archived_plant_task_is_not_operational(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant)
    plant_row = db.get(Plant, plant.id)
    plant_row.status = PlantStatus.ARCHIVED
    db.commit()
    db.refresh(task)
    assert not tasks.is_operational(task, date(2026, 3, 2))


def test_deleting_task_keeps_diary_history(db, plant, at):
    at("2026-03-01 10:00")
    task = make(db, plant)
    result = tasks.complete(db, occurrences(db, task)[0].id)
    tasks.delete_task(db, task)
    entry = db.get(DiaryEntry, result.diary_entry.id)
    db.refresh(entry)
    assert entry.title == "Innaffiatura"
    assert entry.task_id is None and entry.occurrence_id is None
