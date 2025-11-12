import discord
from discord import app_commands

from . import config


class Bot(discord.Client):
    def __init__(self, *, intents: discord.Intents, guild_id: int | None = None):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.guild_id = guild_id

    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def setup_hook(self):
        # Sync slash commands (guild-scoped if provided for instant availability)
        try:
            if self.guild_id:
                await self.tree.sync(guild=discord.Object(id=self.guild_id))
            else:
                await self.tree.sync()
        except Exception as e:
            print(f"Slash command sync failed: {e}")


def build_bot() -> Bot:
    intents = discord.Intents.default()
    # Message content intent is not required for slash commands only
    return Bot(intents=intents, guild_id=config.get_guild_id())
