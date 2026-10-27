from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetime non ammesso")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


class PlantStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class TaskType(StrEnum):
    WATERING = "watering"
    FERTILIZING = "fertilizing"
    REPOTTING = "repotting"
    PRUNING = "pruning"
    CHECK = "check"
    OTHER = "other"


class Recurrence(StrEnum):
    ONCE = "once"
    INTERVAL = "interval"
    CALENDAR = "calendar"


class NotifyMode(StrEnum):
    NONE = "none"
    DAY_OF = "day_of"
    DAY_BEFORE = "day_before"
    BOTH = "both"


class TaskStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class OccurrenceStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    SUSPENDED = "suspended"


class DiaryKind(StrEnum):
    MANUAL = "manual"
    TASK_COMPLETION = "task_completion"
    MEASUREMENT = "measurement"


class DiaryCategory(StrEnum):
    GROWTH = "growth"
    HEALTH = "health"
    PRUNING = "pruning"
    REPOTTING = "repotting"
    FERTILIZING = "fertilizing"
    WATERING = "watering"
    OTHER = "other"


class MeasurementKind(StrEnum):
    HEIGHT = "height"
    WIDTH = "width"
    TRUNK_DIAMETER = "trunk_diameter"


class LengthUnit(StrEnum):
    MM = "mm"
    CM = "cm"


class ReminderKind(StrEnum):
    DAY_BEFORE = "day_before"
    DAY_OF = "day_of"


class NotificationStatus(StrEnum):
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)

    user: Mapped[User] = relationship()


class Group(Base):
    __tablename__ = "plant_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    color: Mapped[str | None] = mapped_column(String(7))
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class PlantTag(Base):
    __tablename__ = "plant_tags"

    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True, index=True)


class Plant(Base):
    __tablename__ = "plants"
    __table_args__ = (Index("ix_plants_status_name", "status", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    common_name: Mapped[str | None] = mapped_column(String(120))
    species: Mapped[str | None] = mapped_column(String(160))
    acquired_on: Mapped[date | None] = mapped_column(Date)
    substrate: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(200))
    pot: Mapped[str | None] = mapped_column(Text)
    style: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("plant_groups.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(16), default=PlantStatus.ACTIVE)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    group: Mapped[Group | None] = relationship(lazy="joined")
    tags: Mapped[list[Tag]] = relationship(secondary="plant_tags", lazy="selectin", order_by=Tag.name)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    task_type: Mapped[str] = mapped_column(String(20), default=TaskType.OTHER)
    description: Mapped[str | None] = mapped_column(Text)
    recurrence: Mapped[str] = mapped_column(String(16))
    interval_days: Mapped[int | None] = mapped_column(Integer)
    calendar_rule: Mapped[dict | None] = mapped_column(JSON)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    notify: Mapped[str] = mapped_column(String(16), default=NotifyMode.NONE)
    status: Mapped[str] = mapped_column(String(16), default=TaskStatus.ACTIVE)
    suspended_from: Mapped[date | None] = mapped_column(Date)
    suspended_until: Mapped[date | None] = mapped_column(Date)
    generated_until: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    plant: Mapped[Plant] = relationship(lazy="joined")


class TaskOccurrence(Base):
    __tablename__ = "task_occurrences"
    __table_args__ = (
        UniqueConstraint("task_id", "calendar_date", name="uq_occurrence_calendar_date"),
        Index("ix_occurrences_status_due", "status", "due_date"),
        Index("ix_occurrences_task_due", "task_id", "due_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    due_date: Mapped[date] = mapped_column(Date)
    calendar_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default=OccurrenceStatus.PENDING)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    skipped_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    task: Mapped[Task] = relationship(lazy="joined")


class Measurement(Base):
    __tablename__ = "measurements"
    __table_args__ = (Index("ix_measurements_plant_kind_date", "plant_id", "kind", "measured_on"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    measured_on: Mapped[date] = mapped_column(Date)
    value_mm: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    input_unit: Mapped[str] = mapped_column(String(4), default=LengthUnit.MM)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class DiaryEntry(Base):
    __tablename__ = "diary_entries"
    __table_args__ = (Index("ix_diary_plant_occurred", "plant_id", "occurred_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    plant_id: Mapped[int] = mapped_column(ForeignKey("plants.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    category: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), index=True)
    occurrence_id: Mapped[int | None] = mapped_column(
        ForeignKey("task_occurrences.id", ondelete="SET NULL"), unique=True
    )
    measurement_id: Mapped[int | None] = mapped_column(
        ForeignKey("measurements.id", ondelete="CASCADE"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    photos: Mapped[list["Photo"]] = relationship(lazy="selectin", order_by="Photo.id")
    measurement: Mapped[Measurement | None] = relationship(lazy="joined")
    occurrence: Mapped[TaskOccurrence | None] = relationship(lazy="joined")


class Photo(Base):
    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    diary_entry_id: Mapped[int] = mapped_column(ForeignKey("diary_entries.id", ondelete="CASCADE"), index=True)
    rel_path: Mapped[str] = mapped_column(String(255), unique=True)
    filename: Mapped[str] = mapped_column(String(100))
    mime_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class NotificationLog(Base):
    __tablename__ = "notification_logs"
    __table_args__ = (
        UniqueConstraint("occurrence_id", "reminder", "due_date", name="uq_notification_once"),
        Index("ix_notification_status_scheduled", "status", "scheduled_for"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    occurrence_id: Mapped[int] = mapped_column(ForeignKey("task_occurrences.id", ondelete="CASCADE"))
    reminder: Mapped[str] = mapped_column(String(16))
    due_date: Mapped[date] = mapped_column(Date)
    scheduled_for: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
