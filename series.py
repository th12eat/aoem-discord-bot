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


# ── rotating time pool ────────────────────────────────────────────────────────
# Some series cycle their fire time through catalog.ROTATION_POOL, advancing one
# slot per occurrence (wrapping). The slot for any occurrence is a pure function
# of an immutable anchor {date, idx} — "the occurrence on `date` used pool[idx]" —
# so it never desyncs across restarts or missed rollovers (unlike a stored
# counter). World Campaign lands on two weekdays, so it advances twice a week.
def occ_count(days: set[int], anchor: date, target: date) -> int:
    """Number of series-weekday dates d with anchor < d <= target (anchor
    EXCLUSIVE, target INCLUSIVE), so occ_count(days, anchor, anchor) == 0 and the
    anchor occurrence itself is index 0."""
    if target <= anchor:
        return 0
    n = 0
    d = anchor + timedelta(days=1)
    while d <= target:
        if d.weekday() in days:
            n += 1
        d += timedelta(days=1)
    return n


def rotation_slot(name: str, anchor_date: date, anchor_idx: int, target: date) -> int:
    """Pool index for `name`'s occurrence on `target`, given its anchor."""
    d = catalog.SERIES.get(name, {})
    days = set(d.get("days", []))
    pool = catalog.ROTATION_POOL
    return (anchor_idx + occ_count(days, anchor_date, target)) % len(pool)


def rotation_times(name: str, anchor_date: date, anchor_idx: int, target: date) -> list[str]:
    """Materialized [HH:MM] for `name`'s occurrence on `target` (single time)."""
    return [catalog.ROTATION_POOL[rotation_slot(name, anchor_date, anchor_idx, target)]]


def starfall_week(name: str, occ: date) -> int | None:
    """1-based week number within a series' fixed season (auto-wrapping), from its
    `season` {anchor, weeks}. E.g. Starfall Vein week 1..12 then back to 1.
    Returns None if the series has no season metadata."""
    season = catalog.SERIES.get(name, {}).get("season")
    if not season:
        return None
    try:
        anchor = date.fromisoformat(season["anchor"])
        weeks = int(season["weeks"])
    except (KeyError, ValueError):
        return None
    return ((occ - anchor).days // 7) % weeks + 1
