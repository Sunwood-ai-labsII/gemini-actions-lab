<div align="center">

![Image](https://raw.githubusercontent.com/Sunwood-ai-labsII/gemini-actions-lab/refs/heads/main/docs/gemini-actions-labs.png)


# Gemini Actions Lab

<a href="./README.md"><img src="https://img.shields.io/badge/English-Readme-blue?style=for-the-badge&logo=github&logoColor=white" alt="English" /></a>
<a href="./README.ja.md"><img src="https://img.shields.io/badge/日本語-Readme-red?style=for-the-badge&logo=github&logoColor=white" alt="日本語" /></a>
<img src="https://img.shields.io/badge/GitHub%20Actions-AI-blue?style=for-the-badge&logo=github-actions&logoColor=white" alt="GitHub Actions" />
<img src="https://img.shields.io/badge/Gemini-AI-4285F4?style=for-the-badge&logo=google-gemini&logoColor=white" alt="Gemini" />
[![PyPI](https://img.shields.io/pypi/v/gemini-actions-lab-cli?style=for-the-badge)](https://pypi.org/project/gemini-actions-lab-cli/)

[![💬 Gemini CLI](https://github.com/Sunwood-ai-labsII/gemini-actions-lab/actions/workflows/gemini-cli.yml/badge.svg)](https://github.com/Sunwood-ai-labsII/gemini-actions-lab/actions/workflows/gemini-cli.yml)


</div>

---

## 📖 概要

このリポジトリは、GoogleのGemini AIをGitHub Actionsと統合するための実験室およびショーケースとして機能します。生成AIの力を利用して、さまざまなリポジトリ管理タスクを自動化する方法を示します。

### 🎯 主な機能
- **AIによる自動化**: Geminiを活用して、Issueのトリアージ、プルリクエストのレビューなどのタスクを処理します。
- **CLIライクな対話**: Issueのコメントから直接AIアシスタントと対話します。
- **拡張可能なワークフロー**: 独自のプロジェクトに合わせてワークフローを簡単に適応およびカスタマイズできます。

---

## 🤖 ワークフロー概要

![](https://raw.githubusercontent.com/Sunwood-ai-labsII/gemini-actions-lab/refs/heads/main/docs/gal-architecture.png)

このリポジトリには、以下のGitHub Actionsワークフローが含まれています（詳細は [.github/workflows/architecture.md](.github/workflows/architecture.md) を参照）：

- `gemini-cli.yml`: 英語CLI。Issue/PR/コメント/手動でAIコマンドを実行
- `gemini-jp-cli.yml`: 日本語CLI。Issue/PR/コメント/手動でAIコマンドを実行
- `gemini-pr-review.yml`: PRレビュー自動化（MCP GitHubサーバー経由でコメント）
- `gemini-issue-automated-triage.yml`: 新規/更新Issueの自動トリアージ
- `gemini-issue-scheduled-triage.yml`: 定期スキャンで未トリアージIssueを一括処理
- `imagen4-issue-trigger-and-commit.yml`: イシュー由来の画像生成→コミット
- `imagen4-generate-and-commit.yml`: 手動/ディスパッチで画像生成→コミット
- `gemini-release-notes.yml`: リリース画像生成とリリースノートの自動作成
- `static-site.yml`: リポジトリ内容をGitHub Pagesに公開
- `sync-to-report-gh.yml`: 旧テンプレ（現状は参考用）

ワークフローの構成・相互関係・実装詳細は、[.github/workflows/architecture.md](.github/workflows/architecture.md) に集約しています。

---

## 🏗️ アーキテクチャ
アーキテクチャ図やワークフローの詳細な説明は、[.github/workflows/architecture.md](.github/workflows/architecture.md) を参照してください。

### 💬 Discord Issue Bot（任意）
- Discord から GitHub Issue を作成する最小ボット
- `discord-issue-bot/.env` にローカルでトークン設定（リポジトリには含めない）
- 起動例: `docker compose -f docker-compose.yaml up -d --build`

## 📸 スクリーンショットと例

### 🤖 CLIの対話例
Issueを作成し、`@gemini-cli-jp /help`とコメントして、利用可能なコマンドを確認します:

```
@gemini-cli-jp /help
```

AIアシスタントが利用可能なコマンドと使用例を返信します。

 

### 💬 対話の例

**コードレビューのリクエスト:**
```
@gemini-cli-jp /review-pr
このプルリクエストをレビューし、改善点を提案してください
```

**Issueのトリアージ:**
```
@gemini-cli-jp /triage
このIssueを分析し、適切なラベルと担当者を提案してください
```

---

## 🚀 インストールとセットアップ

### 前提条件
- リポジトリ作成権限のあるGitHubアカウント
- Google AI StudioのGemini APIキー
- GitHub Actionsの基本的な理解

### クイックスタート
1. **このリポジトリをフォーク**して、自分のGitHubアカウントにコピーします
2. リポジトリの設定で**GitHubシークレットを設定**します:
   - `GEMINI_API_KEY`: あなたのGemini APIキー
   - `GITHUB_TOKEN`: (自動的に提供されます)
3. `.github/workflows/`からあなたのリポジトリに**ワークフローファイルをコピー**します
4. あなたのニーズに合わせて**ワークフローをカスタマイズ**します
5. Issueを作成し、`@gemini-cli-jp /help`とコメントして**セットアップをテスト**します

---

## 🛠️ gemini-actions-lab CLI

リポジトリに付属する `gemini-actions-lab-cli`（エイリアス: `gal`）を使うと、シークレット同期やテンプレートワークフローの取得をコマンド一発で実行できます。

### インストール

PyPI から直接インストールできます。

```bash
pip install gemini-actions-lab-cli
```

ローカル開発でソースを同期したい場合は `uv` によるセットアップもサポートしています。

```bash
uv sync
```

### シークレットの同期

`.secrets.env`（任意のファイルを `--env-file` で指定可能）に定義した値を、リポジトリシークレットへ一括で作成・更新します。

```bash
gal sync-secrets --repo <owner>/<repo> --env-file path/to/.secrets.env
```

- コマンド実行ディレクトリの `.env` ファイルは自動的に読み込まれ、`GITHUB_TOKEN` など CLI 実行に必要な環境変数を設定できます。
- リポジトリへ同期したい secrets は `.secrets.env` に分離してください（任意のファイルを `--env-file` で指定可）。
- `GITHUB_TOKEN` 環境変数、または `--token` オプションで GitHub の個人アクセストークンを指定してください。

### 🚀 クイックスタート

よく使う同期コマンドは下記のとおりです（Pages 連携とトップページのコピー込み）。

```bash
gal sync-workflows \
  --repo Sunwood-ai-labs/demo-001 \
  --destination . \
  --clean \
  --enable-pages-actions \
  --include-index
```

> `uv run` を利用して開発用に実行する場合は、`uv run gal ...` と置き換えてください。

オプションの詳細やその他のユースケースは `src/README.md` を参照してください。

---

## 📁 ディレクトリ構造

```
.
├── .github/
│   └── workflows/
│       ├── architecture.md
│       ├── gemini-cli.yml
│       ├── gemini-jp-cli.yml
│       ├── gemini-pr-review.yml
│       ├── gemini-issue-automated-triage.yml
│       ├── gemini-issue-scheduled-triage.yml
│       ├── imagen4-issue-trigger-and-commit.yml
│       ├── imagen4-generate-and-commit.yml
│       ├── gemini-release-notes.yml
│       ├── static-site.yml
│       └── sync-to-report-gh.yml
├── discord-issue-bot/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── docker-compose.yaml
│   └── bot.py
├── .gitignore
├── LICENSE
└── README.md
```

---



## 🤖 Discord Issue Bot

Discord から直接 GitHub Issue を作成する最小ボットの詳細なドキュメントは、以下を参照してください。

- ドキュメント: [discord-issue-bot/README.md](discord-issue-bot/README.md)

## 📝 ライセンス

このプロジェクトは、[LICENSE](LICENSE)ファイルの条件に基づいてライセンスされています。

---

© 2025 Sunwood-ai-labsII


---
