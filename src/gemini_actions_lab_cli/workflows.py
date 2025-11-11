"""Helpers for synchronising the ``.github`` folder from a template repository."""

from __future__ import annotations

import io
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class ExtractionResult:
    """Outcome of extracting the template archive."""

    written: list[Path]
    skipped_existing: list[Path]


class WorkflowSyncError(RuntimeError):
    """Raised when the template repository does not contain a ``.github`` folder."""


def extract_github_directory(
    archive_bytes: bytes,
    destination: Path,
    clean: bool = False,
    extra_files: Iterable[str] | None = None,
    *,
    overwrite_extras: bool = False,
    overwrite_existing: bool = False,
    workflow_file: str | None = None,
    use_remote: bool = False,
) -> ExtractionResult:
    """Extract the ``.github`` directory from a zip archive into ``destination``.

    Args:
        archive_bytes: Raw bytes of a GitHub ``zipball`` response.
        destination: Base directory to extract into.
        clean: When True the existing ``.github`` directory is removed before
            writing new files.
        extra_files: Additional repository-relative files to extract (e.g. ``index.html``).
        overwrite_extras: When ``True``, always overwrite files listed in ``extra_files``.
            When ``False`` (default), existing files are preserved.
        overwrite_existing: When ``True``, overwrite files inside ``.github`` that already
            exist at the destination. When ``False`` (default), existing files are skipped.
        workflow_file: Optional specific workflow file name to extract from workflows or 
            workflows_remote directory. When provided, only this file is extracted.
        use_remote: When True with workflow_file, prefer workflows_remote over workflows 
            directory.

    Returns:
        An :class:`ExtractionResult` describing which files were written and which were
        skipped because they already existed.
    """

    destination = destination.expanduser().resolve()
    github_root = destination / ".github"
    extras = {path.lstrip("/") for path in (extra_files or [])}
    extras_found: set[str] = set()
    skipped_existing: list[Path] = []

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
        
        # 特定のワークフローファイル指定時の処理 🎯
        if workflow_file:
            workflow_paths = []
            if use_remote:
                # workflows_remote を優先
                workflow_paths = [
                    f"{top_level_prefix}/.github/workflows_remote/{workflow_file}",
                    f"{top_level_prefix}/.github/workflows/{workflow_file}",
                ]
            else:
                # workflows を優先
                workflow_paths = [
                    f"{top_level_prefix}/.github/workflows/{workflow_file}",
                    f"{top_level_prefix}/.github/workflows_remote/{workflow_file}",
                ]
            
            found_workflow = None
            for wf_path in workflow_paths:
                if wf_path in archive.namelist():
                    found_workflow = wf_path
                    break
            
            if not found_workflow:
                raise WorkflowSyncError(
                    f"Workflow file '{workflow_file}' not found in .github/workflows"
                    f"{' or .github/workflows_remote' if use_remote else ''}"
                )

        if clean and github_root.exists():
            shutil.rmtree(github_root)

        written: list[Path] = []
        for member in archive.namelist():
            if member.endswith("/"):
                continue
            
            # 特定のワークフローファイル指定時は、そのファイルだけを処理 🎯
            if workflow_file:
                if member != found_workflow:
                    continue
                # workflows_remote からの場合は workflows にコピー
                if "workflows_remote" in member:
                    relative_path = f".github/workflows/{workflow_file}"
                else:
                    relative_path = member[len(f"{top_level_prefix}/"):]
                target_path = destination / relative_path
                target_path.parent.mkdir(parents=True, exist_ok=True)
                if not overwrite_existing and target_path.exists():
                    skipped_existing.append(target_path)
                    continue
                with archive.open(member) as source, open(target_path, "wb") as dest:
                    shutil.copyfileobj(source, dest)
                written.append(target_path)
                continue
            
            # 既存のロジック：.github 全体のコピー
            if member.startswith(f"{top_level_prefix}/.github/"):
                relative_path = member[len(f"{top_level_prefix}/"):]
                target_path = destination / relative_path
                is_github_file = True
            else:
                relative_repo_path = member[len(f"{top_level_prefix}/"):]
                if relative_repo_path not in extras:
                    continue
                target_path = destination / relative_repo_path
                extras_found.add(relative_repo_path)
                if not overwrite_extras and target_path.exists():
                    # Keep the existing file intact when extras are optional
                    skipped_existing.append(target_path)
                    continue
                is_github_file = False
            if is_github_file and not overwrite_existing and target_path.exists():
                skipped_existing.append(target_path)
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, open(target_path, "wb") as dest:
                shutil.copyfileobj(source, dest)
            written.append(target_path)

        # extra_files のチェックは workflow_file 指定時はスキップ 🎯
        if not workflow_file:
            missing_extras = extras - extras_found
            if missing_extras:
                missing_repr = ", ".join(sorted(missing_extras))
                raise WorkflowSyncError(
                    f"Template archive does not contain the expected files: {missing_repr}"
                )

    return ExtractionResult(written=written, skipped_existing=skipped_existing)
