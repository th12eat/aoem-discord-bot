"""Weekly 'series' events — same weekday(s) each week, time varies per week.

A series is a single persistent event that ROLLS FORWARD: only its next
occurrence is ever live. When that occurrence's day completes (UTC), the bot
advances the same event to the next matching weekday and resets its time — so
the command dropdowns and the event log never fill with future dates.

Schedule shape (stored on the event):
    {"type": "series", "series": "City Clash", "date": "2026-07-25", "times": []}

`times` empty  → the occurrence is shown on the board but NOT pinged (its time is
                 "TBD" until an R4 sets it via /event_edit).
`times` filled → normal pings at each time (auto-filled for `fixed` series like
                 Starfall Vein; otherwise set by an R4).

Pure date logic lives here (no Discord/store deps). The TME-week skip is passed
in as a predicate by the caller, since that needs the guild's KvK event log.
"""

from __future__ import annotations

from datetime import date, timedelta

import catalog


def series_def(name: str) -> dict | None:
    return catalog.SERIES.get(name)


def default_times(name: str) -> list[str]:
    """Times a fresh occurrence starts with: fixed series pre-fill their known
    windows (and thus ping automatically); others start empty (TBD, no ping)."""
    d = catalog.SERIES.get(name, {})
    return list(d.get("fixedTimes", [])) if d.get("fixed") else []


def next_date(name: str, after: date, skip=None) -> date | None:
    """First date strictly after `after` that lands on one of the series'
    weekday(s) and isn't rejected by `skip(candidate_date) -> bool`.

    `skip` lets the caller drop occurrences (e.g. Imperial Showdown on a TME
    invasion Sunday). Searches up to ~1 year, then gives up (returns None)."""
    d = catalog.SERIES.get(name)
    if not d:
        return None
    days = set(d.get("days", []))
    if not days:
        return None
    cand = after + timedelta(days=1)
    for _ in range(400):
        if cand.weekday() in days and not (skip and skip(cand)):
            return cand
        cand += timedelta(days=1)
    return None


def make_occurrence(name: str, on: date) -> dict:
    """A series schedule for the given date, with default (possibly empty) times."""
    return {"type": "series", "series": name, "date": on.isoformat(),
            "times": default_times(name)}
