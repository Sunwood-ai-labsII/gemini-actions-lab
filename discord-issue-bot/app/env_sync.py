"""Helpers for synchronizing GitHub Actions environment variables."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Tuple
from urllib import error, parse, request

from nacl import encoding, public

from . import config


@dataclass(slots=True)
class SyncResult:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    failed: list[Tuple[str, int, str]] = field(default_factory=list)

    @property
    def created_count(self) -> int:
        return len(self.created)

    @property
    def updated_count(self) -> int:
        return len(self.updated)

    @property
    def failed_count(self) -> int:
        return len(self.failed)


def load_env_file(path: str | Path) -> Dict[str, str]:
    env_path = Path(path).expanduser()
    if not env_path.exists():
        raise FileNotFoundError(f".env file not found: {env_path}")

    variables: Dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        variables[key] = value
    return variables


def _call_github(method: str, url: str, payload: dict, token: str) -> Tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, body
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, body
    except error.URLError as exc:
        return 0, str(exc.reason)


def _call_github_get(url: str, token: str) -> Tuple[int, str]:
    """GET request to GitHub API."""
    req = request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, body
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, body
    except error.URLError as exc:
        return 0, str(exc.reason)


def _get_public_key(repo: str, token: str) -> Tuple[str, str] | None:
    """Get repository public key for encrypting secrets.

    Returns (key_id, key) tuple or None on failure.
    """
    url = f"{config.GITHUB_API}/repos/{repo}/actions/secrets/public-key"
    status, body = _call_github_get(url, token)
    if status != 200:
        return None
    try:
        data = json.loads(body)
        return data.get("key_id"), data.get("key")
    except Exception:
        return None


def _encrypt_secret(public_key: str, secret_value: str) -> str:
    """Encrypt a secret using the repository's public key.

    Args:
        public_key: Base64-encoded public key from GitHub
        secret_value: The secret value to encrypt

    Returns:
        Base64-encoded encrypted value
    """
    public_key_bytes = base64.b64decode(public_key)
    sealed_box = public.SealedBox(public.PublicKey(public_key_bytes))
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def sync_repository_variables(
    repo: str,
    items: Dict[str, str],
    *,
    token: str,
    dry_run: bool = False,
) -> SyncResult:
    """Sync environment variables as GitHub Actions secrets (encrypted).

    Note: Despite the function name, this now syncs items as **secrets** (not variables)
    to ensure sensitive data from .env files is properly encrypted.
    """
    if not items:
        return SyncResult()

    # Get repository public key for encrypting secrets
    key_result = _get_public_key(repo, token)
    if not key_result:
        # If we can't get the public key, fail all items
        failures = [(name, 0, "Failed to retrieve repository public key") for name in items.keys()]
        return SyncResult(failed=failures)

    key_id, public_key = key_result

    base_url = f"{config.GITHUB_API}/repos/{repo}/actions/secrets"
    created: list[str] = []
    updated: list[str] = []
    failures: list[Tuple[str, int, str]] = []

    for name, value in items.items():
        if dry_run:
            continue

        # Encrypt the secret value
        try:
            encrypted_value = _encrypt_secret(public_key, value)
        except Exception as exc:
            failures.append((name, 0, f"Encryption failed: {exc}"))
            continue

        # Use PUT to create or update the secret
        target = f"{base_url}/{parse.quote(name, safe='')}"
        payload = {
            "encrypted_value": encrypted_value,
            "key_id": key_id,
        }

        status, body = _call_github("PUT", target, payload, token)
        if status in (201, 204):
            # GitHub returns 201 for creation, 204 for update
            # We can't reliably distinguish between them without a prior GET,
            # so we'll mark all as "updated" for simplicity
            updated.append(name)
        else:
            failures.append((name, status, (body or "")[:300]))

    return SyncResult(created=[], updated=updated, failed=failures)


def filter_variables(
    variables: Dict[str, str],
    include: Iterable[str] | None = None,
    exclude: Iterable[str] | None = None,
) -> Dict[str, str]:
    include_set = {key.strip() for key in (include or []) if key.strip()}
    exclude_set = {key.strip() for key in (exclude or []) if key.strip()}

    filtered: Dict[str, str] = {}
    for name, value in variables.items():
        if include_set and name not in include_set:
            continue
        if name in exclude_set:
            continue
        filtered[name] = value
    return filtered
