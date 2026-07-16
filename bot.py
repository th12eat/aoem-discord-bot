"""Catherine — AoEM event-management Discord bot.

Slash-command based (required for ephemeral replies + no channel spam).

Events carry a SCOPE: "server" (pings @eRa8, any R4 may manage) or an alliance
key WC1/AGC/REU/MyT (pings that alliance's member role, only that alliance's R4
may manage). Manage-Server is always a safety hatch.

Admin:
  /config           set the @eRa8 server member role + board channel
  /config_alliance  register an alliance's R4 role + member role
  /event_add        add an event (scope, once/daily/weekly, UTC times)
  /event_remove     remove an event by id
Member (ephemeral replies, scoped to what the viewer may see):
  /event_list /next /today /week

Background:
  - scheduler pings the scope's role at T-1h and at start
  - #event-scheduler board auto-updates: today's + tomorrow's events, labeled by
    scope, rolling over at UTC midnight (Catherine-only writes)

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
from alliances import ALLIANCES, SERVER_SCOPE, SCOPES, scope_label, scope_display
from helpers import (ts, ts_both, describe_schedule, can_admin_scope, can_view_scope,
                     ping_role_id, is_any_r4)

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
                    date: str | None = None):
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
        "created_by": str(interaction.user.id),
    }
    store.add_event(event)
    await interaction.response.send_message(
        f"✅ Added **{name}** (`{event['id']}`) · [{scope_label(scope.value)}] — "
        f"{describe_schedule(schedule)}", ephemeral=True)
    await refresh_board(interaction.guild)


# ── /event_remove ────────────────────────────────────────────────────────────
async def _remove_autocomplete(interaction: discord.Interaction, current: str):
    """Suggest events the user is allowed to remove, matching typed text."""
    cur = current.lower()
    out = []
    for e in store.events_for_guild(interaction.guild_id):
        scope = e.get("scope", SERVER_SCOPE)
        if not can_admin_scope(interaction.user, scope):
            continue
        label = f"[{scope_label(scope)}] {e['name']}"
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


# ── visibility filter for a viewer ───────────────────────────────────────────
def _visible_events(member: discord.Member) -> list[dict]:
    return [e for e in store.events_for_guild(member.guild.id)
            if can_view_scope(member, e.get("scope", SERVER_SCOPE))]


# ── member queries (ephemeral) ───────────────────────────────────────────────
@bot.tree.command(name="event_list", description="List events you can see.")
async def event_list(interaction: discord.Interaction):
    evs = _visible_events(interaction.user)
    if not evs:
        return await interaction.response.send_message("No events you can see yet.", ephemeral=True)
    lines = [f"• [{scope_label(e.get('scope', SERVER_SCOPE))}] **{e['name']}** (`{e['id']}`) — "
             f"{describe_schedule(e['schedule'])}" for e in evs]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)


@bot.tree.command(name="next", description="Your next upcoming event.")
async def next_cmd(interaction: discord.Interaction):
    now = datetime.now(timezone.utc)
    upcoming = []
    for e in _visible_events(interaction.user):
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
    evs = _visible_events(interaction.user)
    pairs = sched.occurrences_for_events(evs, start, end)
    if not pairs:
        return await interaction.response.send_message(f"No events {label.lower()}.", ephemeral=True)
    lines = [f"• {ts(dt, 't')} — [{scope_label(e.get('scope', SERVER_SCOPE))}] **{e['name']}**"
             for dt, e in pairs]
    await interaction.response.send_message(f"**{label} (UTC day)**\n" + "\n".join(lines), ephemeral=True)


# ── scheduler: ping the scope's role at T-1h and at start ────────────────────
@tasks.loop(minutes=1)
async def scheduler_tick():
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
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
            for offset, when in ((60, "in 1 hour"), (0, "starting now")):
                target = now + timedelta(minutes=offset)
                for dt in sched.occurrences_between(e, target, target):
                    key = f"{e['id']}|{dt.isoformat()}|{offset}"
                    if key in _fired:
                        continue
                    _fired.add(key)
                    try:
                        await channel.send(
                            f"<@&{role_id}> **{e['name']}** ({scope_label(scope)}) {when} — {ts_both(dt)}")
                    except discord.DiscordException as ex:
                        log.error("ping send failed: %s", ex)
    if len(_fired) > 5000:
        _fired.clear()


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
        if not pairs:
            return f"__{title}__\n*(none)*"
        rows = "\n".join(
            f"• {ts(dt, 't')} — **{e['name']}** ({ts(dt,'R')})"
            for dt, e in pairs)
        return f"__{title}__\n{rows}"

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


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    await ctx.send(f"🏓 Pong! {round(bot.latency * 1000)} ms")


def main():
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and add it.")
    bot.run(TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
