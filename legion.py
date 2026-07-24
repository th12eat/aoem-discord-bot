"""Legion (Wonder Contest / Battle of Dawn) alternation + slot scheduling.

Server-wide model:
  • A SEED declares which event (WC or BoD) runs the weekend of an anchor Saturday.
    From there the event alternates every OTHER weekend forever:
    WC → BoD → WC → BoD … (i.e. it repeats every 2 weekends, swapping each weekend).
  • Six time-slots (Sat/Sun × 01:00/11:00/19:00 UTC) each have a pingable role,
    filled by admins ahead of time. On a legion weekend, each slot's role is
    pinged at its slot time with that weekend's event name.
  • Unseed removes the alternation (for the ~quarterly exceptions).

Pure date logic only — no Discord/store deps.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import catalog

# slot key -> (weekday Mon=0…Sun=6, "HH:MM")
SLOT_TIMES = {
    "sat_0100": (5, "01:00"), "sat_1100": (5, "11:00"), "sat_1900": (5, "19:00"),
    "sun_0100": (6, "01:00"), "sun_1100": (6, "11:00"), "sun_1900": (6, "19:00"),
}


def weekend_saturday(d: date) -> date:
    """The Saturday of the legion weekend containing date `d` (Sat or Sun)."""
    wd = d.weekday()
    if wd == 5:                 # Saturday
        return d
    if wd == 6:                 # Sunday → the day before
        return d - timedelta(days=1)
    # any weekday → the upcoming Saturday
    return d + timedelta(days=(5 - wd) % 7)


def event_for_weekend(seed: dict, sat: date) -> str | None:
    """Which legion event ('WC'/'BoD') runs on the weekend of Saturday `sat`,
    given the seed {anchor: 'YYYY-MM-DD' (a Sat), event: 'WC'|'BoD'}. Alternates
    every weekend; returns None if seed is missing/invalid."""
    if not seed or "anchor" not in seed or "event" not in seed:
        return None
    try:
        anchor = date.fromisoformat(seed["anchor"])
    except ValueError:
        return None
    anchor = weekend_saturday(anchor)
    weeks = round((sat - anchor).days / 7)
    base = seed["event"]
    other = "BoD" if base == "WC" else "WC"
    return base if weeks % 2 == 0 else other


def next_slot_fire(slot: str, now: datetime) -> datetime | None:
    """Next UTC datetime this slot fires at or after `now` (within ~2 weeks)."""
    if slot not in SLOT_TIMES:
        return None
    wd, hhmm = SLOT_TIMES[slot]
    h, m = (int(x) for x in hhmm.split(":"))
    now = now.astimezone(timezone.utc)
    for add in range(0, 15):
        d = (now + timedelta(days=add)).date()
        if date(d.year, d.month, d.day).weekday() != wd:
            continue
        dt = datetime(d.year, d.month, d.day, h, m, tzinfo=timezone.utc)
        if dt >= now:
            return dt
    return None
