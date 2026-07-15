# AoEM Event Bot — MVP

Bare-bones Discord bot to verify it can **authenticate on our server** and
respond to a command. Feature build-out comes later.

## What it does (for now)
- Logs in with a bot token and prints the logged-in identity + every guild
  (server) it's in — your proof that auth worked.
- Responds to `!ping` with the gateway latency.

## One-time setup

### 1. Create the bot application
1. Go to <https://discord.com/developers/applications> → **New Application**.
2. Left sidebar → **Bot** → **Reset Token** → copy the token.
3. On that same Bot page, under **Privileged Gateway Intents**, enable
   **Message Content Intent** (needed for the `!ping` prefix command).

### 2. Invite the bot to our server
1. Left sidebar → **OAuth2** → **URL Generator**.
2. Scopes: check **`bot`**.
3. Bot Permissions: check **Send Messages** (and **Read Message History**).
4. Copy the generated URL, open it, pick our server, **Authorize**.
   *(You need "Manage Server" permission on the server to add a bot.)*

### 3. Local setup
```bash
cd aoem-discord-bot
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then edit .env and paste your token
```

## Run
```bash
source .venv/bin/activate
python bot.py
```
Success looks like:
```
Logged in as YourBot#1234 (id: ...)
Connected to 1 guild(s):
  • Our Server (id: ..., members: ...)
Ready. Try '!ping' in a channel the bot can see.
```
Then type `!ping` in any channel the bot can see — it should reply `🏓 Pong!`.

## Notes
- The token is a password. It lives only in `.env`, which is gitignored. If it
  ever leaks, Reset Token in the portal immediately.
- Runs on any machine with Python 3.10+ and network access — your home PC, or
  your work machine for this test. No hosting/deploy needed; it's a long-running
  local process (Ctrl+C to stop).
