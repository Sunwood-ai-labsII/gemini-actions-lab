![](../docs/discord-issue-bot.png)

# Discord Issue Bot (Simple)

シンプルな Discord ボットです。Discord のチャットから直接 GitHub Issue を作成します（ワークフロー不要）。

本ボットはスラッシュコマンドで操作します:
- `/issue`, `/issue_help`, `/tag_latest`, `/sync_env`, `/workflow_preset`, `/set_secret`, `/list_presets`

補助機能:
- 最近使った `owner/repo` を自動記憶し、`repo` 引数でオートコンプリート候補に表示します。
- 追加で、`DISCORD_REPO_SUGGEST_ACCOUNTS` に指定したアカウントのうち直近更新されたリポジトリも候補に含められます。

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
docker compose -f docker-compose.yaml up -d --build
docker compose -f docker-compose.yaml logs -f
```

3) スラッシュコマンド（おすすめ）

- `/issue`: GitHub Issue を作成（モーダル入力）
  - 引数: `repo`(owner/repo), `title`, `labels`(任意), `assignees`(任意), `example`(任意)
  - `example`: `example/` 配下のテンプレート md 名（オートコンプリート対応。例: `create_todo_app`）
  - 例: `/issue repo:owner/repo title:"バグ: 保存できない" labels:#bug #p2 assignees:+alice example:create_todo_app`

- `/issue_help`: `/issue` の使い方を表示（エフェメラルで表示）

- `/tag_latest`: 指定リポジトリの最新コミットに軽量タグを作成
  - 引数: `repo`(owner/repo), `tag`(作成したいタグ名), `branch`(任意; 省略時はデフォルトブランチ)
  - 例: `/tag_latest repo:owner/repo tag:v1.2.3`（デフォルトブランチ先頭に v1.2.3 を作成）
- `/sync_env`: `.env` ファイルの内容を GitHub Actions シークレット変数へ暗号化して同期（有効化時のみ表示）
  - 事前準備: `GITHUB_TOKEN` に `secrets:write` 相当の権限が必要、`DISCORD_ENV_SYNC_ENABLED=1` を設定
  - **セキュリティ**: 値は GitHub の公開鍵で暗号化されてから送信され、シークレット変数として安全に保存されます
  - 引数: `repo`(owner/repo, 任意), `env_file`(任意), `include_keys`/`exclude_keys`(任意), `dry_run`(任意)
    - `include_keys`: 同期対象を絞りたいときにカンマ区切りで指定（未指定なら全キー）。例: `include_keys:SECRET_API_KEY,DISCORD_TOKEN`
    - `exclude_keys`: 除外したいキーをカンマ区切りで指定。例: `exclude_keys:TEST_TOKEN`
    - `dry_run`: `true` を指定するとプレビューのみ実行し、値の先頭4文字までを一覧表示
  - 実行時は専用スレッドに進捗と結果を投稿し、作成/更新/失敗したキーを一覧化します
  - 例: `/sync_env repo:owner/repo env_file:.env.sync dry_run:true`

- `/list_presets`: 利用可能なワークフロープリセットの一覧を表示
  - 引数: なし
  - 例: `/list_presets` → `basic`, `standard`, `pr-review` などのプリセットと説明を表示

- `/workflow_preset`: プリセットからワークフローをリポジトリに同期
  - 引数: `repo`(owner/repo), `preset`(プリセット名), `template_repo`(任意), `dry_run`(任意), `overwrite`(任意)
  - プリセット: `basic`, `standard`, `pr-review`, `gemini-cli`, `release`, `imagen` など
  - テンプレートリポジトリ: デフォルトは `Sunwood-ai-labsII/gemini-actions-lab`
  - 例: `/workflow_preset repo:owner/repo preset:basic` → 基本的なワークフローをリポジトリに追加
  - 例: `/workflow_preset repo:owner/repo preset:standard dry_run:true` → プレビューのみ表示

- `/set_secret`: GitHub Actions のシークレット変数を個別に設定
  - 引数: `repo`(owner/repo), `key`(シークレットのキー名), `value`(シークレットの値)
  - **セキュリティ**: 値は GitHub の公開鍵で暗号化されてから送信されます
  - 例: `/set_secret repo:owner/repo key:GEMINI_API_KEY value:your-secret-value`
  - 注意: このコマンドは ephemeral（非公開）で実行され、あなただけに結果が表示されます

