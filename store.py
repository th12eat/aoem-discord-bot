"""JSON-backed persistence for guild config and events.

Two files under data/:
  config.json — per-guild role/channel setup + board message tracking
  events.json — the list of scheduled events

Everything is keyed by guild id (string) so the bot can serve multiple servers.
Times are stored in UTC throughout. Kept deliberately simple and human-readable
so it can be hand-edited or git-inspected, matching the dashboard's data style.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
EVENTS_PATH = os.path.join(DATA_DIR, "events.json")

_lock = threading.Lock()


def _read(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def _write(path: str, data: Any) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)  # atomic on the same filesystem


# ── config ───────────────────────────────────────────────────────────────────
# shape: { "guilds": { "<guild_id>": {
#            server_member_role_id,    # @eRa8 — pinged for server-wide events
#            board_channel_id, board_message_id,
#            alliances: { "<KEY>": {r4_role_id, member_role_id} }  # per alliance
#          } } }
def load_config() -> dict:
    return _read(CONFIG_PATH, {"guilds": {}})


def save_config(cfg: dict) -> None:
    with _lock:
        _write(CONFIG_PATH, cfg)


def guild_config(guild_id: int) -> dict:
    return load_config()["guilds"].get(str(guild_id), {})


def set_guild_config(guild_id: int, **fields) -> dict:
    with _lock:
        cfg = load_config()
        g = cfg["guilds"].setdefault(str(guild_id), {})
        g.update({k: v for k, v in fields.items() if v is not None})
        _write(CONFIG_PATH, cfg)
        return g


def set_alliance_roles(guild_id: int, key: str, r4_role_id: int, member_role_id: int) -> dict:
    """Register (or update) an alliance's R4 + member role IDs for this guild."""
    with _lock:
        cfg = load_config()
        g = cfg["guilds"].setdefault(str(guild_id), {})
        alli = g.setdefault("alliances", {})
        alli[key] = {"r4_role_id": r4_role_id, "member_role_id": member_role_id}
        _write(CONFIG_PATH, cfg)
        return g


def alliance_roles(guild_id: int, key: str) -> dict:
    return guild_config(guild_id).get("alliances", {}).get(key, {})


# ── legion (server-wide) ─────────────────────────────────────────────────────
# shape under a guild:  "legion": {
#     "slots": { "sat_0100": <role_id>, ... },   # per-time-slot ping roles
#     "seed":  { "anchor": "YYYY-MM-DD", "event": "WC" }  # WC/BoD alternation
#     "roster": { "sat_0100": { "WC1": ["Name", ...], ... }, ... }  # NON-discord
#   }
def legion_config(guild_id: int) -> dict:
    return guild_config(guild_id).get("legion", {})


def _legion(cfg, guild_id):
    return cfg["guilds"].setdefault(str(guild_id), {}).setdefault("legion", {})


def add_legion_names(guild_id: int, slot: str, alliance: str, names: list[str]) -> None:
    """Add non-discord member names to a slot under an alliance (deduped, and
    removed from any OTHER slot — one slot per person, case-insensitive)."""
    with _lock:
        cfg = load_config()
        leg = _legion(cfg, guild_id)
        roster = leg.setdefault("roster", {})
        low = {n.lower() for n in names}
        # remove these names from every other slot (exclusivity)
        for s, per_all in roster.items():
            if s == slot:
                continue
            for a, lst in per_all.items():
                per_all[a] = [n for n in lst if n.lower() not in low]
        bucket = roster.setdefault(slot, {}).setdefault(alliance, [])
        have = {n.lower() for n in bucket}
        for n in names:
            if n.lower() not in have:
                bucket.append(n); have.add(n.lower())
        _write(CONFIG_PATH, cfg)


def remove_legion_names(guild_id: int, names: list[str]) -> int:
    """Remove non-discord names from ALL slots/alliances. Returns count removed."""
    with _lock:
        cfg = load_config()
        roster = _legion(cfg, guild_id).get("roster", {})
        low = {n.lower() for n in names}
        removed = 0
        for per_all in roster.values():
            for a, lst in per_all.items():
                kept = [n for n in lst if n.lower() not in low]
                removed += len(lst) - len(kept)
                per_all[a] = kept
        _write(CONFIG_PATH, cfg)
        return removed


