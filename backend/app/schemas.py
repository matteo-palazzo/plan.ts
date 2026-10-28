from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.models import (
    DiaryCategory,
    DiaryKind,
    LengthUnit,
    MeasurementKind,
    NotifyMode,
    PlantStatus,
    Recurrence,
    TaskStatus,
    TaskType,
)
from app.services.recurrence import validate_calendar_rule


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
OptionalShort = Annotated[
    Annotated[str, StringConstraints(max_length=200)] | None, AfterValidator(_blank_to_none), Field(default=None)
]
OptionalText = Annotated[
    Annotated[str, StringConstraints(max_length=5000)] | None, AfterValidator(_blank_to_none), Field(default=None)
]
HexColor = Annotated[str | None, Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")]


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LoginIn(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    password: Annotated[str, Field(min_length=1, max_length=256)]


class PasswordChangeIn(BaseModel):
    current_password: Annotated[str, Field(min_length=1, max_length=256)]
    new_password: Annotated[str, Field(min_length=10, max_length=256)]


class SessionOut(BaseModel):
    username: str
    csrf_token: str


class GroupIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    description: OptionalText


class GroupOut(OrmModel):
    id: int
    name: str
    description: str | None
    plant_count: int = 0


class GroupRef(OrmModel):
    id: int
    name: str


class TagIn(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    color: HexColor
    description: OptionalShort


class TagOut(OrmModel):
    id: int
    name: str
    color: str | None
    description: str | None
    plant_count: int = 0


class TagRef(OrmModel):
    id: int
    name: str
    color: str | None


class PlantIn(BaseModel):
    name: Name
    common_name: OptionalShort
    species: OptionalShort
    acquired_on: date | None = None
    substrate: OptionalText
    location: OptionalShort
    pot: OptionalText
    style: OptionalText
    notes: Annotated[
        Annotated[str, StringConstraints(max_length=20000)] | None, AfterValidator(_blank_to_none), Field(default=None)
    ]
    group_id: int | None = None
    tag_ids: Annotated[list[int], Field(default_factory=list, max_length=50)]


class PlantOut(OrmModel):
    id: int
    name: str
    common_name: str | None
    species: str | None
    acquired_on: date | None
    substrate: str | None
    location: str | None
    pot: str | None
    style: str | None
    notes: str | None
    group: GroupRef | None
    tags: list[TagRef]
    status: PlantStatus
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    cover_photo_id: int | None = None


class PlantSummary(OrmModel):
    id: int
    name: str
    common_name: str | None
    species: str | None
    group: GroupRef | None
    tags: list[TagRef]
    status: PlantStatus
    cover_photo_id: int | None = None


class TaskIn(BaseModel):
    name: Name
    task_type: TaskType = TaskType.OTHER
    description: OptionalText
    recurrence: Recurrence
    interval_days: Annotated[int | None, Field(default=None, ge=1, le=730)]
    calendar_rule: dict | None = None
    start_date: date
    end_date: date | None = None
    notify: NotifyMode = NotifyMode.NONE

    @field_validator("calendar_rule")
    @classmethod
    def _check_rule(cls, value: dict | None) -> dict | None:
        return None if value is None else validate_calendar_rule(value)

    @model_validator(mode="after")
    def _check_schedule(self):
        if self.recurrence == Recurrence.INTERVAL and self.interval_days is None:
            raise ValueError("Indica ogni quanti giorni ripetere il task")
        if self.recurrence == Recurrence.CALENDAR and self.calendar_rule is None:
            raise ValueError("Indica la regola di calendario")
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("La data finale non può precedere la data iniziale")
        if self.recurrence != Recurrence.INTERVAL:
            self.interval_days = None
        if self.recurrence != Recurrence.CALENDAR:
            self.calendar_rule = None
        return self


DisplayStatus = Literal["todo", "overdue", "completed", "skipped", "suspended", "planned"]


class OccurrenceOut(BaseModel):
    id: int | None
    task_id: int
    task_name: str
    task_type: TaskType
    plant_id: int
    plant_cover_photo_id: int | None = None
    plant_name: str
    due_date: date
    status: DisplayStatus
    completed_at: datetime | None = None
    skipped_at: datetime | None = None


class TaskOut(OrmModel):
    id: int
    plant_id: int
    name: str
    task_type: TaskType
    description: str | None
    recurrence: Recurrence
    interval_days: int | None
    calendar_rule: dict | None
    start_date: date
    end_date: date | None
    notify: NotifyMode
    status: TaskStatus
    suspended_from: date | None
    suspended_until: date | None
    is_suspended: bool = False
    created_at: datetime
    updated_at: datetime
    pending: list[OccurrenceOut] = []


class CompleteIn(BaseModel):
    completed_at: datetime | None = None
    note: OptionalText

    @field_validator("completed_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Specifica il fuso orario della data di completamento")
        return value


class CompleteOut(BaseModel):
    occurrence: OccurrenceOut
    diary_entry_id: int
    already_completed: bool


class SuspendIn(BaseModel):
    until: date | None = None
    days: Annotated[int | None, Field(default=None, ge=1, le=730)]

    @model_validator(mode="after")
    def _one_of(self):
        if (self.until is None) == (self.days is None):
            raise ValueError("Indica una durata in giorni oppure una data di fine")
        return self


class ActiveIn(BaseModel):
    active: bool


class DashboardOut(BaseModel):
    today: date
    days: int
    overdue: list[OccurrenceOut]
    due_today: list[OccurrenceOut]
    upcoming: list[OccurrenceOut]


class PhotoOut(OrmModel):
    id: int
    mime_type: str
    size_bytes: int
    url: str
    created_at: datetime


class MeasurementIn(BaseModel):
    kind: MeasurementKind
    measured_on: date
    value: Annotated[Decimal, Field(gt=0, le=100000, max_digits=10, decimal_places=2)]
    unit: LengthUnit = LengthUnit.MM


class MeasurementOut(BaseModel):
    id: int
    plant_id: int
    kind: MeasurementKind
    measured_on: date
    value_mm: Decimal
    input_unit: LengthUnit
    created_at: datetime


class ChartPoint(BaseModel):
    date: date
    value_mm: Decimal
    measurement_id: int


class MeasurementCharts(BaseModel):
    range: Literal["month", "year", "all"]
    since: date | None
    series: dict[MeasurementKind, list[ChartPoint]]


class DiaryUpdateIn(BaseModel):
    body: OptionalText
    category: DiaryCategory | None = None
    occurred_at: datetime | None = None


class DiaryEntryOut(BaseModel):
    id: int
    plant_id: int
    kind: DiaryKind
    category: DiaryCategory | None
    title: str | None
    body: str | None
    occurred_at: datetime
    task_id: int | None
    occurrence_id: int | None
    photos: list[PhotoOut]
    measurement: MeasurementOut | None


class DiaryPage(BaseModel):
    items: list[DiaryEntryOut]
    has_more: bool


class BackupInfo(BaseModel):
    name: str
    size_bytes: int
    created_at: datetime


class BackupStatus(BaseModel):
    last_run_at: datetime | None
    last_success_at: datetime | None
    last_result: Literal["success", "error"] | None
    last_error: str | None
    last_file: str | None
    backups: list[BackupInfo]


class TelegramStatus(BaseModel):
    enabled: bool
    configured: bool


class SettingsOut(BaseModel):
    version: str
    timezone: str
    dashboard_days: int
    photo_max_mb: int
    photos_per_entry: int
    photo_formats: list[str]
    notify_time: str
    telegram: TelegramStatus
    backup_schedule: str
    backup_retention_days: int
