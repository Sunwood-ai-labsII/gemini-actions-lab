![](../docs/discord-issue-bot.png)

# Discord Issue Bot (Simple)

シンプルな Discord ボットです。Discord のチャットから直接 GitHub Issue を作成します（ワークフロー不要）。

本ボットは2通りの操作に対応しています:
- テキストコマンド: `!issue ...`（既存方式）
- スラッシュコマンド: `/issue`, `/issue_help`, `/tag_latest`（推奨）

補助機能:
- 最近使った `owner/repo` を自動記憶し、`repo` 引数でオートコンプリート候補に表示します。

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

ヒント:
- グローバルコマンドの反映には最大1時間かかることがあります。即時反映したい場合は環境変数 `DISCORD_GUILD_ID` を設定すると、そのギルドへスラッシュコマンドを即時同期します。
  - 例: `.env` に `DISCORD_GUILD_ID=123456789012345678` を追加
- `repo` 引数は直近で使ったリポジトリから補完できます（入力中に候補が表示されます）。

4) テキストコマンド（レガシー互換）

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

注意: スラッシュコマンド利用のみであれば「Message Content Intent」は不要です（本リポはレガシー `!issue` も併存のため既定で有効化しています）。

## 実装
- `bot.py`: 起動エントリ（Bot 初期化とコマンド登録）
- `app/` パッケージ: 本体コードを集約
  - `app/bot_client.py`: Discord クライアント本体（`on_ready`/`on_message` など）
  - `app/commands.py`: スラッシュコマンド定義（`/issue`, `/issue_help`, `/tag_latest`）
  - `app/parser.py`: レガシー `!issue` と入力パース（ラベル/アサイン）
  - `app/github_api.py`: GitHub API ヘルパー
  - `app/config.py`: 環境変数の読み取りと設定
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

### データ永続化（おすすめ）
- `docker-compose.yaml` で `./data:/data` をマウント済みです。
- 既定の保存先は `/data/history.json` に変更しました（コンテナ内パス）。
- ホスト側には `discord-issue-bot/data/history.json` として保存されます。

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

## サンプルプロンプト（そのまま利用可）
以下のテンプレートを Discord に貼り付けて送信すると、指定のリポジトリに Issue を作成できます。
必要に応じてリポジトリ名や本文を編集してください。区切りの `---` は別メッセージとして送る想定です。

```
!issue Sunwood-ai-labsII/gemini-actions-lab

サンプルアプリの作成

@gemini-cli exampleフォルダにTODOアプリを作成して

#example #demo

---
!issue Sunwood-ai-labsII/gemini-actions-lab

サンプルリポジトリの作成

@gemini-cli ghコマンドを使用して、和モダンなサイコロアプリをSunwood-ai-labsII のリポジトリに作成して
https://github.com/Sunwood-ai-labsII/gemini-actions-lab
をテンプレートリポジトリにして作成して

HTMLでアプリを実際に作成して
READMEも刷新してね

下記のコードでpagesをactionsから有効にして
 
```
curl -L -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $(gh auth token)" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/$(gh api user --jq .login)/my-site/pages \
  -d '{"build_type":"workflow"}'
```
 
#example
```

### 送信例（単発で送りたい場合）
- 例1（TODO アプリ作成依頼）
```
!issue Sunwood-ai-labsII/gemini-actions-lab
サンプルアプリの作成

@gemini-cli exampleフォルダにTODOアプリを作成して

#example #demo
```

- 例2（リポジトリ作成＋Pages 有効化メモ付き）
```
!issue Sunwood-ai-labsII/gemini-actions-lab
サンプルリポジトリの作成

@gemini-cli ghコマンドを使用して、和モダンなサイコロアプリをSunwood-ai-labsII のリポジトリに作成して
https://github.com/Sunwood-ai-labsII/gemini-actions-lab
をテンプレートリポジトリにして作成して

HTMLでアプリを実際に作成して
READMEも刷新してね

下記のコードでpagesをactionsから有効にして

curl -L -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $(gh auth token)" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  https://api.github.com/repos/$(gh api user --jq .login)/my-site/pages \
  -d '{"build_type":"workflow"}'

#example
```
