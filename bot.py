"""AoEM event-management Discord bot — bare-bones MVP.

Goal for this stage: connect to Discord, confirm the bot authenticates on our
server, and prove it can respond to a command. Everything else comes later.
"""

import os
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

# ── config ───────────────────────────────────────────────────────────────────
load_dotenv()  # pulls DISCORD_TOKEN from a local .env file (see .env.example)
TOKEN = os.getenv("DISCORD_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(name)s: %(message)s",
)
log = logging.getLogger("aoem-bot")

# Intents: message_content is a "privileged" intent required to read the text of
# messages (so the "!ping" prefix command works). Enable it in the Developer
# Portal → Bot → Privileged Gateway Intents, or this login will fail.
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# ── lifecycle ────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    """Fires once the bot has authenticated and the gateway is ready."""
    log.info("Logged in as %s (id: %s)", bot.user, bot.user.id)
    if bot.guilds:
        log.info("Connected to %d guild(s):", len(bot.guilds))
        for g in bot.guilds:
            log.info("  • %s (id: %s, members: %s)", g.name, g.id, g.member_count)
    else:
        log.warning(
            "Not in any guild yet. Invite the bot with an OAuth2 URL "
            "(scopes: bot; permissions: Send Messages)."
        )
    log.info("Ready. Try '!ping' in a channel the bot can see.")


# ── commands ─────────────────────────────────────────────────────────────────
@bot.command(name="ping")
async def ping(ctx: commands.Context):
    """Simple round-trip check — proves the bot can read and reply."""
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f"🏓 Pong! Gateway latency: {latency_ms} ms")


# ── entrypoint ───────────────────────────────────────────────────────────────
def main():
    if not TOKEN:
        raise SystemExit(
            "DISCORD_TOKEN is not set. Copy .env.example to .env and paste your "
            "bot token, then run again."
        )
    bot.run(TOKEN, log_handler=None)  # we configured logging ourselves above


if __name__ == "__main__":
    main()
