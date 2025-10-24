import os

# Discord / GitHub tokens and endpoints
DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")
GITHUB_API = os.environ.get("GITHUB_API", "https://api.github.com")

# Message prefix for legacy text commands
PREFIX = os.environ.get("DISCORD_MESSAGE_PREFIX", "!issue").strip()

# Optional guild to sync slash commands instantly
GUILD_ID_ENV = os.environ.get("DISCORD_GUILD_ID")

# Optional environment sync command settings
ENV_SYNC_ENABLED = os.environ.get("DISCORD_ENV_SYNC_ENABLED", "").lower() in {"1", "true", "yes", "on"}
ENV_SYNC_DEFAULT_FILE = os.environ.get("DISCORD_ENV_SYNC_FILE", ".env")
ENV_SYNC_DEFAULT_REPO = os.environ.get("DISCORD_ENV_SYNC_REPO", "")
ENV_SYNC_ALLOWED_USERS_RAW = os.environ.get("DISCORD_ENV_SYNC_ALLOWED_USERS", "")

# Repository autocomplete enrichment
REPO_SUGGEST_ACCOUNTS_RAW = os.environ.get("DISCORD_REPO_SUGGEST_ACCOUNTS", "")
REPO_SUGGEST_LOOKBACK_DAYS_RAW = os.environ.get("DISCORD_REPO_SUGGEST_LOOKBACK_DAYS", "7")


def get_env_sync_allowed_users() -> set[int]:
    allowed: set[int] = set()
    for chunk in ENV_SYNC_ALLOWED_USERS_RAW.split(","):
        token = chunk.strip()
        if not token:
            continue
        if token.isdigit():
            allowed.add(int(token))
    return allowed


def get_guild_id() -> int | None:
    return int(GUILD_ID_ENV) if (GUILD_ID_ENV and GUILD_ID_ENV.isdigit()) else None


def get_repo_suggest_accounts() -> list[str]:
    accounts: list[str] = []
    for chunk in REPO_SUGGEST_ACCOUNTS_RAW.split(","):
        name = chunk.strip()
        if name:
            accounts.append(name)
    return accounts


def get_repo_suggest_lookback_days(default: int = 7) -> int:
    raw = REPO_SUGGEST_LOOKBACK_DAYS_RAW.strip()
    if not raw:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default
