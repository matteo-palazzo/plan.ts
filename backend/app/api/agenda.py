from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import authenticated
from app.clock import today
from app.config import get_settings
from app.db import get_db
from app.models import TaskType
from app.schemas import DashboardOut, DisplayStatus, OccurrenceOut
from app.services import agenda, tasks

router = APIRouter(dependencies=authenticated)


@router.get("/dashboard", response_model=DashboardOut, tags=["dashboard"])
def dashboard(days: int | None = Query(default=None, ge=0, le=tasks.GENERATION_HORIZON_DAYS), db: Session = Depends(get_db)):
    tasks.sync_all(db)
    day = today()
    days = get_settings().dashboard_days if days is None else days
    return DashboardOut(today=day, days=days, **agenda.dashboard(db, day, days))


@router.get("/calendar", response_model=list[OccurrenceOut], tags=["calendario"])
def calendar(
    start: date,
    end: date,
    plant_id: int | None = None,
    group_id: int | None = None,
    tag_id: int | None = None,
    task_type: TaskType | None = None,
    status: list[DisplayStatus] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    tasks.sync_all(db)
    return agenda.calendar(
        db, today(), start, end, plant_id, group_id, tag_id, task_type, set(status) if status else None
    )
