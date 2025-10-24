"""Reusable helpers for synchronizing GitHub Actions repository secrets."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping

from .env_loader import load_env_file
from .github_api import API_URL, GitHubClient, GitHubError, encrypt_secret, parse_repo


@dataclass(slots=True)
class SecretSyncError:
    name: str
    status: int
    message: str


@dataclass(slots=True)
class SecretSyncResult:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    failed: list[SecretSyncError] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.created) + len(self.updated) + len(self.failed)

    def ok(self) -> bool:
        return not self.failed


def sync_repository_secrets(
    repo: str,
    values: Mapping[str, str],
    *,
    token: str,
    api_url: str | None = None,
) -> SecretSyncResult:
    """Synchronize ``values`` into GitHub Actions Secrets for ``repo``.

    Args:
        repo: Repository in ``owner/name`` format.
        values: Mapping of secret names to plain-text values.
        token: GitHub token with ``actions:write`` scope.
        api_url: Overridden GitHub API URL (defaults to the public API).

    Returns:
        Details about created, updated, and failed secrets.
    """

    if not values:
        return SecretSyncResult()

    owner, name = parse_repo(repo)
    client = GitHubClient(token=token, api_url=api_url or API_URL)
    public_key = client.get_actions_public_key(owner, name)

    result = SecretSyncResult()
    for secret_name, secret_value in values.items():
        encrypted = encrypt_secret(public_key["key"], secret_value)
        try:
            status = client.put_actions_secret(
                owner,
                name,
                secret_name,
                encrypted,
                public_key["key_id"],
            )
        except GitHubError as exc:
            result.failed.append(
                SecretSyncError(secret_name, exc.status or 0, str(exc))
            )
            continue

        if status == 201:
            result.created.append(secret_name)
        else:
            result.updated.append(secret_name)
    return result


def sync_secrets_from_env_file(
    repo: str,
    env_paths: Iterable[str | Path],
    *,
    token: str,
    api_url: str | None = None,
) -> SecretSyncResult:
    """Load one or more ``.env`` files and synchronize them as secrets."""

    combined: dict[str, str] = {}
    for path in env_paths:
        data = load_env_file(Path(path), missing_ok=False)
        combined.update(data)
    return sync_repository_secrets(repo, combined, token=token, api_url=api_url)
