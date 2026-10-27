import json
import tarfile
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.config import get_settings
from app.db import engine
from app.models import DiaryEntry, Measurement, Photo, Plant, Recurrence, Task, TaskOccurrence
from app.services import backup, tasks
from tests.conftest import JPEG, PNG


def populate(client):
    plant = client.post("/api/plants", json={"name": "Ginepro", "species": "Juniperus"}).json()
    client.post(
        f"/api/plants/{plant['id']}/diary",
        data={"body": "Con foto"},
        files=[("files", ("a.jpg", JPEG, "image/jpeg")), ("files", ("b.png", PNG, "image/png"))],
    )
    client.post(
        f"/api/plants/{plant['id']}/measurements",
        json={"kind": "trunk_diameter", "measured_on": "2026-01-10", "value": "35.5"},
    )
    task = client.post(
        f"/api/plants/{plant['id']}/tasks",
        json={"name": "Innaffiare", "recurrence": "interval", "interval_days": 5, "start_date": "2026-01-01"},
    ).json()
    client.post(f"/api/occurrences/{task['pending'][0]['id']}/complete", json={"note": "fatto"})
    return plant


def counts(db):
    db.expire_all()
    return {
        model.__tablename__: db.scalar(select(func.count()).select_from(model))
        for model in (Plant, DiaryEntry, Photo, Measurement, Task, TaskOccurrence)
    }


def test_backup_contains_database_and_photos(client, db):
    populate(client)
    path = backup.create_backup(engine)
    assert path.name.startswith("plants-backup-") and path.suffix == ".tar"

    with tarfile.open(path) as archive:
        names = archive.getnames()
        manifest = json.load(archive.extractfile("manifest.json"))
    assert "database.jsonl.gz" in names
    assert len([name for name in names if name.startswith("photos/")]) == 2
    assert manifest["schema_revision"] == "0001"
    assert manifest["photo_count"] == 2 and manifest["missing_photos"] == []
    assert manifest["tables"]["plants"] == 1 and manifest["tables"]["photos"] == 2

    status = backup.read_status()
    assert status["last_result"] == "success" and status["last_file"] == path.name


def test_retention_removes_backups_older_than_30_days(client):
    folder = get_settings().backup_dir
    folder.mkdir(parents=True, exist_ok=True)
    zone = get_settings().zone
    reference = datetime(2026, 3, 31, 3, 30, tzinfo=zone)
    for days in (40, 31, 29, 1):
        name = backup.backup_name(reference - timedelta(days=days))
        (folder / name).write_bytes(b"x")
    (folder / "plants-backup-20260101-000000.tar.partial").write_bytes(b"x")
    (folder / "altro-file.txt").write_text("non toccare")

    removed = backup.apply_retention(reference)
    assert len(removed) == 2
    remaining = sorted(path.name for path in folder.iterdir())
    assert remaining == ["altro-file.txt", backup.backup_name(reference - timedelta(days=29)), backup.backup_name(reference - timedelta(days=1))]


def test_backup_runs_retention(client):
    folder = get_settings().backup_dir
    folder.mkdir(parents=True, exist_ok=True)
    old = folder / backup.backup_name(datetime.now(get_settings().zone) - timedelta(days=45))
    old.write_bytes(b"x")
    backup.create_backup(engine)
    assert not old.exists()


def test_restore_round_trip(client, db):
    populate(client)
    before = counts(db)
    photo_files_before = sorted(
        p.relative_to(get_settings().photos_dir).as_posix()
        for p in get_settings().photos_dir.rglob("*")
        if p.is_file() and ".staging" not in p.parts
    )
    archive = backup.create_backup(engine)

    with pytest.raises(backup.BackupError):
        backup.restore_backup(engine, archive)

    plant = db.scalars(select(Plant)).first()
    plant.name = "Modificato dopo il backup"
    db.commit()
    for path in get_settings().photos_dir.rglob("*.jpg"):
        path.unlink()

    result = backup.restore_backup(engine, archive, force=True)
    assert result["photos"] == 2
    assert counts(db) == before
    db.expire_all()
    assert db.scalars(select(Plant)).first().name == "Ginepro"
    restored_files = sorted(
        p.relative_to(get_settings().photos_dir).as_posix() for p in get_settings().photos_dir.rglob("*") if p.is_file()
    )
    assert restored_files == [name for name in photo_files_before]

    entry = db.scalars(select(DiaryEntry).where(DiaryEntry.kind == "task_completion")).first()
    assert entry.body == "fatto" and entry.occurred_at.tzinfo is not None
    assert db.scalars(select(Measurement)).first().value_mm == pytest.approx(35.5)
    task = db.scalars(select(Task)).first()
    assert task.recurrence == Recurrence.INTERVAL
    assert tasks.next_pending(db, task).due_date > date(2026, 1, 1)
    assert client.get("/api/plants").status_code == 401


def test_failed_backup_is_recorded(client, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("disco pieno")

    monkeypatch.setattr(backup, "_export_database", boom)
    with pytest.raises(RuntimeError):
        backup.create_backup(engine)
    status = backup.read_status()
    assert status["last_result"] == "error" and "disco pieno" in status["last_error"]
    assert "disco pieno" in (get_settings().backup_dir / backup.ERROR_LOG).read_text()
    assert list(get_settings().backup_dir.glob("*.tar*")) == []


def test_backup_api(client):
    response = client.post("/api/backups")
    assert response.status_code == 200
    body = response.json()
    assert body["last_result"] == "success" and len(body["backups"]) == 1
