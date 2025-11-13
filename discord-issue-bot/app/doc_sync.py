"""Documentation synchronization for Discord Bot."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass

from . import config
from .github_api import http_get


@dataclass
class DocSyncResult:
    """Result of documentation synchronization."""

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


class DocSyncError(Exception):
    """Raised when documentation synchronization fails."""
    pass


DEFAULT_DOC_FILES = ["AGENTS.md", "Claude.md", "GEMINI.md"]


def download_template_repo(template_repo: str, token: str) -> bytes:
    """Download a template repository as a zip archive.

    Args:
        template_repo: Repository in 'owner/repo' format.
        token: GitHub token for authentication.

    Returns:
        Raw bytes of the zipball.

    Raises:
        DocSyncError: If download fails.
    """
    from urllib import request as urllib_request, error as urllib_error

    url = f"{config.GITHUB_API}/repos/{template_repo}/zipball"
    req = urllib_request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib_request.urlopen(req, timeout=60) as resp:
            if resp.status != 200:
                body = resp.read().decode("utf-8", errors="replace")
                raise DocSyncError(
                    f"Failed to download template repository (status {resp.status}): {body[:500]}"
                )
            return resp.read()
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise DocSyncError(
            f"Failed to download template repository (status {exc.code}): {body[:500]}"
        ) from exc
    except urllib_error.URLError as exc:
        raise DocSyncError(f"Failed to download template repository: {exc.reason}") from exc


def extract_doc_files(
    archive_bytes: bytes,
    doc_files: list[str],
) -> dict[str, str]:
    """Extract specific documentation files from a zip archive.

    Args:
        archive_bytes: Raw bytes of a GitHub zipball response.
        doc_files: List of documentation file names to extract.

    Returns:
        Dictionary mapping relative file paths to file contents.

    Raises:
        DocSyncError: If required files are not found.
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
            raise DocSyncError("Template archive is empty or invalid")

        # Extract documentation files
        for doc_file in doc_files:
            doc_path = f"{top_level_prefix}/{doc_file}"

            if doc_path not in archive.namelist():
                raise DocSyncError(
                    f"Documentation file '{doc_file}' not found in repository root"
                )

            with archive.open(doc_path) as f:
                content = f.read().decode('utf-8', errors='replace')
                extracted[doc_file] = content

    return extracted


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
        DocSyncError: If the operation fails.
    """
    import base64
    from .github_api import http_post

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
        "message": f"Sync documentation file: {file_path}",
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
                raise DocSyncError(
                    f"Failed to write file {file_path}: HTTP {response.status}"
                )
    except Exception as e:
        raise DocSyncError(f"Failed to write file {file_path}: {e}")


def sync_docs(
    target_repo: str,
    template_repo: str,
    token: str,
    doc_files: list[str] | None = None,
    dry_run: bool = False,
    overwrite: bool = False,
) -> DocSyncResult:
    """Synchronize documentation files to a target repository.

    Args:
        target_repo: Target repository in 'owner/repo' format.
        template_repo: Template repository to sync from.
        token: GitHub token for authentication.
        doc_files: List of documentation files to sync. Defaults to DEFAULT_DOC_FILES.
        dry_run: If True, only preview changes without writing.
        overwrite: If True, overwrite existing files.

    Returns:
        DocSyncResult with details of the operation.

    Raises:
        DocSyncError: If synchronization fails.
    """
    if doc_files is None:
        doc_files = DEFAULT_DOC_FILES

    if not doc_files:
        raise DocSyncError("No documentation files specified")

    # Download template repository
    archive_bytes = download_template_repo(template_repo, token)

    # Extract files
    extracted_files = extract_doc_files(archive_bytes, doc_files)

    if dry_run:
        # Return preview without writing
        return DocSyncResult(
            written=[],
            skipped=list(extracted_files.keys()),
            failed=[],
        )

    # Write files to target repository
    result = DocSyncResult(written=[], skipped=[], failed=[])

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
