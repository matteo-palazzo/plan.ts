import errno
import logging
import os
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.clock import now
from app.config import get_settings
from app.errors import InsufficientStorage, InvalidInput, NotFound, Unavailable
from app.models import DiaryEntry, Photo

logger = logging.getLogger(__name__)

storage_lock = threading.RLock()
LOCK_TIMEOUT_SECONDS = 30
CHUNK_SIZE = 256 * 1024

SUPPORTED_FORMATS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


@dataclass
class IncomingFile:
    stream: BinaryIO
    client_name: str | None = None


@dataclass
class StagedFile:
    tmp_path: Path
    mime_type: str
    size_bytes: int


def detect_mime(header: bytes) -> str | None:
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None


def absolute_path(rel_path: str) -> Path:
    root = get_settings().photos_dir.resolve()
    path = (root / rel_path).resolve()
    if not path.is_relative_to(root):
        raise NotFound("Foto non trovata")
    return path


def _staging_dir() -> Path:
    path = get_settings().photos_dir / ".staging"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _stage(incoming: IncomingFile) -> StagedFile:
    settings = get_settings()
    tmp_path = _staging_dir() / uuid.uuid4().hex
    size = 0
    mime_type = None
    try:
        with tmp_path.open("wb") as target:
            while chunk := incoming.stream.read(CHUNK_SIZE):
                if mime_type is None:
                    mime_type = detect_mime(chunk[:16])
                    if mime_type is None:
                        raise InvalidInput(
                            "Formato non supportato: sono ammessi JPEG, PNG e WebP"
                        )
                size += len(chunk)
                if size > settings.photo_max_bytes:
                    raise InvalidInput(f"Ogni foto può pesare al massimo {settings.photo_max_mb} MB")
                target.write(chunk)
        if mime_type is None:
            raise InvalidInput("Il file caricato è vuoto")
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        if exc.errno == errno.ENOSPC:
            raise InsufficientStorage("Spazio su disco esaurito: impossibile salvare la foto") from exc
        raise
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    return StagedFile(tmp_path=tmp_path, mime_type=mime_type, size_bytes=size)


def add_photos(db: Session, entry: DiaryEntry, files: list[IncomingFile]) -> list[Photo]:
    limit = get_settings().photos_per_entry
    if not files:
        return []
    if len(entry.photos) + len(files) > limit:
        raise InvalidInput(f"Puoi allegare al massimo {limit} foto per voce")

    staged: list[StagedFile] = []
    try:
        for incoming in files:
            staged.append(_stage(incoming))
    except Exception:
        for item in staged:
            item.tmp_path.unlink(missing_ok=True)
        raise

    if not storage_lock.acquire(timeout=LOCK_TIMEOUT_SECONDS):
        for item in staged:
            item.tmp_path.unlink(missing_ok=True)
        raise Unavailable("Backup in corso: riprova tra qualche minuto")
    moved: list[Path] = []
    try:
        moment = now()
        photos = []
        for item in staged:
            filename = f"{uuid.uuid4().hex}.{SUPPORTED_FORMATS[item.mime_type]}"
            rel_path = f"{moment:%Y}/{moment:%m}/{filename}"
            target = absolute_path(rel_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(item.tmp_path, target)
            moved.append(target)
            photo = Photo(
                diary_entry_id=entry.id,
                rel_path=rel_path,
                filename=filename,
                mime_type=item.mime_type,
                size_bytes=item.size_bytes,
            )
            db.add(photo)
            photos.append(photo)
        db.commit()
        db.refresh(entry)
        return photos
    except Exception:
        db.rollback()
        for path in moved:
            path.unlink(missing_ok=True)
        raise
    finally:
        for item in staged:
            item.tmp_path.unlink(missing_ok=True)
        storage_lock.release()


def remove_files(rel_paths: list[str]) -> None:
    for rel_path in rel_paths:
        try:
            absolute_path(rel_path).unlink(missing_ok=True)
        except OSError:
            logger.exception("Impossibile eliminare il file della foto %s", rel_path)


def commit_and_remove_files(db: Session, rel_paths: list[str]) -> None:
    if not storage_lock.acquire(timeout=LOCK_TIMEOUT_SECONDS):
        db.rollback()
        raise Unavailable("Backup in corso: riprova tra qualche minuto")
    try:
        db.commit()
        remove_files(rel_paths)
    finally:
        storage_lock.release()


def delete_photo(db: Session, photo: Photo) -> None:
    rel_path = photo.rel_path
    db.delete(photo)
    commit_and_remove_files(db, [rel_path])


def find_orphan_files(known_paths: set[str]) -> list[Path]:
    root = get_settings().photos_dir
    if not root.exists():
        return []
    orphans = []
    for path in root.rglob("*"):
        if not path.is_file() or path.parent.name == ".staging":
            continue
        if path.relative_to(root).as_posix() not in known_paths:
            orphans.append(path)
    return orphans
