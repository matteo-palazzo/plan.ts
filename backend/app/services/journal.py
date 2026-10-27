from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import now, today
from app.config import get_settings
from app.errors import Conflict, InvalidInput, NotFound
from app.models import DiaryCategory, DiaryEntry, DiaryKind, LengthUnit, Measurement, MeasurementKind, Plant
from app.schemas import DiaryUpdateIn, MeasurementIn
from app.services import photos as photo_service

UNIT_FACTORS = {LengthUnit.MM: Decimal(1), LengthUnit.CM: Decimal(10)}
CHART_RANGES = {"month": timedelta(days=31), "year": timedelta(days=365), "all": None}


def get_entry(db: Session, entry_id: int) -> DiaryEntry:
    entry = db.get(DiaryEntry, entry_id)
    if entry is None:
        raise NotFound("Voce del diario non trovata")
    return entry


def list_entries(db: Session, plant: Plant, offset: int, limit: int) -> tuple[list[DiaryEntry], bool]:
    rows = list(
        db.scalars(
            select(DiaryEntry)
            .where(DiaryEntry.plant_id == plant.id)
            .order_by(DiaryEntry.occurred_at.desc(), DiaryEntry.id.desc())
            .offset(offset)
            .limit(limit + 1)
        ).unique()
    )
    return rows[:limit], len(rows) > limit


def _check_moment(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise InvalidInput("Specifica il fuso orario della data")
    if moment > now() + timedelta(minutes=5):
        raise InvalidInput("La data della voce non può essere nel futuro")
    return moment


def create_manual_entry(
    db: Session,
    plant: Plant,
    body: str | None,
    category: DiaryCategory | None,
    occurred_at: datetime | None,
    files: list[photo_service.IncomingFile],
) -> DiaryEntry:
    body = (body or "").strip() or None
    if body is None and not files:
        raise InvalidInput("Scrivi un testo o allega almeno una foto")
    if body is not None and len(body) > 5000:
        raise InvalidInput("Il testo può contenere al massimo 5000 caratteri")
    if len(files) > get_settings().photos_per_entry:
        raise InvalidInput(f"Puoi allegare al massimo {get_settings().photos_per_entry} foto per voce")
    entry = DiaryEntry(
        plant_id=plant.id,
        kind=DiaryKind.MANUAL,
        category=category,
        body=body,
        occurred_at=_check_moment(occurred_at) if occurred_at else now(),
    )
    db.add(entry)
    db.flush()
    if files:
        try:
            photo_service.add_photos(db, entry, files)
        except Exception:
            db.rollback()
            raise
    else:
        db.commit()
    db.refresh(entry)
    return entry


def update_entry(db: Session, entry: DiaryEntry, data: DiaryUpdateIn) -> DiaryEntry:
    if entry.kind == DiaryKind.MEASUREMENT:
        raise Conflict("Le voci di misurazione si modificano dalla misurazione stessa")
    entry.body = data.body
    if entry.kind == DiaryKind.MANUAL:
        entry.category = data.category
        if data.occurred_at is not None:
            entry.occurred_at = _check_moment(data.occurred_at)
        if entry.body is None and not entry.photos:
            raise InvalidInput("Scrivi un testo o allega almeno una foto")
    db.commit()
    db.refresh(entry)
    return entry


def delete_entry(db: Session, entry: DiaryEntry) -> None:
    if entry.kind != DiaryKind.MANUAL:
        raise Conflict(
            "Questa voce è generata automaticamente: annulla il completamento o elimina la misurazione"
        )
    rel_paths = [photo.rel_path for photo in entry.photos]
    db.delete(entry)
    photo_service.commit_and_remove_files(db, rel_paths)


def to_mm(value: Decimal, unit: LengthUnit) -> Decimal:
    return (value * UNIT_FACTORS[unit]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _measurement_moment(measured_on: date) -> datetime:
    if measured_on == today():
        return now()
    return datetime.combine(measured_on, time(12, 0), tzinfo=get_settings().zone)


def get_measurement(db: Session, measurement_id: int) -> Measurement:
    measurement = db.get(Measurement, measurement_id)
    if measurement is None:
        raise NotFound("Misurazione non trovata")
    return measurement


def _validate_measurement(data: MeasurementIn) -> Decimal:
    if data.measured_on > today():
        raise InvalidInput("La data della misurazione non può essere nel futuro")
    return to_mm(data.value, data.unit)


def create_measurement(db: Session, plant: Plant, data: MeasurementIn) -> Measurement:
    measurement = Measurement(
        plant_id=plant.id,
        kind=data.kind,
        measured_on=data.measured_on,
        value_mm=_validate_measurement(data),
        input_unit=data.unit,
    )
    db.add(measurement)
    db.flush()
    db.add(
        DiaryEntry(
            plant_id=plant.id,
            kind=DiaryKind.MEASUREMENT,
            occurred_at=_measurement_moment(data.measured_on),
            measurement_id=measurement.id,
        )
    )
    db.commit()
    db.refresh(measurement)
    return measurement


def update_measurement(db: Session, measurement: Measurement, data: MeasurementIn) -> Measurement:
    value_mm = _validate_measurement(data)
    date_changed = measurement.measured_on != data.measured_on
    measurement.kind = data.kind
    measurement.measured_on = data.measured_on
    measurement.value_mm = value_mm
    measurement.input_unit = data.unit
    if date_changed:
        entry = db.scalars(select(DiaryEntry).where(DiaryEntry.measurement_id == measurement.id)).first()
        if entry is not None:
            entry.occurred_at = _measurement_moment(data.measured_on)
    db.commit()
    db.refresh(measurement)
    return measurement


def delete_measurement(db: Session, measurement: Measurement) -> None:
    db.delete(measurement)
    db.commit()


def list_measurements(db: Session, plant: Plant) -> list[Measurement]:
    return list(
        db.scalars(
            select(Measurement)
            .where(Measurement.plant_id == plant.id)
            .order_by(Measurement.measured_on.desc(), Measurement.id.desc())
        )
    )


def chart_series(db: Session, plant: Plant, range_key: str) -> tuple[date | None, dict[MeasurementKind, list[dict]]]:
    span = CHART_RANGES[range_key]
    since = today() - span if span else None
    query = select(Measurement).where(Measurement.plant_id == plant.id)
    if since is not None:
        query = query.where(Measurement.measured_on >= since)
    rows = db.scalars(query.order_by(Measurement.measured_on, Measurement.id))
    latest_per_day: dict[MeasurementKind, dict[date, Measurement]] = {kind: {} for kind in MeasurementKind}
    for measurement in rows:
        latest_per_day[MeasurementKind(measurement.kind)][measurement.measured_on] = measurement
    series = {
        kind: [
            {"date": day, "value_mm": item.value_mm, "measurement_id": item.id}
            for day, item in sorted(points.items())
        ]
        for kind, points in latest_per_day.items()
    }
    return since, series
