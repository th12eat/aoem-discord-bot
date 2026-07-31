# Catherine — AoEM Event Bot

Discord bot to schedule and announce Age of Empires Mobile events for Era 8,
with **server-wide** and **per-alliance** scopes.

## Concepts

**Scope.** Every event is either:
- **Server** — pings `@eRa8`; any alliance R4 may create/edit it.
- **Alliance** (WC1 / AGC / REU / MyT) — pings that alliance's member role;
  only that alliance's R4 may create/edit it.

Manage-Server always works as a safety hatch.

**Times are UTC.** Admins enter times in UTC; everyone *sees* them in their own
local timezone via Discord's dynamic timestamps.

## Commands

Admin (Manage Server):
| Command | Purpose |
|---|---|
| `/config` | set the `@eRa8` server member role + board channel (`#event-scheduler`) |
| `/config_alliance` | register an alliance's R4 role + member role |

Admin (R4 for the scope, or Manage Server):
| Command | Purpose |
|---|---|
| `/event_add` | add an event: scope, recurrence (once/daily/weekly/every-other), UTC times, duration |
| `/server_event_add` | curated server "opening" event (date range) |
| `/alliance_event_add` | curated alliance leadership event (specific time) |
| `/kvk_add` | multi-day KvK (TME / GE / BC / PC / DD); stages auto-mapped from a start date |
| `/series_setup` | seed the rolling weekly server events (see **Weekly series**) |
| `/event_edit` | edit an event's name / time / duration / scope (+ Behemoth flags — see below) |
| `/event_remove` | remove an event by id |

Legions (server-wide; any R4) — see **Legions** below:
| Command | Purpose |
|---|---|
| `/legion_slot` | bind a ping role to a time-slot (Sat/Sun × 01:00/11:00/19:00 UTC) |
| `/legion_seed` | declare this weekend's event; alternates WC ↔ BoD every weekend |
| `/legion_unseed` | stop the alternation (for the ~quarterly schedule exceptions) |
| `/legion_status` | show the current seed + which slot roles are set |
| `/legion_fill` | add members to a slot (discord @mentions/IDs → role; plain names → roster) |
| `/legion_remove` | remove members (discord + non-discord names) from all slots |
| `/legion_list` | list a slot's members grouped by alliance (non-discord marked ◇) |
| `/legion_reset` | clear all slot roles + roster now (same as the Monday auto-reset) |

**`/event_edit` — Behemoth Conquest flags.** Beyond name/time/duration/scope, a
Behemoth Conquest KvK accepts: `scion_first` (which server hosts the *first* daily
Trial of Scion window — flips the whole rotation), and `inv_atk` / `inv_def`
(the invasion Attack / Defense times, `HH:MM` UTC; same time → one combined
Attack & Defense alert).

For a one-off with a **custom name**, use `/event_add` — the curated commands
(`/server_event_add`, `/alliance_event_add`) no longer carry a "Custom…" option.

**Completed events** can't be edited and aren't listed anywhere: once an event
fully concludes it drops out of every list + the edit/remove picker and is
auto-deleted at the next UTC-midnight rollover (and on restart). A **KvK stays
editable while running** — it only locks after its final stage ends. Recurring
and rolling-series events never "complete."

### Weekly series (rolling)
`/series_setup` seeds recurring **server** events that land on the same weekday(s)
each week but whose **time varies** per week. Only the *next* occurrence is ever
live; the bot rolls it forward at UTC midnight once its day ends, so the dropdowns
and event log never fill with future dates.

| Series | Cadence | Time |
|---|---|---|
| Imperial Showdown | Sundays, **except TME weeks** (detected from the KvK log) | set per week |
| City Clash | Saturdays | set per week |
| World Campaign | Wednesdays & Sundays (4h) | set per week |
| Starfall Vein | Wednesdays | **fixed** 02:00 / 05:00 / 12:00 / 20:00 UTC (35 min each) |

A series shows on the board even before a time is set, but **won't ping until an
R4 sets the time** via `/event_edit` (fixed-time series like Starfall Vein ping
automatically). Set one or more comma-separated `HH:MM` times.

### Legions (Wonder Contest / Battle of Dawn)
Server-wide weekend events with a **six-slot roster**. `/legion_seed` declares this
weekend's event and the bot then **alternates Wonder Contest ↔ Battle of Dawn every
weekend** automatically (`/legion_unseed` for the rare exceptions). The six slots are
**Sat/Sun × 01:00 / 11:00 / 19:00 UTC**; `/legion_slot` binds a pingable role to each.

Rosters mix **discord and non-discord** members: `/legion_fill` takes a mix of
@mentions/IDs (discord users get the slot role) and plain names (stored on a roster
under your alliance, marked ◇ in `/legion_list`). `/legion_remove` removes either.

