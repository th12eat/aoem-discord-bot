"""Curated event-name catalogs for the add-commands.

These are the picklists users choose from (so they don't type names). "Custom"
lets an admin name a one-off. Legion + KvK are fixed sets (no custom).
"""

# Server-wide "opening soon" events (alert everyone; entered as a date RANGE).
SERVER_EVENTS = [
    "Warrior's Trial", "Fallen Frontier", "Treasure Hunt", "World Campaign",
    "Marauder's Hunt", "Rainbow Current", "Starfall Vein",
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
#   rotates    : True → the fire time cycles through ROTATION_POOL, +1 slot per
#                occurrence (see series.rotation_times). Auto-pings once an R4 has
#                seeded the per-guild anchor via /rotation_seed. `fixed` stays
#                False for these (their time changes every occurrence, not weekly).
#   glue       : name of another (rotating) series whose current pool slot this
#                event borrows instead of holding its own anchor (Imperial Showdown
#                follows City Clash). The glued event reads the target's anchor and
#                computes the slot for its own occurrence's weekend.
#   season     : {anchor, weeks} for events that run in fixed back-to-back seasons;
#                used to show "Week N/weeks" (Starfall Vein). Auto-wraps forever.
#   ddForce    : HH:MM the fire time is FORCED to on any week our server runs
#                Desolate Desert (Treasure Hunt → "04:00"). The rotation pointer
#                still advances underneath (the DD occurrence consumes its slot);
#                only the displayed/pinged time is overridden. So the week after a
#                DD week resumes as if nothing happened.

# Rotating events cycle their UTC start time through this pool, one slot per
# occurrence, wrapping. World Campaign (Wed+Sun) advances twice a week; the
# once-weekly series advance once. Imperial Showdown mirrors City Clash's slot.
ROTATION_POOL = ["01:00", "04:00", "11:00", "19:00"]

SERIES = {
    "Imperial Showdown": {"days": [6], "fixed": False, "skipTme": True,
                          "glue": "City Clash",
                          "note": "Every Sunday except TME weeks · time follows City Clash"},
    "City Clash":        {"days": [5], "fixed": False, "rotates": True,
                          "note": "Every Saturday · rotating time (01/04/11/19 UTC)"},
    "World Campaign":    {"days": [2, 6], "fixed": False, "rotates": True, "duration": 240,
                          "note": "Every Wednesday & Sunday (4h) · rotating time (01/04/11/19 UTC)"},
    "Treasure Hunt":     {"days": [3], "fixed": False, "rotates": True, "ddForce": "04:00",
                          "note": "Every Thursday · rotating time (01/04/11/19 UTC); forced 04:00 on DD weeks"},
    "Starfall Vein":     {"days": [2], "fixed": True,
                          "fixedTimes": ["02:00", "05:00", "12:00", "20:00"],
                          "duration": 35,
                          "season": {"anchor": "2026-07-29", "weeks": 12},
                          "note": "Every Wednesday · fixed times 02/05/12/20 UTC (35 min each) · 12-week season"},
}

# Every-N-week recurring windows (fixed cadence, multi-day span). Modeled as an
# `everynweek` schedule anchored to a first-occurrence date; the multi-day window
# is a single start-day ping whose `duration` (minutes) covers the span, so the
# "running now" alert self-clears at the end. day = weekday (Mon=0 … Sun=6).
# NOTE: day/duration are TENTATIVE pending in-game confirmation — tune here.
#   2 days = 2880 min · 3 days = 4320 min. times ["TBD"] → no ping until an R4
#   sets the real start time via /event_edit (matches the series TBD convention).
NWEEK_EVENTS = {
    "Marauder's Hunt": {"interval_weeks": 2, "day": 1, "times": ["TBD"], "duration": 2880},  # Tue, 2-day (tentative)
    "Warrior's Trial": {"interval_weeks": 4, "day": 1, "times": ["TBD"], "duration": 4320},  # Tue, 3-day (tentative)
}

# Alliance leadership actionable events (specific date/time).
ALLIANCE_EVENTS = [
    "Warrior's Trial", "Fallen Frontier", "Treasure Hunt", "World Campaign",
    "Marauder's Hunt", "Trojan Turmoil",
]

# City Clash — which alliance is expected to take which city (with its region).
# Included in the City Clash event alert so members know the plan.
CITY_CLASH_TARGETS = {
    "WC1": [("City of Sapphire", "North Kingsland"),
            ("City of Fiery Stallion", "Kyuno"),
            ("City of Eagle", "Olympia")],
    "REU": [("City of Black Reef", "West Kingsland"),
            ("City of Jade Viper", "Neilos"),
            ("City of Desert Camel", "Tinir")],
    "MyT": [("City of White Pierce", "East Kingsland"),
            ("City of Qilin", "Eastland")],
    "AGC": [("City of Golden Lion", "Gaul")],
}


def city_clash_lines() -> list[str]:
    """Formatted 'ALLIANCE → City [Region]' lines for the City Clash alert."""
    out = []
    for tag, cities in CITY_CLASH_TARGETS.items():
        joined = ", ".join(f"{c} [{r}]" for c, r in cities)
        out.append(f"**{tag}** → {joined}")
    return out


# Weekly legion events — alternate every other week (WC ↔ BoD). 5 legions of
# 20–30 members each; times are Sat/Sun at fixed windows with a per-time role.
LEGION_EVENTS = {
    "WC":  "Wonder Contest",
    "BoD": "Battle of Dawn",
}

# Legion events run Sat/Sun at these UTC times (recent change: 04:00 dropped).
LEGION_TIMES = ["01:00", "11:00", "19:00"]

# The six legion time-slots that get their own pingable role.
LEGION_SLOTS = ["sat_0100", "sat_1100", "sat_1900", "sun_0100", "sun_1100", "sun_1900"]

# Known event durations (minutes). Events not listed default to 60.
# World Campaign is a 4-hour window.
EVENT_DURATIONS = {
    "World Campaign": 240,
}


def default_duration(name: str) -> int:
    """Default duration in minutes for a named event (60 if unknown)."""
    return EVENT_DURATIONS.get(name, 60)


CUSTOM = "Custom…"
