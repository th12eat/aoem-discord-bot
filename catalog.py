"""Curated event-name catalogs for the add-commands.

These are the picklists users choose from (so they don't type names). "Custom"
lets an admin name a one-off. Legion + KvK are fixed sets (no custom).
"""

# Server-wide "opening soon" events (alert everyone; entered as a date RANGE).
SERVER_EVENTS = [
    "Warrior's Trial", "Fallen Frontier", "Treasure Hunt", "World Campaign",
    "Marauder's", "Rainbow Current", "Starfall Vein",
]

# Alliance leadership actionable events (specific date/time).
ALLIANCE_EVENTS = [
    "Warrior's Trial", "Fallen Frontier", "Treasure Hunt", "World Campaign",
    "Marauder's",
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
