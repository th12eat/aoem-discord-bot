"""Catherine — AoEM event-management Discord bot.

Slash-command based (required for ephemeral replies + no channel spam).

Events carry a SCOPE: "server" (pings @eRa8, any R4 may manage) or an alliance
key WC1/AGC/REU/MyT (pings that alliance's member role, only that alliance's R4
may manage). Manage-Server is always a safety hatch.

Admin:
  /config             server @eRa8 role + board channel
  /config_alliance    register an alliance's R4 role + member role
  /event_add          generic event (scope, once/daily/weekly/every-other, UTC, duration)
  /server_event_add   server "opening soon" event (date range, pings everyone)
  /alliance_event_add alliance leadership event (specific date/time)
  /legion_add         WC/BoD legion event (every-other-week, Sat/Sun, fixed times)
  /kvk_add            multi-day KvK; stages auto-mapped from a start date
  /series_setup       seed rolling weekly server events (only next occ live; time
                      TBD = no ping until set; Imperial Showdown skips TME weeks)
  /event_edit         edit name / time / duration / scope
  /event_remove       delete an event
Member (ephemeral, scoped to what the viewer may see):
  /event_list /next /today /week

Background:
  - scheduler alerts the scope's role at T-1h and at start; the 1h alert is
    deleted when the start alert fires, and the start alert self-deletes after
    the event's duration (default 60 min). KvK stages alert at each stage start
    (no T-1h, no auto-delete) and carry the stage's end + actionable info.
  - #event-scheduler board auto-updates: today's + tomorrow's events, rolling
    over at UTC midnight (Catherine-only writes). Board buttons (all ephemeral):
    My Alliance Events, Changelog, How to use.
  - daily clear: at 00:00 UTC the board channel is purged of everything except
    the board message, then the board is re-posted (needs Manage Messages).

All times stored + entered in UTC; shown via Discord dynamic timestamps.
"""

import os
import uuid
import logging
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

import store
import scheduling as sched
import kvk
import catalog
import series as series_mod
import docs
from alliances import ALLIANCES, SERVER_SCOPE, SCOPES, scope_label, scope_display
from helpers import (ts, ts_both, describe_schedule, can_admin_scope,
                     ping_role_id, is_any_r4, member_alliances, r4_alliances)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-8s %(name)s: %(message)s")
log = logging.getLogger("catherine")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True   # for member-role checks + future DM-by-role
bot = commands.Bot(command_prefix="!", intents=intents)

_fired: set[str] = set()
# live alert bookkeeping (in-memory; transient alerts, fine to reset on restart).
#   _alert_1h[occ_key]  = message id of the "in 1 hour" alert (deleted when NOW fires)
#   _alert_now[occ_key] = (channel_id, message_id, expire_dt) for the "starting now"
#                         alert (deleted once the event's duration elapses)
_alert_1h: dict[str, int] = {}
_alert_now: dict[str, tuple[int, int, datetime]] = {}


def _event_duration_min(e: dict) -> int:
    """Event duration in minutes; default 60. KvK stages use their own spans."""
    try:
        return int(e.get("duration", 60))
    except (TypeError, ValueError):
        return 60

# scope choices reused by /event_add and /config_alliance
_SCOPE_CHOICES = [app_commands.Choice(name=scope_display(s), value=s) for s in SCOPES]
_ALLIANCE_CHOICES = [app_commands.Choice(name=f"{v[0]} ({k})", value=k)
                     for k, v in ALLIANCES.items()]


@bot.event
async def on_ready():
    log.info("Logged in as %s (id: %s)", bot.user, bot.user.id)
    # register the persistent board button so clicks work after a restart
    if not getattr(bot, "_board_view_added", False):
        bot.add_view(BoardView())
        bot._board_view_added = True
    try:
        synced = await bot.tree.sync()
        log.info("Synced %d slash command(s).", len(synced))
    except Exception as e:  # noqa: BLE001
        log.error("Slash sync failed: %s", e)
    if not scheduler_tick.is_running():
        scheduler_tick.start()
    if not board_refresh.is_running():
        board_refresh.start()
    if not daily_clear.is_running():
        daily_clear.start()
    # one-time housekeeping on startup: drop any events that concluded while the
    # bot was down, so nothing stale lingers in the log until the next rollover.
    for guild in bot.guilds:
        purge_completed(guild.id)
    log.info("Ready.")


# ── /config ──────────────────────────────────────────────────────────────────
@bot.tree.command(name="config", description="Set the @eRa8 server member role and board channel.")
@app_commands.describe(server_member_role="@eRa8 — pinged for server-wide events",
                       board_channel="Channel for the daily board (e.g. #event-scheduler)")
async def config_cmd(interaction: discord.Interaction,
                     server_member_role: discord.Role | None = None,
                     board_channel: discord.TextChannel | None = None):
    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message(
            "You need **Manage Server** to change configuration.", ephemeral=True)
    store.set_guild_config(
        interaction.guild_id,
        server_member_role_id=server_member_role.id if server_member_role else None,
        board_channel_id=board_channel.id if board_channel else None,
    )
    cfg = store.guild_config(interaction.guild_id)
    smr = cfg.get("server_member_role_id")
    bc = cfg.get("board_channel_id")
    await interaction.response.send_message(
        "✅ Config updated.\n"
        f"**@eRa8 role:** {('<@&'+str(smr)+'>') if smr else '—'}\n"
        f"**Board channel:** {('<#'+str(bc)+'>') if bc else '—'}",
        ephemeral=True)


# ── /config_alliance ─────────────────────────────────────────────────────────
@bot.tree.command(name="config_alliance", description="Register an alliance's R4 + member roles.")
@app_commands.describe(alliance="Which alliance",
                       r4_role="That alliance's R4 role (may manage its events)",
                       member_role="That alliance's member role (pinged / may view)")
