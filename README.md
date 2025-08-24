
![](https://github.com/user-attachments/assets/e8fe7c3c-a8d8-4165-86a1-86b9f433f9b3)

<div align="center">

# Daily Report Hub Template

<img src="https://img.shields.io/badge/GitHub%20Actions-CICD-blue?style=for-the-badge&logo=github-actions&logoColor=white" alt="GitHub Actions" />
<img src="https://img.shields.io/badge/Bash-4EAA25?style=for-the-badge&logo=gnubash&logoColor=white" alt="Bash" />
<a href="https://github.com/Sunwood-ai-labsII/daily-report-hub">
  <img src="https://img.shields.io/badge/daily--report--hub-PANDA-00D4AA?style=for-the-badge&logo=github&logoColor=white" alt="daily-report-hub PANDA" />
</a>

</div>


---

## 📖 概要

このリポジトリは、**Daily Report Hubのテンプレートリポジトリ**です。このテンプレートからリポジトリを作成すると、自動で日報生成・同期機能が有効になります。

### 🎯 主な用途
- 日報自動生成機能を必要とするプロジェクトのテンプレート
- 集約用リポジトリ（daily-report-hub）への自動同期
- GitHub Actionsによる完全自動化されたレポート生成

### 🔄 運用方式
このテンプレートから作成されたリポジトリは、daily-report-hub本体のワークフローから**リモート実行**されるスクリプトを使用して日報を生成・同期します。

---

## 🚩 このテンプレートの役割

### 🛠️ テンプレートとしての機能
- **自動セットアップ**: 日報生成機能の自動有効化
- **ワークフロー提供**: GitHub Actionsワークフローの自動適用
- **同期機能**: 集約用リポジトリへの自動同期機能
- **カスタマイズ**: 必要に応じた設定変更の容易性

### 📦 提供される機能
- Gitのコミット履歴・差分から日報（Markdown形式）を自動生成
- 週単位・日単位でレポートを整理
- 別リポジトリ（daily-report-hub）へPRベースで自動同期
- プルリクエストの自動承認・自動マージ（設定可）
- Docusaurus用のディレクトリ・ナビゲーション構造も自動生成

---

## ⚙️ ワークフロー概要

### 🔄 自動化フロー図

```mermaid
graph TB
    A[開発者のコード<br/>commit/push] --> B[GitHub Actions<br/>ワークフロー]
    B --> C[レポート生成<br/>Markdown]
    C --> D[ファイル同期<br/>クローン]
    D --> E[PR作成・承認<br/>自動化可]
    E --> F[集約リポジトリ<br/>daily-report-hub]
```

### 📋 処理ステップ

1. **トリガー**: **GitHub Actions**がmainブランチへのpushやPRをトリガー
2. **データ収集**: リモートスクリプトで
   - 週情報の計算
   - Git活動の分析
   - Markdownレポートの生成
   - Docusaurus用ディレクトリ構造の作成
3. **同期処理**: 集約用リポジトリ（daily-report-hub）をクローンし、レポートをコピー
4. **PR処理**: PR作成・自動承認・自動マージ（設定に応じて自動化）

### ⚙️ 設定可能なオプション

| 設定 | 説明 | デフォルト値 |
|------|------|-------------|
| `WEEK_START_DAY` | 週の開始曜日（0=日曜日, 1=月曜日, ...） | `1`（月曜日） |
| `AUTO_APPROVE` | PR自動承認 | `true` |
| `AUTO_MERGE` | PR自動マージ | `true` |
| `CREATE_PR` | PR作成/直接プッシュ切り替え | `true` |

---

## 📝 主な機能

> [!NOTE]
> このテンプレートから作成されたリポジトリでは、以下の機能が自動で有効になります。

### 🔄 自動実行されるスクリプト（リモート）

- **週情報計算**
  週情報（週番号・開始日・終了日など）を計算し環境変数に出力

- **Git活動分析**
  Gitのコミット履歴・差分を分析し、生データファイルを生成

- **Markdownレポート生成**
  生データから日報・統計・差分などのMarkdownレポートを自動生成

- **Docusaurus構造作成**
  Docusaurus用のディレクトリ・_category_.jsonを自動生成

- **同期処理**
  集約リポジトリへPR作成・自動承認・自動マージ

---

## 🚀 使い方（クイックスタート）

### 📝 テンプレートからリポジトリを作成する方法

> [!TIP]
> このテンプレートから新しいリポジトリを作成すると、日報生成機能が自動で有効になります。

1. **このリポジトリをテンプレートとして使用**
   - リポジトリトップページの「Use this template」ボタンをクリック
   - リポジトリ名を入力して「Create repository from template」をクリック

2. **必要なシークレットを設定**
   - 作成したリポジトリの「Settings」→「Secrets and variables」→「Actions」に移動
   - 必要なシークレットを設定（下記参照）

3. **自動で日報生成が開始**
   - mainブランチにpushすると自動で日報生成＆集約リポジトリへ同期

### 🌐 ワークフローの実際の動作

> [!IMPORTANT]
> 作成されたリポジトリでは、以下のワークフローが自動で実行されます：

```yaml
name: 📊 デイリーレポートハブ同期 v2.3 (YUKIHIKO PR版 - 完全リモート実行)
on:
  push:
    branches: [main, master]
  pull_request:
    types: [opened, synchronize, closed]

env:
  WEEK_START_DAY: 1
  AUTO_APPROVE: true
  AUTO_MERGE: true
  CREATE_PR: true
  # リモートスクリプトの設定
  SCRIPTS_BASE_URL: https://raw.githubusercontent.com/Sunwood-ai-labsII/daily-report-hub_dev/main/.github/scripts

jobs:
  sync-data:
    runs-on: ubuntu-latest
    steps:
      - name: 📥 現在のリポジトリをチェックアウト
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: 📅 週情報を計算
        run: curl -LsSf ${SCRIPTS_BASE_URL}/calculate-week-info.sh | sh -s -- ${{ env.WEEK_START_DAY }}

      - name: 🔍 Git活動を分析
        run: curl -LsSf ${SCRIPTS_BASE_URL}/analyze-git-activity.sh | sh

      - name: 📝 Markdownレポートを生成
        run: curl -LsSf ${SCRIPTS_BASE_URL}/generate-markdown-reports.sh | sh

      - name: 📂 レポートハブをクローン
        env:
          GITHUB_TOKEN: ${{ secrets.GH_PAT }}
          REPORT_HUB_REPO: ${{ vars.REPORT_HUB_REPO || 'Sunwood-ai-labsII/daily-report-hub' }}
        run: |
          git config --global user.name "GitHub Actions Bot"
          git config --global user.email "actions@github.com"
          git clone https://x-access-token:${GITHUB_TOKEN}@github.com/${REPORT_HUB_REPO}.git daily-report-hub

      - name: 🏗️ Docusaurus構造を作成
        run: curl -LsSf ${SCRIPTS_BASE_URL}/create-docusaurus-structure.sh | sh

      - name: 🚀 YUKIHIKO権限でPR作成＆自動承認
        env:
          GITHUB_TOKEN_ORIGINAL: ${{ secrets.GH_PAT }}      # 承認用
          YUKIHIKO_TOKEN: ${{ secrets.GH_PAT_YUKIHIKO }}     # PR作成用
          GITHUB_TOKEN: ${{ secrets.GH_PAT }}              # デフォルト
          REPORT_HUB_REPO: ${{ vars.REPORT_HUB_REPO || 'Sunwood-ai-labsII/daily-report-hub' }}
        run: curl -LsSf ${SCRIPTS_BASE_URL}/sync-to-hub-gh.sh | sh
```

### 🔑 環境変数・シークレット設定

> [!WARNING]
> 以下のシークレットを設定しないと、日報同期機能が正常に動作しません。

#### 必須シークレット
- `GH_PAT`: GitHub Personal Access Token（リポジトリアクセス用）
- `GH_PAT_YUKIHIKO`: YUKIHIKO権限用のToken（PR作成・承認用）

#### オプション環境変数（ワークフロー内で設定）
- `REPORT_HUB_REPO`: レポートハブリポジトリ（デフォルト: `Sunwood-ai-labsII/daily-report-hub`）
- `WEEK_START_DAY`: 週の開始曜日（0=日曜日, 1=月曜日, ..., 6=土曜日、デフォルト: 1）
- `AUTO_APPROVE`: PR自動承認（true/false、デフォルト: true）
- `AUTO_MERGE`: PR自動マージ（true/false、デフォルト: true）
- `CREATE_PR`: PR作成フラグ（true=PR作成, false=直接プッシュ、デフォルト: true）

#### 環境変数設定例
各環境変数の詳細な設定は、ワークフローファイル内のコメントを参照してください。

### 📋 シークレット設定手順

> [!CAUTION]
> シークレットの漏洩には注意してください。GitHubリポジトリ内に直接記述しないでください。

1. リポジトリの「Settings」→「Secrets and variables」→「Actions」に移動
2. 「New repository secret」をクリックして各シークレットを追加
3. 以下のシークレットを設定：
   - `GH_PAT`: `repo`スコープを持つPersonal Access Token
   - `GH_PAT_YUKIHIKO`: `repo`スコープを持つPersonal Access Token（YUKIHIKO権限用）

---

## 📁 ディレクトリ構成例

> [!NOTE]
> このテンプレートから作成されたリポジトリの基本的な構成です。

```
.
├── .github/
│   └── workflows/
│       └── sync-to-report-gh.yml
├── .gitignore
├── LICENSE
├── README.md
└── [プロジェクト固有のファイル]
```

---

## 🛠️ 設定・カスタマイズ

> [!TIP]
> 必要に応じてワークフローファイルをカスタマイズできます。

- `.github/workflows/sync-to-report-gh.yml`
  - `WEEK_START_DAY`：週の開始曜日（0=日, 1=月, ...）
  - `AUTO_APPROVE`：PR自動承認
  - `AUTO_MERGE`：PR自動マージ
  - `CREATE_PR`：PR作成/直接push切替

- リモートスクリプトの詳細は開発リポジトリを参照

---

## 🔗 参考リンク

- [集約用日報ハブリポジトリ](https://github.com/Sunwood-ai-labsII/daily-report-hub)
- [開発リポジトリ（スクリプトソース）](https://github.com/Sunwood-ai-labsII/daily-report-hub_dev)
- [GitHub Actions公式ドキュメント](https://docs.github.com/ja/actions)
- [Docusaurus公式サイト](https://docusaurus.io/ja/)

---

## 📝 ライセンス

このテンプレートは [LICENSE](LICENSE) に基づいて提供されています。

---

© 2025 Sunwood-ai-labsII
