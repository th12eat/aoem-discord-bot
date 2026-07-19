"""Discord-facing helpers: dynamic timestamps, permission gates, formatting."""

from __future__ import annotations

from datetime import datetime, timezone

import discord

import store
from alliances import ALLIANCES, SERVER_SCOPE


def ts(dt: datetime, style: str = "F") -> str:
    """Discord dynamic timestamp — renders in each viewer's own locale/timezone.
    Styles: t=short time, F=full, R=relative ("in 2 hours"), etc.
    """
    return f"<t:{int(dt.timestamp())}:{style}>"


def ts_both(dt: datetime) -> str:
    """Full timestamp + relative, e.g. 'Mon 20 Jul 19:00 (in 3 hours)'."""
    return f"{ts(dt, 'F')} ({ts(dt, 'R')})"


def has_role(member: discord.Member, role_id: int | None) -> bool:
    if not role_id:
        return False
    return any(r.id == role_id for r in member.roles)


def member_alliances(member: discord.Member) -> set[str]:
    """Alliance keys this member belongs to (by their member role)."""
    cfg = store.guild_config(member.guild.id)
    out = set()
    for key, roles in cfg.get("alliances", {}).items():
        if has_role(member, roles.get("member_role_id")):
            out.add(key)
    return out


def r4_alliances(member: discord.Member) -> set[str]:
    """Alliance keys this member is an R4 (admin) of."""
    cfg = store.guild_config(member.guild.id)
    out = set()
    for key, roles in cfg.get("alliances", {}).items():
        if has_role(member, roles.get("r4_role_id")):
            out.add(key)
    return out


def is_any_r4(member: discord.Member) -> bool:
    return bool(r4_alliances(member)) or member.guild_permissions.manage_guild


def can_admin_scope(member: discord.Member, scope: str) -> bool:
    """Server-wide events: any R4 (or Manage Server). Alliance events: that
    alliance's R4 only (Manage Server always allowed as a safety hatch)."""
    if member.guild_permissions.manage_guild:
        return True
    if scope == SERVER_SCOPE:
        return is_any_r4(member)
    return scope in r4_alliances(member)


def can_view_scope(member: discord.Member, scope: str) -> bool:
    """Server events: everyone (@eRa8). Alliance events: that alliance's members
    (or its R4, or Manage Server)."""
    if scope == SERVER_SCOPE:
        cfg = store.guild_config(member.guild.id)
        return has_role(member, cfg.get("server_member_role_id")) or is_any_r4(member)
    if member.guild_permissions.manage_guild:
        return True
    return scope in member_alliances(member) or scope in r4_alliances(member)


def ping_role_id(guild_id: int, scope: str) -> int | None:
    """The member role to ping for an event of this scope."""
    cfg = store.guild_config(guild_id)
    if scope == SERVER_SCOPE:
        return cfg.get("server_member_role_id")
    return cfg.get("alliances", {}).get(scope, {}).get("member_role_id")


def describe_schedule(schedule: dict) -> str:
    """Human summary of a recurrence rule for list output."""
    t = schedule["type"]
    if t == "once":
        dt = datetime.fromisoformat(schedule["datetime"]).replace(tzinfo=timezone.utc)
        return f"one-time · {ts(dt, 'F')}"
    times = ", ".join(schedule.get("times", []))
    if t == "daily":
        return f"daily · {times} UTC"
    if t == "everyother":
        return f"every other day (from {schedule.get('anchor', '?')}) · {times} UTC"
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    if t == "weekly":
        days = "/".join(names[d] for d in schedule.get("days", []))
        return f"weekly · {days} · {times} UTC"
    if t == "everyotherweek":
        days = "/".join(names[d] for d in schedule.get("days", []))
        return f"every other week · {days} · {times} UTC (from {schedule.get('anchor','?')})"
    if t == "kvk":
        return f"multi-day KvK · starts {schedule.get('start','?')}"
    if t == "series":
        times = ", ".join(schedule.get("times", []))
        when = f"{times} UTC" if times else "time TBD (no ping until set)"
        return f"weekly series · next {schedule.get('date','?')} · {when}"
    return "unknown schedule"
