"""Alliance registry for Era 8.

Each event has a `scope`: either "server" (pings @eRa8, any R4 may manage) or an
alliance key below (pings that alliance's member role, only that alliance's R4
may manage). Role *names* here are documentation only — actual role IDs are
resolved per-guild via /config_alliance and stored in config.json.
"""

# key -> (display name, R4/admin role name, member role name)
ALLIANCES = {
    "WC1": ("WorldClass",     "WorldClass R4 - eRa8",     "WorldClass eRa8"),
    "AGC": ("AuroraGodCourt", "AuroraGodCourt R4 - eRa8", "AuroraGodCourt eRa8"),
    "REU": ("ReUnions",       "ReUnions R4 - eRa8",       "ReUnions eRa8"),
    "MyT": ("Mythic",         "Mythic R4 - eRa8",         "Mythic eRa8"),
}

SERVER_SCOPE = "server"

# valid scope values for an event
SCOPES = [SERVER_SCOPE] + list(ALLIANCES.keys())


def scope_label(scope: str) -> str:
    """Short bracket label for board/list display."""
    if scope == SERVER_SCOPE:
        return "Server"
    return scope  # WC1 / AGC / REU / MyT


def scope_display(scope: str) -> str:
    if scope == SERVER_SCOPE:
        return "Server-wide (@eRa8)"
    name, _, _ = ALLIANCES[scope]
    return f"{name} ({scope})"
