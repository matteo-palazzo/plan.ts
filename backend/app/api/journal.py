from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import authenticated
from app.db import get_db
from app.errors import InvalidInput, NotFound
from app.models import DiaryCategory, DiaryEntry, Measurement, Photo
from app.schemas import (
    DiaryEntryOut,
    DiaryPage,
    DiaryUpdateIn,
    MeasurementCharts,
    MeasurementIn,
    MeasurementOut,
    PhotoOut,
)
from app.services import journal, photos
from app.services.plants import get_plant

router = APIRouter(dependencies=authenticated)


def photo_out(photo: Photo) -> PhotoOut:
    return PhotoOut(
        id=photo.id,
        mime_type=photo.mime_type,
        size_bytes=photo.size_bytes,
        url=f"/api/photos/{photo.id}/file",
        created_at=photo.created_at,
    )


def measurement_out(measurement: Measurement) -> MeasurementOut:
    return MeasurementOut.model_validate(measurement, from_attributes=True)


def entry_out(entry: DiaryEntry) -> DiaryEntryOut:
    return DiaryEntryOut(
        id=entry.id,
        plant_id=entry.plant_id,
        kind=entry.kind,
        category=entry.category,
        title=entry.title,
        body=entry.body,
        occurred_at=entry.occurred_at,
        task_id=entry.task_id,
        occurrence_id=entry.occurrence_id,
        photos=[photo_out(photo) for photo in entry.photos],
        measurement=measurement_out(entry.measurement) if entry.measurement else None,
    )


def _incoming(files: list[UploadFile] | None) -> list[photos.IncomingFile]:
    return [photos.IncomingFile(stream=item.file, client_name=item.filename) for item in files or [] if item.filename]


@router.get("/plants/{plant_id}/diary", response_model=DiaryPage, tags=["diario"])
def list_diary(
    plant_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items, has_more = journal.list_entries(db, get_plant(db, plant_id), offset, limit)
    return DiaryPage(items=[entry_out(entry) for entry in items], has_more=has_more)


@router.post("/plants/{plant_id}/diary", response_model=DiaryEntryOut, status_code=status.HTTP_201_CREATED, tags=["diario"])
def create_diary_entry(
    plant_id: int,
    body: Annotated[str | None, Form(max_length=5000)] = None,
    category: Annotated[DiaryCategory | None, Form()] = None,
    occurred_at: Annotated[datetime | None, Form()] = None,
    files: Annotated[list[UploadFile] | None, File()] = None,
    db: Session = Depends(get_db),
):
    plant = get_plant(db, plant_id)
    entry = journal.create_manual_entry(db, plant, body, category, occurred_at, _incoming(files))
    return entry_out(entry)


@router.patch("/diary/{entry_id}", response_model=DiaryEntryOut, tags=["diario"])
def update_diary_entry(entry_id: int, data: DiaryUpdateIn, db: Session = Depends(get_db)):
    return entry_out(journal.update_entry(db, journal.get_entry(db, entry_id), data))


@router.delete("/diary/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["diario"])
def delete_diary_entry(entry_id: int, db: Session = Depends(get_db)):
    journal.delete_entry(db, journal.get_entry(db, entry_id))


@router.post("/diary/{entry_id}/photos", response_model=DiaryEntryOut, tags=["foto"])
def upload_photos(entry_id: int, files: Annotated[list[UploadFile], File()], db: Session = Depends(get_db)):
    entry = journal.get_entry(db, entry_id)
    incoming = _incoming(files)
    if not incoming:
        raise InvalidInput("Seleziona almeno una foto")
    photos.add_photos(db, entry, incoming)
    return entry_out(entry)


def _photo(db: Session, photo_id: int) -> Photo:
    photo = db.get(Photo, photo_id)
    if photo is None:
        raise NotFound("Foto non trovata")
    return photo


@router.get("/photos/{photo_id}/file", response_class=FileResponse, tags=["foto"])
def photo_file(photo_id: int, db: Session = Depends(get_db)):
    photo = _photo(db, photo_id)
    path = photos.absolute_path(photo.rel_path)
    if not path.is_file():
        raise NotFound("Il file della foto non è più disponibile")
    return FileResponse(
        path,
        media_type=photo.mime_type,
        headers={"Cache-Control": "private, max-age=604800, immutable", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["foto"])
def delete_photo(photo_id: int, db: Session = Depends(get_db)):
    photo = _photo(db, photo_id)
    entry = journal.get_entry(db, photo.diary_entry_id)
    if entry.kind == "manual" and not entry.body and len(entry.photos) == 1:
        raise InvalidInput("È l'unico contenuto della voce: elimina la voce oppure aggiungi un testo")
    photos.delete_photo(db, photo)


@router.get("/plants/{plant_id}/measurements", response_model=list[MeasurementOut], tags=["misurazioni"])
def list_measurements(plant_id: int, db: Session = Depends(get_db)):
    return [measurement_out(item) for item in journal.list_measurements(db, get_plant(db, plant_id))]


@router.get("/plants/{plant_id}/measurements/charts", response_model=MeasurementCharts, tags=["misurazioni"])
def measurement_charts(
    plant_id: int, range: Literal["month", "year", "all"] = "year", db: Session = Depends(get_db)
):
    since, series = journal.chart_series(db, get_plant(db, plant_id), range)
    return MeasurementCharts(range=range, since=since, series=series)


@router.post(
    "/plants/{plant_id}/measurements",
    response_model=MeasurementOut,
    status_code=status.HTTP_201_CREATED,
    tags=["misurazioni"],
)
def create_measurement(plant_id: int, data: MeasurementIn, db: Session = Depends(get_db)):
    return measurement_out(journal.create_measurement(db, get_plant(db, plant_id), data))


@router.put("/measurements/{measurement_id}", response_model=MeasurementOut, tags=["misurazioni"])
def update_measurement(measurement_id: int, data: MeasurementIn, db: Session = Depends(get_db)):
    return measurement_out(journal.update_measurement(db, journal.get_measurement(db, measurement_id), data))


@router.delete("/measurements/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["misurazioni"])
def delete_measurement(measurement_id: int, db: Session = Depends(get_db)):
    journal.delete_measurement(db, journal.get_measurement(db, measurement_id))