ヒント:
- グローバルコマンドの反映には最大1時間かかることがあります。即時反映したい場合は環境変数 `DISCORD_GUILD_ID` を設定すると、そのギルドへスラッシュコマンドを即時同期します。
  - 例: `.env` に `DISCORD_GUILD_ID=123456789012345678` を追加
- `repo` 引数は直近で使ったリポジトリから補完できます（入力中に候補が表示されます）。

## 実装
- `bot.py`: 起動エントリ（Bot 初期化とコマンド登録）
- `app/` パッケージ: 本体コードを集約
  - `app/bot_client.py`: Discord クライアント本体（`on_ready`/`on_message` など）
  - `app/commands.py`: スラッシュコマンド定義（`/issue`, `/issue_help`, `/tag_latest`, `/sync_env`, `/workflow_preset`, `/set_secret`, `/list_presets`）
  - `app/parser.py`: レガシー `!issue` と入力パース（ラベル/アサイン）
  - `app/github_api.py`: GitHub API ヘルパー
  - `app/config.py`: 環境変数の読み取りと設定
  - `app/env_sync.py`: `/sync_env` コマンド用の .env 読み込みと GitHub 変数同期ヘルパー
  - `app/workflow_sync.py`: `/workflow_preset` コマンド用のワークフロープリセット同期ヘルパー
  - `app/store.py`: リポジトリ履歴管理（最近使ったリポジトリの記録）
  - `app/utils.py`: 本文末尾のメタ情報付加などのユーティリティ

### 本文テンプレート（example/）
- `example/` 配下の `*.md` をテンプレートとして利用できます。
- `/issue` の `example` 引数でテンプレート名（拡張子なし）を指定すると、モーダル表示時に本文に事前入力されます。
- 入力欄の制限に合わせ、長文は最大 4000 文字で切り詰められます。

依存: `discord.py`

ビルド: `Dockerfile`（uv インストール → `uv sync` → `uv run bot.py`）

### 任意設定（履歴の保存先）
- `DISCORD_ISSUE_BOT_HISTORY`: 最近使ったリポジトリの保存先ファイルパス。
  - 既定: `/data/history.json`（コンテナ内; ホストでは `discord-issue-bot/data/history.json`）
  - 例: `.env` に `DISCORD_ISSUE_BOT_HISTORY=/data/history.json`

### 環境変数同期コマンド（任意）
- `DISCORD_ENV_SYNC_ENABLED=1` を設定すると `/sync_env` コマンドが有効化されます（既定は無効）
- `DISCORD_ENV_SYNC_FILE`: 同期対象の `.env` ファイル（既定: `.env`）
- `DISCORD_ENV_SYNC_REPO`: 既定の同期先リポジトリ。未指定時は履歴の先頭を利用
- `DISCORD_ENV_SYNC_ALLOWED_USERS`: `,` 区切りの Discord ユーザー ID を指定すると実行権限を限定可能
- `/sync_env` は GitHub Actions シークレット API を利用し、値を暗号化してから送信します（値は表示しません）
- **重要**: 値は GitHub の公開鍵で暗号化されるため、PyNaCl ライブラリが必要です（依存関係に含まれています）

### リポジトリアウトコンプリート（任意強化）
- `DISCORD_REPO_SUGGEST_ACCOUNTS`: 例 `Sunwood-ai-labs,Sunwood-ai-labsII`。指定したアカウントのリポジトリを候補に追加
- `DISCORD_REPO_SUGGEST_LOOKBACK_DAYS`: 例 `7`。何日以内に作成・更新されたリポジトリを候補とみなすか
- 候補はローカル履歴と統合され、API 呼び出し結果は数分間キャッシュされます

### データ永続化（おすすめ）
- `docker-compose.yaml` で `./data:/data` をマウント済みです。
- 既定の保存先は `/data/history.json` に変更しました（コンテナ内パス）。
- ホスト側には `discord-issue-bot/data/history.json` として保存されます。
