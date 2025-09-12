import json
import discord
from discord import app_commands

from . import config
from .github_api import http_post
from .parser import parse_legacy_command
from .utils import build_body_with_footer
from .store import remember_repo


class Bot(discord.Client):
    def __init__(self, *, intents: discord.Intents, guild_id: int | None = None):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.guild_id = guild_id

    async def on_ready(self):
        print(f"Logged in as {self.user} | prefix={config.PREFIX}")

    async def setup_hook(self):
        # Sync slash commands (guild-scoped if provided for instant availability)
        try:
            if self.guild_id:
                await self.tree.sync(guild=discord.Object(id=self.guild_id))
            else:
                await self.tree.sync()
        except Exception as e:
            print(f"Slash command sync failed: {e}")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        content = (message.content or "").strip()
        if not content.lower().startswith(config.PREFIX.lower()):
            return

        if not config.GITHUB_TOKEN:
            await message.reply("GITHUB_TOKEN が未設定です", mention_author=False)
            return

        parsed = parse_legacy_command(content)
        if "error" in parsed:
            await message.reply(parsed["error"], mention_author=False)
            return

        repo = parsed["repo"]
        url = f"{config.GITHUB_API}/repos/{repo}/issues"
        payload = {
            "title": parsed["title"],
            "body": build_body_with_footer(parsed["body"], str(message.author), message.jump_url),
        }
        if parsed["labels"]:
            payload["labels"] = parsed["labels"]
        if parsed["assignees"]:
            payload["assignees"] = parsed["assignees"]

        status, resp = http_post(url, config.GITHUB_TOKEN, payload)
        try:
            data = json.loads(resp) if resp else {}
        except Exception:
            data = {}

        # Success
        if status in (200, 201):
            issue_url = data.get("html_url", "")
            number = data.get("number", "?")
            remember_repo(repo)
            await message.reply(f"Issueを作成しました: #{number} {issue_url}", mention_author=False)
            return

        # If assignees are invalid (422), retry once without assignees
        retried = False
        if status == 422 and isinstance(data, dict):
            errors = data.get("errors") or []
            invalid_assignees = None
            for err in errors:
                if isinstance(err, dict) and err.get("field") == "assignees":
                    invalid_assignees = err.get("value") or parsed.get("assignees")
                    break
            if invalid_assignees and payload.get("assignees"):
                retry_payload = dict(payload)
                retry_payload.pop("assignees", None)
                status2, resp2 = http_post(url, config.GITHUB_TOKEN, retry_payload)
                try:
                    data2 = json.loads(resp2) if resp2 else {}
                except Exception:
                    data2 = {}
                if status2 in (200, 201):
                    issue_url = data2.get("html_url", "")
                    number = data2.get("number", "?")
                    invalid_list = ", ".join(map(str, invalid_assignees)) if isinstance(invalid_assignees, list) else str(invalid_assignees)
                    remember_repo(repo)
                    await message.reply(
                        f"Issueを作成しました: #{number} {issue_url}\n（注意: 次のユーザーはアサインできませんでした → {invalid_list}）",
                        mention_author=False,
                    )
                    retried = True

        if not retried:
            await message.reply(f"作成失敗: {status}\n{(resp or '')[:1500]}", mention_author=False)


def build_bot() -> Bot:
    intents = discord.Intents.default()
    intents.message_content = True  # keep legacy text command working
    return Bot(intents=intents, guild_id=config.get_guild_id())