@app_commands.choices(alliance=_ALLIANCE_CHOICES)
async def config_alliance(interaction: discord.Interaction,
                          alliance: app_commands.Choice[str],
                          r4_role: discord.Role,
                          member_role: discord.Role):
    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message(
            "You need **Manage Server** to change configuration.", ephemeral=True)
    store.set_alliance_roles(interaction.guild_id, alliance.value, r4_role.id, member_role.id)
    name = ALLIANCES[alliance.value][0]
    await interaction.response.send_message(
        f"✅ **{name} ({alliance.value})** registered.\n"
        f"R4: {r4_role.mention} · Members: {member_role.mention}", ephemeral=True)


# ── /event_add ───────────────────────────────────────────────────────────────
@bot.tree.command(name="event_add", description="Add an event (times in UTC).")
@app_commands.describe(
    name="Event name, e.g. Trojan Turmoil",
    scope="Server-wide or a specific alliance",
    recurrence="How it repeats",
    times="UTC time(s), comma HH:MM — e.g. 03:00,13:00,21:00",
    weekdays="Weekly only: Mon,Tue,Wed,Thu,Fri,Sat,Sun",
    date="One-time date, or every-other-day start date: UTC YYYY-MM-DD",
    duration="Minutes the event runs (default 60)",
)
@app_commands.choices(
    scope=_SCOPE_CHOICES,
    recurrence=[app_commands.Choice(name="One-time", value="once"),
                app_commands.Choice(name="Daily", value="daily"),
                app_commands.Choice(name="Every other day", value="everyother"),
                app_commands.Choice(name="Weekly", value="weekly")],
)
async def event_add(interaction: discord.Interaction,
                    name: str,
                    scope: app_commands.Choice[str],
                    recurrence: app_commands.Choice[str],
                    times: str,
                    weekdays: str | None = None,
                    date: str | None = None,
                    duration: int | None = None):
    if not can_admin_scope(interaction.user, scope.value):
        who = "any R4" if scope.value == SERVER_SCOPE else f"{scope.value} R4"
        return await interaction.response.send_message(
            f"Only {who} can add **{scope_label(scope.value)}** events.", ephemeral=True)

    try:
        time_list = [t.strip() for t in times.split(",") if t.strip()]
        for t in time_list:
            h, m = t.split(":")
            if not (0 <= int(h) < 24 and 0 <= int(m) < 60):
                raise ValueError
        if not time_list:
            raise ValueError
    except ValueError:
        return await interaction.response.send_message(
            "⚠️ `times` must be one or more `HH:MM` (24h UTC), comma-separated.", ephemeral=True)

    rtype = recurrence.value
    schedule: dict = {"type": rtype}
    if rtype == "once":
        if not date:
            return await interaction.response.send_message(
                "⚠️ One-time events need a `date` (YYYY-MM-DD).", ephemeral=True)
        try:
            datetime.fromisoformat(f"{date}T{time_list[0]}")
        except ValueError:
            return await interaction.response.send_message(
                "⚠️ Couldn't parse date/time. Use date `YYYY-MM-DD`.", ephemeral=True)
        schedule["datetime"] = f"{date}T{time_list[0]}"
    elif rtype == "daily":
        schedule["times"] = time_list
    elif rtype == "everyother":
        if not date:
            return await interaction.response.send_message(
                "⚠️ Every-other-day events need a start `date` (YYYY-MM-DD).", ephemeral=True)
        try:
            datetime.fromisoformat(f"{date}T00:00")
        except ValueError:
            return await interaction.response.send_message(
                "⚠️ Couldn't parse the start date. Use `YYYY-MM-DD`.", ephemeral=True)
        schedule["anchor"] = date
        schedule["times"] = time_list
    elif rtype == "weekly":
        names = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
        if not weekdays:
            return await interaction.response.send_message(
                "⚠️ Weekly events need `weekdays` (e.g. Mon,Wed,Fri).", ephemeral=True)
        try:
            days = [names[d.strip().lower()[:3]] for d in weekdays.split(",") if d.strip()]
            if not days:
                raise KeyError
        except KeyError:
            return await interaction.response.send_message(
                "⚠️ `weekdays` must be day names like Mon,Wed,Fri.", ephemeral=True)
        schedule["days"] = sorted(set(days))
        schedule["times"] = time_list

    event = {
        "id": uuid.uuid4().hex[:8],
        "guild_id": str(interaction.guild_id),
        "name": name,
        "scope": scope.value,
        "schedule": schedule,
        "duration": max(1, duration) if duration else 60,
        "created_by": str(interaction.user.id),
    }

    # reject a true duplicate: same name + same scope that ever fires at the same
    # time as an existing one. (Different events at the same time are fine.)
    now = datetime.now(timezone.utc)
    for existing in store.events_for_guild(interaction.guild_id):
        if (existing["name"].strip().lower() == name.strip().lower()
                and existing.get("scope", SERVER_SCOPE) == scope.value):
            clash = sched.schedules_collide(existing, event, now)
            if clash:
                return await interaction.response.send_message(
                    f"⚠️ **{name}** ({scope_label(scope.value)}) already occurs at that time "
                    f"— next clash {ts(clash, 'F')}. Not added (duplicate).", ephemeral=True)

    store.add_event(event)
    await interaction.response.send_message(
        f"✅ Added **{name}** (`{event['id']}`) · [{scope_label(scope.value)}] — "
        f"{describe_schedule(schedule)}", ephemeral=True)
    await refresh_board(interaction.guild)


