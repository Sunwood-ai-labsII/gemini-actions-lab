"""Utility helpers for working with ``.env`` files."""

from __future__ import annotations

from pathlib import Path
from typing import Dict


def load_env_file(env_path: Path) -> Dict[str, str]:
    """Parse the given ``.env`` file into a mapping.

    Comments and blank lines are ignored. Values may be wrapped in single or
    double quotes. Leading and trailing whitespace surrounding keys or values is
    stripped. Lines that do not contain an equals sign are skipped silently.
    """

    env_path = env_path.expanduser()
    if not env_path.exists():
        raise FileNotFoundError(f".env file not found: {env_path}")

    variables: Dict[str, str] = {}
    for raw_line in env_path.read_text().splitlines():
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
        if value and ((value[0] == value[-1]) and value[0] in {'"', "'"}):
            value = value[1:-1]
        variables[key] = value
    return variables
