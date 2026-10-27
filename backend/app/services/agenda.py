from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.errors import InvalidInput
from app.models import (
    OccurrenceStatus,
    Plant,
    PlantStatus,
    PlantTag,
    Recurrence,
    Task,
    TaskOccurrence,
    TaskStatus,
)
from app.schemas import OccurrenceOut
from app.services.recurrence import calendar_dates
from app.services.tasks import horizon, is_suspended

MAX_CALENDAR_DAYS = 400


def display_status(occurrence: TaskOccurrence, task: Task, day: date) -> str:
    if occurrence.status == OccurrenceStatus.PENDING:
        if is_suspended(task, day) and occurrence.due_date >= (task.suspended_from or day):
            return "suspended"
        return "overdue" if occurrence.due_date < day else "todo"
    return {
        OccurrenceStatus.COMPLETED: "completed",
        OccurrenceStatus.SKIPPED: "skipped",
        OccurrenceStatus.SUSPENDED: "suspended",
    }[OccurrenceStatus(occurrence.status)]


def present(occurrence: TaskOccurrence, day: date) -> OccurrenceOut:
    task = occurrence.task
    return OccurrenceOut(
        id=occurrence.id,
        task_id=task.id,
        task_name=task.name,
        task_type=task.task_type,
        plant_id=task.plant_id,
        plant_name=task.plant.name,
        due_date=occurrence.due_date,
        status=display_status(occurrence, task, day),
        completed_at=occurrence.completed_at,
        skipped_at=occurrence.skipped_at,
    )


def _operational_filter(day: date):
    return (
        (Task.status == TaskStatus.ACTIVE)
        & (Plant.status == PlantStatus.ACTIVE)
        & (or_(Task.suspended_until.is_(None), Task.suspended_until <= day))
    )


def dashboard(db: Session, day: date, days: int) -> dict[str, list[OccurrenceOut]]:
    rows = db.scalars(
        select(TaskOccurrence)
        .join(TaskOccurrence.task)
        .join(Task.plant)
        .where(
            TaskOccurrence.status == OccurrenceStatus.PENDING,
            TaskOccurrence.due_date <= day + timedelta(days=days),
            _operational_filter(day),
        )
        .order_by(TaskOccurrence.due_date, Plant.name, Task.name, TaskOccurrence.id)
    ).unique()
    result: dict[str, list[OccurrenceOut]] = {"overdue": [], "due_today": [], "upcoming": []}
    for occurrence in rows:
        bucket = "overdue" if occurrence.due_date < day else "due_today" if occurrence.due_date == day else "upcoming"
        result[bucket].append(present(occurrence, day))
    return result


def plant_pending(db: Session, plant: Plant, day: date) -> dict[int, list[OccurrenceOut]]:
    rows = db.scalars(
        select(TaskOccurrence)
        .join(TaskOccurrence.task)
        .where(Task.plant_id == plant.id, TaskOccurrence.status == OccurrenceStatus.PENDING)
        .order_by(TaskOccurrence.due_date, TaskOccurrence.id)
    ).unique()
    pending: dict[int, list[OccurrenceOut]] = {}
    for occurrence in rows:
        items = pending.setdefault(occurrence.task_id, [])
        if occurrence.due_date <= day or not any(item.due_date > day for item in items):
            items.append(present(occurrence, day))
    return pending


def task_history(db: Session, task: Task, day: date, limit: int) -> list[OccurrenceOut]:
    rows = db.scalars(
        select(TaskOccurrence)
        .where(TaskOccurrence.task_id == task.id, TaskOccurrence.status != OccurrenceStatus.PENDING)
        .order_by(TaskOccurrence.due_date.desc(), TaskOccurrence.id.desc())
        .limit(limit)
    ).unique()
    return [present(occurrence, day) for occurrence in rows]


def calendar(
    db: Session,
    day: date,
    start: date,
    end: date,
    plant_id: int | None = None,
    group_id: int | None = None,
    tag_id: int | None = None,
    task_type: str | None = None,
    statuses: set[str] | None = None,
) -> list[OccurrenceOut]:
    if end < start:
        raise InvalidInput("L'intervallo del calendario non è valido")
    if (end - start).days > MAX_CALENDAR_DAYS:
        raise InvalidInput(f"L'intervallo del calendario può coprire al massimo {MAX_CALENDAR_DAYS} giorni")

    def filtered(query):
        if plant_id is not None:
            query = query.where(Task.plant_id == plant_id)
        if group_id is not None:
            query = query.where(Plant.group_id == group_id)
        if tag_id is not None:
            query = query.where(Task.plant_id.in_(select(PlantTag.plant_id).where(PlantTag.tag_id == tag_id)))
        if task_type is not None:
            query = query.where(Task.task_type == task_type)
        return query

    occurrences = db.scalars(
        filtered(
            select(TaskOccurrence)
            .join(TaskOccurrence.task)
            .join(Task.plant)
            .where(
                TaskOccurrence.due_date >= start,
                TaskOccurrence.due_date <= end,
                or_(
                    TaskOccurrence.status != OccurrenceStatus.PENDING,
                    (Task.status == TaskStatus.ACTIVE) & (Plant.status == PlantStatus.ACTIVE),
                ),
            )
        )
    ).unique()
    items = [present(occurrence, day) for occurrence in occurrences]

    generation_end = horizon(day)
    if end > generation_end:
        projected_tasks = db.scalars(
            filtered(
                select(Task)
                .join(Task.plant)
                .where(
                    Task.recurrence == Recurrence.CALENDAR,
                    Task.status == TaskStatus.ACTIVE,
                    Plant.status == PlantStatus.ACTIVE,
                )
            )
        ).unique()
        for task in projected_tasks:
            first = max(start, task.start_date, (task.generated_until or generation_end) + timedelta(days=1))
            last = min(end, task.end_date) if task.end_date else end
            for due in calendar_dates(task.calendar_rule, first, last):
                items.append(
                    OccurrenceOut(
                        id=None,
                        task_id=task.id,
                        task_name=task.name,
                        task_type=task.task_type,
                        plant_id=task.plant_id,
                        plant_name=task.plant.name,
                        due_date=due,
                        status="suspended" if is_suspended(task, due) else "planned",
                    )
                )

    if statuses:
        items = [item for item in items if item.status in statuses or (item.status == "planned" and "todo" in statuses)]
    items.sort(key=lambda item: (item.due_date, item.plant_name, item.task_name))
    return items