Each slot is pinged **1 hour before and at start** (40-min window); the start ping
lists the full roster for that slot, grouped by alliance. Roles + roster
**auto-empty Monday 00:00 UTC** (refill Thu/Fri) — this reset runs **once per week
regardless of restarts** (tracked with a persisted week marker). `/legion_reset`
does the same clear on demand. Needs **Manage Roles** + the bot's role above the slot
roles.

### Behemoth Conquest (Trial of Scion + invasion alerts)
A Behemoth Conquest KvK (`/kvk_add … BC`) fires two extra alert streams during its
stages, on top of the normal stage-start pings:

- **Trial of Scion** (Beast Taming days): four fixed 30-min windows/day. Each pings
  at its start with which server it's on (🛡️ ours #008 vs ⚔️ opponent), the
  duration, and what to do. `scion_first` flips which server hosts the first window.
- **Invasion** (Attack/Defense day): pings **1 hour before** and **at** each 90-min
  window. If both servers picked the same time the windows merge into one **⚔️🛡️
  Attack & Defense** alert; otherwise separate ⚔️ Attack / 🛡️ Defense pings fire.
  Each says where to be (WC1 on both servers; other alliances on ours) and how to
  score. The Attack/Defense stage-start notice also lists the locked time(s). Set
  the times with `/event_edit … inv_atk:HH:MM inv_def:HH:MM`.

Both streams also appear on the board on their days and self-clear after each window.

Member (replies are **ephemeral** — only you see them; **personal**: the server +
your own alliance, read from your roles; completed events excluded):
| Command | Purpose |
|---|---|
| `/event_list` | your events (server + your alliance) |
| `/next` | your next upcoming event |
| `/today` | today's events (UTC day) |
| `/week` | this week's events (UTC week) |

## Background behavior
- **Pings** the scope's role at **T-1h** and **at start** in the board channel.
  (KvK stage-starts ping at start only; legion slots and invasions ping T-1h + start.)
- **City Clash** alerts include the planned **city → alliance takeover list**.
- **Board** (`#event-scheduler`): a single Catherine-owned message showing
  **today's + tomorrow's** events (labeled by scope), auto-refreshing every 10
  min and rolling over at UTC midnight. It carries three buttons — **My Alliance
  Events**, **Changelog**, **How to use** — whose replies are all ephemeral.
- **Daily channel clear:** at **00:00 UTC** the board channel is wiped so only the
  board message survives; transient alerts + any chatter are cleared, then the
  board is re-posted fresh. (A mid-day restart never triggers a wipe — it waits
  for the next UTC rollover.) The **current KvK stage's instructions are re-posted**
  after the wipe so they persist day-to-day. On **Mondays**, the legion roster
  reset also runs (see **Legions**).
- **World Campaign** is a **4-hour** event: `/alliance_event_add` for it defaults
  to a 240-minute window (override with the `duration` field).
- **Series roll-forward:** at the UTC-midnight rollover, any series whose day has
  passed advances to its next matching weekday and resets its time (fixed series
  re-fill; others go back to TBD).

## First-run setup (in Discord, as a Manage-Server user)
1. `/config server_member_role:@eRa8 board_channel:#event-scheduler`
2. For each alliance, e.g.
   `/config_alliance alliance:WorldClass (WC1) r4_role:@WorldClass R4 - eRa8 member_role:@WorldClass eRa8`
   (repeat for AGC, REU, MyT)
3. Add events, e.g. Trojan Turmoil for WC1, Mon/Wed/Fri 19:00 UTC:
   `/event_add name:Trojan Turmoil scope:WorldClass (WC1) recurrence:Weekly times:19:00 weekdays:Mon,Wed,Fri`

## Run
```bash
cd aoem-discord-bot
python3 -m venv .venv && source .venv/bin/activate    # WSL/Linux; keep under ~ not /mnt/c
pip install -r requirements.txt
cp .env.example .env      # paste Catherine's token
python bot.py
```

## Portal settings required
- **Bot → Privileged Gateway Intents:** enable **Message Content** AND
  **Server Members Intent** (the latter is needed to read who has which role).
- **Invite scopes:** `bot` + `applications.commands`; permissions: Send Messages,
  Read Message History, Mention Everyone (for role pings), **Manage Messages**
  (daily board-channel clear), **Manage Roles** (legion slot fill + weekly purge).
- **Role hierarchy:** the bot's own role must sit **above** the legion slot roles
  in Server Settings → Roles, or it can't add/remove members from them.

## Data
`data/config.json` (roles/channel per guild) and `data/events.json` (events) —
JSON, human-readable, survive restarts. The `data/` dir is gitignored (it's
machine/guild-specific runtime state, and role IDs needn't live in source).

## Not yet built (planned)
- DM a role's members for specific events
- Richer per-event content + multi-language translation with per-user locale