# ── shared add helper ────────────────────────────────────────────────────────
async def _finalize_add(interaction, event, human):
    """Duplicate-check (same name+scope colliding in time), save, confirm, refresh."""
    now = datetime.now(timezone.utc)
    for existing in store.events_for_guild(interaction.guild_id):
        if (existing["name"].strip().lower() == event["name"].strip().lower()
                and existing.get("scope", SERVER_SCOPE) == event["scope"]
                and existing.get("schedule", {}).get("type") not in ("kvk",)
                and event["schedule"].get("type") not in ("kvk",)):
            clash = sched.schedules_collide(existing, event, now)
            if clash:
                return await interaction.response.send_message(
                    f"⚠️ **{event['name']}** ({scope_label(event['scope'])}) already occurs then "
                    f"— next clash {ts(clash,'F')}. Not added (duplicate).", ephemeral=True)
    store.add_event(event)
    await interaction.response.send_message(
        f"✅ Added **{event['name']}** (`{event['id']}`) · [{scope_label(event['scope'])}] — {human}",
        ephemeral=True)
    await refresh_board(interaction.guild)


def _mk_event(interaction, name, scope, schedule, **extra):
    return {"id": uuid.uuid4().hex[:8], "guild_id": str(interaction.guild_id),
            "name": name, "scope": scope, "schedule": schedule,
            "created_by": str(interaction.user.id), **extra}


# ── /server_event_add — "opening soon", date RANGE, pings everyone ───────────
# Curated names only; for a one-off custom name use /event_add instead.
_SERVER_EVENT_CHOICES = [app_commands.Choice(name=n, value=n) for n in catalog.SERVER_EVENTS]

@bot.tree.command(name="server_event_add", description="Announce a server-wide event opening (date range).")
@app_commands.describe(event="Event", start_date="Opens UTC YYYY-MM-DD",
                       end_date="Closes UTC YYYY-MM-DD")
@app_commands.choices(event=_SERVER_EVENT_CHOICES)
async def server_event_add(interaction: discord.Interaction, event: app_commands.Choice[str],
                           start_date: str, end_date: str):
    if not can_admin_scope(interaction.user, SERVER_SCOPE):
        return await interaction.response.send_message("Only an R4 can add server events.", ephemeral=True)
    name = event.value
    try:
        s = datetime.fromisoformat(f"{start_date}T00:00"); datetime.fromisoformat(f"{end_date}T00:00")
    except ValueError:
        return await interaction.response.send_message("⚠️ Dates must be `YYYY-MM-DD`.", ephemeral=True)
    # alerts fire at the window open; range shown in the message/board
    schedule = {"type": "once", "datetime": f"{start_date}T00:00", "rangeEnd": end_date, "opening": True}
    ev = _mk_event(interaction, name, SERVER_SCOPE, schedule)
    await _finalize_add(interaction, ev, f"opens {start_date} → {end_date} UTC")


# ── /alliance_event_add — leadership actionable, specific date/time ──────────
# Curated names only; for a one-off custom name use /event_add instead.
_ALLI_EVENT_CHOICES = [app_commands.Choice(name=n, value=n) for n in catalog.ALLIANCE_EVENTS]

@bot.tree.command(name="alliance_event_add", description="Add an alliance leadership event (specific time).")
@app_commands.describe(alliance="Which alliance", event="Event",
                       date="UTC YYYY-MM-DD", time="UTC HH:MM", duration="Minutes (default 60)")
@app_commands.choices(alliance=_ALLIANCE_CHOICES, event=_ALLI_EVENT_CHOICES)
async def alliance_event_add(interaction: discord.Interaction, alliance: app_commands.Choice[str],
                             event: app_commands.Choice[str], date: str, time: str,
                             duration: int | None = None):
    if not can_admin_scope(interaction.user, alliance.value):
        return await interaction.response.send_message(
            f"Only {alliance.value} R4 can add {alliance.value} events.", ephemeral=True)
    name = event.value
    try:
        datetime.fromisoformat(f"{date}T{time}")
    except ValueError:
        return await interaction.response.send_message("⚠️ Use date `YYYY-MM-DD` and time `HH:MM`.", ephemeral=True)
    schedule = {"type": "once", "datetime": f"{date}T{time}"}
    dur = duration or catalog.default_duration(name)  # World Campaign → 240 (4h)
    ev = _mk_event(interaction, name, alliance.value, schedule, duration=dur)
    await _finalize_add(interaction, ev, f"{describe_schedule(schedule)} · {dur}min")


# ── /legion_add — WC/BoD, every other week, Sat/Sun, fixed times ─────────────
_LEGION_CHOICES = [app_commands.Choice(name=f"{v} ({k})", value=k) for k, v in catalog.LEGION_EVENTS.items()]
_LEGION_DAY_CHOICES = [app_commands.Choice(name="Saturday", value="5"), app_commands.Choice(name="Sunday", value="6")]
_LEGION_TIME_CHOICES = [app_commands.Choice(name=f"{t} UTC", value=t) for t in catalog.LEGION_TIMES]

@bot.tree.command(name="legion_add", description="Add a legion event (WC/BoD, every other week).")
@app_commands.describe(alliance="Which alliance", event="Wonder Contest or Battle of Dawn",
                       day="Saturday or Sunday", time="UTC time",
                       anchor_date="First occurrence date (UTC YYYY-MM-DD, that Sat/Sun)")
@app_commands.choices(alliance=_ALLIANCE_CHOICES, event=_LEGION_CHOICES,
                      day=_LEGION_DAY_CHOICES, time=_LEGION_TIME_CHOICES)
