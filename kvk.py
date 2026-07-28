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
        "name": "The Mightiest Empire",
        # Each prep sub-stage carries the exact point-scoring methods for THAT day
        # (`scoring`) and what to do today to be ready for the NEXT stage (`prep`,
        # which may reference `{nextDate}` — the coming stage's date). `king` notes
        # the King's Rights buff that turns on that day. Kept in sync with the TME
        # dashboard's day-by-day descriptions.
        "stages": [
            {"key": "mm", "title": "Matchmaking", "days": 2,
             "summary": "Find a match for TME (wait — no scoring yet)",
             "actionable": "Prep for Stage 1",
             "prep": "Farm Iron Meteorite and save Stamina for Stage 1 (Forging Gear) on {nextDate}"},
            {"key": "prep", "title": "Preparation", "group": True, "subs": [
                {"key": "forge",  "title": "Forging Gear", "days": 1,
                 "summary": "Craft gear + kill tribes; pre-gather for tomorrow",
                 "scoring": [
                    "Craft gear — rare +10,000 · epic +30,000 · legendary +200,000 (per piece)",
                    "Kill tribes — Lv.1-4 +4,000 → Lv.25-28 +20,800 → Lv.29-30 +24,000 (per kill)",
                 ],
                 "prep": "Pre-gather RSS for Stage 2 (every 100 RSS gathered = +10) and sign up for Chief Priest (+10% Building Speed) slots for Enhancing Buildings on {nextDate}"},
                {"key": "bldg",   "title": "Enhancing Buildings", "days": 1,
                 "summary": "Burn building speed-ups + gather",
                 "king": "King's Rights — Building buff active from 04:00 UTC",
                 "scoring": [
                    "Consume 1h of building speed-ups → +18,000",
                    "Increase building power by 1 → +30",
                    "Gather 100 resources (except armories) → +10",
                 ],
                 "prep": "Sign up for Court Sage (Research) slots for Enhancing Technologies on {nextDate}"},
                {"key": "tech",   "title": "Enhancing Technologies", "days": 1,
                 "summary": "Burn research speed-ups; run Starfall Vein",
                 "king": "King's Rights — Research buff active from 04:00 UTC",
                 "scoring": [
                    "Participate in Starfall Vein 1 time → +3,000,000",
                    "Consume 1h of research speed-ups → +18,000",
                    "Increase technology power by 1 → +60",
                 ],
                 "prep": "Sign up for Tactical Master (Unit Training) slots for Unit Training on {nextDate}"},
                {"key": "train",  "title": "Unit Training", "days": 1,
                 "summary": "Train units + merchant ship trade",
                 "king": "King's Rights — Unit Training buff active from 04:00 UTC",
                 "scoring": [
                    "Initiate 1 legendary merchant ship trade → +1,000,000",
                    "Train units — Lv.1 +30 · Lv.2 +50 · Lv.3 +70 · Lv.4 +100 · Lv.5 +160 · Lv.6 +280",
                 ],
                 "prep": "Farm RSS and/or Iron Meteorite. Optionally sign up for Chief Priest, Court Sage, or Tactical Master for Power Boost on {nextDate}"},
                {"key": "boost",  "title": "Power Boost", "days": 2,
                 "summary": "Catch-all — most prior methods score again",
                 "king": "King's Rights — Gathering buff active from 04:00 UTC",
                 "scoring": [
                    "Legendary merchant ship trade → +1,000,000",
                    "Craft gear — rare +10,000 · epic +30,000 · legendary +200,000",
                    "Kill tribes — Lv.1-4 +4,000 → Lv.29-30 +24,000",
                    "Gather 100 resources (except armories) → +10",
                    "Building power +1 → +30 · technology power +1 → +60",
                    "Train/promote units, power +1 → +30",
                 ],
                 "actionable": "Invasion is next — position your marches for the fight"},
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
        # Score three ways: cultivate ours (Beast Taming), then defend ours +
        # attack theirs (Attack/Defense). Runestones grow our Behemoth AND give
        # 10 personal pts each. Details mirror the Behemoth dashboard.
        #
        # Trial of Scion: four fixed 30-min windows/day during Beast Taming. Each
        # window's Scion spawns on ONE server. `server` is our best-known default
        # (mirrors the dashboard: 01:00 & 13:00 on ours, 07:00 & 19:00 on theirs).
        # We don't know for certain which side hosts the first window until the
        # first Trial actually starts — /event_edit scion_first can flip the whole
        # rotation once it's confirmed in-game.
        "scion": {
            "stage_key": "tame",      # runs during Beast Taming
            "duration": 30,           # minutes per window
            "windows": [
                {"time": "01:00", "server": "ours"},
                {"time": "07:00", "server": "theirs"},
                {"time": "13:00", "server": "ours"},
                {"time": "19:00", "server": "theirs"},
            ],
        },
        "stages": [
            {"key": "mm", "title": "Matchmaking", "days": 1,
             "summary": "Servers paired — scout & plan (no scoring yet)",
             "actionable": "Scout the enemy server; line up rally leaders for Beast Taming",
             "prep": "Save Scion attempts & speed-ups for Beast Taming, which opens {nextDate}"},
            {"key": "tame", "title": "Beast Taming", "days": 3,
             "summary": "Cultivate our Behemoth — farm & donate Awaken Runestones",
             "king": "Runestones tip Bloodline Purity our way and pay 10 personal pts each — donate, don't hoard",
             "scoring": [
                "Trial of Scion — farm Scions in the 30-min window (runestones + eliminations)",
                "Cultivation Exploration — 3 open at 04:00 / 12:00 / 20:00 UTC, 18 runestones each",
                "Rally vs Tribes — join every called rally (Days 2 & 4 only)",
                "Maxing everything across the 3 days ≈ 3,036 runestones",
             ],
             "actionable": "Do your Scion window + all 3 Cultivation Explorations daily; donate as you go",
             "prep": "Be online for the Attack/Defense windows starting {nextDate} — that's where most of the score is won"},
            {"key": "ad", "title": "Attack / Defense", "days": 2,
             "summary": "90-min cross-server Behemoth invasions — the score is won here",
             "scoring": [
                "Only RALLIES damage the Behemoth (1,000/sec each) — more separate rallies = more damage",
                "Hold rallies long: after 5 min, damage ramps +500 every 15s — don't let them disband",
                "Milestones dwarf chip damage: a stack = 1B, the kill = 5B",
                "Defense pays 2M per 1,000 HP left on ours — keeping ours alive matters as much as attacking",
                "Enemy Behemoth at 0 HP burns an Undying stack, dazes 30s, revives; 3 stacks ≈ 4 zeroes to kill",
             ],
             "actionable": "Be online for the window — attack their Behemoth in rallies, relocate to the enemy server to help the offense"},
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


def occurrence_label(short: str, start: datetime, dt: datetime) -> str:
    """Legible per-stage label for a KvK occurrence, e.g. 'TME: Forging Gear'.
    Falls back to the KvK's full name if `dt` isn't a known stage start."""
    stage = next((s for s in compute_stages(short, start) if s["start"] == dt), None)
    if stage:
        return f"{short}: {stage['title']}"
    return KVK_DEFS.get(short, {}).get("name", short)


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


def scion_windows(short: str, start: datetime, flip: bool = False) -> list[dict]:
    """All Trial of Scion windows for this KvK, as absolute UTC datetimes.

    Only KvKs with a `scion` config (Behemoth Conquest) produce windows; others
    return []. Each window falls on every day of the configured stage (Beast
    Taming = 3 days → 4 windows/day → 12 total).

    `flip` swaps which server hosts each window (ours ↔ theirs) — used once the
    real first-Trial host is confirmed in-game, since the default is only our
    best guess.

    Returns dicts: {start, end, server ('ours'|'theirs'), time ('HH:MM')}.
    """
    defn = KVK_DEFS.get(short, {})
    cfg = defn.get("scion")
    if not cfg:
        return []
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    stage = next((s for s in compute_stages(short, start) if s["key"] == cfg["stage_key"]), None)
    if stage is None:
        return []
    dur = timedelta(minutes=cfg.get("duration", 30))
    out = []
    day = stage["start"].date()
    last = stage["end"].date()  # exclusive
    while day < last:
        for w in cfg["windows"]:
            h, m = (int(x) for x in w["time"].split(":"))
            ws = datetime(day.year, day.month, day.day, h, m, tzinfo=timezone.utc)
            server = w["server"]
            if flip:
                server = "theirs" if server == "ours" else "ours"
            out.append({"start": ws, "end": ws + dur, "server": server, "time": w["time"]})
        day += timedelta(days=1)
    return sorted(out, key=lambda x: x["start"])
