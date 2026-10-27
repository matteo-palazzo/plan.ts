from functools import cached_property, lru_cache
from pathlib import Path
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_VERSION = "1.0.0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    tz: str = Field(default="Europe/Rome", validation_alias="TZ")

    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str = "plants"
    db_user: str = "plants"
    db_password: SecretStr = SecretStr("")
    database_url: str | None = None

    secret_key: SecretStr = SecretStr("")
    session_days: int = 30
    cookie_secure: bool = False

    data_dir: Path = Path("/data")
    photo_max_mb: int = 15
    photos_per_entry: int = 10

    dashboard_days: int = 7

    telegram_enabled: bool = False
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""
    notify_time: str = "08:00"
    notify_check_minutes: int = 10
    notify_max_attempts: int = 3

    backup_dir: Path = Path("/backups")
    backup_schedule: str = "30 3 * * 0"
    backup_retention_days: int = 30

    scheduler_enabled: bool = True

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        password = quote_plus(self.db_password.get_secret_value())
        user = quote_plus(self.db_user)
        return f"mysql+pymysql://{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"

    @cached_property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)

    @property
    def photos_dir(self) -> Path:
        return self.data_dir / "photos"

    @property
    def photo_max_bytes(self) -> int:
        return self.photo_max_mb * 1024 * 1024

    @property
    def telegram_configured(self) -> bool:
        return bool(
            self.telegram_enabled
            and self.telegram_bot_token.get_secret_value()
            and self.telegram_chat_id
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
