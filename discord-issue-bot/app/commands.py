import json
import discord
from discord import app_commands

from . import config
from .env_sync import (
    SyncResult,
    filter_variables,
    load_env_file,
    sync_repository_variables,
)
from .github_api import http_get, http_post
from .parser import parse_labels_input, parse_assignees_input
from .utils import build_body_with_footer
from .store import recent_repos, remember_repo
from .workflow_sync import (
    list_available_presets,
    sync_workflow_preset,
    WorkflowSyncError,
    load_workflow_presets,
)
from .branch_sync import (
    sync_branches,
    BranchSyncError,
    BranchSyncResult,
)
from .doc_sync import (
    sync_docs as sync_docs_func,
    DocSyncError,
    DocSyncResult,
    DEFAULT_DOC_FILES,
)
from pathlib import Path


# --- Example templates helper ---
EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "example"
DEFAULT_TEMPLATE_REPO = "Sunwood-ai-labsII/gemini-actions-lab"


def list_example_names() -> list[str]:
    try:
        return [p.stem for p in EXAMPLE_DIR.glob("*.md")]
    except Exception:
        return []


def load_example_text(name: str) -> str:
    if not name:
        return ""
    try:
        # allow "example01" or "example01.md"
        candidates = [EXAMPLE_DIR / name, EXAMPLE_DIR / f"{name}.md"]
        for c in candidates:
            if c.is_file():
                return c.read_text(encoding="utf-8")
        # fallback: exact stem match
        for p in EXAMPLE_DIR.glob("*.md"):
            if p.stem == name:
                return p.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


ENV_NO_KEYS_GUIDANCE = [
    "同期対象の変数がありません。以下を確認してください:",
    "• `.env` に値が入っているか",
    "• `include_keys` を指定した場合はキー名が一致しているか",
    "• `exclude_keys` により除外されていないか",
    "（どちらの引数も任意です。未入力ならすべてのキーが対象になります）",
]


def _env_no_keys_message() -> str:
    return "\n".join(ENV_NO_KEYS_GUIDANCE)


def _split_env_keys(raw: str) -> list[str]:
    if not raw:
        return []
    tokens: list[str] = []
    for chunk in raw.replace(",", " ").split():
        part = chunk.strip()
        if part:
            tokens.append(part)
    return tokens


def _mask_value(value: str) -> str:
    if not value:
        return "(空)"
    preview = value[:4]
    return f"{preview}{'…' if len(value) > 4 else ''}"


def _format_env_dry_run_text(repo: str, env_path: Path, filtered: dict[str, str]) -> str:
    names = sorted(filtered.keys())
    lines = [
        "🔍 ドライラン結果",
        f"同期先: `{repo}`",
        f"ファイル: `{str(env_path)}`",
        f"対象キー数: {len(names)}",
    ]
    if names:
        lines.append("対象キー一覧:")
        for name in names:
            lines.append(f"- {name}: {_mask_value(filtered[name])}")
    else:
        lines.append("対象キー: (なし)")
    return "\n".join(lines)


def _format_env_result_blocks(
    repo: str,
    env_path: Path,
    filtered: dict[str, str],
    result: SyncResult,
) -> list[str]:
    blocks: list[str] = []

    def masked(name: str) -> str:
        return _mask_value(filtered.get(name, ""))

    if result.created:
        lines = ["✨ 新規作成したシークレット:"]
        lines.extend(f"- {name}: {masked(name)}" for name in result.created)
        blocks.append("\n".join(lines))

    if result.updated:
        lines = ["✅ 更新/作成したシークレット:"]
        lines.extend(f"- {name}: {masked(name)}" for name in result.updated)
        blocks.append("\n".join(lines))

    if result.failed:
        lines = ["⚠️ 失敗したキー:"]
        for name, status, snippet in result.failed:
            detail = f"{name} ({status})"
            if snippet:
                detail += f": {snippet}"
            lines.append(f"- {detail}")
        blocks.append("\n".join(lines))

    summary = [
        f"同期先: `{repo}`",
        f"ファイル: `{str(env_path)}`",
        f"対象キー数: {len(filtered)}",
        f"作成: {result.created_count}",
        f"更新: {result.updated_count}",
        f"失敗: {result.failed_count}",
    ]
    blocks.append("\n".join(summary))

    status_line = "✅ 同期処理が完了しました" if result.failed_count == 0 else "⚠️ 一部のキーでエラーが発生しました"
    blocks.append(status_line)
    return blocks