async def legion_add(interaction: discord.Interaction, alliance: app_commands.Choice[str],
                     event: app_commands.Choice[str], day: app_commands.Choice[str],
                     time: app_commands.Choice[str], anchor_date: str):
    if not can_admin_scope(interaction.user, alliance.value):
        return await interaction.response.send_message(
            f"Only {alliance.value} R4 can add {alliance.value} legion events.", ephemeral=True)
    wd = int(day.value)
    try:
        adt = datetime.fromisoformat(f"{anchor_date}T00:00")
    except ValueError:
        return await interaction.response.send_message("⚠️ `anchor_date` must be `YYYY-MM-DD`.", ephemeral=True)
    if adt.weekday() != wd:
        return await interaction.response.send_message(
            f"⚠️ {anchor_date} isn't a {day.name}. Pick the date of the first {day.name}.", ephemeral=True)
    name = catalog.LEGION_EVENTS[event.value]
    schedule = {"type": "everyotherweek", "anchor": anchor_date, "days": [wd], "times": [time.value]}
    ev = _mk_event(interaction, name, alliance.value, schedule, duration=60, legion=True)
    await _finalize_add(interaction, ev, f"{describe_schedule(schedule)} · pings {alliance.value} (Legion role TBD)")


# ── /kvk_add — multi-day, stages auto-derived from a start date ──────────────
_KVK_CHOICES = [app_commands.Choice(name=lbl, value=k) for k, lbl in kvk.KVK_CHOICES]

@bot.tree.command(name="kvk_add", description="Add a multi-day KvK; stages auto-mapped from the start date.")
@app_commands.describe(event="Which KvK", start_date="UTC start date YYYY-MM-DD")
@app_commands.choices(event=_KVK_CHOICES)
async def kvk_add(interaction: discord.Interaction, event: app_commands.Choice[str], start_date: str):
    if not can_admin_scope(interaction.user, SERVER_SCOPE):
        return await interaction.response.send_message("Only an R4 can add KvK events.", ephemeral=True)
    try:
        datetime.fromisoformat(f"{start_date}T00:00")
    except ValueError:
        return await interaction.response.send_message("⚠️ `start_date` must be `YYYY-MM-DD`.", ephemeral=True)
    short = event.value
    name = kvk.KVK_DEFS[short]["name"]
    schedule = {"type": "kvk", "short": short, "start": f"{start_date}T00:00"}
    ev = _mk_event(interaction, name, SERVER_SCOPE, schedule)
    stages = kvk.compute_stages(short, datetime.fromisoformat(f"{start_date}T00:00").replace(tzinfo=timezone.utc))
    preview = "\n".join(f"• {s['title']} — {ts(s['start'],'D')}" for s in stages)
    # KvK bypasses duplicate-time check (stage-based); add directly.
    store.add_event(ev)
    await interaction.response.send_message(
        f"✅ Added **{name}** (`{ev['id']}`) — {len(stages)} stages:\n{preview}", ephemeral=True)
    await refresh_board(interaction.guild)


# ── weekly series (rolling) ──────────────────────────────────────────────────
#   A series is one persistent event whose single next occurrence rolls forward
#   the moment its day completes (UTC). Time is TBD (no ping) until an R4 sets it
#   via /event_edit — except `fixed` series (Starfall Vein) which pre-fill their
#   known times and ping automatically. Imperial Showdown skips TME invasion
#   Sundays, detected from this guild's KvK event log.
def _tme_skip_predicate(guild_id: int):
    """Return skip(d)->bool that's True on any TME *invasion* day, derived from
    TME KvK events in this guild's log (so Imperial Showdown avoids that Sunday)."""
    tme_starts = []
    for e in store.events_for_guild(guild_id):
        s = e.get("schedule", {})
        if s.get("type") == "kvk" and s.get("short") == "TME":
            try:
                tme_starts.append(datetime.fromisoformat(s["start"]).replace(tzinfo=timezone.utc))
            except (ValueError, KeyError):
                pass

    def skip(d):
        return any(kvk.stage_active_on("TME", st, d, stage_keys={"inv"}) for st in tme_starts)
    return skip


def _seed_series_event(guild_id: int, name: str) -> dict | None:
    """Create the next occurrence of a series (if not already present). Returns
    the event, or None if no future date could be computed."""
    skip = _tme_skip_predicate(guild_id) if catalog.SERIES.get(name, {}).get("skipTme") else None
    today = datetime.now(timezone.utc).date()
    # roll from yesterday so an event *today* is still seeded as the current one
    nxt = series_mod.next_date(name, today - timedelta(days=1), skip=skip)
    if not nxt:
        return None
    ev = {"id": uuid.uuid4().hex[:8], "guild_id": str(guild_id), "name": name,
          "scope": SERVER_SCOPE, "schedule": series_mod.make_occurrence(name, nxt),
          "duration": catalog.SERIES[name].get("duration", 60), "series_auto": True,
          "created_by": "system"}
    store.add_event(ev)
    return ev


@bot.tree.command(name="series_setup", description="Seed the recurring weekly server events (Imperial Showdown, City Clash, …).")
async def series_setup(interaction: discord.Interaction):
    if not can_admin_scope(interaction.user, SERVER_SCOPE):
        return await interaction.response.send_message("Only an R4 can set up series events.", ephemeral=True)
    existing = {e["name"] for e in store.events_for_guild(interaction.guild_id)
                if e.get("schedule", {}).get("type") == "series"}
    added, skipped = [], []
    for name in catalog.SERIES:
        if name in existing:
            skipped.append(name)
            continue
        ev = _seed_series_event(interaction.guild_id, name)
        if ev:
            added.append(f"**{name}** — {describe_schedule(ev['schedule'])}")
    msg = "✅ Series events seeded.\n"
    if added:
        msg += "\n".join(f"• {a}" for a in added)
    if skipped:
        msg += f"\n\n_Already present (unchanged):_ {', '.join(skipped)}"
    if not added and not skipped:
        msg = "No series are defined."
    await interaction.response.send_message(msg, ephemeral=True)
    await refresh_board(interaction.guild)


