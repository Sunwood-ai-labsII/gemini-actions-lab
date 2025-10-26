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
| `--include-index` | テンプレート直下の `index.html` を同期し、Pages のトップページとして配置します。 |
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
- `--include-index` と併用することでトップページ (`index.html`) も反映されます。

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
