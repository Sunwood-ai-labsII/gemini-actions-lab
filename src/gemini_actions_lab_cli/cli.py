"""Entry point for the ``gemini-actions-lab-cli`` command line interface."""

from __future__ import annotations

import argparse
import itertools
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable

try:  # Optional dependency for banner rendering
    import pyfiglet  # type: ignore
except ImportError:  # pragma: no cover - falls back to plain text banner
    pyfiglet = None

from .env_loader import apply_env_file, load_env_file
from .github_api import GitHubClient, GitHubError, encrypt_secret, parse_repo
from .workflows import WorkflowSyncError, extract_github_directory

DEFAULT_TEMPLATE_REPO = "Sunwood-ai-labsII/gemini-actions-lab"
DEFAULT_SECRETS_FILE = ".secrets.env"

_INTRO_SHOWN = False
DEFAULT_BANNER_TEXT = "Gemini Actions Lab CLI"


def _render_ascii_banner(text: str) -> list[str]:
    if pyfiglet is not None:
        rendered = pyfiglet.figlet_format(text, font="slant")
        return [line for line in rendered.splitlines() if line.strip()]
    return [text.upper()]


BANNER_LINES = _render_ascii_banner(DEFAULT_BANNER_TEXT)


def _render_intro_animation() -> None:
    global _INTRO_SHOWN
    if _INTRO_SHOWN:
        return
    colors = ["\033[95m", "\033[94m", "\033[96m", "\033[36m", "\033[92m", "\033[32m"]
    for line, color in zip(BANNER_LINES, itertools.cycle(colors)):
        print(f"{color}{line}\033[0m", flush=True)
        time.sleep(0.04)
    # print("\033[92m✨ GEMINI ACTIONS LAB CLI ✨\033[0m\n")
    _INTRO_SHOWN = True


