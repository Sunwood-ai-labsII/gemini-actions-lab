"""Entry point for the ``gemini-actions-lab-cli`` command line interface."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable

from .env_loader import load_env_file
from .github_api import GitHubClient, GitHubError, encrypt_secret, parse_repo
from .workflows import WorkflowSyncError, extract_github_directory

DEFAULT_TEMPLATE_REPO = "Sunwood-ai-labsII/gemini-actions-lab"


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

    print(f"🎉 Successfully synced {len(encrypted_payloads)} secrets to {owner}/{repo}")
    return 0


def sync_workflows(args: argparse.Namespace) -> int:
    token = args.token or os.getenv("GITHUB_TOKEN")
    client = GitHubClient(token=token, api_url=args.api_url)
    owner, repo = parse_repo(args.template_repo)
    archive = client.download_repository_archive(owner, repo, ref=args.ref)

    destination = Path(args.destination)
    written = extract_github_directory(archive, destination, clean=args.clean)

    print("📦 Updated the following files:")
    for path in written:
        print(f" - {path.relative_to(destination)}")

    print("🚀 .github directory is now in sync with the template repository")
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
        "--env-file", default=".env", help="Path to the .env file containing secret values"
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
        "--clean",
        action="store_true",
        help="Remove the existing .github directory before extracting the template",
    )
    workflows_parser.add_argument(
        "--token", help="Optional GitHub token if the template repository is private"
    )
    workflows_parser.set_defaults(func=sync_workflows)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return args.func(args)
    except (GitHubError, WorkflowSyncError, FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
