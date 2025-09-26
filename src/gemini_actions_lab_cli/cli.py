"""Entry point for the ``gemini-actions-lab-cli`` command line interface."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable

from .env_loader import apply_env_file, load_env_file
from .github_api import GitHubClient, GitHubError, encrypt_secret, parse_repo
from .workflows import WorkflowSyncError, extract_github_directory

DEFAULT_TEMPLATE_REPO = "Sunwood-ai-labsII/gemini-actions-lab"
DEFAULT_SECRETS_FILE = ".secrets.env"


def _require_token(explicit_token: str | None) -> str:
    token = explicit_token or os.getenv("GITHUB_TOKEN")
    if not token:
        raise SystemExit(
            "A GitHub personal access token is required. Provide it via the --token "
            "option or the GITHUB_TOKEN environment variable."
        )
    return token


def sync_secrets(args: argparse.Namespace) -> int:
    owner, repo = parse_repo(args.repo)
    env_values = load_env_file(Path(args.env_file))
    token = _require_token(args.token)

    client = GitHubClient(token=token, api_url=args.api_url)
    public_key = client.get_actions_public_key(owner, repo)

    encrypted_payloads = {
        name: encrypt_secret(public_key["key"], value) for name, value in env_values.items()
    }

    for name, encrypted in encrypted_payloads.items():
        client.put_actions_secret(owner, repo, name, encrypted, public_key["key_id"])
        print(f"✅ シークレット {name} を同期しました")

    print(f"🎉 {len(encrypted_payloads)} 件のシークレットを {owner}/{repo} に反映しました")
    return 0


def _sync_workflows_remote(
    client: GitHubClient,
    template_repo: str,
    archive_bytes: bytes,
    target_repo: str,
    branch: str | None,
    *,
    clean: bool,
    commit_message: str | None,
    force: bool,
    enable_pages: bool,
) -> int:
    owner_template, repo_template = parse_repo(template_repo)
    owner_target, repo_target = parse_repo(target_repo)

    print(
        f"📥 テンプレート {owner_template}/{repo_template} を展開し、"
        f"{owner_target}/{repo_target} へ適用する準備をしています..."
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        written = extract_github_directory(archive_bytes, tmp_path, clean=True)
        if not written:
            print("❌ テンプレートアーカイブに .github ディレクトリが含まれていません", file=sys.stderr)
            return 1
        github_root = tmp_path / ".github"
        payloads = []
        new_paths: set[str] = set()
        new_dirs: set[str] = {".github"}
        for file_path in written:
            relative = file_path.relative_to(github_root)
            posix_path = relative.as_posix()
            full_path = f".github/{posix_path}"
            mode = "100755" if os.access(file_path, os.X_OK) else "100644"
            payloads.append(
                {
                    "path": full_path,
                    "mode": mode,
                    "content": file_path.read_bytes(),
                }
            )
            new_paths.add(full_path)
            parent = Path(full_path)
            for ancestor in parent.parents:
                if ancestor == Path("."):
                    continue
                new_dirs.add(ancestor.as_posix())

    print("🧹 新しいファイルセットを生成しています...")

    target_branch = branch or client.get_default_branch(owner_target, repo_target)
    commit_message = commit_message or f"✨ Sync .github directory from {owner_template}/{repo_template}"

    print(f"🔍 対象リポジトリ {owner_target}/{repo_target} の {target_branch} ブランチを取得中...")
    ref = client.get_ref(owner_target, repo_target, f"heads/{target_branch}")
    base_commit_sha = ref["object"]["sha"]
    base_commit = client.get_git_commit(owner_target, repo_target, base_commit_sha)
    base_tree_sha = base_commit["tree"]["sha"]

    tree_entries = []

    if clean:
        print("🧽 `--clean` 指定のため、既存の .github 配下をクリーンアップします...")
        tree = client.get_tree(owner_target, repo_target, base_tree_sha, recursive=True)
        for item in tree.get("tree", []):
            path = item.get("path")
            if not path or not path.startswith(".github"):
                continue
            if path in new_paths or path in new_dirs:
                continue
            tree_entries.append({
                "path": path,
                "mode": item["mode"],
                "type": item["type"],
                "sha": None,
            })

    for payload in payloads:
        blob_sha = client.create_blob(owner_target, repo_target, payload["content"])
        tree_entries.append(
            {
                "path": payload["path"],
                "mode": payload["mode"],
                "type": "blob",
                "sha": blob_sha,
            }
        )

    if not tree_entries:
        print("✅ 更新は不要でした。リモートリポジトリは既にテンプレートと一致しています")
        return 0

    dedup: Dict[tuple[str, str], dict[str, Any]] = {}
    for entry in tree_entries:
        key = (entry["path"], entry["type"])
        dedup[key] = entry
    tree_entries = list(dedup.values())

    print("🪄 新しいツリーを作成し、コミットを準備しています...")
    tree_sha = client.create_tree(owner_target, repo_target, tree_entries, base_tree=base_tree_sha)["sha"]
    commit = client.create_commit(
        owner_target,
        repo_target,
        commit_message,
        tree_sha,
        parents=[base_commit_sha],
    )
    client.update_ref(owner_target, repo_target, target_branch, commit["sha"], force=force)

    print("📦 リモートリポジトリで更新されたファイル一覧:")
    for payload in payloads:
        print(f" - {payload['path']}")
    print(
        f"🚀 {owner_target}/{repo_target}@{target_branch} に "
        f"{len(payloads)} 件のファイルをコミットしました ({commit['sha'][:7]})"
    )

    if enable_pages:
        print("🌐 GitHub Pages のビルドソースを GitHub Actions に設定しています...")
        try:
            client.configure_pages_actions(owner_target, repo_target)
        except GitHubError as exc:
            print(f"⚠️ GitHub Pages の設定に失敗しました: {exc}", file=sys.stderr)
        else:
            print("✅ GitHub Pages を GitHub Actions デプロイに設定しました")
    return 0


def sync_workflows(args: argparse.Namespace) -> int:
    token = args.token or os.getenv("GITHUB_TOKEN")
    client = GitHubClient(token=token, api_url=args.api_url)
    owner, repo = parse_repo(args.template_repo)

    print(f"📡 テンプレートリポジトリ {owner}/{repo} からアーカイブを取得します...")
    archive = client.download_repository_archive(owner, repo, ref=args.ref)
    print("✅ アーカイブのダウンロードが完了しました")

    if args.repo:
        print(
            f"🌐 リモートリポジトリ {args.repo} に .github ディレクトリを同期します"
        )
        return _sync_workflows_remote(
            client,
            args.template_repo,
            archive,
            args.repo,
            args.branch,
            clean=args.clean,
            commit_message=args.message,
            force=args.force,
            enable_pages=args.enable_pages_actions,
        )

    destination = Path(args.destination)
    print(f"🗂️ ローカル {destination} へ展開しています...")
    written = extract_github_directory(archive, destination, clean=args.clean)

    print("📦 更新されたファイル一覧:")
    for path in written:
        print(f" - {path.relative_to(destination)}")
    print("🚀 ローカルの .github ディレクトリがテンプレートと同期されました")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gemini-actions-lab-cli",
        description="Utilities for managing Gemini Actions Lab GitHub repositories",
    )
    parser.add_argument(
        "--api-url",
        default="https://api.github.com",
        help="Base URL for the GitHub API (override for GitHub Enterprise).",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    secrets_parser = subparsers.add_parser(
        "sync-secrets", help="Create or update repository secrets from a .env file"
    )
    secrets_parser.add_argument("--repo", required=True, help="Target repository in owner/name format")
    secrets_parser.add_argument(
        "--env-file",
        default=DEFAULT_SECRETS_FILE,
        help=(
            "Path to the .env file containing secret values (defaults to .secrets.env)."
            " This file is separate from the runtime .env used to configure the CLI."
        ),
    )
    secrets_parser.add_argument(
        "--token", help="GitHub personal access token (defaults to the GITHUB_TOKEN env var)"
    )
    secrets_parser.set_defaults(func=sync_secrets)

    workflows_parser = subparsers.add_parser(
        "sync-workflows",
        help="Download the .github directory from a template repository and copy it locally",
    )
    workflows_parser.add_argument(
        "--template-repo",
        default=DEFAULT_TEMPLATE_REPO,
        help="Repository that hosts the canonical .github directory (owner/name)",
    )
    workflows_parser.add_argument(
        "--ref", help="Optional Git reference (branch, tag, or commit SHA) to download"
    )
    workflows_parser.add_argument(
        "--destination",
        default=Path.cwd(),
        help="Destination directory whose .github folder should be updated",
    )
    workflows_parser.add_argument(
        "--repo",
        help="When set, sync the template .github directory directly to this repository (owner/name)",
    )
    workflows_parser.add_argument(
        "--branch",
        help="Target branch to update when using --repo (defaults to the repository's default branch)",
    )
    workflows_parser.add_argument(
        "--message",
        help="Custom commit message when syncing to a remote repository",
    )
    workflows_parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove the existing .github directory before extracting the template",
    )
    workflows_parser.add_argument(
        "--token", help="Optional GitHub token if the template repository is private"
    )
    workflows_parser.add_argument(
        "--force",
        action="store_true",
        help="Force update the target branch reference when syncing to a remote repository",
    )
    workflows_parser.add_argument(
        "--enable-pages-actions",
        action="store_true",
        help="Also configure GitHub Pages to use GitHub Actions for builds when syncing to a remote repository",
    )
    workflows_parser.set_defaults(func=sync_workflows)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    # Load the runtime configuration from the current directory's .env before
    # parsing arguments so commands can rely on those environment variables.
    apply_env_file(Path.cwd() / ".env", missing_ok=True)

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return args.func(args)
    except (GitHubError, WorkflowSyncError, FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
