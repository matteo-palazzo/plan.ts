from datetime import UTC, date, datetime

from app.config import get_settings

_frozen: datetime | None = None


def freeze(moment: datetime | None) -> None:
    global _frozen
    _frozen = moment


def now() -> datetime:
    return _frozen or datetime.now(UTC)


def local_now() -> datetime:
    return now().astimezone(get_settings().zone)


def today() -> date:
    return local_now().date()


def local_date(moment: datetime) -> date:
    return moment.astimezone(get_settings().zone).date()
