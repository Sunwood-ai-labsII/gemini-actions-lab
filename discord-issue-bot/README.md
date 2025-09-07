# Discord Issue Bot (Simple)

シンプルな Discord ボットです。Discord のチャットから直接 GitHub Issue を作成します（ワークフロー不要）。

必要な環境変数は 2 つだけ:
- `DISCORD_BOT_TOKEN`
- `GITHUB_TOKEN`（プライベートリポの場合は `repo` 権限推奨）

## 使い方

1) 環境変数を設定

```bash
export DISCORD_BOT_TOKEN=xxxx
export GITHUB_TOKEN=ghp_xxx
```

2) Docker で起動（uv sync により依存を自動セットアップ）

```bash
cd discord-issue-bot
docker compose -f compose.yaml up -d --build
docker compose -f compose.yaml logs -f
```

3) Discord で投稿（例）

```
!issue owner/repo "バグ: 保存できない" 再現手順… #kind/bug #priority/p2 +maki
```

書式:
- プレフィックス: `!issue`
- 最初に `owner/repo` を必ず含める
- タイトルは `"ダブルクオート"` で囲むと1行で指定可能（未指定なら1行目がタイトル、2行目以降が本文）
- `#label` でラベル、`+user` でアサイン

## 実装
- `bot.py`: Discord メッセージをパースし、GitHub API (`POST /repos/{owner}/{repo}/issues`) に直接作成
- 依存: `discord.py`
- ビルド: `Dockerfile`（uv インストール → `uv sync` → `uv run bot.py`）

