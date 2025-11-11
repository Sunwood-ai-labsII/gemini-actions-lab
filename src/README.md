# gemini-actions-lab CLI ユースケース集

このドキュメントでは、`uv run gal ...` コマンドの実践的な使い方をまとめています。メイン README ではクイックスタートのみを掲載し、詳細はこちらに集約しています。

## 🔑 事前準備
- 依存関係の同期: `uv sync`
- `.env` に CLI 実行用の環境変数 (例: `GITHUB_TOKEN`) をセットすると自動で読み込まれます。
- リモートリポジトリに書き込む場合は、十分な権限を持つトークン (`GH_PAT` など) を用意してください。

## 🗂️ ローカルにテンプレートを同期したい
```bash
uv run gal sync-workflows --destination . --clean
```

- `--template-repo` でテンプレートを差し替え可能です。
- `--ref` でタグやブランチを固定できます。
- `.github` 配下の既存ファイルはデフォで温存されるので安心だよ。すべて上書きしたいときは `--overwrite-github` を付けてね。
- `--clean` を付けると既存の `.github` ディレクトリを削除してから展開します。

## 🌐 リモートリポジトリに直接同期したい
```bash
uv run gal sync-workflows \
  --repo <owner>/<repo> \
  --clean \
  --enable-pages-actions \
  --include-index
```

| オプション | 説明 |
| --- | --- |
| `--repo` | `.github` ディレクトリを指定リポジトリへ直接コミットします。 |
| `--branch` | 書き込み先ブランチを変更したい場合に指定します (未指定ならデフォルトブランチ)。 |
| `--message` | コミットメッセージを上書きします。デフォルトは `✨ Sync .github directory ...`。 |
| `--enable-pages-actions` | GitHub Pages のビルドソースを Actions に設定し、公開 URL をリポジトリの "Website" 欄へ反映します。 |
| `--include-index` | テンプレート直下の `index.html` を同期し、存在しない場合のみコピーします。 |
| `--overwrite-index` | `--include-index` と併用し、既存の `index.html` も上書きしたいときに指定します。 |
| `--overwrite-github` | `.github` 配下の既存ファイルもテンプレートで上書きしたいときに指定します。 |
| `--clean` | 既存の `.github` ディレクトリや関連ファイルを削除したい場合に使用します。 |
| `--force` | ブランチのリファレンス更新を強制したい場合に指定します。 |

> メモ: `--destination` は `--repo` と同時に指定しても無視されます。ローカルへの展開は行われません。

## 🔐 Secrets を同期したい
```bash
uv run gal sync-secrets --repo <owner>/<repo> --env-file path/to/.secrets.env
```

- `.secrets.env` には同期したいキー/値を記述してください。
- `.env` (実行ディレクトリ) に設定した `GITHUB_TOKEN` などは自動で読み込まれます。
- `--token` を指定すると明示的な PAT を利用できます。

## 🤖 AI エージェントのガイドラインファイルを同期したい
```bash
uv run gal sync-agent --repo <owner>/<repo>
```

- カレントディレクトリにある `Claude.md`, `GEMINI.md`, `AGENT.md` をリポジトリのルートに同期します。
- 存在しないファイルは自動的にスキップされます。
- `.env` (実行ディレクトリ) に設定した `GITHUB_TOKEN` などは自動で読み込まれます。
- `--token` を指定すると明示的な PAT を利用できます。

| オプション | 説明 |
| --- | --- |
| `--repo` | (必須) 同期先のリポジトリ (`owner/name` 形式)。 |
| `--branch` | 書き込み先ブランチを変更したい場合に指定します (未指定ならデフォルトブランチ)。 |
| `--message` | コミットメッセージを上書きします。デフォルトは `🤖 Sync AI agent guideline files ...`。 |
| `--token` | GitHub personal access token (未指定なら `GITHUB_TOKEN` 環境変数を使用)。 |
| `--force` | ブランチのリファレンス更新を強制したい場合に指定します。 |

**使用例:**
```bash
# デフォルトブランチに同期
uv run gal sync-agent --repo Sunwood-ai-labs/my-repo

# 特定のブランチに同期
uv run gal sync-agent --repo Sunwood-ai-labs/my-repo --branch develop

# カスタムメッセージで同期
uv run gal sync-agent --repo Sunwood-ai-labs/my-repo --message "docs: update AI agent guidelines"
```

## 🧾 Pages + index.html を含む同期の例
```bash
uv run gal sync-workflows \
  --repo Sunwood-ai-labs/demo-001 \
  --destination . \
  --clean \
  --enable-pages-actions \
  --include-index
```

- Pages が有効化されていないリポジトリでも、`--enable-pages-actions` で Actions デプロイに切り替わります。
- `--include-index` と併用することでトップページ (`index.html`) も反映されます (既存のファイルは保持されます)。
- `.github` 内の既存ワークフローを守りたい場合はそのままで OK。テンプレートで更新したいときは `--overwrite-github` を足してね。
- 既存の `index.html` を置き換えたい場合は `--overwrite-index` も指定してください。

