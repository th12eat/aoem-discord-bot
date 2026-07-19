"""Multi-day KvK event definitions + stage computation.

Each KvK is picked by name; given a start datetime (UTC), all stage start/end
times are derived from the fixed per-stage durations below. Stages alert at
their START (never at end), but every notification carries the end info too.

For TME, "Preparation" is an umbrella of 5 sub-stages; we alert on the leaves
(Forging Gear … Power Boost), not the umbrella. Fight-time stages start at
00:00 UTC by default and can be refined to an exact time via /event_edit.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# Each KvK: ordered list of stages. A stage is a leaf (has `days`) OR a group
# with `subs` (each sub is a leaf). Leaves are what get alerts + scheduled.
KVK_DEFS = {
    "TME": {
        "name": "The Mightiest Emperor",
        "stages": [
            {"key": "mm", "title": "Matchmaking", "days": 2,
             "summary": "Find a match for TME (wait)", "actionable": "Prepare for Prep Stage 1"},
            {"key": "prep", "title": "Preparation", "group": True, "subs": [
                {"key": "forge",  "title": "Forging Gear",           "days": 1, "summary": "Forge Gear, Gather"},
                {"key": "bldg",   "title": "Enhancing Buildings",    "days": 1, "summary": "Use building speed-ups to advance buildings"},
                {"key": "tech",   "title": "Enhancing Technologies", "days": 1, "summary": "Use technology speed-ups to advance technology"},
                {"key": "train",  "title": "Unit Training",          "days": 1, "summary": "Use training speed-ups to make more units"},
                {"key": "boost",  "title": "Power Boost",            "days": 2, "summary": "Everything from the previous days"},
            ]},
            {"key": "inv", "title": "Invasion", "days": 1,
             "summary": "Attack or Defend the Imperial City", "actionable": "Fight at the invasion time"},
        ],
    },
    "GE": {
        "name": "Golden Expedition",
        "stages": [
            {"key": "mm",  "title": "Matchmaking", "days": 2, "summary": "Find a match for GE (wait)"},
            {"key": "inv", "title": "Invasion", "days": 3,
             "summary": "Do your dailies on the opposing server", "actionable": "PvP + PvE dailies"},
        ],
    },
    "BC": {
        "name": "Behemoth Conquest",
        "stages": [
            {"key": "mm",   "title": "Matchmaking", "days": 1, "summary": "Find a match for BC (wait)"},
            {"key": "tame", "title": "Beast Taming", "days": 3,
             "summary": "Daily events to buff your Elephant", "actionable": "Trials of Scion + other dailies"},
            {"key": "ad",   "title": "Attack / Defense", "days": 2,
             "summary": "Defend or attack the Elephant at set time", "actionable": "Defend or attack the Elephant"},
        ],
    },
    "PC": {
        "name": "Primordial Conflict",
        "stages": [
            {"key": "mm",   "title": "Matchmaking", "days": 1, "summary": "Find a match for PC (wait)"},
            {"key": "shop", "title": "Workshop", "days": 3,
             "summary": "Fight each server 3× a day", "actionable": "Do the Workshop events"},
            {"key": "batl", "title": "Battle", "days": 2,
             "summary": "Wait 1 day, then fight at Imperial", "actionable": "Hold Refineries"},
        ],
    },
    "DD": {
        "name": "Desolate Desert",
        "stages": [
            {"key": "mm",   "title": "Matchmaking", "days": 1, "summary": "Find a match for DD (wait)"},
            {"key": "z1",   "title": "Zone 1", "days": 1, "summary": "Build SH and gather", "actionable": "Build SH and gather"},
            {"key": "z2",   "title": "Zone 2", "days": 1, "summary": "Build to Pillar Cities and Tower", "actionable": "Follow alliance markers"},
            {"key": "tower", "title": "Tower of Rotation", "days": 3,
             "summary": "Tower of Rotation opens + Z2→Z2 gates", "actionable": "Follow markers; do Tower of Rotation"},
            {"key": "z3",   "title": "Zone 3", "days": 1, "summary": "Zone 3 opens", "actionable": "Follow alliance markers"},
            {"key": "aaru", "title": "Aaru Palace", "days": 1, "summary": "Fight at Aaru Palace", "actionable": "Follow alliance instructions"},
        ],
    },
}

KVK_CHOICES = [(k, f"{v['name']} ({k})") for k, v in KVK_DEFS.items()]


def _leaves(defn: dict):
    """Flatten a KvK def to its alertable leaf stages, in order."""
    out = []
    for st in defn["stages"]:
        if st.get("group"):
            for sub in st["subs"]:
                out.append({**sub, "parent": st["title"]})
        else:
            out.append(st)
    return out


def compute_stages(short: str, start: datetime) -> list[dict]:
    """Return ordered leaf stages with absolute start/end (UTC).
    Each: {key,title,parent?,summary,actionable?,start,end,days}."""
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    defn = KVK_DEFS[short]
    out = []
    cursor = start
    for leaf in _leaves(defn):
        s = cursor
        e = cursor + timedelta(days=leaf["days"])
        out.append({**leaf, "start": s, "end": e})
        cursor = e
    return out


def total_days(short: str) -> int:
    return sum(l["days"] for l in _leaves(KVK_DEFS[short]))


def stage_active_on(short: str, start: datetime, target, stage_keys=None) -> bool:
    """True if any stage (optionally limited to `stage_keys`) of this KvK is
    active on the `target` date. Used to detect a 'TME week' — pass
    stage_keys={'inv'} to test only the invasion day, or None for the whole run.
    `target` is a date; a stage covers [start_day, end_day)."""
    for st in compute_stages(short, start):
        if stage_keys and st["key"] not in stage_keys:
            continue
        if st["start"].date() <= target < st["end"].date():
            return True
    return False
