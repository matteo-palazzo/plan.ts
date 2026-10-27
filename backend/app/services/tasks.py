from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.clock import local_date, now, today
from app.errors import Conflict, InvalidInput, NotFound
from app.models import (
    DiaryEntry,
    DiaryKind,
    OccurrenceStatus,
    Plant,
    PlantStatus,
    Recurrence,
    Task,
    TaskOccurrence,
    TaskStatus,
)
from app.services.recurrence import calendar_dates, next_interval_date_after

GENERATION_HORIZON_DAYS = 31
MAX_GENERATED_PER_SYNC = 400
SCHEDULE_FIELDS = ("recurrence", "interval_days", "calendar_rule", "start_date", "end_date")


@dataclass
class CompletionResult:
    occurrence: TaskOccurrence
    diary_entry: DiaryEntry
    already_completed: bool


def horizon(day: date) -> date:
    return day + timedelta(days=GENERATION_HORIZON_DAYS)


def is_suspended(task: Task, day: date) -> bool:
    return task.suspended_until is not None and day < task.suspended_until


def is_operational(task: Task, day: date) -> bool:
    return (
        task.status == TaskStatus.ACTIVE
        and task.plant.status == PlantStatus.ACTIVE
        and not is_suspended(task, day)
    )


def get_task(db: Session, task_id: int, lock: bool = False) -> Task:
    query = select(Task).where(Task.id == task_id)
    if lock:
        query = query.with_for_update()
    task = db.scalars(query).first()
    if task is None:
        raise NotFound("Task non trovato")
    return task


def get_occurrence(db: Session, occurrence_id: int, lock: bool = False) -> TaskOccurrence:
    query = select(TaskOccurrence).where(TaskOccurrence.id == occurrence_id)
    if lock:
        query = query.with_for_update()
    occurrence = db.scalars(query).first()
    if occurrence is None:
        raise NotFound("Scadenza non trovata")
    return occurrence


def _pending(db: Session, task: Task) -> list[TaskOccurrence]:
    return list(
        db.scalars(
            select(TaskOccurrence)
            .where(TaskOccurrence.task_id == task.id, TaskOccurrence.status == OccurrenceStatus.PENDING)
            .order_by(TaskOccurrence.due_date, TaskOccurrence.id)
        )
    )


def _last_completion_date(db: Session, task: Task) -> date | None:
    completed_at = db.scalar(
        select(func.max(TaskOccurrence.completed_at)).where(
            TaskOccurrence.task_id == task.id, TaskOccurrence.status == OccurrenceStatus.COMPLETED
        )
    )
    if completed_at is None:
        return None
    return local_date(completed_at)


def _has_handled(db: Session, task: Task) -> bool:
    return (
        db.scalar(
            select(func.count())
            .select_from(TaskOccurrence)
            .where(TaskOccurrence.task_id == task.id, TaskOccurrence.status != OccurrenceStatus.PENDING)
        )
        > 0
    )


def _within_end(task: Task, day: date) -> bool:
    return task.end_date is None or day <= task.end_date


def _add_occurrence(db: Session, task: Task, due: date) -> TaskOccurrence | None:
    if not _within_end(task, due):
        return None
    occurrence = TaskOccurrence(
        task_id=task.id,
        due_date=due,
        calendar_date=due if task.recurrence == Recurrence.CALENDAR else None,
        status=OccurrenceStatus.PENDING,
    )
    db.add(occurrence)
    db.flush()
    return occurrence


def create_task(db: Session, plant: Plant, values: dict) -> Task:
    task = Task(plant_id=plant.id, **values)
    db.add(task)
    db.flush()
    _initialize_schedule(db, task, today())
    db.commit()
    db.refresh(task)
    return task


def _initialize_schedule(db: Session, task: Task, day: date) -> None:
    if task.recurrence == Recurrence.CALENDAR:
        task.generated_until = task.start_date - timedelta(days=1)
        _generate_calendar(db, task, day)
    else:
        _add_occurrence(db, task, task.start_date)


def _generate_calendar(db: Session, task: Task, day: date) -> None:
    if task.recurrence != Recurrence.CALENDAR or task.calendar_rule is None:
        return
    if task.status != TaskStatus.ACTIVE or task.plant.status != PlantStatus.ACTIVE:
        return
    start = max(task.start_date, (task.generated_until or task.start_date - timedelta(days=1)) + timedelta(days=1))
    end = horizon(day)
    if task.end_date is not None:
        end = min(end, task.end_date)
    if start > end:
        return
    existing = set(
        db.scalars(
            select(TaskOccurrence.calendar_date).where(
                TaskOccurrence.task_id == task.id,
                TaskOccurrence.calendar_date >= start,
                TaskOccurrence.calendar_date <= end,
            )
        )
    )
    generated_until = end
    for count, due in enumerate(calendar_dates(task.calendar_rule, start, end)):
        if count >= MAX_GENERATED_PER_SYNC:
            generated_until = due - timedelta(days=1)
            break
        if due not in existing:
            _add_occurrence(db, task, due)
    task.generated_until = generated_until


