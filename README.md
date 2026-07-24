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
| `/kvk_add` | multi-day KvK; stages auto-mapped from a start date |
| `/series_setup` | seed the rolling weekly server events (see **Weekly series**) |
| `/event_edit` | edit an event's name / time / duration / scope |
| `/event_remove` | remove an event by id |

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
- **Board** (`#event-scheduler`): a single Catherine-owned message showing
  **today's + tomorrow's** events (labeled by scope), auto-refreshing every 10
  min and rolling over at UTC midnight. It carries three buttons — **My Alliance
  Events**, **Changelog**, **How to use** — whose replies are all ephemeral.
- **Daily channel clear:** at **00:00 UTC** the board channel is wiped so only the
  board message survives; transient alerts + any chatter are cleared, then the
  board is re-posted fresh. (A mid-day restart never triggers a wipe — it waits
  for the next UTC rollover.)
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
