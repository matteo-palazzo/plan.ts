from datetime import timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import authenticated
from app.clock import today
from app.db import get_db
from app.models import Task
from app.schemas import ActiveIn, CompleteIn, CompleteOut, OccurrenceOut, SuspendIn, TaskIn, TaskOut
from app.services import agenda, photos, tasks
from app.services.plants import get_plant

router = APIRouter(dependencies=authenticated, tags=["task"])


def task_out(task: Task, pending: list[OccurrenceOut]) -> TaskOut:
    out = TaskOut.model_validate(task)
    out.is_suspended = tasks.is_suspended(task, today())
    out.pending = pending
    return out


def _single(db: Session, task: Task) -> TaskOut:
    pending = agenda.plant_pending(db, task.plant, today()).get(task.id, [])
    return task_out(task, pending)


@router.get("/plants/{plant_id}/tasks", response_model=list[TaskOut])
def list_plant_tasks(plant_id: int, db: Session = Depends(get_db)):
    plant = get_plant(db, plant_id)
    tasks.sync_all(db)
    pending = agenda.plant_pending(db, plant, today())
    rows = db.scalars(select(Task).where(Task.plant_id == plant.id).order_by(Task.status, Task.name)).unique()
    return [task_out(task, pending.get(task.id, [])) for task in rows]


@router.post("/plants/{plant_id}/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(plant_id: int, data: TaskIn, db: Session = Depends(get_db)):
    plant = get_plant(db, plant_id)
    return _single(db, tasks.create_task(db, plant, data.model_dump()))


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    return _single(db, tasks.get_task(db, task_id))


@router.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, data: TaskIn, db: Session = Depends(get_db)):
    task = tasks.get_task(db, task_id, lock=True)
    return _single(db, tasks.update_task(db, task, data.model_dump()))


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    tasks.delete_task(db, tasks.get_task(db, task_id, lock=True))


@router.get("/tasks/{task_id}/history", response_model=list[OccurrenceOut])
def task_history(task_id: int, limit: int = Query(default=50, ge=1, le=500), db: Session = Depends(get_db)):
    return agenda.task_history(db, tasks.get_task(db, task_id), today(), limit)


@router.post("/tasks/{task_id}/suspend", response_model=TaskOut)
def suspend_task(task_id: int, data: SuspendIn, db: Session = Depends(get_db)):
    task = tasks.get_task(db, task_id, lock=True)
    until = data.until or today() + timedelta(days=data.days)
    return _single(db, tasks.suspend(db, task, until))


@router.post("/tasks/{task_id}/resume", response_model=TaskOut)
def resume_task(task_id: int, db: Session = Depends(get_db)):
    return _single(db, tasks.resume(db, tasks.get_task(db, task_id, lock=True)))


@router.post("/tasks/{task_id}/active", response_model=TaskOut)
def set_task_active(task_id: int, data: ActiveIn, db: Session = Depends(get_db)):
    return _single(db, tasks.set_active(db, tasks.get_task(db, task_id, lock=True), data.active))


@router.post("/occurrences/{occurrence_id}/complete", response_model=CompleteOut)
def complete_occurrence(occurrence_id: int, data: CompleteIn | None = None, db: Session = Depends(get_db)):
    data = data or CompleteIn()
    result = tasks.complete(db, occurrence_id, data.completed_at, data.note)
    return CompleteOut(
        occurrence=agenda.present(result.occurrence, today()),
        diary_entry_id=result.diary_entry.id,
        already_completed=result.already_completed,
    )


@router.post("/occurrences/{occurrence_id}/skip", response_model=OccurrenceOut)
def skip_occurrence(occurrence_id: int, db: Session = Depends(get_db)):
    return agenda.present(tasks.skip(db, occurrence_id), today())


@router.post("/occurrences/{occurrence_id}/reopen", response_model=OccurrenceOut)
def reopen_occurrence(occurrence_id: int, db: Session = Depends(get_db)):
    removed_files = tasks.reopen(db, occurrence_id)
    photos.commit_and_remove_files(db, removed_files)
    return agenda.present(tasks.get_occurrence(db, occurrence_id), today())
