"""Activity Tracker submission commands for Catherine.

Lets a member submit their weekly activities to the Activity Tracker app from
Discord, instead of visiting the web UI. The bot never touches the database or
holds Supabase credentials: every call goes to the `discord-submit` Supabase Edge
Function (authenticated with a shared bot secret), which runs the SECURITY DEFINER
RPCs that validate + score the submission server-side. The bot only shapes the
request and relays the function's JSON verdict.

A user must first link their Discord account to their Activity Tracker account in
the app (Settings → "Connect Discord"); until then the function replies
`not_linked` and we point them there.

Config (bot .env):
  ACTIVITY_FN_URL     — the discord-submit function URL
  ACTIVITY_BOT_SECRET — the shared secret sent as the `x-bot-secret` header

Self-contained: `register(bot)` defines the commands on the existing tree, so
bot.py just calls activity.register(bot). No DB, no per-user storage here.
"""

from __future__ import annotations

import os
import logging

import aiohttp
import discord
from discord import app_commands

log = logging.getLogger("catherine.activity")

FN_URL = os.getenv("ACTIVITY_FN_URL", "").rstrip("/")
BOT_SECRET = os.getenv("ACTIVITY_BOT_SECRET", "")

# Link to the app's account settings, shown when a user isn't linked yet.
_SETTINGS_URL = "https://guillomef06.github.io/activity-tracker/app"


async def _call(action: str, **payload) -> dict:
    """POST one action to the Edge Function; return its parsed JSON (or a synthetic
    error dict). All business logic lives server-side — this is a thin client."""
    if not FN_URL or not BOT_SECRET:
        return {"ok": False, "reason": "not_configured",
                "message": "Activity submission isn't configured on the bot (missing ACTIVITY_FN_URL / ACTIVITY_BOT_SECRET)."}
    body = {"action": action, **payload}
    headers = {"x-bot-secret": BOT_SECRET, "content-type": "application/json"}
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(FN_URL, json=body, headers=headers) as resp:
                try:
                    data = await resp.json()
                except aiohttp.ContentTypeError:
                    text = await resp.text()
                    return {"ok": False, "reason": "bad_response",
                            "message": f"Unexpected response ({resp.status}): {text[:150]}"}
                if isinstance(data, dict):
                    return data
                return {"ok": False, "reason": "bad_response", "message": "Unexpected response shape."}
    except aiohttp.ClientError as e:
        log.error("activity fn call failed: %s", e)
        return {"ok": False, "reason": "network", "message": "Couldn't reach the Activity Tracker service — try again shortly."}


