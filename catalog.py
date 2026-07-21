"""Curated event-name catalogs for the add-commands.

These are the picklists users choose from (so they don't type names). "Custom"
lets an admin name a one-off. Legion + KvK are fixed sets (no custom).
"""

# Server-wide "opening soon" events (alert everyone; entered as a date RANGE).
SERVER_EVENTS = [
    "Warrior's Trial", "Fallen Frontier", "Treasure Hunt", "World Campaign",
    "Marauder's", "Rainbow Current", "Starfall Vein",
    "Imperial Showdown", "City Clash",
]

# Weekly "series": recur on the same weekday(s) every week, but the TIME VARIES
# per occurrence. Only the *next* occurrence is ever live — it rolls forward the
# moment its day completes (UTC) — so the dropdowns never fill with future dates.
#   days       : weekday(s) it lands on (Mon=0 … Sun=6)
#   fixed      : True  → times auto-populate from `fixedTimes` each week and PING
#                        automatically (e.g. Starfall Vein's known windows).
#                False → the occurrence stays "time TBD" (shown on the board but
#                        NOT pinged) until an R4 sets the time via /event_edit.
#   skipTme    : skip any occurrence that lands on a TME invasion day (Imperial
#                Showdown only — it runs the Sundays that don't clash with TME).
#   duration   : minutes (World Campaign is a 4-hour window).
SERIES = {
    "Imperial Showdown": {"days": [6], "fixed": False, "skipTme": True,
                          "note": "Every Sunday except TME weeks"},
    "City Clash":        {"days": [5], "fixed": False,
                          "note": "Every Saturday"},
    "World Campaign":    {"days": [2, 6], "fixed": False, "duration": 240,
                          "note": "Every Wednesday & Sunday (4h)"},
    "Starfall Vein":     {"days": [2], "fixed": True,
                          "fixedTimes": ["02:00", "05:00", "12:00", "20:00"],
                          "duration": 35,
                          "note": "Every Wednesday · fixed times 02/05/12/20 UTC (35 min each)"},
}

# Alliance leadership actionable events (specific date/time).
ALLIANCE_EVENTS = [
    "Warrior's Trial", "Fallen Frontier", "Treasure Hunt", "World Campaign",
    "Marauder's", "Trojan Turmoil",
]

# Weekly legion events — every other week, opposite each other.
LEGION_EVENTS = {
    "WC":  "Wonder Contest",
    "BoD": "Battle of Dawn",
}

# Legion events can only run Sat/Sun at these UTC times.
LEGION_TIMES = ["01:00", "04:00", "11:00", "19:00"]

# Known event durations (minutes). Events not listed default to 60.
# World Campaign is a 4-hour window.
EVENT_DURATIONS = {
    "World Campaign": 240,
}


def default_duration(name: str) -> int:
    """Default duration in minutes for a named event (60 if unknown)."""
    return EVENT_DURATIONS.get(name, 60)


CUSTOM = "Custom…"