def _finish_suspension(db: Session, task: Task, resume_on: date) -> None:
    window_start = task.suspended_from or resume_on
    for occurrence in _pending(db, task):
        if task.recurrence == Recurrence.CALENDAR:
            if window_start <= occurrence.due_date < resume_on:
                occurrence.status = OccurrenceStatus.SUSPENDED
        elif occurrence.due_date < resume_on:
            occurrence.due_date = resume_on
    task.suspended_from = None
    task.suspended_until = None


def sync_task(db: Session, task: Task, day: date) -> None:
    if task.suspended_until is not None and day >= task.suspended_until:
        _finish_suspension(db, task, task.suspended_until)
    _generate_calendar(db, task, day)


def sync_all(db: Session, day: date | None = None) -> None:
    day = day or today()
    tasks = db.scalars(
        select(Task)
        .join(Task.plant)
        .where(
            (Task.suspended_until <= day)
            | (
                (Task.recurrence == Recurrence.CALENDAR)
                & (Task.status == TaskStatus.ACTIVE)
                & (Plant.status == PlantStatus.ACTIVE)
                & ((Task.generated_until.is_(None)) | (Task.generated_until < horizon(day)))
                & ((Task.end_date.is_(None)) | (Task.generated_until.is_(None)) | (Task.generated_until < Task.end_date))
            )
        )
        .with_for_update()
    ).all()
    for task in tasks:
        sync_task(db, task, day)
    db.commit()


def complete(db: Session, occurrence_id: int, at: datetime | None = None, note: str | None = None) -> CompletionResult:
    occurrence = get_occurrence(db, occurrence_id, lock=True)
    task = occurrence.task
    moment = at or now()
    if moment > now() + timedelta(minutes=5):
        raise InvalidInput("La data di completamento non può essere nel futuro")

    if occurrence.status == OccurrenceStatus.COMPLETED:
        entry = db.scalars(select(DiaryEntry).where(DiaryEntry.occurrence_id == occurrence.id)).first()
        db.commit()
        return CompletionResult(occurrence, entry, already_completed=True)
    if occurrence.status != OccurrenceStatus.PENDING:
        raise Conflict("Questa scadenza è già stata gestita e non può essere completata")

    occurrence.status = OccurrenceStatus.COMPLETED
    occurrence.completed_at = moment
    entry = DiaryEntry(
        plant_id=task.plant_id,
        kind=DiaryKind.TASK_COMPLETION,
        title=task.name,
        body=note or None,
        occurred_at=moment,
        task_id=task.id,
        occurrence_id=occurrence.id,
    )
    db.add(entry)
    if task.recurrence == Recurrence.INTERVAL and task.status == TaskStatus.ACTIVE:
        _schedule_interval_successor(db, task, local_date(moment) + timedelta(days=task.interval_days))
    db.commit()
    db.refresh(entry)
    return CompletionResult(occurrence, entry, already_completed=False)


def _schedule_interval_successor(db: Session, task: Task, due: date) -> None:
    for pending in _pending(db, task):
        db.delete(pending)
    db.flush()
    _add_occurrence(db, task, due)


def skip(db: Session, occurrence_id: int) -> TaskOccurrence:
    occurrence = get_occurrence(db, occurrence_id, lock=True)
    task = occurrence.task
    if occurrence.status == OccurrenceStatus.SKIPPED:
        db.commit()
        return occurrence
    if occurrence.status != OccurrenceStatus.PENDING:
        raise Conflict("Questa scadenza è già stata gestita e non può essere saltata")

    occurrence.status = OccurrenceStatus.SKIPPED
    occurrence.skipped_at = now()
    if task.recurrence == Recurrence.INTERVAL and task.status == TaskStatus.ACTIVE:
        anchor = _last_completion_date(db, task) or occurrence.due_date
        after = max(occurrence.due_date, today())
        db.flush()
        _schedule_interval_successor(db, task, next_interval_date_after(anchor, task.interval_days, after))
    db.commit()
    return occurrence


def reopen(db: Session, occurrence_id: int) -> list[str]:
    occurrence = get_occurrence(db, occurrence_id, lock=True)
    task = get_task(db, occurrence.task_id, lock=True)
    if occurrence.status not in (OccurrenceStatus.COMPLETED, OccurrenceStatus.SKIPPED):
        raise Conflict("Solo una scadenza completata o saltata può essere annullata")

    if task.recurrence != Recurrence.CALENDAR:
        later_handled = db.scalar(
            select(func.count())
            .select_from(TaskOccurrence)
            .where(
                TaskOccurrence.task_id == task.id,
                TaskOccurrence.id > occurrence.id,
                TaskOccurrence.status != OccurrenceStatus.PENDING,
            )
        )
        if later_handled:
            raise Conflict("Puoi annullare solo l'ultima esecuzione registrata di questo task")
        db.execute(
            delete(TaskOccurrence).where(
                TaskOccurrence.task_id == task.id,
                TaskOccurrence.id > occurrence.id,
                TaskOccurrence.status == OccurrenceStatus.PENDING,
            )
        )

    removed_files: list[str] = []
    entry = db.scalars(select(DiaryEntry).where(DiaryEntry.occurrence_id == occurrence.id)).first()
    if entry is not None:
        removed_files = [photo.rel_path for photo in entry.photos]
        db.delete(entry)

    occurrence.status = OccurrenceStatus.PENDING
    occurrence.completed_at = None
    occurrence.skipped_at = None
    return removed_files


