#!/usr/bin/env python3
import os
import re
import json
from urllib import request, error

import discord

DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")
GITHUB_API = os.environ.get("GITHUB_API", "https://api.github.com")

PREFIX = os.environ.get("DISCORD_MESSAGE_PREFIX", "!issue").strip()


def http_post(url: str, token: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, body
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, body


def parse(content: str):
    """
    Syntax (simple):
      !issue owner/repo "Title" Body text ... #label1 +assignee1
    or  !issue owner/repo Title on first line\nBody from second line ... #bug
    Returns: dict(repo, title, body, labels[], assignees[])
    """
    text = content.strip()
    if text.lower().startswith(PREFIX.lower()):
        text = text[len(PREFIX):].strip()

    # Find first owner/repo token
    m_repo = re.search(r"\b([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)\b", text)
    repo = m_repo.group(1) if m_repo else ""
    if not repo:
        return {"error": "リポジトリ (owner/repo) を含めてください: 例) !issue owner/repo \"タイトル\" 本文"}

    # Remove repo from text before parsing title/body
    text_wo_repo = (text[:m_repo.start()] + text[m_repo.end():]).strip() if m_repo else text

    # Title/body parsing
    m = re.match(r'^"([^"]+)"\s*(.*)$', text_wo_repo, flags=re.S)
    if m:
        title = m.group(1).strip()
        body = m.group(2).strip()
    else:
        lines = text_wo_repo.splitlines()
        title = lines[0].strip() if lines else "New Issue"
        body = "\n".join(lines[1:]).strip()

    # Extract labels (#label) and assignees (+user)
    labels = [tok[1:].strip() for tok in re.findall(r'(#[\w\-/\.]+)', text_wo_repo)]
    assignees = [tok[1:].strip() for tok in re.findall(r'(\+[A-Za-z0-9-]+)', text_wo_repo)]

    # Clean tokens from body
    body = re.sub(r'(#[\w\-/\.]+)', '', body)
    body = re.sub(r'(\+[A-Za-z0-9-]+)', '', body).strip()

    return {
        "repo": repo,
        "title": title or "New Issue",
        "body": body or "(no body)",
        "labels": list(dict.fromkeys(labels)),
        "assignees": list(dict.fromkeys(assignees)),
    }


def build_body_with_footer(body: str, author: str, source_url: str | None):
    parts = [body]
    meta = []
    if author:
        meta.append(f"Reported via Discord by: {author}")
    if source_url:
        meta.append(f"Source: {source_url}")
    if meta:
        parts.append("\n\n---\n" + "\n".join(meta))
    return "".join(parts)


class Bot(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user} | prefix={PREFIX}")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        content = (message.content or "").strip()
        if not content.lower().startswith(PREFIX.lower()):
            return

        if not GITHUB_TOKEN:
            await message.reply("GITHUB_TOKEN が未設定です", mention_author=False)
            return

        parsed = parse(content)
        if "error" in parsed:
            await message.reply(parsed["error"], mention_author=False)
            return

        repo = parsed["repo"]
        url = f"{GITHUB_API}/repos/{repo}/issues"
        payload = {"title": parsed["title"], "body": build_body_with_footer(parsed["body"], str(message.author), message.jump_url)}
        if parsed["labels"]:
            payload["labels"] = parsed["labels"]
        if parsed["assignees"]:
            payload["assignees"] = parsed["assignees"]

        status, resp = http_post(url, GITHUB_TOKEN, payload)
        try:
            data = json.loads(resp) if resp else {}
        except Exception:
            data = {}
        if status in (200, 201):
            issue_url = data.get("html_url", "")
            number = data.get("number", "?")
            await message.reply(f"Issueを作成しました: #{number} {issue_url}", mention_author=False)
        else:
            await message.reply(f"作成失敗: {status}\n{resp[:1500]}", mention_author=False)


def main():
    if not DISCORD_TOKEN:
        raise SystemExit("DISCORD_BOT_TOKEN が未設定です")
    intents = discord.Intents.default()
    intents.message_content = True
    Bot(intents=intents).run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()