# ── /event_remove ────────────────────────────────────────────────────────────
def _short_schedule(schedule: dict) -> str:
    """Compact schedule for an autocomplete label (no dynamic timestamps there)."""
    t = schedule["type"]
    times = ",".join(schedule.get("times", []))
    if t == "once":
        return schedule.get("datetime", "?").replace("T", " ") + " UTC"
    if t == "daily":
        return f"daily {times} UTC"
    if t == "everyother":
        return f"every-other-day {times} UTC"
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    if t == "weekly":
        days = "/".join(names[d] for d in schedule.get("days", []))
        return f"{days} {times} UTC"
    if t == "everyotherweek":
        days = "/".join(names[d] for d in schedule.get("days", []))
        return f"EOW {days} {times} UTC"
    if t == "kvk":
        return f"KvK from {schedule.get('start','?')[:10]}"
    if t == "series":
        return f"series {schedule.get('date','?')} " + (f"{times} UTC" if times else "· TBD")
    return times


async def _remove_autocomplete(interaction: discord.Interaction, current: str):
    """Suggest events the user may remove, labeled with schedule + next occurrence
    so same-named events are distinguishable."""
    cur = current.lower()
    now = datetime.now(timezone.utc)
    out = []
    for e in store.events_for_guild(interaction.guild_id):
        scope = e.get("scope", SERVER_SCOPE)
        if not can_admin_scope(interaction.user, scope):
            continue
        if sched.is_completed(e, now):
            continue  # completed events aren't editable/listable
        nxt = sched.next_occurrence(e, now)
        nxt_txt = nxt.strftime("%b %d %H:%M") if nxt else "past"
        # e.g. "[WC1] Trojan Turmoil · Mon/Wed/Fri 19:00 UTC · next Jul 20 19:00"
        label = f"[{scope_label(scope)}] {e['name']} · {_short_schedule(e['schedule'])} · next {nxt_txt}"
        if cur in label.lower() or cur in e["id"]:
            out.append(app_commands.Choice(name=label[:100], value=e["id"]))
    return out[:25]  # Discord caps autocomplete at 25


@bot.tree.command(name="event_remove", description="Delete an event (pick from the list).")
@app_commands.describe(event="Start typing to pick the event to delete")
@app_commands.autocomplete(event=_remove_autocomplete)
async def event_remove(interaction: discord.Interaction, event: str):
    event_id = event.strip()
    ev = next((e for e in store.events_for_guild(interaction.guild_id) if e["id"] == event_id), None)
    if ev is None:
        return await interaction.response.send_message(f"⚠️ No matching event found.", ephemeral=True)
    if not can_admin_scope(interaction.user, ev.get("scope", SERVER_SCOPE)):
        return await interaction.response.send_message(
            f"You can't remove a **{scope_label(ev.get('scope', SERVER_SCOPE))}** event.", ephemeral=True)
    store.remove_event(event_id, interaction.guild_id)
    await interaction.response.send_message(f"🗑️ Removed **{ev['name']}** (`{event_id}`).", ephemeral=True)
    await refresh_board(interaction.guild)


# ── /event_edit ──────────────────────────────────────────────────────────────
@bot.tree.command(name="event_edit", description="Edit an event: name, time, duration, or scope.")
@app_commands.describe(event="Pick the event to edit",
                       name="New name (optional)",
                       time="New UTC time HH:MM — for recurring events (optional)",
                       datetime_="New UTC date+time YYYY-MM-DDTHH:MM — for one-time/KvK start (optional)",
                       duration="New duration in minutes (optional)",
                       scope="New scope (optional)")
@app_commands.autocomplete(event=_remove_autocomplete)  # same picker: events you may admin
@app_commands.choices(scope=_SCOPE_CHOICES)
async def event_edit(interaction: discord.Interaction, event: str,
                     name: str | None = None, time: str | None = None,
                     datetime_: str | None = None, duration: int | None = None,
                     scope: app_commands.Choice[str] | None = None):
    ev = next((e for e in store.events_for_guild(interaction.guild_id) if e["id"] == event.strip()), None)
    if ev is None:
        return await interaction.response.send_message("⚠️ No matching event found.", ephemeral=True)
    if not can_admin_scope(interaction.user, ev.get("scope", SERVER_SCOPE)):
        return await interaction.response.send_message("You can't edit that event.", ephemeral=True)
    # a completed event can't be edited (a KvK stays editable while running)
    if sched.is_completed(ev, datetime.now(timezone.utc)):
        return await interaction.response.send_message(
            f"🔒 **{ev['name']}** has already completed — it can't be edited.", ephemeral=True)
    # changing scope requires admin over the NEW scope too
    if scope and not can_admin_scope(interaction.user, scope.value):
        return await interaction.response.send_message(
            f"You can't move it to **{scope_label(scope.value)}** (not your scope).", ephemeral=True)

    changes: dict = {}
    stype = ev.get("schedule", {}).get("type")
    if name:
        changes["name"] = name
    if duration is not None:
        changes["duration"] = max(1, duration)
    if scope:
        changes["scope"] = scope.value
    if time:
        # accept one or more comma-separated HH:MM (a series occurrence can have
        # several, e.g. Starfall Vein's four windows)
        tlist = [x.strip() for x in time.split(",") if x.strip()]
        try:
            for x in tlist:
                h, m = x.split(":");  assert 0 <= int(h) < 24 and 0 <= int(m) < 60
            assert tlist
        except (ValueError, AssertionError):
            return await interaction.response.send_message("⚠️ `time` must be one or more `HH:MM` (24h UTC), comma-separated.", ephemeral=True)
        if stype in ("daily", "weekly", "everyother", "everyotherweek", "series"):
            changes["schedule"] = {"times": tlist}
        else:
            return await interaction.response.send_message(
                "⚠️ This event isn't recurring — use `datetime_` to move it.", ephemeral=True)
    if datetime_:
        try:
            datetime.fromisoformat(datetime_)
        except ValueError:
            return await interaction.response.send_message("⚠️ `datetime_` must be `YYYY-MM-DDTHH:MM`.", ephemeral=True)
        if stype == "once":
            changes.setdefault("schedule", {})["datetime"] = datetime_
        elif stype == "kvk":
            changes.setdefault("schedule", {})["start"] = datetime_
        else:
            return await interaction.response.send_message(
                "⚠️ This event is recurring — use `time` to change its time.", ephemeral=True)
    if not changes:
        return await interaction.response.send_message("Nothing to change — pass at least one field.", ephemeral=True)

    updated = store.update_event(event.strip(), interaction.guild_id, changes)
    await interaction.response.send_message(
        f"✏️ Updated **{updated['name']}** (`{updated['id']}`) — {describe_schedule(updated['schedule'])}"
        + (f" · {updated.get('duration')}min" if updated.get('duration') else ""),
        ephemeral=True)
    await refresh_board(interaction.guild)


