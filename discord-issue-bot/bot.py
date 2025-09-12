#!/usr/bin/env python3
import discord

from app import config
from app.bot_client import build_bot
from app.commands import setup_commands


def main():
    if not config.DISCORD_TOKEN:
        raise SystemExit("DISCORD_BOT_TOKEN が未設定です")

    bot = build_bot()
    setup_commands(bot)
    bot.run(config.DISCORD_TOKEN)


if __name__ == "__main__":
    main()
