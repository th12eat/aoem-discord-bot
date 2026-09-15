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
        # Single Imperial City invasion (one 90-min window on the Invasion day),
        # unlike Behemoth's dual attack/defense. kind="siege" → one window whose
        # time defaults to 11:00 UTC and is set per cycle via /event_edit inv_time.
        # We attack OR defend the IC depending on the prep outcome (shown on the
        # dashboard); the ping is neutral about which.
        "invasion": {
            "stage_key": "inv",   # TME's Invasion stage
            "kind": "siege",
            "duration": 240,      # the Imperial City fight runs 4 hours
            "day": "start",       # the Invasion stage is a single day
            "time": "19:00",      # default; override per cycle via /event_edit inv_time
        },
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
                    "Increase technology power (including Research, Facility, and Animal Research) by 1 → +60",
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
                    "Building power +1 → +30 · technology power (including Research, Facility, and Animal Research) +1 → +60",
                    "Train/promote units, power +1 → +30",
                 ],
                 "actionable": "Invasion is next — position your marches for the fight"},
            ]},
            {"key": "inv", "title": "Invasion", "days": 1,
             "summary": "Attack or Defend the Imperial City",
             "actionable": "Be online for the invasion window — follow the tower/gate plan on the TME dashboard"},
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
        # Behemoth invasions during Attack/Defense: each server's Behemoth invades
        # the other at a locked time (90-min window). Two sides:
        #   defense = we defend OUR server / OUR Behemoth (enemy invades us)
        #   attack  = we attack THE OPPONENT server / their Behemoth (our Behemoth invades)
        # Both servers picked Sat 19:00 → the two windows coincide, so alerts merge
        # into one "Attack & Defense" ping. Times are on the Attack/Defense stage's
        # LAST day (the invasion day). Editable via /event_edit inv_atk / inv_def.
        "invasion": {
            "stage_key": "ad",        # Attack / Defense stage
            "duration": 90,           # minutes per invasion window
            "day": "last",            # invasion falls on the AD stage's last day
            "attack": "19:00",        # we invade the opponent server
            "defense": "19:00",       # the opponent invades our server
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
        # Seven-day, four-kingdom round-robin. Details mirror the Primordial
        # Conflict dashboard + the Order Workshop / Day 6 Showdown flyers.
        #
        # Order Workshop: TWO 1-hour contests per battle day (Days 2-4). The first
        # is ALWAYS 19:00 UTC on OUR server (guaranteed); the second is the
        # opponent's, at their voted time (varies, unknown until set). Per-day
        # second times are set via /event_edit ws2_d2 / ws2_d3 / ws2_d4.
        "workshop": {
            "stage_key": "battle",   # runs during the Battle Stage
            "duration": 60,          # minutes per contest
            "first_time": "19:00",   # our server, every battle day (fixed)
        },
        "stages": [
            {"key": "mm", "title": "Matchmaking", "days": 1,
             "summary": "Servers paired — scout & plan (no scoring yet)",
             "actionable": "Scout the three opponent servers (dashboard Scouting tab) and assign gather/PvP roles",
             "prep": "Save gather marches & speed-ups. The Battle Stage opens {nextDate} — our Order Workshop is 19:00 UTC daily"},
            {"key": "battle", "title": "Battle Stage", "days": 3,
             "summary": "Round-robin — gather Primordial Dew + contest Order Workshops (2 per day)",
             "king": "Special KvK — NO troop loss. Units wounded in PvP recover, so fight freely.",
             "scoring": [
                "Gather Primordial Dew at Alchemy Pools — 100 Dew → 10K points (1 march on a Lv.4 pool + rest on Lv.3)",
                "Order Workshops — capture = 600M, +200M if held at end, +500 pts/sec per person inside",
                "Lv.4 pool Corrupted Hyena — land the killing blow for +10% gather speed at that pool",
                "Combat eliminations — score within tier gap ≤ 2 (no lasting loss this cycle)",
             ],
             "actionable": "Fight BOTH workshop events daily (ours 19:00 UTC + the opponent's) and keep marches gathering Dew",
             "prep": "Win the Battle Stage to earn the Day 5 battlefield pick — selection is {nextDate}"},
            {"key": "select", "title": "Battlefield Selection", "days": 1,
             "summary": "Leading kingdom picks the showdown map + time",
             "actionable": "If we lead, the king (or top-alliance R5) picks the battlefield & time by 12:00 UTC — pick our prime window",
             "prep": "Position marches for the 4-way showdown on {nextDate}"},
            {"key": "showdown", "title": "Showdown", "days": 1,
             "summary": "4-way fight over 8 Essence Refineries around the chosen Imperial City",
             "scoring": [
                "Occupying kingdom earns 1M Kingdom Points/sec per refinery held",
                "Each refinery pays 800M to its last holder at contest end (8 × 800M = 6.4B)",
                "Refineries are rally-only — no solo marches, no war machines",
                "Primordial Essence: garrison a refinery (50K+ units) for 1/sec, + 1 per 500 combat pts (max 70K)",
             ],
             "actionable": "Lock our home-corner refinery cluster first, then push the flanks; taxi-rally the roster in after start"},
            {"key": "recovery", "title": "Recovery", "days": 1,
             "summary": "Partial recovery of battle losses (minimal this no-troop-loss cycle)",
             "actionable": "Collect rewards — event complete"},
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


def workshop_windows(short: str, start: datetime, second_times: dict | None = None,
                     first_time: str | None = None) -> list[dict]:
    """Order Workshop contest windows (Primordial Conflict, Battle Stage), as
    absolute UTC datetimes.

    Only KvKs with a `workshop` config produce windows. Two contests per battle
    day: the FIRST is OUR server's, defaulting to the configured `first_time`
    (19:00 UTC) but overridable via `first_time` if we move it; the SECOND is the
    opponent's, whose time varies and is unknown until set — pass it per
    battle-day-number in `second_times`, e.g. {2: "11:00", 3: "01:00"}. A day
    with no second time yields only its first window (ours).

    Returns dicts: {start, end, kind ('ours'|'theirs'), day (2..4), time ('HH:MM')}.
    """
    defn = KVK_DEFS.get(short, {})
    cfg = defn.get("workshop")
    if not cfg:
        return []
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    stage = next((s for s in compute_stages(short, start) if s["key"] == cfg["stage_key"]), None)
    if stage is None:
        return []
    second_times = second_times or {}
    ours_time = first_time or cfg["first_time"]
    dur = timedelta(minutes=cfg.get("duration", 60))

    def _dt(day_date, hhmm):
        h, m = (int(x) for x in hhmm.split(":"))
        return datetime(day_date.year, day_date.month, day_date.day, h, m, tzinfo=timezone.utc)

    # Battle Stage day 1 == event Day 2 (matchmaking is Day 1). Number windows by
    # the event day (2,3,4) so /event_edit ws2_d2 etc. line up with the dashboard.
    out = []
    day = stage["start"].date()
    last = stage["end"].date()  # exclusive
    event_day = 2
    while day < last:
        # first (ours) — default 19:00 UTC, or the per-event override
        ws = _dt(day, ours_time)
        out.append({"start": ws, "end": ws + dur, "kind": "ours", "day": event_day, "time": ours_time})
        # second (theirs) — only if a time has been set for this battle day
        t2 = second_times.get(event_day) or second_times.get(str(event_day))
        if t2:
            ws2 = _dt(day, t2)
            out.append({"start": ws2, "end": ws2 + dur, "kind": "theirs", "day": event_day, "time": t2})
        day += timedelta(days=1)
        event_day += 1
    return sorted(out, key=lambda x: x["start"])


def invasion_windows(short: str, start: datetime,
                     atk_time: str | None = None, def_time: str | None = None,
                     inv_time: str | None = None) -> list[dict]:
    """Behemoth invasion windows (Attack/Defense stage), as absolute UTC datetimes.

    Only KvKs with an `invasion` config (Behemoth Conquest) produce windows.
    Two invasions — `attack` (we invade the opponent) and `defense` (they invade
    us). When both times coincide they MERGE into one window with kind='both'
    (defend ours AND attack theirs at once); otherwise two separate windows with
    kind 'attack' / 'defense'.

    `atk_time` / `def_time` override the configured time (per-event edit). Each
    accepts either `HH:MM` — placed on the default invasion day (the AD stage's
    last day, i.e. Saturday) — or a full `YYYY-MM-DDTHH:MM`, which pins it to an
    explicit day (some cycles run the invasion on Friday, not Saturday).

    Returns dicts: {start, end, kind ('attack'|'defense'|'both'), time ('HH:MM')}.
    Attack and Defense merge into one 'both' window only when their start instants
    coincide (same day AND time) — so a Fri/Sat split stays two windows.
    """
    defn = KVK_DEFS.get(short, {})
    cfg = defn.get("invasion")
    if not cfg:
        return []
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    stage = next((s for s in compute_stages(short, start) if s["key"] == cfg["stage_key"]), None)
    if stage is None:
        return []
    # default invasion day = the AD stage's last day (day before its exclusive end)
    inv_day = (stage["end"] - timedelta(days=1)).date() if cfg.get("day") == "last" else stage["start"].date()
    dur = timedelta(minutes=cfg.get("duration", 90))

    def _dt(spec):
        """Parse an invasion spec — 'HH:MM' (→ default inv_day) or an ISO
        'YYYY-MM-DDTHH:MM' (→ explicit day) — to a UTC datetime."""
        spec = spec.strip()
        if "T" in spec:
            dt = datetime.fromisoformat(spec)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
        h, m = (int(x) for x in spec.split(":"))
        return datetime(inv_day.year, inv_day.month, inv_day.day, h, m, tzinfo=timezone.utc)

    # Single Imperial City siege (TME): one window, attack-or-defend (kind='siege').
    if cfg.get("kind") == "siege":
        ws = _dt(inv_time or cfg["time"])
        return [{"start": ws, "end": ws + dur, "kind": "siege", "time": ws.strftime("%H:%M")}]

    atk = atk_time or cfg["attack"]
    dfn = def_time or cfg["defense"]
    wsa, wsd = _dt(atk), _dt(dfn)
    out = []
    if wsa == wsd:
        out.append({"start": wsa, "end": wsa + dur, "kind": "both", "time": wsa.strftime("%H:%M")})
    else:
        out.append({"start": wsa, "end": wsa + dur, "kind": "attack", "time": wsa.strftime("%H:%M")})
        out.append({"start": wsd, "end": wsd + dur, "kind": "defense", "time": wsd.strftime("%H:%M")})
    return sorted(out, key=lambda x: x["start"])


# ── TME Imperial City invasion timeline ──────────────────────────────────────
# The invasion at time T triggers a fixed sequence of notifications. Offsets are
# in minutes from T (negative = before). Each entry is ONE notification — items
# that share an offset are one combined message. `slot` picks the staging
# alliance (1/2/3 → that alliance's role gets pinged); everything else pings the
# server role. `key` is a stable id used for de-dup + timeline labels.
TME_INVASION_STEPS = [
    {"key": "bubble1", "off": -180, "role": "server"},   # T-3h: first warning — bubble up
    {"key": "bubble2", "off": -120, "role": "server"},   # T-2h: final bubble + enemy teleport-in opens (combined)
    {"key": "stage1",  "off": -30,  "role": "slot", "slot": 1},   # T-30m: #1 alliance stages in IC tiles
    {"key": "stage2",  "off": -20,  "role": "slot", "slot": 2},   # T-20m: #2 alliance stages
    {"key": "stage3",  "off": -10,  "role": "slot", "slot": 3},   # T-10m: #3 alliance stages
    {"key": "start",   "off": 0,    "role": "server"},   # T: invasion begins
    {"key": "close",   "off": 240,  "role": "server"},   # T+4h: Imperial City closes if not taken
    {"key": "tpout",   "off": 360,  "role": "server"},   # T+6h: teleport-out (enemy if defense / us if attack)
]


def tme_invasion_schedule(short, start, inv_time=None):
    """Absolute-UTC timeline for a TME Imperial City invasion.

    Returns [] unless `short` is a siege-type KvK (TME). Otherwise a list of
    {key, at (datetime), slot (or None), role ('server'|'slot')} sorted by time,
    where `at` = invasion start + the step's offset.
    """
    defn = KVK_DEFS.get(short, {})
    cfg = defn.get("invasion")
    if not cfg or cfg.get("kind") != "siege":
        return []
    wins = invasion_windows(short, start, inv_time=inv_time)
    if not wins:
        return []
    t0 = wins[0]["start"]
    out = []
    for step in TME_INVASION_STEPS:
        out.append({
            "key": step["key"],
            "at": t0 + timedelta(minutes=step["off"]),
            "role": step["role"],
            "slot": step.get("slot"),
        })
    return out