def _format_workflow_dry_run_text(
    result: "WorkflowSyncResult", repo: str, preset: str, template_repo: str
) -> str:
    lines = [
        "🔍 ドライラン結果",
        f"同期先: `{repo}`",
        f"プリセット: `{preset}`",
        f"テンプレート: `{template_repo}`",
        f"対象ファイル数: {len(result.skipped)}",
    ]
    if result.skipped:
        lines.append("\n対象ファイル一覧:")
        for file in result.skipped:
            lines.append(f"- {file}")
    lines.append("\n✅ ドライランを完了しました（実際の変更はありません）")
    return "\n".join(lines)


def _format_workflow_summary_text(result: "WorkflowSyncResult", repo: str, preset: str) -> str:
    lines = [
        "✅ ワークフロー同期が完了しました",
        f"同期先: `{repo}`",
        f"プリセット: `{preset}`",
        "",
        f"✨ 書き込み: {result.success_count}",
        f"⏭️ スキップ: {result.skipped_count}",
        f"❌ 失敗: {result.failed_count}",
    ]
    if result.written:
        lines.append("\n書き込まれたファイル:")
        for file in result.written:
            lines.append(f"- {file}")
    if result.skipped:
        lines.append("\nスキップされたファイル（既存）:")
        for file in result.skipped:
            lines.append(f"- {file}")
    if result.failed:
        lines.append("\n失敗したファイル:")
        for file, error in result.failed:
            lines.append(f"- {file}: {error}")
    return "\n".join(lines)


def _format_branch_dry_run_text(result: BranchSyncResult, repo: str, branches: list[str]) -> str:
    lines = [
        "🔍 ドライラン結果",
        f"同期先: `{repo}`",
        f"対象ブランチ数: {len(branches)}",
    ]
    if result.created:
        lines.append("\n作成予定のブランチ:")
        for branch in result.created:
            lines.append(f"- {branch}")
    if result.skipped:
        lines.append("\nスキップ（既存）:")
        for branch in result.skipped:
            lines.append(f"- {branch}")
    lines.append("\n✅ ドライランを完了しました（実際の変更はありません）")
    return "\n".join(lines)


def _format_branch_summary_text(result: BranchSyncResult, repo: str) -> str:
    lines = [
        "✅ ブランチ同期が完了しました",
        f"同期先: `{repo}`",
        "",
        f"✨ 作成: {result.created_count}",
        f"⏭️ スキップ: {result.skipped_count}",
        f"❌ 失敗: {result.failed_count}",
    ]
    if result.created:
        lines.append("\n作成されたブランチ:")
        for branch in result.created:
            lines.append(f"- {branch}")
    if result.skipped:
        lines.append("\nスキップされたブランチ（既存）:")
        for branch in result.skipped:
            lines.append(f"- {branch}")
    if result.failed:
        lines.append("\n失敗したブランチ:")
        for branch, error in result.failed:
            lines.append(f"- {branch}: {error}")
    return "\n".join(lines)


def _format_doc_dry_run_text(result: DocSyncResult, repo: str, template_repo: str, doc_files: list[str]) -> str:
    lines = [
        "🔍 ドライラン結果",
        f"同期先: `{repo}`",
        f"テンプレート: `{template_repo}`",
        f"対象ファイル数: {len(doc_files)}",
    ]
    if result.skipped:
        lines.append("\n対象ファイル一覧:")
        for file in result.skipped:
            lines.append(f"- {file}")
    lines.append("\n✅ ドライランを完了しました（実際の変更はありません）")
    return "\n".join(lines)


def _format_doc_summary_text(result: DocSyncResult, repo: str) -> str:
    lines = [
        "✅ エージェント設定同期が完了しました",
        f"同期先: `{repo}`",
        "",
        f"✨ 書き込み: {result.success_count}",
        f"⏭️ スキップ: {result.skipped_count}",
        f"❌ 失敗: {result.failed_count}",
    ]
    if result.written:
        lines.append("\n書き込まれたファイル:")
        for file in result.written:
            lines.append(f"- {file}")
    if result.skipped:
        lines.append("\nスキップされたファイル（既存）:")
        for file in result.skipped:
            lines.append(f"- {file}")
    if result.failed:
        lines.append("\n失敗したファイル:")
        for file, error in result.failed:
            lines.append(f"- {file}: {error}")
    return "\n".join(lines)


async def _start_progress_thread(
    interaction: discord.Interaction,
    headline: str,
    thread_label: str,
):
    status_message = await interaction.followup.send(headline, wait=True)
    thread = None
    thread_error = None
    try:
        channel = interaction.channel
        if channel and hasattr(channel, "create_thread"):
            thread = await channel.create_thread(
                name=thread_label[:95],
                message=status_message,
                auto_archive_duration=1440,
            )
    except discord.Forbidden:
        thread_error = "スレッドを作成する権限がありませんでした。"
    except discord.HTTPException as exc:
        thread_error = f"スレッド作成時にエラーが発生しました: {exc}"

    if thread:
        await status_message.edit(content=f"🧵 進捗ログ: <#{thread.id}>")
        target = thread
    else:
        fallback_note = thread_error or "スレッドを利用できなかったため、このチャンネルに投稿します。"
        await status_message.edit(content=f"⚠️ {fallback_note}")
        target = status_message.channel

    return status_message, target, thread