class ProgressReporter:
    RESET = "\033[0m"

    def __init__(self) -> None:
        self._spinner = itertools.cycle([
            "\033[95m◆\033[0m",
            "\033[94m◇\033[0m",
            "\033[96m◆\033[0m",
            "\033[36m◇\033[0m",
        ])
        self._buffer: list[tuple[str, str | None]] = []

    @staticmethod
    def _visible_len(text: str) -> int:
        return len(re.sub(r"\x1b\[[0-9;]*m", "", text))

    def _panel(self, header: str, body: list[str], accent: str) -> None:
        visible_lengths = [self._visible_len(header) + 2] + [
            self._visible_len(line) + 2 for line in body
        ]
        content_width = max(visible_lengths) if visible_lengths else 20
        term_width = shutil.get_terminal_size(fallback=(100, 20)).columns
        target_width = max(term_width - 2, 20)
        inner_width = max(target_width, content_width)
        horiz = "─" * inner_width
        top = f"{accent}┌{horiz}┐{self.RESET}"
        bottom = f"{accent}└{horiz}┘{self.RESET}"
        print(top)
        print(f"{accent}│{self._pad(header, inner_width)}│{self.RESET}")
        for line in body:
            print(f"{accent}│{self._pad(line, inner_width)}│{self.RESET}")
        print(bottom)

    def _pad(self, text: str, width: int) -> str:
        visible_len = self._visible_len(text)
        extra = width - visible_len
        if extra >= 0:
            right_pad = max(extra - 1, 0)
            return f" {text}{' ' * right_pad}"
        return f" {text}"

    def stage(self, title: str, detail: str | None = None) -> None:
        badge = next(self._spinner)
        self._buffer.append((f"{badge} {title}", detail))

    def success(self, message: str) -> None:
        self._buffer.append((f"✔ {message}", None))

    def info(self, message: str) -> None:
        self._buffer.append((f"… {message}", None))

    def list_panel(self, title: str, items: list[str]) -> None:
        body = [f"• {item}" for item in items] if items else ["(none)"]
        header = f"📂 {title}"
        self._panel(header, body, "\033[94m")

    def grouped(self, title: str, entries: list[tuple[str, str | None]]) -> None:
        lines: list[str] = []
        for label, detail in entries:
            text = label if detail is None else f"{label}: {detail}"
            lines.append(text)
        self._panel(f"🚀 {title}", lines, "\033[95m")

    def flush(self, title: str) -> None:
        if not self._buffer:
            return
        lines: list[str] = []
        for label, detail in self._buffer:
            lines.append(label)
            if detail:
                lines.append(f"  • {detail}")
        self._panel(f"🚀 {title}", lines, "\033[95m")
        self._buffer.clear()


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
        print(f"✅ Synced secret {name}")

    print(f"🎉 Applied {len(encrypted_payloads)} secrets to {owner}/{repo}")
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
    extra_files: list[str] | None,
) -> int:
    owner_template, repo_template = parse_repo(template_repo)
    owner_target, repo_target = parse_repo(target_repo)

    reporter = ProgressReporter()
    reporter.stage(
        "Extract template archive", f"{owner_template}/{repo_template} → {owner_target}/{repo_target}"
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        written = extract_github_directory(
            archive_bytes,
            tmp_path,
            clean=True,
            extra_files=extra_files,
        )
        if not written:
            print("❌ Template archive does not contain a .github directory", file=sys.stderr)
            return 1
        payloads = []
        new_paths: set[str] = set()
        new_dirs: set[str] = set()
        for file_path in written:
            relative = file_path.relative_to(tmp_path)
            full_path = relative.as_posix()
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

    reporter.success("Template extraction completed")

    reporter.stage("Inspect target branch", target_repo)

    target_branch = branch or client.get_default_branch(owner_target, repo_target)
    commit_message = commit_message or f"✨ Sync .github directory from {owner_template}/{repo_template}"

    reporter.info(f"Fetched {owner_target}/{repo_target}@{target_branch}")
    ref = client.get_ref(owner_target, repo_target, f"heads/{target_branch}")
    base_commit_sha = ref["object"]["sha"]
    base_commit = client.get_git_commit(owner_target, repo_target, base_commit_sha)
    base_tree_sha = base_commit["tree"]["sha"]

    tree_entries = []

    if clean:
        reporter.stage("Clean existing .github contents", "--clean option active")
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
        print("✅ No updates required; remote repository already matches the template")
        return 0

    dedup: Dict[tuple[str, str], dict[str, Any]] = {}
    for entry in tree_entries:
        key = (entry["path"], entry["type"])
        dedup[key] = entry
    tree_entries = list(dedup.values())

    reporter.stage("Create commit", "Uploading new tree")
    tree_sha = client.create_tree(owner_target, repo_target, tree_entries, base_tree=base_tree_sha)["sha"]
    commit = client.create_commit(
        owner_target,
        repo_target,
        commit_message,
        tree_sha,
        parents=[base_commit_sha],
    )
    client.update_ref(owner_target, repo_target, target_branch, commit["sha"], force=force)

    reporter.success("Commit created")
    reporter.flush("Sync steps")
    reporter.list_panel("Updated files", [payload["path"] for payload in payloads])
    reporter.success(
        f"Applied {len(payloads)} updates to {owner_target}/{repo_target}@{target_branch} ({commit['sha'][:7]})"
    )

    if enable_pages:
        reporter.stage("Switch GitHub Pages to GitHub Actions")
        try:
            client.configure_pages_actions(owner_target, repo_target)
        except GitHubError as exc:
            print(f"⚠️ Failed to configure GitHub Pages: {exc}", file=sys.stderr)
        else:
            reporter.success("Switched to GitHub Actions deployment")
            try:
                pages_info = client.get_pages_info(owner_target, repo_target)
            except GitHubError as exc:
                print(f"⚠️ Failed to retrieve GitHub Pages info: {exc}", file=sys.stderr)
            else:
                html_url = pages_info.get("html_url")
                if html_url:
                    reporter.stage("Update repository website URL", html_url)
                    try:
                        client.update_repository(owner_target, repo_target, homepage=html_url)
                    except GitHubError as exc:
                        print(f"⚠️ Failed to update website URL: {exc}", file=sys.stderr)
                    else:
                        reporter.success("Updated repository website field")

    reporter.flush("Finishing touches")
    return 0


def sync_workflows(args: argparse.Namespace) -> int:
    token = args.token or os.getenv("GITHUB_TOKEN")
    client = GitHubClient(token=token, api_url=args.api_url)
    owner, repo = parse_repo(args.template_repo)

    reporter = ProgressReporter()
    reporter.stage("Fetch template archive", f"{owner}/{repo}")
    archive = client.download_repository_archive(owner, repo, ref=args.ref)
    reporter.success("Archive download completed")
    reporter.flush("Preparation")

    extra_files = ["index.html"] if args.include_index else None

    if args.repo:
        reporter.stage("Start remote sync", args.repo)
        reporter.flush("Remote sync kickoff")
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
            extra_files=extra_files,
        )

    destination = Path(args.destination)
    reporter.stage("Start local sync", str(destination))
    written = extract_github_directory(
        archive,
        destination,
        clean=args.clean,
        extra_files=extra_files,
    )

    reporter.flush("Sync steps")
    reporter.list_panel(
        "Updated files",
        [path.relative_to(destination).as_posix() for path in written],
    )
    reporter.success("Local .github directory synchronized with template")
    reporter.flush("Results")
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
    workflows_parser.add_argument(
        "--include-index",
        action="store_true",
        help="Copy the template repository root index.html alongside the .github directory",
    )
    workflows_parser.set_defaults(func=sync_workflows)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    # Load the runtime configuration from the current directory's .env before
    # parsing arguments so commands can rely on those environment variables.
    apply_env_file(Path.cwd() / ".env", missing_ok=True)

    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    _render_intro_animation()
    try:
        return args.func(args)
    except (GitHubError, WorkflowSyncError, FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
