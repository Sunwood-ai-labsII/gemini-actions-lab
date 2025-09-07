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

### Discord でのチャット例

以下は、実際に Discord 上でボットに話しかけて Issue を作成する際の例です。

- 1行で完結（タイトルをダブルクオートで囲む）

```
!issue Sunwood-ai-labsII/gemini-actions-lab "バグ: セーブできない" 再現手順を書きます。 #bug #p2 +your-github-username
```

- 複数行で本文をしっかり書く（1行目がタイトル、2行目以降が本文）

```
!issue Sunwood-ai-labsII/gemini-actions-lab
エディタがクラッシュする
特定のファイルを開いた直後にクラッシュします。
再現手順:
1. プロジェクトを開く
2. settings.json を開く
3. 5秒後にクラッシュ
#bug #crash +your-github-username
```

- ラベルやアサインを省略してシンプルに

```
!issue Sunwood-ai-labsII/gemini-actions-lab "ドキュメントを更新" README の手順が古いので更新してください。
```

ヒント:
- 既定のプレフィックスは `!issue` です。変更したい場合は環境変数 `DISCORD_MESSAGE_PREFIX` を設定してください。
- ボットは作成に成功すると Issue の URL を返信します。メッセージへのリンク（jump URL）は本文末尾に自動で記録されます。
- ギルド（サーバー）内でボットがメッセージ本文を読むには、Developer Portal で「Message Content Intent」を ON にしてください（下記「Discord 設定（特権インテント）」参照）。

## 実装
- `bot.py`: Discord メッセージをパースし、GitHub API (`POST /repos/{owner}/{repo}/issues`) に直接作成
- 依存: `discord.py`
- ビルド: `Dockerfile`（uv インストール → `uv sync` → `uv run bot.py`）

## Discord 設定（特権インテント）
- 本ボットはメッセージ本文を読むため、Discord の「Message Content Intent（特権インテント）」が必要です。
- 設定手順:
  - https://discord.com/developers/applications で対象アプリを開く
  - 左メニュー「Bot」→ Privileged Gateway Intents → 「MESSAGE CONTENT INTENT」を ON
  - 「Save Changes」で保存
- 反映後、コンテナを再起動してください（例: `docker compose up -d --build` または `docker-compose up --build`）。

## トラブルシューティング
- 起動時に以下のエラーが出る場合:
  - `discord.errors.PrivilegedIntentsRequired: ... requesting privileged intents ... enable the privileged intents ...`
  - 上記「Discord 設定（特権インテント）」の手順で「Message Content Intent」を有効化してください。
- 応急処置（動作制限あり）:
  - `bot.py` の `intents.message_content = True` を外す/`False` にすると接続自体は通りますが、ギルド内のメッセージ本文を読めず、本ボットのコマンドは動作しません。
- 代替案:
  - スラッシュコマンドに移行すると、Message Content Intent なしでも運用できます（実装変更が必要）。
