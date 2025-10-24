"""Helpers for synchronizing GitHub Actions environment variables."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Tuple
from urllib import error, parse, request

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


def sync_repository_variables(
    repo: str,
    items: Dict[str, str],
    *,
    token: str,
    dry_run: bool = False,
) -> SyncResult:
    if not items:
        return SyncResult()

    base_url = f"{config.GITHUB_API}/repos/{repo}/actions/variables"
    created: list[str] = []
    updated: list[str] = []
    failures: list[Tuple[str, int, str]] = []

    for name, value in items.items():
        if dry_run:
            continue
        target = f"{base_url}/{parse.quote(name, safe='')}"
        status, body = _call_github("PATCH", target, {"value": value}, token)
        if status == 204:
            updated.append(name)
            continue
        if status == 404:
            status, body = _call_github("POST", base_url, {"name": name, "value": value}, token)
            if status in (201, 204):
                created.append(name)
                continue
        failures.append((name, status, (body or "")[:300]))

    return SyncResult(created=created, updated=updated, failed=failures)


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
