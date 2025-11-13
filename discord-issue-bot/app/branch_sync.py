"""Branch synchronization for Discord Bot."""

from __future__ import annotations

import json
from dataclasses import dataclass

from . import config
from .github_api import http_get, http_post


@dataclass
class BranchSyncResult:
    """Result of branch synchronization."""

    created: list[str]  # Successfully created branches
    skipped: list[str]  # Skipped existing branches
    failed: list[tuple[str, str]]  # (branch_name, error_message)

    @property
    def created_count(self) -> int:
        return len(self.created)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    @property
    def failed_count(self) -> int:
        return len(self.failed)


class BranchSyncError(Exception):
    """Raised when branch synchronization fails."""
    pass


def get_default_branch(repo: str, token: str) -> str:
    """Get the default branch of a repository.

    Args:
        repo: Repository in 'owner/repo' format.
        token: GitHub token for authentication.

    Returns:
        Default branch name.

    Raises:
        BranchSyncError: If retrieval fails.
    """
    url = f"{config.GITHUB_API}/repos/{repo}"
    status, body = http_get(url, token)

    try:
        data = json.loads(body) if body else {}
    except Exception as e:
        raise BranchSyncError(f"Failed to parse repository info: {e}")

    if status != 200:
        raise BranchSyncError(
            f"Failed to get repository info (status {status}): {body[:500]}"
        )

    default_branch = data.get("default_branch")
    if not default_branch:
        raise BranchSyncError("Repository has no default branch")

    return default_branch


def get_branch_sha(repo: str, branch: str, token: str) -> str | None:
    """Get the latest commit SHA of a branch.

    Args:
        repo: Repository in 'owner/repo' format.
        branch: Branch name.
        token: GitHub token for authentication.

    Returns:
        Commit SHA, or None if branch doesn't exist.

    Raises:
        BranchSyncError: If retrieval fails (not including 404).
    """
    url = f"{config.GITHUB_API}/repos/{repo}/git/ref/heads/{branch}"
    status, body = http_get(url, token)

    if status == 404:
        return None

    try:
        data = json.loads(body) if body else {}
    except Exception as e:
        raise BranchSyncError(f"Failed to parse branch info: {e}")

    if status != 200:
        raise BranchSyncError(
            f"Failed to get branch info (status {status}): {body[:500]}"
        )

    sha = data.get("object", {}).get("sha")
    if not sha:
        raise BranchSyncError(f"Branch {branch} has no commit SHA")

    return sha


def create_branch(
    repo: str,
    branch_name: str,
    base_sha: str,
    token: str,
) -> bool:
    """Create a new branch in a repository.

    Args:
        repo: Repository in 'owner/repo' format.
        branch_name: Name of the branch to create.
        base_sha: Commit SHA to base the branch on.
        token: GitHub token for authentication.

    Returns:
        True if created, False if already exists.

    Raises:
        BranchSyncError: If creation fails.
    """
    # Check if branch already exists
    existing_sha = get_branch_sha(repo, branch_name, token)
    if existing_sha:
        return False

    # Create the branch
    url = f"{config.GITHUB_API}/repos/{repo}/git/refs"
    payload = {
        "ref": f"refs/heads/{branch_name}",
        "sha": base_sha,
    }

    status, body = http_post(url, token, payload)

    if status in (200, 201):
        return True

    # Handle already exists error
    if status == 422 and body and "already exists" in body.lower():
        return False

    raise BranchSyncError(
        f"Failed to create branch {branch_name} (status {status}): {body[:500]}"
    )


def sync_branches(
    repo: str,
    branches: list[str],
    token: str,
    base_branch: str | None = None,
    dry_run: bool = False,
) -> BranchSyncResult:
    """Synchronize branches to a repository.

    Args:
        repo: Repository in 'owner/repo' format.
        branches: List of branch names to create.
        token: GitHub token for authentication.
        base_branch: Base branch to create from. If None, uses default branch.
        dry_run: If True, only preview changes without creating.

    Returns:
        BranchSyncResult with details of the operation.

    Raises:
        BranchSyncError: If synchronization fails.
    """
    result = BranchSyncResult(created=[], skipped=[], failed=[])

    # Get base branch
    if not base_branch:
        base_branch = get_default_branch(repo, token)

    # Get base commit SHA
    base_sha = get_branch_sha(repo, base_branch, token)
    if not base_sha:
        raise BranchSyncError(f"Base branch {base_branch} not found")

    # Dry run: check which branches exist
    if dry_run:
        for branch_name in branches:
            existing_sha = get_branch_sha(repo, branch_name, token)
            if existing_sha:
                result.skipped.append(branch_name)
            else:
                result.created.append(branch_name)
        return result

    # Create branches
    for branch_name in branches:
        try:
            created = create_branch(repo, branch_name, base_sha, token)
            if created:
                result.created.append(branch_name)
            else:
                result.skipped.append(branch_name)
        except BranchSyncError as e:
            result.failed.append((branch_name, str(e)))
        except Exception as e:
            result.failed.append((branch_name, f"Unexpected error: {e}"))

    return result
