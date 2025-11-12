"""Workflow preset synchronization for Discord Bot."""

from __future__ import annotations

import io
import json
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config
from .github_api import http_get


@dataclass
class WorkflowSyncResult:
    """Result of workflow synchronization."""

    written: list[str]  # Successfully written files
    skipped: list[str]  # Skipped existing files
    failed: list[tuple[str, str]]  # (filename, error_message)

    @property
    def success_count(self) -> int:
        return len(self.written)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)

    @property
    def failed_count(self) -> int:
        return len(self.failed)


class WorkflowSyncError(Exception):
    """Raised when workflow synchronization fails."""
    pass


def load_workflow_presets() -> dict[str, Any]:
    """Load workflow presets from the CLI package.

    Returns:
        Dictionary of preset configurations.

    Raises:
        WorkflowSyncError: If presets cannot be loaded.
    """
    try:
        # Try to import from the CLI package
        from gemini_actions_lab_cli.workflow_presets import WORKFLOW_PRESETS
        return WORKFLOW_PRESETS
    except ImportError as e:
        raise WorkflowSyncError(
            f"Failed to import workflow presets. Is gemini-actions-lab-cli installed? Error: {e}"
        )


def get_preset_info(preset_name: str) -> tuple[list[str], bool, list[str] | None, list[str] | None]:
    """Get workflow list, use_remote flag, prompts, and agents for a preset.

    Args:
        preset_name: Name of the preset to retrieve.

    Returns:
        Tuple of (workflow_list, use_remote_flag, prompt_files, agent_files).

    Raises:
        WorkflowSyncError: If preset_name doesn't exist.
    """
    presets = load_workflow_presets()

    if preset_name not in presets:
        available = ", ".join(sorted(presets.keys()))
        raise WorkflowSyncError(
            f"Unknown preset '{preset_name}'. Available presets: {available}"
        )

    preset = presets[preset_name]
    workflows = preset.get("workflows", [])
    use_remote = preset.get("use_remote", False)
    prompts = preset.get("prompts")
    agents = preset.get("agents")

    return workflows, use_remote, prompts, agents


def list_available_presets() -> list[tuple[str, str]]:
    """List all available presets with their descriptions.

    Returns:
        List of (preset_name, description) tuples.
    """
    try:
        presets = load_workflow_presets()
        return [
            (name, preset.get("description", "No description"))
            for name, preset in sorted(presets.items())
        ]
    except WorkflowSyncError:
        return []


def download_template_repo(template_repo: str, token: str) -> bytes:
    """Download a template repository as a zip archive.

    Args:
        template_repo: Repository in 'owner/repo' format.
        token: GitHub token for authentication.

    Returns:
        Raw bytes of the zipball.

    Raises:
        WorkflowSyncError: If download fails.
    """
    url = f"{config.GITHUB_API}/repos/{template_repo}/zipball"
    status, body = http_get(url, token)

    if status != 200:
        raise WorkflowSyncError(
            f"Failed to download template repository (status {status}): {body[:500] if body else 'No response'}"
        )

    return body.encode('latin-1') if isinstance(body, str) else body


def extract_workflow_files(
    archive_bytes: bytes,
    workflow_files: list[str],
    use_remote: bool = False,
    prompt_files: list[str] | None = None,
    agent_files: list[str] | None = None,
) -> dict[str, str]:
    """Extract specific workflow, prompt, and agent files from a zip archive.

    Args:
        archive_bytes: Raw bytes of a GitHub zipball response.
        workflow_files: List of workflow file names to extract.
        use_remote: When True, prefer workflows_remote over workflows directory.
        prompt_files: Optional list of prompt file names to extract.
        agent_files: Optional list of agent file names to extract.

    Returns:
        Dictionary mapping relative file paths to file contents.

    Raises:
        WorkflowSyncError: If required files are not found.
    """
    extracted: dict[str, str] = {}

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        # Find the top-level prefix
        top_level_prefix = None
        for member in archive.namelist():
            if member.endswith("/"):
                continue
            top_level_prefix = member.split("/", 1)[0]
            break

        if not top_level_prefix:
            raise WorkflowSyncError("Template archive is empty or invalid")

        # Extract workflow files
        for wf_file in workflow_files:
            workflow_paths = []
            if use_remote:
                workflow_paths = [
                    f"{top_level_prefix}/.github/workflows_remote/{wf_file}",
                    f"{top_level_prefix}/.github/workflows/{wf_file}",
                ]
            else:
                workflow_paths = [
                    f"{top_level_prefix}/.github/workflows/{wf_file}",
                    f"{top_level_prefix}/.github/workflows_remote/{wf_file}",
                ]

            found = None
            for wf_path in workflow_paths:
                if wf_path in archive.namelist():
                    found = wf_path
                    break

            if not found:
                raise WorkflowSyncError(
                    f"Workflow file '{wf_file}' not found in .github/workflows"
                    f"{' or .github/workflows_remote' if use_remote else ''}"
                )

            with archive.open(found) as f:
                content = f.read().decode('utf-8')
                extracted[f".github/workflows/{wf_file}"] = content

        # Extract prompt files
        if prompt_files:
            for prompt_file in prompt_files:
                prompt_path = f"{top_level_prefix}/.github/prompts/{prompt_file}"
                if prompt_path not in archive.namelist():
                    raise WorkflowSyncError(
                        f"Prompt file '{prompt_file}' not found in .github/prompts"
                    )

                with archive.open(prompt_path) as f:
                    content = f.read().decode('utf-8')
                    extracted[f".github/prompts/{prompt_file}"] = content

        # Extract agent files
        if agent_files:
            for agent_file in agent_files:
                agent_path = f"{top_level_prefix}/.github/agents/{agent_file}"
                if agent_path not in archive.namelist():
                    raise WorkflowSyncError(
                        f"Agent file '{agent_file}' not found in .github/agents"
                    )

                with archive.open(agent_path) as f:
                    content = f.read().decode('utf-8')
                    extracted[f".github/agents/{agent_file}"] = content

    return extracted


