import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

_workdir = Path(tempfile.mkdtemp(prefix="plants-tests-"))
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_workdir / 'test.db'}")
os.environ["DATA_DIR"] = str(_workdir / "data")
os.environ["BACKUP_DIR"] = str(_workdir / "backups")
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["TZ"] = "Europe/Rome"
os.environ["TELEGRAM_ENABLED"] = "false"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import clock  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Plant  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _reset_schema() -> None:
    with engine.begin() as connection:
        if engine.dialect.name == "mysql":
            connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for table in [*Base.metadata.tables, "alembic_version"]:
                connection.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
            connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        else:
            Base.metadata.drop_all(connection)
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session", autouse=True)
def schema():
    _reset_schema()
    yield


@pytest.fixture(autouse=True)
def clean_state(schema):
    yield
    clock.freeze(None)
    with engine.begin() as connection:
        if engine.dialect.name == "mysql":
            connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
        if engine.dialect.name == "mysql":
            connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    settings = get_settings()
    for folder in (settings.photos_dir, settings.backup_dir):
        if folder.exists():
            shutil.rmtree(folder)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def at():
    zone = get_settings().zone

    def freeze(value: str) -> datetime:
        moment = datetime.fromisoformat(value).replace(tzinfo=zone)
        clock.freeze(moment)
        return moment

    return freeze


@pytest.fixture
def plant(db):
    item = Plant(name="Ginepro")
    db.add(item)
    db.commit()
    return item
