import json
import discord
from discord import app_commands

from . import config
from .github_api import http_get, http_post
from .parser import parse_labels_input, parse_assignees_input
from .utils import build_body_with_footer


def setup_commands(bot: discord.Client):
    @bot.tree.command(name="issue", description="GitHub Issue を作成します")
    @app_commands.describe(
        repo="対象リポジトリ (owner/repo)",
        title="Issue タイトル",
        body="本文（省略可）",
        labels="ラベル（例: #bug #p2 または bug,p2）",
        assignees="アサイン（例: +alice +bob または alice,bob)",
    )
    async def issue_slash(
        interaction: discord.Interaction,
        repo: str,
        title: str,
        body: str = "",
        labels: str = "",
        assignees: str = "",
    ):
        if not config.GITHUB_TOKEN:
            await interaction.response.send_message("GITHUB_TOKEN が未設定です", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        payload = {
            "title": title.strip() or "New Issue",
            "body": build_body_with_footer(body.strip() or "(no body)", str(interaction.user), None),
        }
        label_list = parse_labels_input(labels)
        assignee_list = parse_assignees_input(assignees)
        if label_list:
            payload["labels"] = label_list
        if assignee_list:
            payload["assignees"] = assignee_list

        url = f"{config.GITHUB_API}/repos/{repo}/issues"
        status, resp = http_post(url, config.GITHUB_TOKEN, payload)
        try:
            data = json.loads(resp) if resp else {}
        except Exception:
            data = {}

        if status in (200, 201):
            issue_url = data.get("html_url", "")
            number = data.get("number", "?")
            await interaction.followup.send(f"Issueを作成しました: #{number} {issue_url}")
            return

        # Retry once if assignee invalid
        retried = False
        if status == 422 and isinstance(data, dict) and payload.get("assignees"):
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
                await interaction.followup.send(
                    f"Issueを作成しました: #{number} {issue_url}\n（注意: 一部アサインに失敗したため、アサインなしで作成しました）"
                )
                retried = True

        if not retried:
            snippet = (resp or "")[:1500]
            await interaction.followup.send(f"作成失敗: {status}\n{snippet}")

    @bot.tree.command(name="issue_help", description="/issue の使い方を表示します")
    async def issue_help(interaction: discord.Interaction):
        text = (
            "使い方:\n"
            "/issue repo:<owner/repo> title:<タイトル> [body:<本文>] [labels:<#bug #p2>] [assignees:<+alice +bob>]\n\n"
            "例1: /issue repo:owner/repo title:\"バグ: 保存できない\" labels:#bug #p2 assignees:+alice\n"
            "例2: /issue repo:owner/repo title:ドキュメント更新 body:手順を最新化してください labels:doc\n"
            "ヒント: labels/assignees はカンマ区切り（bug,p2 / alice,bob）も OK\n"
        )
        await interaction.response.send_message(text, ephemeral=True)

    @bot.tree.command(name="tag_latest", description="最新コミットにタグを付けます（軽量タグ）")
    @app_commands.describe(
        repo="対象リポジトリ (owner/repo)",
        tag="作成するタグ名（例: v1.2.3）",
        branch="対象ブランチ（省略時はデフォルト）",
    )
    async def tag_latest(
        interaction: discord.Interaction,
        repo: str,
        tag: str,
        branch: str | None = None,
    ):
        if not config.GITHUB_TOKEN:
            await interaction.response.send_message("GITHUB_TOKEN が未設定です", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        # 1) default branch if not provided
        target_branch = branch
        if not target_branch:
            st, body = http_get(f"{config.GITHUB_API}/repos/{repo}", config.GITHUB_TOKEN)
            try:
                repo_info = json.loads(body) if body else {}
            except Exception:
                repo_info = {}
            if st != 200 or not repo_info.get("default_branch"):
                await interaction.followup.send(f"失敗: デフォルトブランチ取得に失敗しました ({st})\n{(body or '')[:500]}")
                return
            target_branch = repo_info["default_branch"]

        # 2) get latest commit sha for branch
        st2, body2 = http_get(f"{config.GITHUB_API}/repos/{repo}/commits/{target_branch}", config.GITHUB_TOKEN)
        try:
            commit_info = json.loads(body2) if body2 else {}
        except Exception:
            commit_info = {}
        sha = commit_info.get("sha")
        if st2 != 200 or not sha:
            await interaction.followup.send(f"失敗: 最新コミット取得に失敗しました ({st2})\n{(body2 or '')[:500]}")
            return

        # 3) create lightweight tag (ref)
        payload = {"ref": f"refs/tags/{tag}", "sha": sha}
        st3, body3 = http_post(f"{config.GITHUB_API}/repos/{repo}/git/refs", config.GITHUB_TOKEN, payload)
        if st3 in (200, 201):
            await interaction.followup.send(
                f"タグを作成しました: {repo} {target_branch}@{sha[:7]} → {tag}"
            )
            return

        # 422 if already exists
        if st3 == 422 and body3 and "Reference already exists" in body3:
            await interaction.followup.send(f"作成失敗: タグ '{tag}' は既に存在します")
            return

        await interaction.followup.send(f"作成失敗: {st3}\n{(body3 or '')[:800]}")