async def _close_progress_thread(thread: discord.Thread | None):
    if isinstance(thread, discord.Thread):
        try:
            await thread.edit(archived=True)
        except (discord.HTTPException, discord.Forbidden):
            pass


class IssueModal(discord.ui.Modal, title='GitHub Issue 作成'):
    def __init__(self, repo: str, title: str, labels: str, assignees: str, body_default: str = ""):
        super().__init__()
        self.repo = repo
        self.labels = labels
        self.assignees = assignees
        
        # タイトルフィールド（事前入力）
        self.title_input = discord.ui.TextInput(
            label='Issue タイトル',
            placeholder='Issue のタイトルを入力してください...',
            default=title,
            max_length=300,
            required=True
        )
        self.add_item(self.title_input)
        
        # 本文フィールド（複数行対応）
        # モーダル本文（テンプレートを既定値として挿入可能）
        self.body_input = discord.ui.TextInput(
            label='Issue 本文',
            placeholder='Issue の詳細な説明を入力してください...\n\n複数行での入力が可能です。\n例：\n- 問題の詳細\n- 再現手順\n- 期待する動作',
            style=discord.TextStyle.long,  # 複数行入力を可能にする
            default=(body_default or "")[:4000],
            max_length=4000,
            required=False
        )
        self.add_item(self.body_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not config.GITHUB_TOKEN:
            await interaction.response.send_message("GITHUB_TOKEN が未設定です", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        payload = {
            "title": self.title_input.value.strip() or "New Issue",
            "body": build_body_with_footer(self.body_input.value.strip() or "(no body)", str(interaction.user), None),
        }
        
        label_list = parse_labels_input(self.labels)
        assignee_list = parse_assignees_input(self.assignees)
        if label_list:
            payload["labels"] = label_list
        if assignee_list:
            payload["assignees"] = assignee_list

        url = f"{config.GITHUB_API}/repos/{self.repo}/issues"
        status, resp = http_post(url, config.GITHUB_TOKEN, payload)
        try:
            data = json.loads(resp) if resp else {}
        except Exception:
            data = {}

        if status in (200, 201):
            issue_url = data.get("html_url", "")
            number = data.get("number", "?")
            remember_repo(self.repo)
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
                remember_repo(self.repo)
                await interaction.followup.send(
                    f"Issueを作成しました: #{number} {issue_url}\n（注意: 一部アサインに失敗したため、アサインなしで作成しました）"
                )
                retried = True

        if not retried:
            snippet = (resp or "")[:1500]
            await interaction.followup.send(f"作成失敗: {status}\n{snippet}")


def setup_commands(bot: discord.Client):
    @bot.tree.command(name="issue", description="GitHub Issue を作成します（モーダル入力版・推奨）")
    @app_commands.describe(
        repo="対象リポジトリ (owner/repo)",
        title="Issue タイトル（モーダルで再編集可能）",
        labels="ラベル（例: #bug #p2 または bug,p2）",
        assignees="アサイン（例: +alice +bob または alice,bob)",
        example="本文テンプレート（example/ 配下の md 名）",
    )
    async def issue_modal(
        interaction: discord.Interaction,
        repo: str,
        title: str = "",
        labels: str = "",
        assignees: str = "",
        example: str = "",
    ):
        # 例テンプレートの読み込み（存在すれば本文の既定値として設定）
        body_default = load_example_text(example).strip() if example else ""
        if body_default:
            # TextInput の制限に合わせて安全に切り詰め
            body_default = body_default[:4000]

        # モーダルを表示して複数行入力を可能にする
        modal = IssueModal(
            repo=repo,
            title=title,
            labels=labels,
            assignees=assignees,
            body_default=body_default,
        )
        await interaction.response.send_modal(modal)

    # オートコンプリート: repo パラメータ（最近使ったリポジトリ）
    @issue_modal.autocomplete("repo")
    async def issue_repo_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        repos = recent_repos(current, limit=25)
        return [app_commands.Choice(name=r, value=r) for r in repos]

    # オートコンプリート: example パラメータ（example/ 配下の md ファイル）
    @issue_modal.autocomplete("example")
    async def issue_example_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        names = list_example_names()
        q = (current or "").lower()
        if q:
            names = [n for n in names if q in n.lower()]
        names = names[:25]
        return [app_commands.Choice(name=n, value=n) for n in names]

    @bot.tree.command(name="issue_quick", description="GitHub Issue を作成します（クイック入力版）")
    @app_commands.describe(
        repo="対象リポジトリ (owner/repo)",
        title="Issue タイトル",
        body="本文（省略可）",
        labels="ラベル（例: #bug #p2 または bug,p2）",
        assignees="アサイン（例: +alice +bob または alice,bob)",
    )
    async def issue_quick(
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
            remember_repo(repo)
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
                remember_repo(repo)
                await interaction.followup.send(
                    f"Issueを作成しました: #{number} {issue_url}\n（注意: 一部アサインに失敗したため、アサインなしで作成しました）"
                )
                retried = True

        if not retried:
            snippet = (resp or "")[:1500]
            await interaction.followup.send(f"作成失敗: {status}\n{snippet}")

    @bot.tree.command(name="issue_help", description="Issue 作成コマンドの使い方を表示します")
    async def issue_help(interaction: discord.Interaction):
        text = (
            "**Issue 作成コマンド 2種類の使い方**\n\n"
            "**🔹 /issue（モーダル版・推奨）**\n"
            "ポップアップフォームで複数行入力が可能です\n"
            "例: `/issue repo:owner/repo title:\"バグ報告\" labels:#bug assignees:+alice`\n"
            "→ フォームが表示され、タイトル・本文を広いエリアで編集可能\n\n"
            "**🔹 /issue_quick（クイック版）**\n"
            "コマンドライン風の従来の入力方式です\n"
            "例: `/issue_quick repo:owner/repo title:\"バグ報告\" body:\"詳細説明\" labels:#bug assignees:+alice`\n"
            "→ 全てのパラメータをコマンド内で指定\n\n"
            "**共通仕様:**\n"
            "• labels: `#bug #p2` または `bug,p2` 形式\n"
            "• assignees: `+alice +bob` または `alice,bob` 形式\n"
            "• レガシーテキストコマンド `!issue owner/repo ...` も併用可能\n\n"
            "**使い分けの目安:**\n"
            "• 詳細な Issue → `/issue`（モーダル版）\n"
            "• 簡単な Issue → `/issue_quick`（クイック版）\n"
            "• 慣れ親しんだ方式 → `!issue`（テキスト版）"
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
            remember_repo(repo)
            await interaction.followup.send(
                f"タグを作成しました: {repo} {target_branch}@{sha[:7]} → {tag}"
            )
            return

        # 422 if already exists
        if st3 == 422 and body3 and "Reference already exists" in body3:
            await interaction.followup.send(f"作成失敗: タグ '{tag}' は既に存在します")
            return

    @bot.tree.command(name="sync_env", description="GitHub Actions のシークレット変数を .env から同期します（暗号化）")
    @app_commands.describe(
        repo="同期先リポジトリ (owner/repo)。未指定時は設定値や履歴を使用します",
        env_file="読み込む .env ファイル（デフォルト: DISCORD_ENV_SYNC_FILE）",
        include_keys="同期対象をキー名で制限（カンマ区切り・任意。例: SECRET_API_KEY,DISCORD_TOKEN）",
        exclude_keys="同期から除外するキー名（カンマ区切り・任意。例: TEST_TOKEN）",
        dry_run="プレビューのみ実行し、GitHub へは反映しません",
    )
    async def sync_env_command(
        interaction: discord.Interaction,
        repo: str | None = None,
        env_file: str | None = None,
        include_keys: str = "",
        exclude_keys: str = "",
        dry_run: bool = False,
    ):
        if not config.ENV_SYNC_ENABLED:
            await interaction.response.send_message(
                "シークレット変数の同期は無効化されています。DISCORD_ENV_SYNC_ENABLED=1 を設定してください。"
            )
            return

        if not config.GITHUB_TOKEN:
            await interaction.response.send_message("GITHUB_TOKEN が未設定です")
            return

        allowed_users = config.get_env_sync_allowed_users()
        if allowed_users and interaction.user.id not in allowed_users:
            await interaction.response.send_message("このコマンドを実行する権限がありません。")
            return

        target_repo = (repo or config.ENV_SYNC_DEFAULT_REPO or "").strip()
        if not target_repo:
            history = recent_repos("", limit=1)
            if history:
                target_repo = history[0]
        if not target_repo:
            await interaction.response.send_message(
                "同期先のリポジトリを指定してください（引数 repo または DISCORD_ENV_SYNC_REPO）。"
            )
            return

        env_path = Path(env_file or config.ENV_SYNC_DEFAULT_FILE or ".env").expanduser()
        try:
            variables = load_env_file(env_path)
        except FileNotFoundError:
            await interaction.response.send_message(f".env ファイルが見つかりません: {env_path}")
            return
        except Exception as exc:
            await interaction.response.send_message(f".env の読み込みに失敗しました: {exc}")
            return

        include_list = _split_env_keys(include_keys)
        exclude_list = _split_env_keys(exclude_keys)
        filtered = filter_variables(variables, include=include_list or None, exclude=exclude_list or None)

        if not filtered:
            await interaction.response.send_message(_env_no_keys_message())
            return

        await interaction.response.defer(thinking=True)

        headline = f"🔄 `{target_repo}` へのシークレット変数同期を開始します（暗号化）"
        status_message = await interaction.followup.send(headline, wait=True)

        thread_name = f"sync-env {target_repo}".replace("/", "-")
        thread = None
        thread_error = None
        try:
            channel = interaction.channel
            if channel and hasattr(channel, "create_thread"):
                thread = await channel.create_thread(
                    name=thread_name[:95],
                    message=status_message,
                    auto_archive_duration=1440,
                )
            else:
                thread_error = "スレッド対応チャンネルではないため、このチャンネルに投稿します。"
        except discord.Forbidden as exc:
            thread_error = "スレッドを作成する権限がありませんでした。"
        except discord.HTTPException as exc:
            thread_error = f"スレッド作成時にエラーが発生しました: {exc}"
        if thread:
            await status_message.edit(content=f"🧵 `{target_repo}` の同期ログ: <#{thread.id}>")
        else:
            fallback_note = thread_error or "スレッドを利用できなかったため、このチャンネルに投稿します。"
            await status_message.edit(content=f"⚠️ {fallback_note}")
            thread = status_message.channel

        if dry_run:
            await thread.send(_format_env_dry_run_text(target_repo, env_path, filtered))
            await thread.send("✅ ドライランを完了しました（GitHub への変更はありません）")
            return

        await thread.send(
            f"⚙️ 同期対象キー数: {len(filtered)}\n"
            f"ファイル: `{str(env_path)}`\n"
            "🔐 値を暗号化して GitHub API にリクエストを送信しています…"
        )

        result = sync_repository_variables(target_repo, filtered, token=config.GITHUB_TOKEN, dry_run=False)

        if result.failed_count == 0:
            remember_repo(target_repo)

        for block in _format_env_result_blocks(target_repo, env_path, filtered, result):
            await thread.send(block)

    # オートコンプリート: issue_quick の repo
    @issue_quick.autocomplete("repo")
    async def issue_quick_repo_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        repos = recent_repos(current, limit=25)
        return [app_commands.Choice(name=r, value=r) for r in repos]

    # オートコンプリート: tag_latest の repo
    @tag_latest.autocomplete("repo")
    async def tag_latest_repo_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        repos = recent_repos(current, limit=25)
        return [app_commands.Choice(name=r, value=r) for r in repos]

    @sync_env_command.autocomplete("repo")
    async def sync_env_repo_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        repos = recent_repos(current, limit=25)
        if not current and config.ENV_SYNC_DEFAULT_REPO:
            default_repo = config.ENV_SYNC_DEFAULT_REPO.strip()
            if default_repo and default_repo not in repos:
                repos = [default_repo] + repos
        return [app_commands.Choice(name=r, value=r) for r in repos]

    @bot.tree.command(name="list_presets", description="利用可能なワークフロープリセットの一覧を表示します")
    async def list_presets(interaction: discord.Interaction):
        try:
            presets = list_available_presets()
            if not presets:
                await interaction.response.send_message(
                    "利用可能なプリセットがありません。gemini-actions-lab-cli がインストールされているか確認してください。",
                    ephemeral=True
                )
                return

            lines = ["**利用可能なワークフロープリセット一覧**\n"]
            for name, description in presets:
                lines.append(f"**`{name}`**: {description}")

            await interaction.response.send_message("\n".join(lines), ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"エラーが発生しました: {e}", ephemeral=True)

    @bot.tree.command(name="workflow_preset", description="プリセットからワークフローをリポジトリに同期します")
    @app_commands.describe(
        repo="同期先リポジトリ (owner/repo)",
        preset="プリセット名（例: basic, standard, pr-review）",
        template_repo="テンプレートリポジトリ (owner/repo)。デフォルト: Sunwood-ai-labsII/gemini-actions-lab",
        dry_run="プレビューのみ実行し、実際には反映しません",
        overwrite="既存のファイルを上書きします",
    )
    async def workflow_preset(
        interaction: discord.Interaction,
        repo: str,
        preset: str,
        template_repo: str = DEFAULT_TEMPLATE_REPO,
        dry_run: bool = False,
        overwrite: bool = False,
    ):
        if not config.GITHUB_TOKEN:
            await interaction.response.send_message("GITHUB_TOKEN が未設定です", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        try:
            result = sync_workflow_preset(
                target_repo=repo,
                preset_name=preset,
                template_repo=template_repo,
                token=config.GITHUB_TOKEN,
                dry_run=dry_run,
                overwrite=overwrite,
            )

            if dry_run:
                await interaction.followup.send(
                    _format_workflow_dry_run_text(result, repo, preset, template_repo)
                )
                return

            remember_repo(repo)
            await interaction.followup.send(_format_workflow_summary_text(result, repo, preset))

        except WorkflowSyncError as e:
            await interaction.followup.send(f"❌ ワークフロー同期に失敗しました: {e}")
        except Exception as e:
            await interaction.followup.send(f"❌ 予期しないエラーが発生しました: {e}")

    @workflow_preset.autocomplete("repo")
    async def workflow_preset_repo_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        repos = recent_repos(current, limit=25)
        return [app_commands.Choice(name=r, value=r) for r in repos]

    @workflow_preset.autocomplete("preset")
    async def workflow_preset_preset_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            presets = list_available_presets()
            q = (current or "").lower()
            if q:
                presets = [(name, desc) for name, desc in presets if q in name.lower()]
            presets = presets[:25]
            return [app_commands.Choice(name=f"{name} - {desc}", value=name) for name, desc in presets]
        except Exception:
            return []

    @bot.tree.command(name="create_branches", description="main と develop ブランチを作成します")
    @app_commands.describe(
        repo="対象リポジトリ (owner/repo)",
        base_branch="ベースブランチ（省略時はデフォルトブランチ）",
        dry_run="プレビューのみ実行し、GitHub へは反映しません",
    )
    async def create_branches(
        interaction: discord.Interaction,
        repo: str,
        base_branch: str | None = None,
        dry_run: bool = False,
    ):
        if not config.GITHUB_TOKEN:
            await interaction.response.send_message("GITHUB_TOKEN が未設定です", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        branches_to_create = ["main", "develop"]

        try:
            result = sync_branches(
                repo=repo,
                branches=branches_to_create,
                token=config.GITHUB_TOKEN,
                base_branch=base_branch,
                dry_run=dry_run,
            )

            if dry_run:
                await interaction.followup.send(
                    _format_branch_dry_run_text(result, repo, branches_to_create)
                )
                return

            remember_repo(repo)
            await interaction.followup.send(_format_branch_summary_text(result, repo))

        except BranchSyncError as e:
            await interaction.followup.send(f"❌ ブランチ作成に失敗しました: {e}")
        except Exception as e:
            await interaction.followup.send(f"❌ 予期しないエラーが発生しました: {e}")

    @create_branches.autocomplete("repo")
    async def create_branches_repo_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        repos = recent_repos(current, limit=25)
        return [app_commands.Choice(name=r, value=r) for r in repos]

    @bot.tree.command(name="sync_agent", description="エージェント設定ファイル（AGENTS.md, Claude.md, GEMINI.md）を同期します")
    @app_commands.describe(
        repo="対象リポジトリ (owner/repo)",
        template_repo="テンプレートリポジトリ (owner/repo)。デフォルト: Sunwood-ai-labsII/gemini-actions-lab",
        dry_run="プレビューのみ実行し、GitHub へは反映しません",
        overwrite="既存のファイルを上書きします",
    )
    async def sync_agent_command(
        interaction: discord.Interaction,
        repo: str,
        template_repo: str = DEFAULT_TEMPLATE_REPO,
        dry_run: bool = False,
        overwrite: bool = False,
    ):
        if not config.GITHUB_TOKEN:
            await interaction.response.send_message("GITHUB_TOKEN が未設定です", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        doc_files = DEFAULT_DOC_FILES

        try:
            result = sync_docs_func(
                target_repo=repo,
                template_repo=template_repo,
                token=config.GITHUB_TOKEN,
                doc_files=doc_files,
                dry_run=dry_run,
                overwrite=overwrite,
            )

            if dry_run:
                await interaction.followup.send(
                    _format_doc_dry_run_text(result, repo, template_repo, doc_files)
                )
                return

            remember_repo(repo)
            await interaction.followup.send(_format_doc_summary_text(result, repo))

        except DocSyncError as e:
            await interaction.followup.send(f"❌ エージェント設定の同期に失敗しました: {e}")
        except Exception as e:
            await interaction.followup.send(f"❌ 予期しないエラーが発生しました: {e}")

    @sync_agent_command.autocomplete("repo")
    async def sync_agent_repo_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        repos = recent_repos(current, limit=25)
        return [app_commands.Choice(name=r, value=r) for r in repos]

    @bot.tree.command(name="repo_setup", description="ワークフロー、.env 同期、ブランチ作成、エージェント設定をまとめて実行します")
    @app_commands.describe(
        repo="同期先リポジトリ (owner/repo)",
        preset="プリセット名（例: basic, standard, pr-review）",
        env_file="読み込む .env ファイル（デフォルト: DISCORD_ENV_SYNC_FILE）",
        template_repo="テンプレートリポジトリ (owner/repo)。デフォルト: Sunwood-ai-labsII/gemini-actions-lab",
        include_keys="同期対象をキー名で制限（任意）",
        exclude_keys="同期から除外するキー名（任意）",
        dry_run="プレビューのみ実行し、GitHub へは反映しません",
        overwrite="既存のワークフローファイルを上書きします",
        create_branches="main と develop ブランチを作成します",
        sync_agent="エージェント設定ファイル（AGENTS.md, Claude.md, GEMINI.md）を同期します",
    )
    async def repo_setup(
        interaction: discord.Interaction,
        repo: str,
        preset: str,
        env_file: str | None = None,
        template_repo: str = DEFAULT_TEMPLATE_REPO,
        include_keys: str = "",
        exclude_keys: str = "",
        dry_run: bool = False,
        overwrite: bool = False,
        create_branches: bool = True,
        sync_agent: bool = True,
    ):
        if not config.GITHUB_TOKEN:
            await interaction.response.send_message("GITHUB_TOKEN が未設定です", ephemeral=True)
            return

        if not config.ENV_SYNC_ENABLED:
            await interaction.response.send_message(
                "シークレット変数の同期は無効化されています。DISCORD_ENV_SYNC_ENABLED=1 を設定してください。",
                ephemeral=True,
            )
            return

        allowed_users = config.get_env_sync_allowed_users()
        if allowed_users and interaction.user.id not in allowed_users:
            await interaction.response.send_message("このコマンドを実行する権限がありません。", ephemeral=True)
            return

        env_path = Path(env_file or config.ENV_SYNC_DEFAULT_FILE or ".env").expanduser()
        try:
            variables = load_env_file(env_path)
        except FileNotFoundError:
            await interaction.response.send_message(f".env ファイルが見つかりません: {env_path}", ephemeral=True)
            return
        except Exception as exc:
            await interaction.response.send_message(f".env の読み込みに失敗しました: {exc}", ephemeral=True)
            return

        include_list = _split_env_keys(include_keys)
        exclude_list = _split_env_keys(exclude_keys)
        filtered = filter_variables(variables, include=include_list or None, exclude=exclude_list or None)

        if not filtered:
            await interaction.response.send_message(_env_no_keys_message(), ephemeral=True)
            return

        await interaction.response.defer(thinking=True)

        headline = f"🚧 `{repo}` の repo_setup を開始します"
        thread_label = f"repo-setup {repo}".replace("/", "-")
        status_message, log_target, progress_thread = await _start_progress_thread(
            interaction, headline, thread_label
        )

        async def conclude(message: str):
            await log_target.send(message)
            await status_message.edit(content=message)
            await _close_progress_thread(progress_thread)

        if dry_run:
            await log_target.send("🧪 ドライランモード: GitHub へは変更を加えません")

        await log_target.send(
            "⚙️ ワークフロー同期を開始します\n"
            f"• プリセット: `{preset}`\n"
            f"• テンプレート: `{template_repo}`\n"
            f"• overwrite: {'ON' if overwrite else 'OFF'}"
        )

        try:
            workflow_result = sync_workflow_preset(
                target_repo=repo,
                preset_name=preset,
                template_repo=template_repo,
                token=config.GITHUB_TOKEN,
                dry_run=dry_run,
                overwrite=overwrite,
            )
        except WorkflowSyncError as e:
            await conclude(f"❌ ワークフロー同期に失敗しました: {e}（スレッドをクローズします）")
            return
        except Exception as e:
            await conclude(f"❌ 予期しないエラーが発生しました: {e}（スレッドをクローズします）")
            return

        if dry_run:
            workflow_text = _format_workflow_dry_run_text(workflow_result, repo, preset, template_repo)
            env_text = _format_env_dry_run_text(repo, env_path, filtered)
            await log_target.send("**workflow_preset (dry-run)**\n" + workflow_text)
            await log_target.send("**sync_env (dry-run)**\n" + env_text)

            if create_branches:
                try:
                    branches_to_create = ["main", "develop"]
                    branch_result = sync_branches(
                        repo=repo,
                        branches=branches_to_create,
                        token=config.GITHUB_TOKEN,
                        dry_run=True,
                    )
                    branch_text = _format_branch_dry_run_text(branch_result, repo, branches_to_create)
                    await log_target.send("**create_branches (dry-run)**\n" + branch_text)
                except BranchSyncError as e:
                    await log_target.send(f"⚠️ ブランチプレビュー中にエラーが発生しました: {e}")

            if sync_agent:
                try:
                    doc_files = DEFAULT_DOC_FILES
                    doc_result = sync_docs_func(
                        target_repo=repo,
                        template_repo=template_repo,
                        token=config.GITHUB_TOKEN,
                        doc_files=doc_files,
                        dry_run=True,
                        overwrite=overwrite,
                    )
                    doc_text = _format_doc_dry_run_text(doc_result, repo, template_repo, doc_files)
                    await log_target.send("**sync_agent (dry-run)**\n" + doc_text)
                except DocSyncError as e:
                    await log_target.send(f"⚠️ エージェント設定プレビュー中にエラーが発生しました: {e}")

            await conclude("✅ repo_setup (dry-run) を完了しました。スレッドをクローズします。")
            return

        await log_target.send(
            "🔐 シークレット同期を開始します\n"
            f"• ファイル: `{str(env_path)}`\n"
            f"• 対象キー数: {len(filtered)}"
        )

        env_result = sync_repository_variables(repo, filtered, token=config.GITHUB_TOKEN, dry_run=False)

        # Branch creation
        branch_result = None
        if create_branches:
            await log_target.send(
                "🌿 ブランチ作成を開始します\n"
                "• 対象ブランチ: main, develop"
            )
            try:
                branches_to_create = ["main", "develop"]
                branch_result = sync_branches(
                    repo=repo,
                    branches=branches_to_create,
                    token=config.GITHUB_TOKEN,
                    dry_run=False,
                )
            except BranchSyncError as e:
                await log_target.send(f"⚠️ ブランチ作成中にエラーが発生しました: {e}")
                branch_result = BranchSyncResult(created=[], skipped=[], failed=[("branch_sync", str(e))])
            except Exception as e:
                await log_target.send(f"⚠️ 予期しないエラーが発生しました: {e}")
                branch_result = BranchSyncResult(created=[], skipped=[], failed=[("branch_sync", str(e))])

        # Agent configuration synchronization
        doc_result = None
        if sync_agent:
            await log_target.send(
                "📄 エージェント設定同期を開始します\n"
                f"• 対象ファイル: {', '.join(DEFAULT_DOC_FILES)}"
            )
            try:
                doc_result = sync_docs_func(
                    target_repo=repo,
                    template_repo=template_repo,
                    token=config.GITHUB_TOKEN,
                    doc_files=DEFAULT_DOC_FILES,
                    dry_run=False,
                    overwrite=overwrite,
                )
            except DocSyncError as e:
                await log_target.send(f"⚠️ エージェント設定同期中にエラーが発生しました: {e}")
                doc_result = DocSyncResult(written=[], skipped=[], failed=[("agent_sync", str(e))])
            except Exception as e:
                await log_target.send(f"⚠️ 予期しないエラーが発生しました: {e}")
                doc_result = DocSyncResult(written=[], skipped=[], failed=[("agent_sync", str(e))])

        await log_target.send("**workflow_preset**\n" + _format_workflow_summary_text(workflow_result, repo, preset))
        await log_target.send("**sync_env**")
        for block in _format_env_result_blocks(repo, env_path, filtered, env_result):
            await log_target.send(block)

        if branch_result:
            await log_target.send("**create_branches**\n" + _format_branch_summary_text(branch_result, repo))

        if doc_result:
            await log_target.send("**sync_agent**\n" + _format_doc_summary_text(doc_result, repo))

        success = (
            env_result.failed_count == 0
            and workflow_result.failed_count == 0
            and (branch_result is None or branch_result.failed_count == 0)
            and (doc_result is None or doc_result.failed_count == 0)
        )
        if success:
            remember_repo(repo)

        completion_note = (
            "✅ repo_setup が完了しました。スレッドをクローズします。"
            if success
            else "⚠️ repo_setup が完了しました（エラーあり）。スレッドをクローズします。"
        )
        await conclude(completion_note)

    @repo_setup.autocomplete("repo")
    async def repo_setup_repo_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        repos = recent_repos(current, limit=25)
        return [app_commands.Choice(name=r, value=r) for r in repos]

    @repo_setup.autocomplete("preset")
    async def repo_setup_preset_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        try:
            presets = list_available_presets()
            q = (current or "").lower()
            if q:
                presets = [(name, desc) for name, desc in presets if q in name.lower()]
            presets = presets[:25]
            return [app_commands.Choice(name=f"{name} - {desc}", value=name) for name, desc in presets]
        except Exception:
            return []
