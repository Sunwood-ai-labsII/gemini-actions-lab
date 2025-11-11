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
    workflow_files: list[str] | None = None,
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
        workflow_files: Optional list of workflow file names to extract. Takes precedence
            over workflow_file if both are provided.
        use_remote: When True with workflow_file(s), prefer workflows_remote over workflows 
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
        
        # 複数ワークフローファイル指定時の処理 🎯
        target_workflows = workflow_files or ([workflow_file] if workflow_file else None)
        
        if target_workflows:
            # 各ワークフローファイルのパスを検索
            found_workflows: dict[str, str] = {}  # filename -> archive_path
            
            for wf_file in target_workflows:
                workflow_paths = []
                if use_remote:
                    # workflows_remote を優先
                    workflow_paths = [
                        f"{top_level_prefix}/.github/workflows_remote/{wf_file}",
                        f"{top_level_prefix}/.github/workflows/{wf_file}",
                    ]
                else:
                    # workflows を優先
                    workflow_paths = [
                        f"{top_level_prefix}/.github/workflows/{wf_file}",
                        f"{top_level_prefix}/.github/workflows_remote/{wf_file}",
                    ]
                
                found = None
                for wf_path in workflow_paths:
                    if wf_path in archive.namelist():
                        found = wf_path
                        break
                
                if found:
                    found_workflows[wf_file] = found
                else:
                    raise WorkflowSyncError(
                        f"Workflow file '{wf_file}' not found in .github/workflows"
                        f"{' or .github/workflows_remote' if use_remote else ''}"
                    )

        if clean and github_root.exists():
            shutil.rmtree(github_root)

        written: list[Path] = []
        for member in archive.namelist():
            if member.endswith("/"):
                continue
            
            # 複数ワークフローファイル指定時は、それらのファイルだけを処理 🎯
            if target_workflows:
                # このメンバーが対象ワークフローかチェック
                matched_wf = None
                for wf_file, wf_path in found_workflows.items():
                    if member == wf_path:
                        matched_wf = wf_file
                        break
                
                if not matched_wf:
                    continue
                
                # workflows_remote からの場合は workflows にコピー
                if "workflows_remote" in member:
                    relative_path = f".github/workflows/{matched_wf}"
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

                # --use-remote の場合の特別な処理
                if use_remote:
                    # workflows_remote 内のワークフローを workflows にコピー
                    if relative_path.startswith(".github/workflows_remote/") and relative_path.endswith(".yml"):
                        # workflows_remote/ を workflows/ に変換
                        workflow_file = relative_path.split("/")[-1]
                        relative_path = f".github/workflows/{workflow_file}"
                        target_path = destination / relative_path
                    # workflows_remote ディレクトリそのものはスキップ
                    elif relative_path.startswith(".github/workflows_remote/"):
                        continue
                    # scripts ディレクトリはスキップ
                    elif relative_path.startswith(".github/scripts/"):
                        continue
                    else:
                        target_path = destination / relative_path
                else:
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

        # extra_files のチェックは workflow 指定時はスキップ 🎯
        if not target_workflows:
            missing_extras = extras - extras_found
            if missing_extras:
                missing_repr = ", ".join(sorted(missing_extras))
                raise WorkflowSyncError(
                    f"Template archive does not contain the expected files: {missing_repr}"
                )

    return ExtractionResult(written=written, skipped_existing=skipped_existing)
