"""Tests for workflow synchronisation helpers."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from unittest import mock

import pytest

from gemini_actions_lab_cli.cli import _sync_workflows_remote
from gemini_actions_lab_cli.github_api import GitHubClient
from gemini_actions_lab_cli.workflows import extract_github_directory


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

        written = extract_github_directory(
            archive,
            destination,
            extra_files=["index.html"],
            overwrite_extras=False,
        )

        assert (destination / ".github/workflows/test.yml").exists()
        assert index_path.read_text() == "<html>existing</html>"
        assert index_path not in written

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

        written = extract_github_directory(
            archive,
            destination,
            extra_files=["index.html"],
            overwrite_extras=True,
        )

        assert index_path in written
        assert index_path.read_text() == "<html>template</html>"


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
        )

        assert result == 0
        assert base_client.create_blob.call_count == 2
        index_blob = base_client.create_blob.call_args_list[1][0]
        assert index_blob[2] == b"<html>template</html>"
