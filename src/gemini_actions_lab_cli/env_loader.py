"""Utility helpers for working with ``.env`` files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


def load_env_file(env_path: Path, *, missing_ok: bool = False) -> Dict[str, str]:
    """Parse the given ``.env`` file into a mapping.

    Comments and blank lines are ignored. Values may be wrapped in single or
    double quotes. Leading and trailing whitespace surrounding keys or values is
    stripped. Lines that do not contain an equals sign are skipped silently.

    Args:
        env_path: Path-like pointing to the ``.env`` file.
        missing_ok: When ``True`` a missing file is treated as empty instead of
            raising :class:`FileNotFoundError`.
    """

    env_path = env_path.expanduser()
    if not env_path.exists():
        if missing_ok:
            return {}
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


def apply_env_file(env_path: Path, *, override: bool = False, missing_ok: bool = True) -> Dict[str, str]:
    """Load ``env_path`` and merge its values into ``os.environ``.

    Args:
        env_path: File whose key/value pairs should be loaded.
        override: When ``True`` values from the file always overwrite existing
            environment variables. Defaults to only populating previously unset
            keys so that explicit env vars win.
        missing_ok: When ``True`` (default) a missing file is ignored.

    Returns:
        The parsed key/value mapping (which is empty for a missing file when
        ``missing_ok`` is enabled).
    """

    variables = load_env_file(env_path, missing_ok=missing_ok)
    for key, value in variables.items():
        if override or key not in os.environ:
            os.environ[key] = value
    return variables
