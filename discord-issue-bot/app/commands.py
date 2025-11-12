import json
import discord
from discord import app_commands

from . import config
from .env_sync import filter_variables, load_env_file, sync_repository_variables
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
from pathlib import Path


# --- Example templates helper ---
EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "example"


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

        def _split_keys(raw: str) -> list[str]:
            if not raw:
                return []
            tokens: list[str] = []
            for chunk in raw.replace(",", " ").split():
                part = chunk.strip()
                if part:
                    tokens.append(part)
            return tokens

        include_list = _split_keys(include_keys)
        exclude_list = _split_keys(exclude_keys)
        filtered = filter_variables(variables, include=include_list or None, exclude=exclude_list or None)

        if not filtered:
            guidance = [
                "同期対象の変数がありません。以下を確認してください:",
                "• `.env` に値が入っているか",
                "• `include_keys` を指定した場合はキー名が一致しているか",
                "• `exclude_keys` により除外されていないか",
                "（どちらの引数も任意です。未入力ならすべてのキーが対象になります）",
            ]
            await interaction.response.send_message("\n".join(guidance))
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
            names = sorted(filtered.keys())
            message_lines = [
                "🔍 ドライラン結果",
                f"同期先: `{target_repo}`",
                f"ファイル: `{str(env_path)}`",
                f"対象キー数: {len(names)}",
            ]
            if names:
                message_lines.append("対象キー一覧:")
                for name in names:
                    preview = filtered[name][:4] + ("…" if len(filtered[name]) > 4 else "")
                    message_lines.append(f"- {name}: {preview or '(空)'}")
            else:
                message_lines.append("対象キー: (なし)")
            await thread.send("\n".join(message_lines))
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

        def masked(name: str) -> str:
            value = filtered.get(name, "")
            preview = value[:4]
            return f"{preview}{'…' if len(value) > 4 else ''}" if value else "(空)"

        if result.created:
            created_lines = ["✨ 新規作成したシークレット:"]
            created_lines.extend(f"- {name}: {masked(name)}" for name in result.created)
            await thread.send("\n".join(created_lines))

        if result.updated:
            updated_lines = ["✅ 更新/作成したシークレット:"]
            updated_lines.extend(f"- {name}: {masked(name)}" for name in result.updated)
            await thread.send("\n".join(updated_lines))

        if result.failed:
            failed_lines = ["⚠️ 失敗したキー:"]
            for name, status, snippet in result.failed:
                detail = f"{name} ({status})"
                if snippet:
                    detail += f": {snippet}"
                failed_lines.append(f"- {detail}")
            await thread.send("\n".join(failed_lines))

        summary = [
            f"同期先: `{target_repo}`",
            f"ファイル: `{str(env_path)}`",
            f"対象キー数: {len(filtered)}",
            f"作成: {result.created_count}",
            f"更新: {result.updated_count}",
            f"失敗: {result.failed_count}",
        ]
        await thread.send("\n".join(summary))
        await thread.send("✅ 同期処理が完了しました" if result.failed_count == 0 else "⚠️ 一部のキーでエラーが発生しました")

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
        template_repo: str = "Sunwood-ai-labsII/gemini-actions-lab",
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
                lines = [
                    "🔍 ドライラン結果",
                    f"同期先: `{repo}`",
                    f"プリセット: `{preset}`",
                    f"テンプレート: `{template_repo}`",
                    f"\n対象ファイル数: {len(result.skipped)}",
                ]
                if result.skipped:
                    lines.append("\n対象ファイル一覧:")
                    for file in result.skipped:
                        lines.append(f"- {file}")
                lines.append("\n✅ ドライランを完了しました（実際の変更はありません）")
                await interaction.followup.send("\n".join(lines))
                return

            summary_lines = [
                f"✅ ワークフロー同期が完了しました",
                f"同期先: `{repo}`",
                f"プリセット: `{preset}`",
                f"",
                f"✨ 書き込み: {result.success_count}",
                f"⏭️ スキップ: {result.skipped_count}",
                f"❌ 失敗: {result.failed_count}",
            ]

            if result.written:
                summary_lines.append("\n書き込まれたファイル:")
                for file in result.written:
                    summary_lines.append(f"- {file}")

            if result.skipped:
                summary_lines.append("\nスキップされたファイル（既存）:")
                for file in result.skipped:
                    summary_lines.append(f"- {file}")

            if result.failed:
                summary_lines.append("\n失敗したファイル:")
                for file, error in result.failed:
                    summary_lines.append(f"- {file}: {error}")

            remember_repo(repo)
            await interaction.followup.send("\n".join(summary_lines))

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

    @bot.tree.command(name="set_secret", description="GitHub Actions のシークレット変数を個別に設定します")
    @app_commands.describe(
        repo="同期先リポジトリ (owner/repo)",
        key="シークレットのキー名（例: GEMINI_API_KEY）",
        value="シークレットの値（暗号化されて送信されます）",
    )
    async def set_secret(
        interaction: discord.Interaction,
        repo: str,
        key: str,
        value: str,
    ):
        if not config.GITHUB_TOKEN:
            await interaction.response.send_message("GITHUB_TOKEN が未設定です", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Use the existing env_sync module to set a single secret
            variables = {key: value}
            result = sync_repository_variables(repo, variables, token=config.GITHUB_TOKEN, dry_run=False)

            if result.failed_count == 0:
                remember_repo(repo)
                value_preview = value[:4] + ("..." if len(value) > 4 else "")
                await interaction.followup.send(
                    f"✅ シークレット変数を設定しました\n"
                    f"リポジトリ: `{repo}`\n"
                    f"キー: `{key}`\n"
                    f"値: `{value_preview}`",
                    ephemeral=True
                )
            else:
                error_detail = result.failed[0] if result.failed else ("Unknown", 0, "Unknown error")
                await interaction.followup.send(
                    f"❌ シークレット変数の設定に失敗しました\n"
                    f"リポジトリ: `{repo}`\n"
                    f"キー: `{key}`\n"
                    f"エラー: {error_detail[2]}",
                    ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(
                f"❌ 予期しないエラーが発生しました: {e}",
                ephemeral=True
            )

    @set_secret.autocomplete("repo")
    async def set_secret_repo_autocomplete(
        interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        repos = recent_repos(current, limit=25)
        return [app_commands.Choice(name=r, value=r) for r in repos]
