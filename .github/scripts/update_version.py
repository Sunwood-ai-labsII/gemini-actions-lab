#!/usr/bin/env python3
"""Update the version field inside the [project] table of pyproject.toml."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inject release version into pyproject.toml")
    parser.add_argument("version", help="Version string to set")
    parser.add_argument(
        "--path",
        default="pyproject.toml",
        help="Path to pyproject.toml (default: %(default)s)",
    )
    return parser.parse_args()


def update_version(path: Path, version: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")

    lines = path.read_text(encoding="utf-8").splitlines()
    updated_lines: list[str] = []
    in_project = False
    project_found = False
    version_set = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_project and not version_set:
                updated_lines.append(f'version = "{version}"')
                version_set = True
            in_project = stripped == "[project]"
            project_found = project_found or in_project
            updated_lines.append(line)
            continue

        if in_project and stripped.startswith("version") and "=" in stripped:
            indent = line[: len(line) - len(line.lstrip())]
            if not version_set:
                updated_lines.append(f'{indent}version = "{version}"')
                version_set = True
            continue

        updated_lines.append(line)

    if not project_found:
        raise RuntimeError("[project] table not found in pyproject.toml")

    if in_project and not version_set:
        updated_lines.append(f'version = "{version}"')
        version_set = True

    if not version_set:
        for idx, line in enumerate(updated_lines):
            if line.strip() == "[project]":
                updated_lines.insert(idx + 1, f'version = "{version}"')
                version_set = True
                break

    if not version_set:
        raise RuntimeError("Failed to inject version into [project] table")

    path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    try:
        update_version(Path(args.path), args.version)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