# ── visibility filter for a viewer ───────────────────────────────────────────
def _personal_scopes(member: discord.Member) -> set[str]:
    """The scopes that PERTAIN TO this member: always the server, plus each
    alliance they're in (by member role) or an R4 of. This is derived from their
    roles — so a WorldClass member sees Server + WC1, nothing else. (Manage-Server
    users are treated the same here; the personal lists are about relevance, not
    permissions — admins use the edit/remove picker for cross-scope management.)"""
    return {SERVER_SCOPE} | member_alliances(member) | r4_alliances(member)


def _personal_events(member: discord.Member, drop_completed: bool = True) -> list[dict]:
    """Events relevant to this member: their server + own-alliance scopes, with
    completed events dropped (nothing lingers after it's over)."""
    now = datetime.now(timezone.utc)
    scopes = _personal_scopes(member)
    out = []
    for e in store.events_for_guild(member.guild.id):
        if e.get("scope", SERVER_SCOPE) not in scopes:
            continue
        if drop_completed and sched.is_completed(e, now):
            continue
        out.append(e)
    return out


# ── member queries (ephemeral) ───────────────────────────────────────────────
@bot.tree.command(name="event_list", description="List your events (server + your alliance).")
async def event_list(interaction: discord.Interaction):
    evs = _personal_events(interaction.user)
    if not evs:
        return await interaction.response.send_message("No events for you right now.", ephemeral=True)
    scopes = ", ".join(scope_label(s) for s in sorted(_personal_scopes(interaction.user)))
    lines = [f"• [{scope_label(e.get('scope', SERVER_SCOPE))}] **{e['name']}** (`{e['id']}`) — "
             f"{describe_schedule(e['schedule'])}" for e in evs]
    await interaction.response.send_message(
        f"📋 **Your events** ({scopes})\n" + "\n".join(lines), ephemeral=True)


@bot.tree.command(name="next", description="Your next upcoming event.")
async def next_cmd(interaction: discord.Interaction):
    now = datetime.now(timezone.utc)
    upcoming = []
    for e in _personal_events(interaction.user):
        nxt = sched.next_occurrence(e, now)
        if nxt:
            upcoming.append((nxt, e))
    if not upcoming:
        return await interaction.response.send_message("No upcoming events.", ephemeral=True)
    upcoming.sort(key=lambda p: p[0])
    dt, e = upcoming[0]
    await interaction.response.send_message(
        f"⏭️ Next: [{scope_label(e.get('scope', SERVER_SCOPE))}] **{e['name']}** — {ts_both(dt)}",
        ephemeral=True)


@bot.tree.command(name="today", description="Today's events you can see (UTC).")
async def today_cmd(interaction: discord.Interaction):
    await _list_window(interaction, *sched.utc_day_bounds(datetime.now(timezone.utc)), "Today")


@bot.tree.command(name="week", description="This week's events you can see (UTC).")
async def week_cmd(interaction: discord.Interaction):
    await _list_window(interaction, *sched.utc_week_bounds(datetime.now(timezone.utc)), "This week")


async def _list_window(interaction, start, end, label):
    evs = _personal_events(interaction.user)
    pairs = sched.occurrences_for_events(evs, start, end)
    if not pairs:
        return await interaction.response.send_message(f"No events {label.lower()}.", ephemeral=True)
    lines = [f"• {ts(dt, 't')} — [{scope_label(e.get('scope', SERVER_SCOPE))}] **{e['name']}**"
             for dt, e in pairs]
    await interaction.response.send_message(f"**{label} (UTC day)**\n" + "\n".join(lines), ephemeral=True)


