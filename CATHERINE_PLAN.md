# Catherine — Event System Expansion

Status: **Layers 1–5 DONE & tested + live-synced (13 commands).** Committed.
Remaining: named catalog polish, Legion roles/DM-by-role (await rosters),
per-stage alliance scoping for KvK, alert-lifecycle across restarts (currently
in-memory — transient alerts don't survive a restart, which is acceptable).

## The four add-commands (each a curated dropdown)

- **/server_event_add** — dropdown: Warrior's Trial, Fallen Frontier, Treasure Hunt,
  World Campaign, Marauder's, Rainbow Current, Starfall Vein **+ Custom**.
  Purpose: alert EVERYONE an event is opening. Input = **date RANGE**. Scope = server (@eRa8).
- **/alliance_event_add** — dropdown: Warrior's Trial, Fallen Frontier, Treasure Hunt,
  World Campaign, Marauder's **+ Custom**.
  Purpose: alliance leadership's actionable window. Input = **specific date/time**. Scope = alliance.
  (Note: several names overlap with server list but mean different things — server = "opening soon",
   alliance = "leadership acts now".)
- **/legion_add** — dropdown: Wonder Contest (WC), Battle of Dawn (BoD) ONLY.
  Every-other-week, opposite each other (WC one week, BoD the next).
  Day = next available Saturday OR Sunday; Time = dropdown 01:00/04:00/11:00/19:00 UTC.
  Supply legion members' discord names → later a Legion role; **for now ping the alliance role.**
- **/kvk_add** — dropdown: TME, GE, BC, PC, DD ONLY. Input = **name + start date only**;
  all stages auto-derived from kvk.py. Scope = server (stages retaggable to alliance via edit).

## New fields / behaviors (decided, just build)

- **duration** on events; default **60 min** if not given.
- **Alert lifecycle** (the ephemeral part):
  - Board (top master schedule) = unchanged, persistent.
  - The 1-hour alert is DELETED when the "starting now" alert fires (no double).
  - The "now" alert is DELETED after the event's duration elapses (or ~30 min fallback).
  - Implement by tracking sent alert message IDs per (event, occurrence) and deleting.
- **KvK alerts**: fire at START and at EACH STAGE START. NO end alert, but end info
  is included in every notification. Server-wide; some stages can be alliance-scoped (via edit).
- **Legion**: pings alliance for now (Legion role TBD when roster arrives).
- Every-other-week recurrence (anchored to a start date, like every-other-day) — for legion.

## KvK stage offsets (derived from user's JSON; cumulative day-offsets from start)

- **TME** (3 stages, prep has 5 subs): MM d0(2d) · Forging d2 · Enh.Bldg d3 · Enh.Tech d4 ·
  Unit Train d5 · Power Boost d6(2d) · Invasion d8(1d). Alert on the 5 sub-stages, not "Preparation" umbrella.
- **GE**: MM d0(2d) · Invasion d2(3d).
- **BC**: MM d0(1d) · Beast Taming d1(3d) · Attack/Defense d4(2d).
- **PC**: MM d0(1d) · Workshop d1(3d) · Battle d4(2d).
- **DD**: MM d0(1d) · Zone1 d1 · Zone2 d2 · Tower d3(3d) · Zone3 d6 · Aaru d7(1d).

## Defaults chosen (confirm on resume if any are wrong)

1. KvK stages start 00:00 UTC of their day; fight-time stages (Invasion / Attack-Defense /
   Battle / Aaru) refined to exact time via /event_edit.
2. TME alerts on the 5 sub-stages (not a separate "Preparation" umbrella alert).
3. All KvK stages default to server scope; retag specific stages to alliance via edit.
4. KvK: no T-1h pre-alert (multi-day, avoid noise) — alert at stage start only.
   Regular + legion events keep 1h + start alerts.
5. Legion: pick event + Sat/Sun + time → compute next matching date.

## Build order (verified layers)

1. **[DONE ✓ tested]** `kvk.py` — KvK defs + `compute_stages()` + `total_days()`. 22 tests pass.
2. **[DONE ✓ tested]** every-other-week recurrence + `kvk` type in `scheduling.py`
   (KvK fires at each stage start via standard `occurrences_between`); describe_schedule
   updated. eow + regression tests pass. Duration field still needs plumbing into add-commands.
3. **[NEXT]** Alert-lifecycle rework in scheduler_tick: track sent alert msg IDs per
   (event, occurrence); delete the 1h alert when "now" fires; delete "now" after duration.
   Needs a small persistent store for live-alert message IDs (survive restart) OR in-memory
   (simpler; alerts just won't auto-delete across a restart — acceptable).
4. The four add-commands (+ curated event-name lists as data). Include duration (default 60).
5. **/event_edit** (edit any event: time, duration, scope, name).
6. Later: named alliance/legion event catalog so names aren't typed; Legion role + DM-by-role.

## Curated event-name catalogs (from user)
- server_event_add: Warrior's Trial, Fallen Frontier, Treasure Hunt, World Campaign,
  Marauder's, Rainbow Current, Starfall Vein + Custom. (date RANGE, "opening soon")
- alliance_event_add: Warrior's Trial, Fallen Frontier, Treasure Hunt, World Campaign,
  Marauder's + Custom. (specific date/time, "leadership acts")
- legion_add: Wonder Contest (WC), Battle of Dawn (BoD). every-other-week opposite;
  Sat/Sun; time dropdown 01:00/04:00/11:00/19:00 UTC.
- kvk_add: TME/GE/BC/PC/DD (name + start date → stages auto-derived from kvk.py).

## Still awaited from user

- Exact KvK event names → DONE (in kvk.py).
- Named catalog for weekly alliance + weekly legion events (so people don't type names).
- Legion rosters (discord usernames) → to build Legion roles + targeted pings.
- Which KvK stages are alliance-specific (currently all server-scoped).
