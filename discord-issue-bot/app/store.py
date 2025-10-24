import json
import os
import time
from pathlib import Path
from typing import Dict, List
from datetime import datetime, timedelta, timezone

from . import config
from .github_api import http_get


HISTORY_ENV = "DISCORD_ISSUE_BOT_HISTORY"
REMOTE_CACHE_TTL_SECONDS = 300

_remote_repo_cache: Dict[str, object] = {"timestamp": 0.0, "repos": []}


def _history_path() -> Path:
    custom = os.environ.get(HISTORY_ENV)
    if custom:
        p = Path(os.path.expanduser(custom)).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # Default: use container-mounted volume at /data/history.json
    p = Path("/data/history.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load() -> Dict:
    path = _history_path()
    if not path.exists():
        return {"repos": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"repos": []}
        data.setdefault("repos", [])
        if not isinstance(data["repos"], list):
            data["repos"] = []
        return data
    except Exception:
        return {"repos": []}


def _save(data: Dict) -> None:
    path = _history_path()
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        # best-effort persistence; ignore write failures
        pass


def normalize_repo(repo: str) -> str:
    return (repo or "").strip()


def remember_repo(repo: str, limit: int = 50) -> None:
    repo = normalize_repo(repo)
    if not repo:
        return
    data = _load()
    repos: List[str] = [r for r in data.get("repos", []) if isinstance(r, str)]
    # Move to front, unique
    repos = [r for r in repos if r.lower() != repo.lower()]
    repos.insert(0, repo)
    if limit and len(repos) > limit:
        repos = repos[:limit]
    data["repos"] = repos
    _save(data)


def recent_repos(query: str = "", limit: int = 25) -> List[str]:
    q = (query or "").strip().lower()
    local_repos = [r for r in _load().get("repos", []) if isinstance(r, str)]

    results: List[str] = []
    seen = set()

    def _matches(name: str) -> bool:
        return not q or q in name.lower()

    for repo in local_repos:
        if not isinstance(repo, str):
            continue
        if not _matches(repo):
            continue
        key = repo.lower()
        if key in seen:
            continue
        results.append(repo)
        seen.add(key)
        if len(results) >= limit:
            return results

    remote_candidates = _get_remote_repo_candidates()
    for repo in remote_candidates:
        if not _matches(repo):
            continue
        key = repo.lower()
        if key in seen:
            continue
        results.append(repo)
        seen.add(key)
        if len(results) >= limit:
            break

    return results[:limit]


def _get_remote_repo_candidates() -> List[str]:
    now = time.monotonic()
    cached_timestamp = _remote_repo_cache.get("timestamp", 0.0)
    if now - float(cached_timestamp) < REMOTE_CACHE_TTL_SECONDS:
        repos = _remote_repo_cache.get("repos", [])
        return list(repos) if isinstance(repos, list) else []

    repos = _fetch_remote_repos()
    _remote_repo_cache["timestamp"] = now
    _remote_repo_cache["repos"] = repos
    return repos


def _fetch_remote_repos() -> List[str]:
    accounts = config.get_repo_suggest_accounts()
    if not accounts:
        return []

    lookback_days = config.get_repo_suggest_lookback_days()
    threshold = datetime.now(timezone.utc) - timedelta(days=lookback_days) if lookback_days > 0 else None

    collected: List[str] = []
    seen: set[str] = set()

    for account in accounts:
        account = account.strip()
        if not account:
            continue
        url = f"{config.GITHUB_API}/users/{account}/repos?sort=updated&per_page=100&type=all"
        status, body = http_get(url, config.GITHUB_TOKEN)
        if status != 200 or not body:
            continue
        try:
            data = json.loads(body)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for repo in data:
            if not isinstance(repo, dict):
                continue
            full_name = repo.get("full_name")
            if not isinstance(full_name, str) or not full_name:
                continue
            key = full_name.lower()
            if key in seen:
                continue
            if repo.get("archived"):
                continue
            if threshold:
                updated_at = _parse_github_timestamp(repo.get("updated_at"))
                created_at = _parse_github_timestamp(repo.get("created_at"))
                if updated_at and updated_at >= threshold:
                    pass
                elif created_at and created_at >= threshold:
                    pass
                else:
                    continue
            seen.add(key)
            collected.append(full_name)
    return collected


def _parse_github_timestamp(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None