# ── scheduler: alert at T-1h and at start, with a self-cleaning lifecycle ────
#   • the "in 1 hour" alert is DELETED the moment the "starting now" alert posts
#   • the "starting now" alert is DELETED once the event's duration elapses
#   • KvK stage alerts get no T-1h pre-alert (multi-day → too noisy) and don't
#     auto-delete (a stage lasts days); they carry the stage's end info instead
@tasks.loop(minutes=1)
async def scheduler_tick():
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    # 1) expire any "starting now" alerts whose duration has elapsed
    for okey, (cid, mid, expire) in list(_alert_now.items()):
        if now >= expire:
            ch = bot.get_channel(cid)
            if ch:
                try:
                    msg = await ch.fetch_message(mid)
                    await msg.delete()
                except discord.DiscordException:
                    pass
            _alert_now.pop(okey, None)

    for guild in bot.guilds:
        cfg = store.guild_config(guild.id)
        chan_id = cfg.get("board_channel_id")
        channel = guild.get_channel(chan_id) if chan_id else None
        if channel is None:
            continue
        for e in store.events_for_guild(guild.id):
            scope = e.get("scope", SERVER_SCOPE)
            role_id = ping_role_id(guild.id, scope)
            if not role_id:
                continue
            is_kvk = e.get("schedule", {}).get("type") == "kvk"
            # KvK: start-only alerts; others: 1h + now
            offsets = ((0, "starting now"),) if is_kvk else ((60, "in 1 hour"), (0, "starting now"))
            for offset, when in offsets:
                target = now + timedelta(minutes=offset)
                for dt in sched.occurrences_between(e, target, target):
                    okey = f"{e['id']}|{dt.isoformat()}"
                    fkey = f"{okey}|{offset}"
                    if fkey in _fired:
                        continue
                    _fired.add(fkey)
                    text = _alert_text(e, scope, role_id, when, dt, is_kvk)
                    try:
                        msg = await channel.send(text)
                    except discord.DiscordException as ex:
                        log.error("alert send failed: %s", ex)
                        continue
                    if offset == 60:
                        _alert_1h[okey] = msg.id
                    else:
                        # NOW fired → delete the earlier 1h alert if present
                        old = _alert_1h.pop(okey, None)
                        if old:
                            try:
                                m = await channel.fetch_message(old)
                                await m.delete()
                            except discord.DiscordException:
                                pass
                        # schedule this NOW alert to self-delete after duration
                        # (KvK stage alerts persist — no expiry entry)
                        if not is_kvk:
                            expire = dt + timedelta(minutes=_event_duration_min(e))
                            _alert_now[okey] = (channel.id, msg.id, expire)
    if len(_fired) > 5000:
        _fired.clear()


def _alert_text(e, scope, role_id, when, dt, is_kvk):
    """Compose the alert message. KvK alerts name the current stage + its end."""
    if is_kvk:
        short = e["schedule"]["short"]
        kstart = datetime.fromisoformat(e["schedule"]["start"]).replace(tzinfo=timezone.utc)
        stage = next((s for s in kvk.compute_stages(short, kstart)
                      if s["start"] == dt), None)
        if stage:
            title = stage["title"]
            parent = f" · {stage['parent']}" if stage.get("parent") else ""
            act = f"\n▸ {stage['actionable']}" if stage.get("actionable") else ""
            return (f"<@&{role_id}> **{e['name']}** — stage **{title}**{parent} starts {ts_both(dt)}\n"
                    f"_{stage.get('summary','')}_ · ends {ts(stage['end'], 'F')}{act}")
    return f"<@&{role_id}> **{e['name']}** ({scope_label(scope)}) {when} — {ts_both(dt)}"


