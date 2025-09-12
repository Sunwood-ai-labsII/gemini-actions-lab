import os

# Discord / GitHub tokens and endpoints
DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")
GITHUB_API = os.environ.get("GITHUB_API", "https://api.github.com")

# Message prefix for legacy text commands
PREFIX = os.environ.get("DISCORD_MESSAGE_PREFIX", "!issue").strip()

# Optional guild to sync slash commands instantly
GUILD_ID_ENV = os.environ.get("DISCORD_GUILD_ID")

def get_guild_id() -> int | None:
    return int(GUILD_ID_ENV) if (GUILD_ID_ENV and GUILD_ID_ENV.isdigit()) else None
