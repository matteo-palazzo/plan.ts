import gzip
import io
import json
import logging
import os
import re
import shutil
import tarfile
import tempfile
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Date, Engine, Numeric, inspect, text

from app.clock import now
from app.config import APP_VERSION, get_settings
from app.db import Base
from app.models import UTCDateTime
from app.services import photos as photo_service

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1
NAME_PATTERN = re.compile(r"^plants-backup-(\d{8}-\d{6})\.tar$")
STATUS_FILE = "last-backup.json"
ERROR_LOG = "backup-errors.log"
LOCK_TIMEOUT_SECONDS = 600
INSERT_BATCH = 500
EXCLUDED_TABLES = {"user_sessions"}
BACKEND_DIR = Path(__file__).resolve().parents[2]


class BackupError(Exception):
    pass


def _json_default(value):
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Tipo non serializzabile: {type(value).__name__}")


def _alembic_config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


def _schema_revision(connection) -> str | None:
    if not inspect(connection).has_table("alembic_version"):
        return None
    return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()


def backup_name(moment: datetime) -> str:
    return f"plants-backup-{moment.astimezone(get_settings().zone):%Y%m%d-%H%M%S}.tar"


def _write_status(**values) -> None:
    settings = get_settings()
    path = settings.backup_dir / STATUS_FILE
    current = read_status()
    current.update(values)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, default=_json_default, indent=2))
    os.replace(tmp, path)


def read_status() -> dict:
    path = get_settings().backup_dir / STATUS_FILE
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def list_backups() -> list[dict]:
    folder = get_settings().backup_dir
    if not folder.exists():
        return []
    items = []
    for path in folder.iterdir():
        match = NAME_PATTERN.match(path.name)
        if not match or not path.is_file():
            continue
        created = datetime.strptime(match.group(1), "%Y%m%d-%H%M%S").replace(tzinfo=get_settings().zone)
        items.append({"name": path.name, "size_bytes": path.stat().st_size, "created_at": created, "path": path})
    return sorted(items, key=lambda item: item["created_at"], reverse=True)


def apply_retention(moment: datetime | None = None) -> list[str]:
    settings = get_settings()
    cutoff = (moment or now()) - timedelta(days=settings.backup_retention_days)
    removed = []
    for item in list_backups():
        if item["created_at"] < cutoff:
            item["path"].unlink(missing_ok=True)
            removed.append(item["name"])
    for stale in settings.backup_dir.glob("*.partial"):
        stale.unlink(missing_ok=True)
    return removed


def _export_database(connection, target: Path) -> tuple[dict[str, int], list[str]]:
    counts: dict[str, int] = {}
    photo_paths: list[str] = []
    with gzip.open(target, "wt", encoding="utf-8") as output:
        for table in Base.metadata.sorted_tables:
            if table.name in EXCLUDED_TABLES:
                continue
            count = 0
            result = connection.execution_options(yield_per=500).execute(table.select().order_by(*table.primary_key.columns))
            for row in result.mappings():
                record = dict(row)
                output.write(json.dumps({"t": table.name, "r": record}, default=_json_default, ensure_ascii=False))
                output.write("\n")
                if table.name == "photos":
                    photo_paths.append(record["rel_path"])
                count += 1
            counts[table.name] = count
    return counts, photo_paths


