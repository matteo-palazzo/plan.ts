import calendar
from collections.abc import Iterator
from datetime import date, timedelta

WEEKLY = "weekly"
MONTHLY = "monthly"


def validate_calendar_rule(rule: dict) -> dict:
    kind = rule.get("kind")
    if kind == WEEKLY:
        weekdays = rule.get("weekdays")
        if not isinstance(weekdays, list) or not weekdays:
            raise ValueError("Indica almeno un giorno della settimana")
        if any(not isinstance(day, int) or isinstance(day, bool) or not 0 <= day <= 6 for day in weekdays):
            raise ValueError("I giorni della settimana vanno da 0 (lunedì) a 6 (domenica)")
        return {"kind": WEEKLY, "weekdays": sorted(set(weekdays))}
    if kind == MONTHLY:
        day = rule.get("day")
        if not isinstance(day, int) or isinstance(day, bool) or not 1 <= day <= 31:
            raise ValueError("Il giorno del mese deve essere compreso tra 1 e 31")
        return {"kind": MONTHLY, "day": day}
    raise ValueError("Regola di calendario non valida")


def monthly_date(year: int, month: int, day: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def calendar_dates(rule: dict, start: date, end: date) -> Iterator[date]:
    if end < start:
        return
    if rule["kind"] == WEEKLY:
        weekdays = set(rule["weekdays"])
        current = start
        while current <= end:
            if current.weekday() in weekdays:
                yield current
            current += timedelta(days=1)
        return
    year, month = start.year, start.month
    while True:
        candidate = monthly_date(year, month, rule["day"])
        if candidate > end:
            return
        if candidate >= start:
            yield candidate
        month += 1
        if month > 12:
            year, month = year + 1, 1


def next_interval_date_after(anchor: date, interval_days: int, after: date) -> date:
    steps = max(1, (after - anchor).days // interval_days + 1)
    return anchor + timedelta(days=steps * interval_days)
