"""Tests for workflow synchronisation helpers."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from unittest import mock

import pytest

from gemini_actions_lab_cli.cli import _sync_workflows_remote
from gemini_actions_lab_cli.github_api import GitHubClient
from gemini_actions_lab_cli.workflows import extract_github_directory, WorkflowSyncError


def _make_template_archive(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(f"template-main/{path}", content)
    return buffer.getvalue()


class TestExtractGithubDirectory:
    """Behaviour tests for ``extract_github_directory``."""

    def test_preserves_existing_extra_file(self, tmp_path: Path) -> None:
        """Extra files are not overwritten unless requested."""
        archive = _make_template_archive(
            {
                ".github/workflows/test.yml": "name: CI",
                "index.html": "<html>template</html>",
            }
        )
        destination = tmp_path / "dest"
        destination.mkdir()
        index_path = destination / "index.html"
        index_path.write_text("<html>existing</html>")

        result = extract_github_directory(
            archive,
            destination,
            extra_files=["index.html"],
            overwrite_extras=False,
        )

        assert (destination / ".github/workflows/test.yml").exists()
        assert index_path.read_text() == "<html>existing</html>"
        assert index_path not in result.written
        assert index_path in result.skipped_existing

    def test_overwrites_extra_file_when_requested(self, tmp_path: Path) -> None:
        """Setting ``overwrite_extras`` replaces existing files."""
        archive = _make_template_archive(
            {
                ".github/workflows/test.yml": "name: CI",
                "index.html": "<html>template</html>",
            }
        )
        destination = tmp_path / "dest"
        destination.mkdir()
        index_path = destination / "index.html"
        index_path.write_text("<html>existing</html>")

        result = extract_github_directory(
            archive,
            destination,
            extra_files=["index.html"],
            overwrite_extras=True,
            overwrite_existing=True,
        )

        assert index_path in result.written
        assert index_path.read_text() == "<html>template</html>"

    def test_preserves_existing_github_file_by_default(self, tmp_path: Path) -> None:
        """Existing files inside .github are not overwritten unless requested."""
        archive = _make_template_archive(
            {
                ".github/workflows/test.yml": "name: CI",
            }
        )
        destination = tmp_path / "dest"
        github_dir = destination / ".github/workflows"
        github_dir.mkdir(parents=True)
        workflow_path = github_dir / "test.yml"
        workflow_path.write_text("name: Existing")

        result = extract_github_directory(archive, destination)

        assert workflow_path.read_text() == "name: Existing"
        assert workflow_path not in result.written
        assert workflow_path in result.skipped_existing

    def test_overwrites_github_file_when_requested(self, tmp_path: Path) -> None:
        """Setting overwrite_existing replaces .github files."""
        archive = _make_template_archive(
            {
                ".github/workflows/test.yml": "name: CI",
            }
        )
        destination = tmp_path / "dest"
        github_dir = destination / ".github/workflows"
        github_dir.mkdir(parents=True)
        workflow_path = github_dir / "test.yml"
        workflow_path.write_text("name: Existing")

        result = extract_github_directory(archive, destination, overwrite_existing=True)

        assert workflow_path.read_text() == "name: CI"
        assert workflow_path in result.written


class TestSyncWorkflowsRemote:
    """Tests for remote workflow sync behaviour around optional extras."""

    @pytest.fixture
    def archive(self) -> bytes:
        return _make_template_archive(
            {
                ".github/workflows/test.yml": "name: CI",
                "index.html": "<html>template</html>",
            }
        )
    
    @pytest.fixture
    def archive_with_remote(self) -> bytes:
        return _make_template_archive(
            {
                ".github/workflows/test.yml": "name: CI",
                ".github/workflows_remote/remote-workflow.yml": "name: Remote CI",
                "index.html": "<html>template</html>",
            }
        )

    @pytest.fixture
    def base_client(self) -> mock.Mock:
        client = mock.Mock(spec=GitHubClient)
        client.get_default_branch.return_value = "main"
        client.get_ref.return_value = {"object": {"sha": "abc123"}}
        client.get_git_commit.return_value = {"tree": {"sha": "tree123"}}
        client.create_tree.return_value = {"sha": "newtree"}
        client.create_commit.return_value = {"sha": "commit123"}
        return client

    def test_skips_existing_index_when_not_overwriting(
        self, archive: bytes, base_client: mock.Mock
    ) -> None:
        base_client.get_tree.return_value = {
            "tree": [
                {"path": "index.html", "type": "blob", "mode": "100644"},
            ]
        }
        base_client.create_blob.side_effect = ["blob-workflow"]

        result = _sync_workflows_remote(
            base_client,
            "owner/template",
            archive,
            "owner/repo",
            branch=None,
            clean=False,
            commit_message=None,
            force=False,
            enable_pages=False,
            extra_files=["index.html"],
            overwrite_extras=False,
            overwrite_github=False,
        )

        assert result == 0
        assert base_client.create_blob.call_count == 1
        blob_args = base_client.create_blob.call_args_list[0][0]
        assert blob_args[2] == b"name: CI"

    def test_overwrites_index_when_flag_enabled(
        self, archive: bytes, base_client: mock.Mock
    ) -> None:
        base_client.get_tree.return_value = {
            "tree": [
                {"path": "index.html", "type": "blob", "mode": "100644"},
            ]
        }
        base_client.create_blob.side_effect = ["blob-workflow", "blob-index"]

        result = _sync_workflows_remote(
            base_client,
            "owner/template",
            archive,
            "owner/repo",
            branch=None,
            clean=False,
            commit_message=None,
            force=False,
            enable_pages=False,
            extra_files=["index.html"],
            overwrite_extras=True,
            overwrite_github=False,
        )

        assert result == 0
        assert base_client.create_blob.call_count == 2
        index_blob = base_client.create_blob.call_args_list[1][0]
        assert index_blob[2] == b"<html>template</html>"

    def test_skips_existing_github_files_when_not_overwriting(
        self, archive: bytes, base_client: mock.Mock
    ) -> None:
        base_client.get_tree.return_value = {
            "tree": [
                {"path": ".github/workflows/test.yml", "type": "blob", "mode": "100644"},
            ]
        }

        result = _sync_workflows_remote(
            base_client,
            "owner/template",
            archive,
            "owner/repo",
            branch=None,
            clean=False,
            commit_message=None,
            force=False,
            enable_pages=False,
            extra_files=None,
            overwrite_extras=False,
            overwrite_github=False,
        )

        assert result == 0
        base_client.create_blob.assert_not_called()

    def test_overwrites_github_files_when_enabled(
        self, archive: bytes, base_client: mock.Mock
    ) -> None:
        base_client.get_tree.return_value = {
            "tree": [
                {"path": ".github/workflows/test.yml", "type": "blob", "mode": "100644"},
            ]
        }
        base_client.create_blob.side_effect = ["blob-workflow"]

        result = _sync_workflows_remote(
            base_client,
            "owner/template",
            archive,
            "owner/repo",
            branch=None,
            clean=False,
            commit_message=None,
            force=False,
            enable_pages=False,
            extra_files=None,
            overwrite_extras=False,
            overwrite_github=True,
        )

        assert result == 0
        base_client.create_blob.assert_called_once()


class TestExtractSpecificWorkflow:
    """Tests for extracting specific workflow files."""

    def test_extracts_specific_workflow_from_workflows(self, tmp_path: Path) -> None:
        """Extract a specific workflow file from .github/workflows directory."""
        archive = _make_template_archive(
            {
                ".github/workflows/test.yml": "name: CI",
                ".github/workflows/another.yml": "name: Another",
            }
        )
        destination = tmp_path / "dest"
        destination.mkdir()

        result = extract_github_directory(
            archive, 
            destination, 
            workflow_file="test.yml"
        )

        workflow_path = destination / ".github/workflows/test.yml"
        another_path = destination / ".github/workflows/another.yml"
        
        assert workflow_path.exists()
        assert workflow_path.read_text() == "name: CI"
        assert not another_path.exists()
        assert workflow_path in result.written

    def test_extracts_workflow_from_workflows_remote(self, tmp_path: Path) -> None:
        """Extract workflow from workflows_remote and save to workflows directory."""
        archive = _make_template_archive(
            {
                ".github/workflows/test.yml": "name: CI",
                ".github/workflows_remote/remote-workflow.yml": "name: Remote CI",
            }
        )
        destination = tmp_path / "dest"
        destination.mkdir()

        result = extract_github_directory(
            archive,
            destination,
            workflow_file="remote-workflow.yml",
            use_remote=True,
        )

        # workflows_remote から workflows にコピーされる 🎯
        workflow_path = destination / ".github/workflows/remote-workflow.yml"
        assert workflow_path.exists()
        assert workflow_path.read_text() == "name: Remote CI"
        assert workflow_path in result.written

    def test_prefers_workflows_remote_when_use_remote_flag(self, tmp_path: Path) -> None:
        """When use_remote is True, prefer workflows_remote over workflows."""
        archive = _make_template_archive(
            {
                ".github/workflows/test.yml": "name: Regular CI",
                ".github/workflows_remote/test.yml": "name: Remote CI",
            }
        )
        destination = tmp_path / "dest"
        destination.mkdir()

        result = extract_github_directory(
            archive,
            destination,
            workflow_file="test.yml",
            use_remote=True,
        )

        workflow_path = destination / ".github/workflows/test.yml"
        assert workflow_path.exists()
        assert workflow_path.read_text() == "name: Remote CI"

    def test_falls_back_to_workflows_when_not_in_remote(self, tmp_path: Path) -> None:
        """Falls back to workflows directory if workflow not found in workflows_remote."""
        archive = _make_template_archive(
            {
                ".github/workflows/test.yml": "name: Regular CI",
            }
        )
        destination = tmp_path / "dest"
        destination.mkdir()

        result = extract_github_directory(
            archive,
            destination,
            workflow_file="test.yml",
            use_remote=True,  # workflows_remote を優先するがそこにないのでフォールバック
        )

        workflow_path = destination / ".github/workflows/test.yml"
        assert workflow_path.exists()
        assert workflow_path.read_text() == "name: Regular CI"

    def test_raises_error_when_workflow_not_found(self, tmp_path: Path) -> None:
        """Raises error when specified workflow file doesn't exist."""
        archive = _make_template_archive(
            {
                ".github/workflows/test.yml": "name: CI",
            }
        )
        destination = tmp_path / "dest"
        destination.mkdir()

        with pytest.raises(WorkflowSyncError, match="Workflow file 'nonexistent.yml' not found"):
            extract_github_directory(
                archive,
                destination,
                workflow_file="nonexistent.yml",
            )

    def test_specific_workflow_respects_overwrite_flag(self, tmp_path: Path) -> None:
        """Specific workflow extraction respects overwrite_existing flag."""
        archive = _make_template_archive(
            {
                ".github/workflows/test.yml": "name: New CI",
            }
        )
        destination = tmp_path / "dest"
        workflow_dir = destination / ".github/workflows"
        workflow_dir.mkdir(parents=True)
        workflow_path = workflow_dir / "test.yml"
        workflow_path.write_text("name: Old CI")

        # Without overwrite
        result = extract_github_directory(
            archive,
            destination,
            workflow_file="test.yml",
            overwrite_existing=False,
        )

        assert workflow_path.read_text() == "name: Old CI"
        assert workflow_path in result.skipped_existing

        # With overwrite
        result = extract_github_directory(
            archive,
            destination,
            workflow_file="test.yml",
            overwrite_existing=True,
        )

        assert workflow_path.read_text() == "name: New CI"
        assert workflow_path in result.written