## 🎯 特定のワークフローだけコピーしたい（新機能！）

`.github/workflows_remote` または `.github/workflows` から、指定したワークフローファイルだけを取得できます。全体を同期する必要がないときに便利だよ〜✨

### 単一ワークフローのコピー

```bash
# workflows_remote から特定のワークフローをコピー 🎯
uv run gal sync-workflows \
  --workflow gemini-release-notes-remote.yml \
  --use-remote \
  --destination .

# 通常の workflows から特定のワークフローをコピー
uv run gal sync-workflows \
  --workflow gemini-cli.yml \
  --destination .
```

### 複数ワークフローのコピー（NEW！✨）

```bash
# 複数のワークフローを一度にコピー 🎯
uv run gal sync-workflows \
  --workflows gemini-cli.yml gemini-jp-cli.yml pr-review-kozaki-remote.yml \
  --destination .
```

### プリセットの使用（NEW！✨）

よく使う組み合わせをプリセットとして定義できます。

```bash
# 利用可能なプリセット一覧を表示
uv run gal sync-workflows --list-presets

# プリセットを使ってワークフローをコピー
uv run gal sync-workflows --preset pr-review --destination .

# 新規リポジトリ用の基本セット
uv run gal sync-workflows --preset basic --destination .
```

**利用可能なプリセット:**

| プリセット名 | 説明 | 含まれるワークフロー |
| --- | --- | --- |
| `pr-review` | PR レビューワークフロー | Kozaki, Onizuka, Yukimura の3つ |
| `gemini-cli` | Gemini CLI ワークフロー | 英語版と日本語版 |
| `release` | リリース自動化 | リリースノート生成 |
| `imagen` | 画像生成 | Issue トリガーと手動実行 |
| `basic` | 新規リポジトリ向け基本セット | CLI + PR レビュー (Kozaki) |
| `full-remote` | すべてのリモートワークフロー | 全リモートワークフロー |
| `standard` | 標準プロダクション構成 | CLI, Release Articles, Release Notes, PR Review 3種, Static Site の7つ |

> **カスタムプリセットの追加**: プリセットは `src/gemini_actions_lab_cli/workflow_presets.yml` で管理されています。新しいプリセットを追加したい場合は、このYAMLファイルを編集してください✨

### リモートリポジトリに直接同期

```bash
# 単一ワークフロー
uv run gal sync-workflows \
  --workflow pr-review-kozaki-remote.yml \
  --use-remote \
  --repo Sunwood-ai-labs/my-repo \
  --overwrite-github

# 複数ワークフロー
uv run gal sync-workflows \
  --workflows gemini-cli.yml gemini-jp-cli.yml \
  --repo Sunwood-ai-labs/my-repo \
  --overwrite-github

# プリセット
uv run gal sync-workflows \
  --preset pr-review \
  --repo Sunwood-ai-labs/my-repo \
  --overwrite-github
```

| オプション | 説明 |
| --- | --- |
| `--workflow` | コピーしたいワークフローファイル名（単一） |
| `--workflows` | コピーしたいワークフローファイル名（複数、スペース区切り） |
| `--preset` | プリセット名（`--workflow` や `--workflows` より優先） |
| `--list-presets` | 利用可能なプリセット一覧を表示して終了 |
| `--use-remote` | `.github/workflows_remote` から優先的に取得。見つからない場合は `workflows` から自動フォールバック |

**動作の詳細:**
- `--workflow` または `--workflows` を指定すると、指定したファイルだけが `.github/workflows` にコピーされます
- `--preset` を使うと、事前定義された複数のワークフローをまとめてコピーできます
- `--use-remote` フラグがあると、`.github/workflows_remote` を優先的に探します
- `workflows_remote` に見つからない場合は、自動的に `.github/workflows` から取得します
- `--overwrite-github` フラグで既存ファイルの上書きが可能です

**使用例シナリオ:**
1. **PRレビューだけ導入したい**: `--preset pr-review` で3つのレビューワークフローをまとめて導入
2. **複数のワークフローを一度にコピー**: `--workflows` で必要なファイルを列挙
3. **リモートワークフローを試したい**: `--use-remote` で `workflows_remote` から取得
4. **新規リポジトリのセットアップ**: `--preset basic` で最小限の構成を一発導入
5. **既存ワークフローを更新したい**: `--overwrite-github` を追加して上書き

---

## 🧪 テストの実行

単体テストを実行するには、以下のコマンドを使用します：

```bash
# テストのみ実行
pytest tests/

# カバレッジレポート付きで実行
pytest tests/ --cov=gemini_actions_lab_cli --cov-report=term-missing

# 特定のテストファイルのみ実行
pytest tests/test_sync_agent.py -v
```

テスト依存関係のインストール：
```bash
pip install -e ".[test]"
```

---

困ったときは `uv run gal --help` または各サブコマンドに `--help` を付けて確認してください。
