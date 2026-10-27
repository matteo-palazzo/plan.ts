from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.clock import now, today
from app.errors import Conflict, InvalidInput, NotFound
from app.models import DiaryEntry, Group, Photo, Plant, PlantStatus, PlantTag, Recurrence, Tag, Task
from app.schemas import GroupIn, PlantIn, TagIn
from app.services import photos as photo_service
from app.services.tasks import restart_generation


def get_plant(db: Session, plant_id: int) -> Plant:
    plant = db.get(Plant, plant_id)
    if plant is None:
        raise NotFound("Pianta non trovata")
    return plant


def cover_photos(db: Session, plant_ids: list[int]) -> dict[int, int]:
    if not plant_ids:
        return {}
    rows = db.execute(
        select(DiaryEntry.plant_id, func.max(Photo.id))
        .join(Photo, Photo.diary_entry_id == DiaryEntry.id)
        .where(DiaryEntry.plant_id.in_(plant_ids))
        .group_by(DiaryEntry.plant_id)
    )
    return {plant_id: photo_id for plant_id, photo_id in rows}


def search_plants(
    db: Session,
    q: str | None = None,
    status: str = "active",
    group_id: int | None = None,
    tag_id: int | None = None,
    limit: int = 500,
) -> list[Plant]:
    query = select(Plant).outerjoin(Plant.group)
    if status != "all":
        query = query.where(Plant.status == status)
    if group_id is not None:
        query = query.where(Plant.group_id == group_id)
    if tag_id is not None:
        query = query.where(Plant.id.in_(select(PlantTag.plant_id).where(PlantTag.tag_id == tag_id)))
    if q:
        pattern = f"%{q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')}%"
        tagged = select(PlantTag.plant_id).join(Tag, Tag.id == PlantTag.tag_id).where(Tag.name.ilike(pattern, escape="\\"))
        query = query.where(
            or_(
                Plant.name.ilike(pattern, escape="\\"),
                Plant.common_name.ilike(pattern, escape="\\"),
                Plant.species.ilike(pattern, escape="\\"),
                Group.name.ilike(pattern, escape="\\"),
                Plant.id.in_(tagged),
            )
        )
    return list(db.scalars(query.order_by(Plant.name, Plant.id).limit(limit)).unique())


def _resolve_tags(db: Session, tag_ids: list[int]) -> list[Tag]:
    unique_ids = list(dict.fromkeys(tag_ids))
    tags = list(db.scalars(select(Tag).where(Tag.id.in_(unique_ids)))) if unique_ids else []
    if len(tags) != len(unique_ids):
        raise InvalidInput("Uno o più tag selezionati non esistono")
    return tags


def _check_group(db: Session, group_id: int | None) -> None:
    if group_id is not None and db.get(Group, group_id) is None:
        raise InvalidInput("Il gruppo selezionato non esiste")


def create_plant(db: Session, data: PlantIn) -> Plant:
    _check_group(db, data.group_id)
    plant = Plant(**data.model_dump(exclude={"tag_ids"}), status=PlantStatus.ACTIVE)
    plant.tags = _resolve_tags(db, data.tag_ids)
    db.add(plant)
    db.commit()
    db.refresh(plant)
    return plant


def update_plant(db: Session, plant: Plant, data: PlantIn) -> Plant:
    _check_group(db, data.group_id)
    for field, value in data.model_dump(exclude={"tag_ids"}).items():
        setattr(plant, field, value)
    plant.tags = _resolve_tags(db, data.tag_ids)
    plant.updated_at = now()
    db.commit()
    db.refresh(plant)
    return plant


def archive_plant(db: Session, plant: Plant) -> Plant:
    if plant.status != PlantStatus.ARCHIVED:
        plant.status = PlantStatus.ARCHIVED
        plant.archived_at = now()
        db.commit()
    return plant


def restore_plant(db: Session, plant: Plant) -> Plant:
    if plant.status == PlantStatus.ARCHIVED:
        plant.status = PlantStatus.ACTIVE
        plant.archived_at = None
        day = today()
        for task in db.scalars(
            select(Task).where(Task.plant_id == plant.id, Task.recurrence == Recurrence.CALENDAR)
        ):
            restart_generation(task, day)
        db.commit()
    return plant


def delete_plant(db: Session, plant: Plant, confirm_name: str) -> None:
    if confirm_name.strip() != plant.name:
        raise InvalidInput("Per confermare l'eliminazione scrivi esattamente il nome della pianta")
    rel_paths = list(
        db.scalars(
            select(Photo.rel_path)
            .join(DiaryEntry, Photo.diary_entry_id == DiaryEntry.id)
            .where(DiaryEntry.plant_id == plant.id)
        )
    )
    db.delete(plant)
    photo_service.commit_and_remove_files(db, rel_paths)


def list_groups(db: Session) -> list[tuple[Group, int]]:
    counts = (
        select(Plant.group_id, func.count(Plant.id).label("total"))
        .where(Plant.status == PlantStatus.ACTIVE)
        .group_by(Plant.group_id)
        .subquery()
    )
    rows = db.execute(
        select(Group, func.coalesce(counts.c.total, 0))
        .outerjoin(counts, counts.c.group_id == Group.id)
        .order_by(Group.name)
    )
    return [(group, total) for group, total in rows]


def save_group(db: Session, data: GroupIn, group: Group | None = None) -> Group:
    group = group or Group()
    group.name = data.name
    group.description = data.description
    db.add(group)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("Esiste già un gruppo con questo nome") from exc
    return group


def delete_group(db: Session, group: Group) -> None:
    for plant in db.scalars(select(Plant).where(Plant.group_id == group.id)):
        plant.group_id = None
    db.delete(group)
    db.commit()


def list_tags(db: Session) -> list[tuple[Tag, int]]:
    counts = (
        select(PlantTag.tag_id, func.count(PlantTag.plant_id).label("total"))
        .group_by(PlantTag.tag_id)
        .subquery()
    )
    rows = db.execute(
        select(Tag, func.coalesce(counts.c.total, 0)).outerjoin(counts, counts.c.tag_id == Tag.id).order_by(Tag.name)
    )
    return [(tag, total) for tag, total in rows]


def save_tag(db: Session, data: TagIn, tag: Tag | None = None) -> Tag:
    tag = tag or Tag()
    tag.name = data.name
    tag.color = data.color
    tag.description = data.description
    db.add(tag)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict("Esiste già un tag con questo nome") from exc
    return tag


def delete_tag(db: Session, tag: Tag) -> None:
    db.delete(tag)
    db.commit()
