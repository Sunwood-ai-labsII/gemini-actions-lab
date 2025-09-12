import json
import os
from pathlib import Path
from typing import Dict, List


HISTORY_ENV = "DISCORD_ISSUE_BOT_HISTORY"


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
    repos = [r for r in _load().get("repos", []) if isinstance(r, str)]
    if q:
        repos = [r for r in repos if q in r.lower()]
    return repos[:limit]
