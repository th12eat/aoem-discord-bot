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
| `/event_add` | add an event: scope, recurrence (once/daily/weekly), UTC times |
| `/event_remove` | remove an event by id |

Member (replies are **ephemeral** — only you see them; scoped to what you can view):
| Command | Purpose |
|---|---|
| `/event_list` | events you can see |
| `/next` | your next upcoming event |
| `/today` | today's events (UTC day) |
| `/week` | this week's events (UTC week) |

## Background behavior
- **Pings** the scope's role at **T-1h** and **at start** in the board channel.
- **Board** (`#event-scheduler`): a single Catherine-owned message showing
  **today's + tomorrow's** events (labeled by scope), auto-refreshing every 10
  min and rolling over at UTC midnight.

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
  Read Message History, Mention Everyone (for role pings).

## Data
`data/config.json` (roles/channel per guild) and `data/events.json` (events) —
JSON, human-readable, survive restarts. The `data/` dir is gitignored (it's
machine/guild-specific runtime state, and role IDs needn't live in source).

## Not yet built (planned)
- DM a role's members for specific events
- Richer per-event content + multi-language translation with per-user locale