def suspend(db: Session, task: Task, until: date) -> Task:
    day = today()
    if until <= day:
        raise InvalidInput("La sospensione deve terminare in una data futura")
    if task.status != TaskStatus.ACTIVE:
        raise Conflict("Un task disattivato non può essere sospeso")
    if not is_suspended(task, day):
        task.suspended_from = day
    task.suspended_until = until
    db.commit()
    return task


def resume(db: Session, task: Task) -> Task:
    if task.suspended_until is None:
        return task
    day = today()
    _finish_suspension(db, task, min(day, task.suspended_until))
    _generate_calendar(db, task, day)
    db.commit()
    return task


def set_active(db: Session, task: Task, active: bool) -> Task:
    day = today()
    if active and task.status != TaskStatus.ACTIVE:
        task.status = TaskStatus.ACTIVE
        restart_generation(task, day)
        _generate_calendar(db, task, day)
        if task.recurrence != Recurrence.CALENDAR and not _pending(db, task) and not _has_handled(db, task):
            _add_occurrence(db, task, task.start_date)
    elif not active:
        task.status = TaskStatus.DISABLED
        task.suspended_from = None
        task.suspended_until = None
    db.commit()
    return task


def restart_generation(task: Task, day: date) -> None:
    if task.recurrence == Recurrence.CALENDAR and task.generated_until is not None:
        task.generated_until = max(task.generated_until, day - timedelta(days=1))


def update_task(db: Session, task: Task, values: dict) -> Task:
    previous = {field: getattr(task, field) for field in SCHEDULE_FIELDS}
    for field, value in values.items():
        setattr(task, field, value)
    _validate_schedule(task)
    if any(previous[field] != getattr(task, field) for field in SCHEDULE_FIELDS):
        _reschedule(db, task, today(), recurrence_changed=previous["recurrence"] != task.recurrence)
    db.commit()
    db.refresh(task)
    return task


def _validate_schedule(task: Task) -> None:
    if task.end_date is not None and task.end_date < task.start_date:
        raise InvalidInput("La data finale non può precedere la data iniziale")
    if task.recurrence == Recurrence.INTERVAL and not task.interval_days:
        raise InvalidInput("Indica ogni quanti giorni ripetere il task")
    if task.recurrence == Recurrence.CALENDAR and not task.calendar_rule:
        raise InvalidInput("Indica la regola di calendario")
    if task.recurrence != Recurrence.INTERVAL:
        task.interval_days = None
    if task.recurrence != Recurrence.CALENDAR:
        task.calendar_rule = None


def _reschedule(db: Session, task: Task, day: date, recurrence_changed: bool) -> None:
    pending = _pending(db, task)
    if recurrence_changed:
        for occurrence in pending:
            if occurrence.due_date >= day:
                db.delete(occurrence)
        db.flush()
        pending = [occurrence for occurrence in pending if occurrence.due_date < day]

    if task.recurrence == Recurrence.CALENDAR:
        allowed = set(calendar_dates(task.calendar_rule, max(task.start_date, day), horizon(day)))
        for occurrence in pending:
            if occurrence.due_date >= day and (occurrence.calendar_date not in allowed or not _within_end(task, occurrence.due_date)):
                db.delete(occurrence)
        db.flush()
        task.generated_until = max(task.start_date, day) - timedelta(days=1)
        _generate_calendar(db, task, day)
        return

    if task.recurrence == Recurrence.ONCE:
        target = task.start_date
    else:
        last_completion = _last_completion_date(db, task)
        if last_completion is not None:
            target = last_completion + timedelta(days=task.interval_days)
        elif pending and _has_handled(db, task) and not recurrence_changed:
            target = pending[0].due_date
        else:
            target = task.start_date

    current = pending[0] if pending else None
    for extra in pending[1:]:
        db.delete(extra)
    if current is None:
        if task.recurrence == Recurrence.ONCE and _has_handled(db, task) and not recurrence_changed:
            return
        if task.status == TaskStatus.ACTIVE:
            _add_occurrence(db, task, target)
        return
    if _within_end(task, target):
        current.due_date = target
    else:
        db.delete(current)


def delete_task(db: Session, task: Task) -> None:
    db.delete(task)
    db.commit()


def next_pending(db: Session, task: Task) -> TaskOccurrence | None:
    pending = _pending(db, task)
    return pending[0] if pending else None