def _begin_snapshot(connection) -> None:
    if connection.dialect.name == "mysql":
        connection.exec_driver_sql("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        connection.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
    else:
        connection.exec_driver_sql("BEGIN")


def create_backup(engine: Engine, moment: datetime | None = None) -> Path:
    settings = get_settings()
    moment = moment or now()
    settings.backup_dir.mkdir(parents=True, exist_ok=True)
    final_path = settings.backup_dir / backup_name(moment)
    partial_path = final_path.with_name(final_path.name + ".partial")
    _write_status(last_run_at=moment)
    try:
        if not photo_service.storage_lock.acquire(timeout=LOCK_TIMEOUT_SECONDS):
            raise BackupError("Impossibile ottenere il blocco sui file: un'altra operazione è in corso")
        try:
            with tempfile.TemporaryDirectory(dir=settings.backup_dir) as workdir:
                dump_path = Path(workdir) / "database.jsonl.gz"
                with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
                    _begin_snapshot(connection)
                    try:
                        revision = _schema_revision(connection)
                        counts, photo_paths = _export_database(connection, dump_path)
                    finally:
                        connection.exec_driver_sql("ROLLBACK")
                missing = []
                manifest = {
                    "format_version": FORMAT_VERSION,
                    "app_version": APP_VERSION,
                    "schema_revision": revision,
                    "created_at": moment,
                    "timezone": settings.tz,
                    "tables": counts,
                    "photo_count": len(photo_paths),
                    "missing_photos": missing,
                }
                with tarfile.open(partial_path, "w") as archive:
                    archive.add(dump_path, arcname="database.jsonl.gz")
                    for rel_path in photo_paths:
                        source = photo_service.absolute_path(rel_path)
                        if source.is_file():
                            archive.add(source, arcname=f"photos/{rel_path}", recursive=False)
                        else:
                            missing.append(rel_path)
                    payload = json.dumps(manifest, default=_json_default, indent=2).encode()
                    info = tarfile.TarInfo("manifest.json")
                    info.size = len(payload)
                    info.mtime = int(moment.timestamp())
                    archive.addfile(info, io.BytesIO(payload))
                os.replace(partial_path, final_path)
        finally:
            photo_service.storage_lock.release()
        removed = apply_retention(moment)
        _write_status(last_success_at=moment, last_result="success", last_error=None, last_file=final_path.name)
        logger.info(
            "Backup completato: %s (%d foto, %d rimossi per retention)", final_path.name, len(photo_paths), len(removed)
        )
        if missing:
            logger.warning("Backup %s: %d foto mancanti sul disco", final_path.name, len(missing))
        return final_path
    except Exception as exc:
        partial_path.unlink(missing_ok=True)
        message = f"{type(exc).__name__}: {exc}"[:500]
        _write_status(last_result="error", last_error=message)
        with (settings.backup_dir / ERROR_LOG).open("a", encoding="utf-8") as log:
            log.write(f"{moment.isoformat()} {message}\n")
        logger.exception("Backup fallito")
        raise


def read_manifest(archive_path: Path) -> dict:
    with tarfile.open(archive_path, "r") as archive:
        member = archive.extractfile("manifest.json")
        if member is None:
            raise BackupError("Archivio non valido: manifest mancante")
        manifest = json.load(member)
    if manifest.get("format_version") != FORMAT_VERSION:
        raise BackupError("Formato di backup non supportato")
    return manifest


def _parse_value(column, value):
    if value is None:
        return None
    if isinstance(column.type, UTCDateTime):
        return datetime.fromisoformat(value)
    if isinstance(column.type, Date):
        return date.fromisoformat(value)
    if isinstance(column.type, Numeric):
        return Decimal(value)
    return value


def _app_tables_have_data(connection) -> bool:
    inspector = inspect(connection)
    for table in Base.metadata.sorted_tables:
        if inspector.has_table(table.name) and connection.execute(table.select().limit(1)).first():
            return True
    return False


def _drop_app_tables(connection) -> None:
    inspector = inspect(connection)
    if connection.dialect.name == "mysql":
        connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
    for table in reversed(Base.metadata.sorted_tables):
        if inspector.has_table(table.name):
            table.drop(connection)
    if inspector.has_table("alembic_version"):
        connection.exec_driver_sql("DROP TABLE alembic_version")
    if connection.dialect.name == "mysql":
        connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")


def _run_alembic(engine: Engine, revision: str) -> None:
    config = _alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


def _restore_rows(engine: Engine, dump_stream) -> dict[str, int]:
    tables = {table.name: table for table in Base.metadata.sorted_tables}
    counts: dict[str, int] = {}
    pending: dict[str, list[dict]] = {}
    with engine.begin() as connection:
        if connection.dialect.name == "mysql":
            connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")

        def flush(name: str) -> None:
            if pending.get(name):
                connection.execute(tables[name].insert(), pending[name])
                pending[name] = []

        for line in io.TextIOWrapper(gzip.GzipFile(fileobj=dump_stream), encoding="utf-8"):
            item = json.loads(line)
            table = tables.get(item["t"])
            if table is None:
                raise BackupError(f"Tabella sconosciuta nel backup: {item['t']}")
            row = {name: _parse_value(table.columns[name], value) for name, value in item["r"].items()}
            pending.setdefault(table.name, []).append(row)
            counts[table.name] = counts.get(table.name, 0) + 1
            if len(pending[table.name]) >= INSERT_BATCH:
                flush(table.name)
        for name in tables:
            flush(name)
        if connection.dialect.name == "mysql":
            connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")
    return counts


def _restore_photos(archive: tarfile.TarFile, photos_dir: Path) -> int:
    staging = photos_dir.parent / f".photos-restore-{os.getpid()}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    count = 0
    for member in archive.getmembers():
        if not member.name.startswith("photos/"):
            continue
        if not member.isfile():
            continue
        archive.extract(member, staging, filter="data")
        count += 1
    restored = staging / "photos"
    restored.mkdir(exist_ok=True)
    if photos_dir.exists():
        previous = photos_dir.parent / f"photos-before-restore-{datetime.now():%Y%m%d-%H%M%S}"
        os.replace(photos_dir, previous)
        logger.info("Foto precedenti spostate in %s", previous)
    os.replace(restored, photos_dir)
    shutil.rmtree(staging, ignore_errors=True)
    return count


def restore_backup(engine: Engine, archive_path: Path, force: bool = False) -> dict:
    manifest = read_manifest(archive_path)
    revision = manifest.get("schema_revision")
    if not revision:
        raise BackupError("Il backup non indica la versione dello schema")

    with engine.begin() as connection:
        if _app_tables_have_data(connection) and not force:
            raise BackupError("Il database contiene già dati: usa --force per sostituirli con il backup")
        _drop_app_tables(connection)

    _run_alembic(engine, revision)
    with tarfile.open(archive_path, "r") as archive:
        dump = archive.extractfile("database.jsonl.gz")
        if dump is None:
            raise BackupError("Archivio non valido: dump del database mancante")
        counts = _restore_rows(engine, dump)
        photo_count = _restore_photos(archive, get_settings().photos_dir)
    _run_alembic(engine, "head")
    if counts != {name: total for name, total in manifest["tables"].items() if total}:
        raise BackupError("Il numero di righe ripristinate non corrisponde al manifest")
    logger.info("Ripristino completato da %s", archive_path.name)
    return {"tables": counts, "photos": photo_count, "schema_revision": revision}
