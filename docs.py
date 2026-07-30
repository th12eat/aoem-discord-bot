"""User-facing help + changelog text for Catherine's board buttons.

Kept here (not in bot.py) so the prose is easy to edit without touching command
logic. Both strings are shown ephemerally when a board button is tapped.

VERSION is the human release tag; CHANGELOG lists broad, user-visible changes per
release (not every commit). HOWTO documents every command, its SCOPE (server vs
alliance vs anyone), and which ROLES may use it.
"""

VERSION = "1.8.0"

CHANGELOG = f"""📜 **Catherine — v{VERSION}**
_Broad, user-visible changes per release._

**v1.8.0 — Behemoth invasion alerts**
• **Behemoth Conquest** now pings the **Attack/Defense invasions** — **1 hour before**
  and **at** each 90-min window. When both servers pick the same time the windows
  merge into one **⚔️🛡️ Attack & Defense** alert; otherwise separate ⚔️ Attack /
  🛡️ Defense pings fire. Each says where to be — **WC1** on both servers (attack +
  defend), **AGC/REU/MyT** on our server rallying the Elephant — plus how to score.
• The **Attack/Defense stage-start (Day-4) notice** now lists the locked invasion
  time(s) and the same who-goes-where plan; invasions also show on the board.
• Set the times with `/event_edit … inv_atk:HH:MM inv_def:HH:MM` (defaults to the
  dashboard's Sat 19:00 for both → combined).

**v1.7.1 — Legion weekly-reset fix**
• **Fixed:** the Monday 00:00 UTC legion role reset was skipped whenever the bot
  restarted on a Monday (or wasn't running at the exact rollover), leaving last
  week's slot roles (e.g. `sat_0100`) tagged on people. The reset now runs once
  per week reliably across restarts (tracked with a persisted week marker).
• New **`/legion_reset`** (R4) clears all slot roles + roster on demand — handy to
  clean up stale tags immediately or between weeks.

**v1.7.0 — Trial of Scion window alerts**
• **Behemoth Conquest** now pings the **Trial of Scion** windows automatically —
  four 30-min windows/day through **Beast Taming**. Each ping says which server it's
  on (🛡️ **ours #008** vs ⚔️ **opponent**), the 30-min duration, and what to do
  (kill Scions for runestones + eliminations, then donate). They also show on the
  board on Beast-Taming days and self-clear after each window.
• The host rotation defaults to the dashboard's best guess. Once the real first
  window is confirmed in-game, flip the whole rotation with
  `/event_edit … scion_first:<Our server | Opponent server>`.

**v1.6.0 — Legions, City Clash targets, KvK-stage fix**
• **Legions are back, server-wide:** `/legion_seed` declares this weekend's event
  and the bot alternates **Wonder Contest ↔ Battle of Dawn** every weekend forever
  (`/legion_unseed` for the rare exceptions). `/legion_slot` binds a ping role to
  each of the six slots (Sat/Sun × 01:00/11:00/19:00 UTC); the bot pings that slot's
  role at its time with the weekend's event. `/legion_status` shows the setup.
• **Legion roster management:** `/legion_fill` takes a **mix of discord @mentions/IDs
  and plain non-discord names** — discord users get the slot role, non-discord names
  are stored on a roster under your alliance. `/legion_remove` removes anyone (discord
  or name); `/legion_list` shows a slot grouped by alliance (non-discord marked ◇).
  Roles + roster **auto-empty Monday 00:00 UTC**; refill Thu/Fri. Slots are pinged
  **1h before and at start** (40-min window) and the start ping lists the full roster
  by alliance. (Needs **Manage Roles** + the bot's role above the slot roles.)
• **City Clash** alerts now include the planned **city → alliance takeover list**.
• **Fixed:** KvK stage instructions (e.g. Power Boost) were vanishing at the
  00:00 UTC board wipe — the current stage is now re-posted after the daily clear.

**v1.5.0 — Richer KvK alerts + no duplicate popups**
• KvK stage alerts now spell out that day's **exact point-scoring** and a
  **prep-ahead** note for the next stage (e.g. Forging Gear: craft gear, kill
  tribes, pre-gather RSS for Enhancing Buildings, and sign up for Chief Priest).
• Board buttons (Changelog / How to use / My Alliance Events) no longer stack:
  pressing one again **replaces** your previous popup instead of adding another.

**v1.4.0 — Personal lists + completed-event cleanup**
• `/event_list`, `/next`, `/today`, `/week` are now **personal** — they show only
  the events that pertain to *you* (the server + your own alliance, read from your
  roles), instead of everything you could see.
• **Completed events are gone for good:** once an event fully concludes it can no
  longer be edited, stops appearing in any list/picker, and is auto-deleted at the
  next UTC-midnight rollover (and on bot restart). A **KvK stays editable while
  it's running** — it only locks once its final stage ends.

**v1.3.0 — Recurring weekly series**
• `/series_setup` seeds the rolling weekly server events: **Imperial Showdown**
  (Sundays, skips TME weeks), **City Clash** (Saturdays), **World Campaign**
  (Wed & Sun, 4h), **Starfall Vein** (Wednesdays, fixed 02/05/12/20 UTC).
• Only the **next** occurrence is ever live — it rolls forward automatically once
  its day ends, so the dropdowns/log never fill with future dates.
• Series show on the board even before a time is set, but **don't ping until an
  R4 sets the time** via `/event_edit` (Starfall's fixed times ping on their own).
• `/event_add` gained a **duration** field; the redundant **Custom…** option was
  removed from `/server_event_add` and `/alliance_event_add` — use `/event_add`
  for one-off custom names.

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
• `/event_add` (scope: Server-wide) — recurring/one-time server event (+ duration). *[Server]*
• `/kvk_add` — multi-day KvK (TME/GE/BC/PC/DD); stages auto-derived from the start date. *[Server]*
• `/series_setup` — seed the rolling weekly events (Imperial Showdown, City Clash,
  World Campaign, Starfall Vein). Run once; they auto-advance each week. *[Server]*

**⚔️ Legions (Wonder Contest / Battle of Dawn) — _any R4_, server-wide**
• `/legion_slot` — bind a ping role to a time-slot (Sat/Sun × 01:00/11:00/19:00 UTC).
• `/legion_seed` — declare **this weekend's** event; it alternates WC↔BoD every weekend.
• `/legion_unseed` — stop pings (for the ~quarterly schedule exceptions).
• `/legion_status` — show the current seed + which slot roles are set.
• `/legion_fill` — add members to a slot. Paste a **mix of @mentions/IDs (discord)
  and plain names (non-discord)**; discord users get the slot role, non-discord
  names go on a roster under your alliance. Everyone is moved off any other slot.
• `/legion_remove` — remove members (discord + non-discord names) from all slots.
• `/legion_list` — list a slot's members grouped by alliance; filter by `alliance`
  and/or `slot`. Non-discord names are marked ◇.
• `/legion_reset` — clear all slot roles + roster now (same as the Monday auto-reset).
Roles + roster auto-empty **Monday 00:00 UTC**; refill Thu/Fri. The bot pings each
slot **1h before and at start** (40-min window) and the start ping lists the full
roster (all 4 alliances). Needs **Manage Roles** + the bot's role above the slots.

**🏰 Alliance events — _that alliance's R4 only_ (or Manage Server)**
Pings that alliance's member role; only its R4 may create/edit.
• `/alliance_event_add` — leadership actionable at a specific date/time. *[Alliance]*
• `/event_add` (scope: your alliance) — recurring/one-time alliance event. *[Alliance]*

**✏️ Manage — _R4 of the event's scope_ (or Manage Server)**
• `/event_edit` — change an event's name, time, duration, or scope. For **Behemoth
  Conquest**, `scion_first` flips which server hosts the first daily Trial of Scion
  window, and `inv_atk` / `inv_def` set the invasion Attack/Defense times (HH:MM UTC;
  same time → one combined Attack & Defense alert). *[scope of the event]*
• `/event_remove` — delete an event. *[scope of the event]*

**👀 Look up — _personal to you_**
Replies are **private to you** and scoped to *your* events — the server plus your
own alliance, read from your roles (a WorldClass member sees Server + WC1 only).
Completed events never appear.
• `/event_list` · `/next` · `/today` · `/week`
• **My Alliance Events** button — your alliance's today + tomorrow.

**🔁 Weekly series (rolling)**
Seeded by `/series_setup`; each shows the **next** date and advances automatically:
• **Imperial Showdown** — Sundays, except TME weeks. • **City Clash** — Saturdays.
• **World Campaign** — Wednesdays & Sundays (4h). • **Starfall Vein** — Wednesdays (fixed times).
Most have a **variable time**: they appear on the board as "time TBD" and **won't
ping** until an R4 sets the time with `/event_edit` (Starfall pings automatically).

**ℹ️ Notes**
• **World Campaign** runs **4 hours** — its events default to a 4h window.
• For a one-off with a **custom name**, use `/event_add` (Custom… was removed from the curated commands).
• The board shows **server-wide** events publicly; alliance events stay private (use the button).
• This channel auto-clears daily at 00:00 UTC — only this board message persists."""
