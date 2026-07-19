"""User-facing help + changelog text for Catherine's board buttons.

Kept here (not in bot.py) so the prose is easy to edit without touching command
logic. Both strings are shown ephemerally when a board button is tapped.

VERSION is the human release tag; CHANGELOG lists broad, user-visible changes per
release (not every commit). HOWTO documents every command, its SCOPE (server vs
alliance vs anyone), and which ROLES may use it.
"""

VERSION = "1.2.0"

CHANGELOG = f"""📜 **Catherine — v{VERSION}**
_Broad, user-visible changes per release._

**v1.2.0 — Board housekeeping**
• #event-scheduler now **auto-clears daily** at 00:00 UTC — only the pinned board (this message) stays.
• New buttons on the board: **Changelog** and **How to use** (both private to you).
• **World Campaign** now defaults to a **4-hour** window when added as an alliance event.

**v1.1.0 — Event categories & editing**
• Curated add-commands: `/server_event_add`, `/alliance_event_add`, `/legion_add`, `/kvk_add`.
• `/event_edit` to change an event's name, time, duration, or scope.
• Self-cleaning alerts: the 1-hour ping is removed when "starting now" fires; the
  start ping removes itself after the event's duration.
• Duplicate events (same name + scope firing at the same time) are rejected.

**v1.0.0 — First release**
• Server-wide (@eRa8) and per-alliance (WC1/AGC/REU/MyT) event scopes.
• `/event_add` (once/daily/weekly/every-other) with UTC times.
• Auto-updating board of today's + tomorrow's server events, rolling over at UTC midnight.
• Role pings at T-1h and at start; ephemeral member queries (`/next`, `/today`, `/week`)."""


HOWTO = """❓ **How to use Catherine**
All times are entered in **UTC**; everyone *sees* them in their own local time.
Each command notes its **scope** and **who can use it**.

**⚙️ Setup — _Manage Server only_**
• `/config` — set the @eRa8 role + board channel (#event-scheduler). *[Server]*
• `/config_alliance` — register an alliance's R4 + member roles. *[Server]*

**📣 Server-wide events — _any R4_ (or Manage Server)**
Pings @eRa8; any alliance's R4 may create/edit these.
• `/server_event_add` — announce an event **opening** (date range). *[Server]*
• `/event_add` (scope: Server-wide) — recurring/one-time server event. *[Server]*
• `/kvk_add` — multi-day KvK (TME/GE/BC/PC/DD); stages auto-derived from the start date. *[Server]*

**🏰 Alliance events — _that alliance's R4 only_ (or Manage Server)**
Pings that alliance's member role; only its R4 may create/edit.
• `/alliance_event_add` — leadership actionable at a specific date/time. *[Alliance]*
• `/event_add` (scope: your alliance) — recurring/one-time alliance event. *[Alliance]*
• `/legion_add` — Wonder Contest / Battle of Dawn (every other week). *[Alliance]*

**✏️ Manage — _R4 of the event's scope_ (or Manage Server)**
• `/event_edit` — change an event's name, time, duration, or scope. *[scope of the event]*
• `/event_remove` — delete an event. *[scope of the event]*

**👀 Look up — _anyone who can see the event_**
Replies are **private to you** and only show what your roles allow.
• `/event_list` · `/next` · `/today` · `/week`
• **My Alliance Events** button — your alliance's today + tomorrow.

**ℹ️ Notes**
• **World Campaign** runs **4 hours** — alliance events for it default to a 4h window.
• The board shows **server-wide** events publicly; alliance events stay private (use the button).
• This channel auto-clears daily at 00:00 UTC — only this board message persists."""