def clear_legion_roster(guild_id: int) -> None:
    """Wipe all non-discord roster names (weekly Monday reset)."""
    with _lock:
        cfg = load_config()
        _legion(cfg, guild_id)["roster"] = {}
        _write(CONFIG_PATH, cfg)


def set_legion_slot(guild_id: int, slot: str, role_id: int) -> dict:
    """Bind a ping role to one legion time-slot (sat_0100 … sun_1900)."""
    with _lock:
        cfg = load_config()
        g = cfg["guilds"].setdefault(str(guild_id), {})
        leg = g.setdefault("legion", {})
        leg.setdefault("slots", {})[slot] = role_id
        _write(CONFIG_PATH, cfg)
        return leg


def set_legion_seed(guild_id: int, anchor: str, event: str) -> dict:
    """Seed the WC↔BoD alternation: `event` runs the weekend of `anchor` (a Sat)."""
    with _lock:
        cfg = load_config()
        g = cfg["guilds"].setdefault(str(guild_id), {})
        g.setdefault("legion", {})["seed"] = {"anchor": anchor, "event": event}
        _write(CONFIG_PATH, cfg)
        return g["legion"]


def clear_legion_seed(guild_id: int) -> bool:
    """Remove the seed (unseed). Returns True if there was one."""
    with _lock:
        cfg = load_config()
        leg = cfg["guilds"].get(str(guild_id), {}).get("legion", {})
        had = "seed" in leg
        leg.pop("seed", None)
        _write(CONFIG_PATH, cfg)
        return had


# ── rotating-series anchors ───────────────────────────────────────────────────
# shape under a guild:  "rotation": { "anchors": {
#     "City Clash": {"date": "2026-08-08", "idx": 2}, ...   # date + pool index
#   } }
# An anchor means "the occurrence on `date` used ROTATION_POOL[idx]"; every other
# occurrence's slot is computed from it (see series.rotation_times), so it's
# immutable and restart-safe. Set by /rotation_seed with a week's real timings.
def set_rotation_anchor(guild_id: int, name: str, anchor_date: str, idx: int) -> dict:
    """Store (or overwrite) the pool anchor for a rotating series."""
    with _lock:
        cfg = load_config()
        g = cfg["guilds"].setdefault(str(guild_id), {})
        anchors = g.setdefault("rotation", {}).setdefault("anchors", {})
        anchors[name] = {"date": anchor_date, "idx": idx}
        _write(CONFIG_PATH, cfg)
        return anchors[name]


def rotation_anchor(guild_id: int, name: str) -> dict:
    """The stored {date, idx} anchor for a rotating series (empty if unseeded)."""
    return guild_config(guild_id).get("rotation", {}).get("anchors", {}).get(name, {})


# ── events ───────────────────────────────────────────────────────────────────
# shape: { "events": [ {id, guild_id, name, schedule{...}, created_by} ] }
def load_events() -> list[dict]:
    return _read(EVENTS_PATH, {"events": []})["events"]


def save_events(events: list[dict]) -> None:
    with _lock:
        _write(EVENTS_PATH, {"events": events})


def events_for_guild(guild_id: int) -> list[dict]:
    return [e for e in load_events() if e.get("guild_id") == str(guild_id)]


def add_event(event: dict) -> None:
    with _lock:
        data = _read(EVENTS_PATH, {"events": []})
        data["events"].append(event)
        _write(EVENTS_PATH, data)


def remove_event(event_id: str, guild_id: int) -> bool:
    with _lock:
        data = _read(EVENTS_PATH, {"events": []})
        before = len(data["events"])
        data["events"] = [
            e for e in data["events"]
            if not (e["id"] == event_id and e.get("guild_id") == str(guild_id))
        ]
        _write(EVENTS_PATH, data)
        return len(data["events"]) < before


def update_event(event_id: str, guild_id: int, changes: dict) -> dict | None:
    """Shallow-merge `changes` into the matching event. Returns the updated
    event, or None if not found. Nested `schedule` keys merge, not replace."""
    with _lock:
        data = _read(EVENTS_PATH, {"events": []})
        for e in data["events"]:
            if e["id"] == event_id and e.get("guild_id") == str(guild_id):
                for k, v in changes.items():
                    if k == "schedule" and isinstance(v, dict) and isinstance(e.get("schedule"), dict):
                        e["schedule"].update(v)
                    else:
                        e[k] = v
                _write(EVENTS_PATH, data)
                return e
        return None