# ── "My Alliance Events" button (persistent) ─────────────────────────────────
class BoardView(discord.ui.View):
    """Attached to the public board. The board itself shows only server-wide
    events; this button reveals the clicker's OWN alliance events, ephemerally."""

    def __init__(self):
        super().__init__(timeout=None)  # persistent across restarts

    @discord.ui.button(label="My Alliance Events", emoji="🔎",
                       style=discord.ButtonStyle.primary,
                       custom_id="board:my_alliance_events")
    async def my_events(self, interaction: discord.Interaction, button: discord.ui.Button):
        from helpers import member_alliances, r4_alliances
        keys = member_alliances(interaction.user) | r4_alliances(interaction.user)
        if not keys:
            return await interaction.response.send_message(
                "You're not in an alliance I have events for. Server-wide events are on the board above.",
                ephemeral=True)
        now = datetime.now(timezone.utc)
        d0s, d0e = sched.utc_day_bounds(now)
        d1s, d1e = sched.utc_day_bounds(now + timedelta(days=1))
        evs = [e for e in store.events_for_guild(interaction.guild_id)
               if e.get("scope") in keys]

        def block(title, start, end):
            pairs = sched.occurrences_for_events(evs, start, end)
            if not pairs:
                return f"__{title}__\n*(none)*"
            rows = "\n".join(
                f"• {ts(dt,'t')} — [{scope_label(e.get('scope', SERVER_SCOPE))}] **{e['name']}** ({ts(dt,'R')})"
                for dt, e in pairs)
            return f"__{title}__\n{rows}"

        names = ", ".join(sorted(keys))
        await interaction.response.send_message(
            f"🔎 **Your alliance events** ({names})\n\n"
            f"{block('Today (UTC)', d0s, d0e)}\n\n"
            f"{block('Tomorrow (UTC)', d1s, d1e)}",
            ephemeral=True)

    @discord.ui.button(label="Changelog", emoji="📜",
                       style=discord.ButtonStyle.secondary,
                       custom_id="board:changelog")
    async def changelog(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(docs.CHANGELOG, ephemeral=True)

    @discord.ui.button(label="How to use", emoji="❓",
                       style=discord.ButtonStyle.secondary,
                       custom_id="board:howto")
    async def howto(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(docs.HOWTO, ephemeral=True)


def _tbd_series_on(evs: list[dict], day_start: datetime) -> list[dict]:
    """Series events that land on `day_start`'s UTC date but have no times set
    (so occurrences_between yields nothing) — shown on the board as 'time TBD'."""
    d = day_start.date()
    out = []
    for e in evs:
        s = e.get("schedule", {})
        if s.get("type") == "series" and not s.get("times"):
            try:
                if datetime.fromisoformat(s["date"]).date() == d:
                    out.append(e)
            except (ValueError, KeyError):
                pass
    return out


# ── board channel: server-wide events only (alliance events via the button) ──
async def refresh_board(guild: discord.Guild):
    cfg = store.guild_config(guild.id)
    chan_id = cfg.get("board_channel_id")
    channel = guild.get_channel(chan_id) if chan_id else None
    if channel is None:
        return
    now = datetime.now(timezone.utc)
    d0s, d0e = sched.utc_day_bounds(now)
    d1s, d1e = sched.utc_day_bounds(now + timedelta(days=1))
    # board is PUBLIC → show only server-wide events; alliance events are private
    evs = [e for e in store.events_for_guild(guild.id)
           if e.get("scope", SERVER_SCOPE) == SERVER_SCOPE]

    def block(title, start, end):
        pairs = sched.occurrences_for_events(evs, start, end)
        rows = [f"• {ts(dt, 't')} — **{e['name']}** ({ts(dt,'R')})" for dt, e in pairs]
        # TBD-time series land on their day but have no fire-times: show them as a
        # "time TBD" note so people know they're happening (they just aren't pinged).
        rows += [f"• ⏳ **{e['name']}** — _time TBD (set it to enable alerts)_"
                 for e in _tbd_series_on(evs, start)]
        if not rows:
            return f"__{title}__\n*(none)*"
        return f"__{title}__\n" + "\n".join(rows)

    content = (f"📅 **Event Board** (server-wide) — updated {ts(now, 'F')}\n\n"
               f"{block('Today (UTC)', d0s, d0e)}\n\n"
               f"{block('Tomorrow (UTC)', d1s, d1e)}\n\n"
               f"*In an alliance? Tap **My Alliance Events** below for your own schedule.*")

    msg_id = cfg.get("board_message_id")
    try:
        if msg_id:
            try:
                msg = await channel.fetch_message(msg_id)
                await msg.edit(content=content, view=BoardView())
                return
            except discord.NotFound:
                pass
        sent = await channel.send(content, view=BoardView())
        store.set_guild_config(guild.id, board_message_id=sent.id)
    except discord.DiscordException as ex:
        log.error("board refresh failed: %s", ex)


@tasks.loop(minutes=10)
async def board_refresh():
    for guild in bot.guilds:
        await refresh_board(guild)


# ── daily board-channel clear at UTC midnight ────────────────────────────────
#   Wipes #event-scheduler each UTC day so only the persistent board message (the
#   one with the buttons) remains. Transient alerts + any chatter are removed.
#   Runs once per UTC date (tracked in _last_clear_date); the board is re-posted
#   fresh afterward so its buttons keep working.
_last_clear_date = None  # date object of the last successful clear


async def clear_board_channel(guild: discord.Guild):
    """Delete every message in the board channel except the board message, then
    re-render the board so today's/tomorrow's events + buttons are present."""
    cfg = store.guild_config(guild.id)
    chan_id = cfg.get("board_channel_id")
    channel = guild.get_channel(chan_id) if chan_id else None
    if channel is None:
        return
    keep_id = cfg.get("board_message_id")

    def _keep(m: discord.Message) -> bool:
        return m.id != keep_id  # purge everything but the board message

    try:
        # bulk delete handles <14-day-old messages; a daily clear never leaves
        # anything older, but fall back to per-message delete just in case.
        await channel.purge(limit=None, check=_keep, bulk=True)
    except discord.HTTPException as ex:
        log.warning("board channel purge (bulk) failed, trying per-message: %s", ex)
        try:
            async for m in channel.history(limit=None):
                if m.id != keep_id:
                    try:
                        await m.delete()
                    except discord.DiscordException:
                        pass
        except discord.DiscordException as ex2:
            log.error("board channel clear failed: %s", ex2)
    # re-post/refresh the board so it (and its buttons) survive the wipe
    await refresh_board(guild)


@tasks.loop(minutes=1)
async def daily_clear():
    global _last_clear_date
    today = datetime.now(timezone.utc).date()
    if _last_clear_date == today:
        return
    # first tick after (re)start seeds the marker without clearing, so a restart
    # mid-day doesn't wipe the channel; the wipe happens at the next UTC rollover.
    if _last_clear_date is None:
        _last_clear_date = today
        return
    _last_clear_date = today
    for guild in bot.guilds:
        roll_series(guild.id)          # advance any series whose day has passed
        purge_completed(guild.id)      # drop events that have fully concluded
        await clear_board_channel(guild)


def purge_completed(guild_id: int):
    """Delete events that have fully completed — nothing is stored or listed after
    it's over. Recurring/series events never complete, so they're never purged."""
    now = datetime.now(timezone.utc)
    for e in list(store.events_for_guild(guild_id)):
        if sched.is_completed(e, now):
            store.remove_event(e["id"], guild_id)
            log.info("purged completed event %s (%s)", e.get("name"), e.get("id"))


def roll_series(guild_id: int):
    """Advance each series event whose stored date is now in the past to its next
    matching weekday, resetting the time (fixed series re-fill; others go TBD).
    Runs at the UTC-midnight rollover so the log only ever holds the next one."""
    today = datetime.now(timezone.utc).date()
    for e in store.events_for_guild(guild_id):
        s = e.get("schedule", {})
        if s.get("type") != "series":
            continue
        try:
            occ = datetime.fromisoformat(s["date"]).date()
        except (ValueError, KeyError):
            continue
        if occ >= today:
            continue  # still upcoming (or today) — leave it
        name = s.get("series")
        skip = _tme_skip_predicate(guild_id) if catalog.SERIES.get(name, {}).get("skipTme") else None
        nxt = series_mod.next_date(name, today - timedelta(days=1), skip=skip)
        if not nxt:
            continue
        store.update_event(e["id"], guild_id,
                           {"schedule": series_mod.make_occurrence(name, nxt)})


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    await ctx.send(f"🏓 Pong! {round(bot.latency * 1000)} ms")


def main():
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and add it.")
    bot.run(TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