class TestExtractMultipleWorkflows:
    """Tests for extracting multiple workflow files at once."""

    def test_extracts_multiple_workflows(self, tmp_path: Path) -> None:
        """Extract multiple specific workflow files."""
        archive = _make_template_archive(
            {
                ".github/workflows/test1.yml": "name: CI 1",
                ".github/workflows/test2.yml": "name: CI 2",
                ".github/workflows/test3.yml": "name: CI 3",
            }
        )
        destination = tmp_path / "dest"
        destination.mkdir()

        result = extract_github_directory(
            archive,
            destination,
            workflow_files=["test1.yml", "test2.yml"],
        )

        workflow1_path = destination / ".github/workflows/test1.yml"
        workflow2_path = destination / ".github/workflows/test2.yml"
        workflow3_path = destination / ".github/workflows/test3.yml"

        assert workflow1_path.exists()
        assert workflow1_path.read_text() == "name: CI 1"
        assert workflow2_path.exists()
        assert workflow2_path.read_text() == "name: CI 2"
        assert not workflow3_path.exists()
        assert len(result.written) == 2

    def test_extracts_multiple_from_workflows_remote(self, tmp_path: Path) -> None:
        """Extract multiple workflows from workflows_remote directory."""
        archive = _make_template_archive(
            {
                ".github/workflows/test.yml": "name: Regular",
                ".github/workflows_remote/remote1.yml": "name: Remote 1",
                ".github/workflows_remote/remote2.yml": "name: Remote 2",
            }
        )
        destination = tmp_path / "dest"
        destination.mkdir()

        result = extract_github_directory(
            archive,
            destination,
            workflow_files=["remote1.yml", "remote2.yml"],
            use_remote=True,
        )

        remote1_path = destination / ".github/workflows/remote1.yml"
        remote2_path = destination / ".github/workflows/remote2.yml"

        assert remote1_path.exists()
        assert remote1_path.read_text() == "name: Remote 1"
        assert remote2_path.exists()
        assert remote2_path.read_text() == "name: Remote 2"
        assert len(result.written) == 2

    def test_mixed_workflows_and_workflows_remote(self, tmp_path: Path) -> None:
        """Extract workflows from both workflows and workflows_remote directories."""
        archive = _make_template_archive(
            {
                ".github/workflows/regular.yml": "name: Regular",
                ".github/workflows_remote/remote.yml": "name: Remote",
            }
        )
        destination = tmp_path / "dest"
        destination.mkdir()

        result = extract_github_directory(
            archive,
            destination,
            workflow_files=["regular.yml", "remote.yml"],
            use_remote=False,  # workflows 優先だけど remote も探す
        )

        regular_path = destination / ".github/workflows/regular.yml"
        remote_path = destination / ".github/workflows/remote.yml"

        assert regular_path.exists()
        assert regular_path.read_text() == "name: Regular"
        assert remote_path.exists()
        assert remote_path.read_text() == "name: Remote"
        assert len(result.written) == 2

    def test_raises_error_when_one_workflow_not_found(self, tmp_path: Path) -> None:
        """Raises error when any of the specified workflows doesn't exist."""
        archive = _make_template_archive(
            {
                ".github/workflows/test1.yml": "name: CI 1",
            }
        )
        destination = tmp_path / "dest"
        destination.mkdir()

        with pytest.raises(WorkflowSyncError, match="Workflow file 'missing.yml' not found"):
            extract_github_directory(
                archive,
                destination,
                workflow_files=["test1.yml", "missing.yml"],
            )