def sync_workflow_preset(
    target_repo: str,
    preset_name: str,
    template_repo: str,
    token: str,
    dry_run: bool = False,
    overwrite: bool = False,
) -> WorkflowSyncResult:
    """Synchronize a workflow preset to a target repository.

    Args:
        target_repo: Target repository in 'owner/repo' format.
        preset_name: Name of the preset to synchronize.
        template_repo: Template repository to sync from.
        token: GitHub token for authentication.
        dry_run: If True, only preview changes without writing.
        overwrite: If True, overwrite existing files.

    Returns:
        WorkflowSyncResult with details of the operation.

    Raises:
        WorkflowSyncError: If synchronization fails.
    """
    # Get preset information
    workflow_files, use_remote, prompt_files, agent_files = get_preset_info(preset_name)

    if not workflow_files and not prompt_files and not agent_files:
        raise WorkflowSyncError(f"Preset '{preset_name}' has no files to sync")

    # Download template repository
    archive_bytes = download_template_repo(template_repo, token)

    # Extract files
    extracted_files = extract_workflow_files(
        archive_bytes,
        workflow_files,
        use_remote,
        prompt_files,
        agent_files,
    )

    if dry_run:
        # Return preview without writing
        return WorkflowSyncResult(
            written=[],
            skipped=list(extracted_files.keys()),
            failed=[],
        )

    # Clone the target repository and write files
    # For Discord Bot, we'll use GitHub API to create/update files
    result = WorkflowSyncResult(written=[], skipped=[], failed=[])

    for file_path, content in extracted_files.items():
        try:
            status = create_or_update_file(
                target_repo,
                file_path,
                content,
                token,
                overwrite=overwrite,
            )
            if status == "written":
                result.written.append(file_path)
            elif status == "skipped":
                result.skipped.append(file_path)
        except Exception as e:
            result.failed.append((file_path, str(e)))

    return result


def create_or_update_file(
    repo: str,
    file_path: str,
    content: str,
    token: str,
    overwrite: bool = False,
) -> str:
    """Create or update a file in a repository using GitHub API.

    Args:
        repo: Repository in 'owner/repo' format.
        file_path: Path to the file in the repository.
        content: File content.
        token: GitHub token for authentication.
        overwrite: If True, overwrite existing files.

    Returns:
        Status: "written" or "skipped".

    Raises:
        WorkflowSyncError: If the operation fails.
    """
    import base64
    from .github_api import http_get, http_post

    # Check if file exists
    url = f"{config.GITHUB_API}/repos/{repo}/contents/{file_path}"
    status, body = http_get(url, token)

    file_exists = status == 200
    sha = None

    if file_exists:
        if not overwrite:
            return "skipped"

        try:
            data = json.loads(body) if body else {}
            sha = data.get("sha")
        except Exception:
            pass

    # Create or update the file
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')

    payload = {
        "message": f"Sync workflow file: {file_path}",
        "content": encoded_content,
    }

    if sha:
        payload["sha"] = sha

    # Use PUT request for creating/updating files
    import urllib.request as request

    req = request.Request(url, method="PUT")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", "application/json")

    try:
        with request.urlopen(req, data=json.dumps(payload).encode('utf-8')) as response:
            if response.status in (200, 201):
                return "written"
            else:
                raise WorkflowSyncError(
                    f"Failed to write file {file_path}: HTTP {response.status}"
                )
    except Exception as e:
        raise WorkflowSyncError(f"Failed to write file {file_path}: {e}")
