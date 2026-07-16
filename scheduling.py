"""Recurrence logic — pure functions, no Discord dependency (so it's testable).

An event's `schedule` is one of four shapes (all times UTC):

  one-time : {"type": "once",   "datetime": "2026-07-20T19:00"}
  daily    : {"type": "daily",  "times": ["03:00", "13:00", "21:00"]}
  weekly   : {"type": "weekly", "days": [0,2,4], "times": ["19:00"]}
             (days: Mon=0 … Sun=6, matching datetime.weekday())
  multi/day: expressed as "daily" or "weekly" with multiple "times" entries.

The core primitive is `occurrences_between(event, start, end)` → sorted list of
timezone-aware UTC datetimes when the event fires in the window. Everything else
(next occurrence, today's list, week list, T-1h ping detection) builds on it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware in UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_hhmm(s: str) -> tuple[int, int]:
    h, m = s.split(":")
    return int(h), int(m)


def occurrences_between(event: dict, start: datetime, end: datetime) -> list[datetime]:
    """All UTC fire-times for `event` in [start, end] inclusive, sorted."""
    start, end = _utc(start), _utc(end)
    sched = event["schedule"]
    stype = sched["type"]
    out: list[datetime] = []

    if stype == "once":
        dt = _utc(datetime.fromisoformat(sched["datetime"]))
        if start <= dt <= end:
            out.append(dt)
        return out

    # daily / weekly / everyother all iterate day-by-day across the window
    times = [_parse_hhmm(t) for t in sched.get("times", [])]
    days = sched.get("days")  # None for daily; list of weekdays for weekly

    # every-other-day: fires only on days an even number of days after `anchor`
    anchor_date = None
    if stype == "everyother":
        anchor_date = datetime.fromisoformat(sched["anchor"]).date()

    day = start.date()
    last = end.date()
    while day <= last:
        fires = True
        if stype == "weekly":
            fires = datetime(day.year, day.month, day.day).weekday() in days
        elif stype == "everyother":
            delta = (day - anchor_date).days
            fires = delta >= 0 and delta % 2 == 0
        # stype == "daily" → fires every day
        if fires:
            for h, m in times:
                dt = datetime(day.year, day.month, day.day, h, m, tzinfo=timezone.utc)
                if start <= dt <= end:
                    out.append(dt)
        day += timedelta(days=1)

    return sorted(out)


def next_occurrence(event: dict, now: datetime, horizon_days: int = 366) -> datetime | None:
    """The soonest fire-time at or after `now`, or None within the horizon."""
    now = _utc(now)
    window_end = now + timedelta(days=horizon_days)
    occ = occurrences_between(event, now, window_end)
    return occ[0] if occ else None


def schedules_collide(a: dict, b: dict, now: datetime, horizon_days: int = 60) -> datetime | None:
    """Return the first UTC instant where events `a` and `b` BOTH fire within the
    horizon, or None. Used to reject a duplicate (same name, same time). Compares
    on the minute — two occurrences at the same HH:MM on the same date collide.
    """
    now = _utc(now)
    end = now + timedelta(days=horizon_days)
    occ_a = {dt.replace(second=0, microsecond=0) for dt in occurrences_between(a, now, end)}
    if not occ_a:
        return None
    for dt in occurrences_between(b, now, end):
        if dt.replace(second=0, microsecond=0) in occ_a:
            return dt
    return None


def occurrences_for_events(events: list[dict], start: datetime, end: datetime) -> list[tuple[datetime, dict]]:
    """(fire_time, event) pairs across many events in a window, sorted by time."""
    pairs: list[tuple[datetime, dict]] = []
    for e in events:
        for dt in occurrences_between(e, start, end):
            pairs.append((dt, e))
    pairs.sort(key=lambda p: p[0])
    return pairs


def utc_day_bounds(now: datetime) -> tuple[datetime, datetime]:
    """[00:00, 23:59:59.999999] UTC of the day containing `now`."""
    now = _utc(now)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1) - timedelta(microseconds=1)
    return start, end


def utc_week_bounds(now: datetime) -> tuple[datetime, datetime]:
    """[Mon 00:00, Sun 23:59:59.999999] UTC of the week containing `now`."""
    now = _utc(now)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
    end = start + timedelta(days=7) - timedelta(microseconds=1)
    return start, end
