from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import authenticated
from app.db import get_db
from app.errors import NotFound
from app.models import Group, Plant, Tag
from app.schemas import GroupIn, GroupOut, PlantIn, PlantOut, PlantSummary, TagIn, TagOut
from app.services import plants as service

router = APIRouter(dependencies=authenticated)


def plant_out(db: Session, plant: Plant) -> PlantOut:
    out = PlantOut.model_validate(plant)
    out.cover_photo_id = service.cover_photos(db, [plant.id]).get(plant.id)
    return out


@router.get("/plants", response_model=list[PlantSummary], tags=["piante"])
def list_plants(
    q: str | None = Query(default=None, max_length=100),
    status: Literal["active", "archived", "all"] = "active",
    group_id: int | None = None,
    tag_id: int | None = None,
    limit: int = Query(default=500, ge=1, le=500),
    db: Session = Depends(get_db),
):
    plants = service.search_plants(db, q, status, group_id, tag_id, limit)
    covers = service.cover_photos(db, [plant.id for plant in plants])
    return [
        PlantSummary.model_validate(plant).model_copy(update={"cover_photo_id": covers.get(plant.id)})
        for plant in plants
    ]


@router.post("/plants", response_model=PlantOut, status_code=status.HTTP_201_CREATED, tags=["piante"])
def create_plant(data: PlantIn, db: Session = Depends(get_db)):
    return plant_out(db, service.create_plant(db, data))


@router.get("/plants/{plant_id}", response_model=PlantOut, tags=["piante"])
def get_plant(plant_id: int, db: Session = Depends(get_db)):
    return plant_out(db, service.get_plant(db, plant_id))


@router.put("/plants/{plant_id}", response_model=PlantOut, tags=["piante"])
def update_plant(plant_id: int, data: PlantIn, db: Session = Depends(get_db)):
    return plant_out(db, service.update_plant(db, service.get_plant(db, plant_id), data))


@router.post("/plants/{plant_id}/archive", response_model=PlantOut, tags=["piante"])
def archive_plant(plant_id: int, db: Session = Depends(get_db)):
    return plant_out(db, service.archive_plant(db, service.get_plant(db, plant_id)))


@router.post("/plants/{plant_id}/restore", response_model=PlantOut, tags=["piante"])
def restore_plant(plant_id: int, db: Session = Depends(get_db)):
    return plant_out(db, service.restore_plant(db, service.get_plant(db, plant_id)))


@router.delete("/plants/{plant_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["piante"])
def delete_plant(plant_id: int, confirm: str = Query(max_length=120), db: Session = Depends(get_db)):
    service.delete_plant(db, service.get_plant(db, plant_id), confirm)


def _group(db: Session, group_id: int) -> Group:
    group = db.get(Group, group_id)
    if group is None:
        raise NotFound("Gruppo non trovato")
    return group


@router.get("/groups", response_model=list[GroupOut], tags=["gruppi"])
def list_groups(db: Session = Depends(get_db)):
    return [GroupOut.model_validate(group).model_copy(update={"plant_count": total}) for group, total in service.list_groups(db)]


@router.post("/groups", response_model=GroupOut, status_code=status.HTTP_201_CREATED, tags=["gruppi"])
def create_group(data: GroupIn, db: Session = Depends(get_db)):
    return service.save_group(db, data)


@router.put("/groups/{group_id}", response_model=GroupOut, tags=["gruppi"])
def update_group(group_id: int, data: GroupIn, db: Session = Depends(get_db)):
    return service.save_group(db, data, _group(db, group_id))


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["gruppi"])
def delete_group(group_id: int, db: Session = Depends(get_db)):
    service.delete_group(db, _group(db, group_id))


def _tag(db: Session, tag_id: int) -> Tag:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise NotFound("Tag non trovato")
    return tag


@router.get("/tags", response_model=list[TagOut], tags=["tag"])
def list_tags(db: Session = Depends(get_db)):
    return [TagOut.model_validate(tag).model_copy(update={"plant_count": total}) for tag, total in service.list_tags(db)]


@router.post("/tags", response_model=TagOut, status_code=status.HTTP_201_CREATED, tags=["tag"])
def create_tag(data: TagIn, db: Session = Depends(get_db)):
    return service.save_tag(db, data)


@router.put("/tags/{tag_id}", response_model=TagOut, tags=["tag"])
def update_tag(tag_id: int, data: TagIn, db: Session = Depends(get_db)):
    return service.save_tag(db, data, _tag(db, tag_id))


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["tag"])
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    service.delete_tag(db, _tag(db, tag_id))