def register(bot) -> None:
    """Define the activity commands on the bot's command tree."""

    # ── autocomplete: open weeks for the caller (mirrors the app's week dropdown) ──
    async def _week_autocomplete(interaction: discord.Interaction, current: str):
        data = await _call("open_weeks", discord_id=str(interaction.user.id))
        if not data.get("ok"):
            # not linked / not configured → a single hint entry (value kept valid-ish)
            hint = "Link your account first — /activity_link" if data.get("reason") == "not_linked" \
                   else "Activity submission unavailable right now"
            return [app_commands.Choice(name=hint[:100], value="")]
        weeks = data.get("weeks", [])
        out = []
        for w in weeks:
            monday = w.get("monday", "")
            label = f"Week {w.get('week_index')} ({monday})" + (" · current" if w.get("is_current") else "")
            if current.lower() in label.lower():
                out.append(app_commands.Choice(name=label[:100], value=monday))
        # most-recent first, Discord caps at 25
        return out[-25:][::-1]

    # ── autocomplete: activities offered in the chosen week (+ legion) ──
    async def _activity_autocomplete(interaction: discord.Interaction, current: str):
        week = getattr(interaction.namespace, "week", None)
        if not week:
            return [app_commands.Choice(name="Pick a week first", value="")]
        data = await _call("week_activities", week_date=week)
        if not data.get("ok"):
            return [app_commands.Choice(name="Couldn't load activities", value="")]
        acts = data.get("activities", [])
        cur = current.lower()
        return [app_commands.Choice(name=a[:100], value=a) for a in acts if cur in a.lower()][:25]

    # ── /activity_link ──────────────────────────────────────────────────────
    @bot.tree.command(name="activity_link",
                      description="How to link your Discord to your Activity Tracker account (one-time, in the app).")
    async def activity_link(interaction: discord.Interaction):
        # Linking is done in the APP (verified OAuth), not here — point them there.
        data = await _call("open_weeks", discord_id=str(interaction.user.id))
        linked = data.get("ok") is True
        if linked:
            msg = ("✅ Your Discord is already linked to your Activity Tracker account.\n"
                   "Use **/activity_submit** to log your weekly activities.")
        else:
            msg = ("🔗 **Link your account (one-time):**\n"
                   f"1. Open the Activity Tracker: {_SETTINGS_URL}\n"
                   "2. Log in → open **My Account** → **Discord Account** → **Connect Discord**.\n"
                   "3. Authorize, then come back and use **/activity_submit**.\n\n"
                   "_This proves the Discord account is yours so the bot can submit on your behalf._")
        await interaction.response.send_message(msg, ephemeral=True)

    # ── /activity_submit ────────────────────────────────────────────────────
    @bot.tree.command(name="activity_submit",
                      description="Log a weekly activity to the Activity Tracker.")
    @app_commands.describe(
        week="Which week (pick from the list; defaults to the current week)",
        activity="Which activity (pick from the list of this week's activities)",
        rank="Your rank 1–500 (leave blank for participation-only activities like legion)",
    )
    @app_commands.autocomplete(week=_week_autocomplete, activity=_activity_autocomplete)
    async def activity_submit(interaction: discord.Interaction,
                              activity: str,
                              week: str | None = None,
                              rank: int | None = None):
        await interaction.response.defer(ephemeral=True, thinking=True)
        data = await _call("submit",
                           discord_id=str(interaction.user.id),
                           activity=activity,
                           rank=rank,
                           week_date=week or "")
        await interaction.followup.send(_format_submit(data), ephemeral=True)

    # ── /activity_status ──────────────────────────────────────────────────────
    @bot.tree.command(name="activity_status",
                      description="Check whether your Discord is linked to the Activity Tracker.")
    async def activity_status(interaction: discord.Interaction):
        data = await _call("open_weeks", discord_id=str(interaction.user.id))
        if data.get("ok"):
            weeks = data.get("weeks", [])
            cur = next((w for w in weeks if w.get("is_current")), None)
            cur_txt = f" · current week: Week {cur['week_index']} ({cur['monday']})" if cur else ""
            msg = f"✅ Linked.{cur_txt}\nUse **/activity_submit** to log activities."
        elif data.get("reason") == "not_linked":
            msg = ("❌ Not linked yet. Run **/activity_link** for the one-time setup.")
        else:
            msg = f"⚠️ {data.get('message', 'Activity submission is unavailable right now.')}"
        await interaction.response.send_message(msg, ephemeral=True)


def _format_submit(data: dict) -> str:
    """Turn the function's JSON verdict into a friendly ephemeral message."""
    if data.get("ok"):
        act = data.get("activity_type", "activity")
        pts = data.get("points")
        wk = data.get("week_start", "")
        pos = data.get("position")
        verb = "Updated" if data.get("action") == "updated" else "Recorded"
        pos_txt = f" rank {pos}" if pos is not None else " (participation)"
        return f"✅ {verb} **{act}**{pos_txt} — {pts} pts · week of {wk}."
    reason = data.get("reason", "error")
    # Known reasons get a tailored nudge; everything else shows the server message.
    if reason == "not_linked":
        return ("❌ Your Discord isn't linked yet. Run **/activity_link** for the one-time setup "
                "in the Activity Tracker app.")
    if reason == "not_configured":
        return f"⚠️ {data.get('message')}"
    return f"⚠️ {data.get('message', 'Submission rejected.')}"
