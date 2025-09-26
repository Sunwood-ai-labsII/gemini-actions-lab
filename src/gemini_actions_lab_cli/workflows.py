"""Helpers for synchronising the ``.github`` folder from a template repository."""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path
from typing import Iterable


class WorkflowSyncError(RuntimeError):
    """Raised when the template repository does not contain a ``.github`` folder."""


def extract_github_directory(
    archive_bytes: bytes,
    destination: Path,
    clean: bool = False,
    extra_files: Iterable[str] | None = None,
) -> list[Path]:
    """Extract the ``.github`` directory from a zip archive into ``destination``.

    Args:
        archive_bytes: Raw bytes of a GitHub ``zipball`` response.
        destination: Base directory to extract into.
        clean: When True the existing ``.github`` directory is removed before
            writing new files.
        extra_files: Additional repository-relative files to extract (e.g. ``index.html``).

    Returns:
        A list with the paths of the files that were written.
    """

    destination = destination.expanduser().resolve()
    github_root = destination / ".github"
    extras = {path.lstrip("/") for path in (extra_files or [])}
    extras_found: set[str] = set()

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        top_level_prefix = None
        for member in archive.namelist():
            if member.endswith("/"):
                continue
            if top_level_prefix is None:
                top_level_prefix = member.split("/", 1)[0]
            if member.startswith(f"{top_level_prefix}/.github/"):
                break
        else:
            raise WorkflowSyncError("Template archive does not contain a .github directory")

        if clean and github_root.exists():
            shutil.rmtree(github_root)

        written: list[Path] = []
        for member in archive.namelist():
            if member.endswith("/"):
                continue
            if member.startswith(f"{top_level_prefix}/.github/"):
                relative_path = member[len(f"{top_level_prefix}/"):]
                target_path = destination / relative_path
            else:
                relative_repo_path = member[len(f"{top_level_prefix}/"):]
                if relative_repo_path not in extras:
                    continue
                target_path = destination / relative_repo_path
                extras_found.add(relative_repo_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, open(target_path, "wb") as dest:
                shutil.copyfileobj(source, dest)
            written.append(target_path)

        missing_extras = extras - extras_found
        if missing_extras:
            missing_repr = ", ".join(sorted(missing_extras))
            raise WorkflowSyncError(
                f"Template archive does not contain the expected files: {missing_repr}"
            )

    return written
