"""Unit tests for the sync-agent command."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict
from unittest import mock

import pytest

from gemini_actions_lab_cli.cli import sync_agent
from gemini_actions_lab_cli.github_api import GitHubClient, GitHubError


class TestSyncAgent:
    """Tests for the sync_agent command."""

    @pytest.fixture
    def mock_github_client(self) -> mock.Mock:
        """Create a mock GitHubClient."""
        client = mock.Mock(spec=GitHubClient)
        client.get_default_branch.return_value = "main"
        client.get_ref.return_value = {
            "object": {"sha": "abc123"}
        }
        client.get_git_commit.return_value = {
            "tree": {"sha": "tree123"}
        }
        client.create_blob.return_value = "blob123"
        client.create_tree.return_value = {"sha": "newtree123"}
        client.create_commit.return_value = {"sha": "commit123"}
        client.update_ref.return_value = None
        return client

    @pytest.fixture
    def base_args(self) -> argparse.Namespace:
        """Create base argument namespace."""
        return argparse.Namespace(
            repo="owner/repo",
            branch=None,
            message=None,
            token="fake-token",
            force=False,
            api_url="https://api.github.com",
        )

    def test_sync_agent_all_files_exist(
        self, tmp_path: Path, base_args: argparse.Namespace, mock_github_client: mock.Mock
    ) -> None:
        """Test syncing when all agent files exist."""
        # Create test files
        (tmp_path / "Claude.md").write_text("# Claude Guide")
        (tmp_path / "GEMINI.md").write_text("# Gemini Guide")
        (tmp_path / "AGENT.md").write_text("# Agent Guide")

        with mock.patch("gemini_actions_lab_cli.cli.Path.cwd", return_value=tmp_path):
            with mock.patch("gemini_actions_lab_cli.cli.GitHubClient", return_value=mock_github_client):
                with mock.patch("gemini_actions_lab_cli.cli._require_token", return_value="fake-token"):
                    result = sync_agent(base_args)

        assert result == 0
        assert mock_github_client.create_blob.call_count == 3
        assert mock_github_client.create_tree.call_count == 1
        assert mock_github_client.create_commit.call_count == 1
        assert mock_github_client.update_ref.call_count == 1

    def test_sync_agent_partial_files_exist(
        self, tmp_path: Path, base_args: argparse.Namespace, mock_github_client: mock.Mock
    ) -> None:
        """Test syncing when only some agent files exist."""
        # Create only two files
        (tmp_path / "Claude.md").write_text("# Claude Guide")
        (tmp_path / "GEMINI.md").write_text("# Gemini Guide")

        with mock.patch("gemini_actions_lab_cli.cli.Path.cwd", return_value=tmp_path):
            with mock.patch("gemini_actions_lab_cli.cli.GitHubClient", return_value=mock_github_client):
                with mock.patch("gemini_actions_lab_cli.cli._require_token", return_value="fake-token"):
                    result = sync_agent(base_args)

        assert result == 0
        # Should create blobs only for existing files
        assert mock_github_client.create_blob.call_count == 2
        assert mock_github_client.create_tree.call_count == 1

    def test_sync_agent_no_files_exist(
        self, tmp_path: Path, base_args: argparse.Namespace, mock_github_client: mock.Mock
    ) -> None:
        """Test syncing when no agent files exist."""
        with mock.patch("gemini_actions_lab_cli.cli.Path.cwd", return_value=tmp_path):
            with mock.patch("gemini_actions_lab_cli.cli.GitHubClient", return_value=mock_github_client):
                with mock.patch("gemini_actions_lab_cli.cli._require_token", return_value="fake-token"):
                    result = sync_agent(base_args)

        assert result == 1
        # Should not create any blobs or commits
        assert mock_github_client.create_blob.call_count == 0
        assert mock_github_client.create_commit.call_count == 0

    def test_sync_agent_custom_branch(
        self, tmp_path: Path, base_args: argparse.Namespace, mock_github_client: mock.Mock
    ) -> None:
        """Test syncing to a custom branch."""
        (tmp_path / "Claude.md").write_text("# Claude Guide")
        base_args.branch = "develop"

        with mock.patch("gemini_actions_lab_cli.cli.Path.cwd", return_value=tmp_path):
            with mock.patch("gemini_actions_lab_cli.cli.GitHubClient", return_value=mock_github_client):
                with mock.patch("gemini_actions_lab_cli.cli._require_token", return_value="fake-token"):
                    result = sync_agent(base_args)

        assert result == 0
        # Should use custom branch instead of default
        mock_github_client.get_ref.assert_called_once_with("owner", "repo", "heads/develop")
        assert mock_github_client.get_default_branch.call_count == 0

    def test_sync_agent_custom_message(
        self, tmp_path: Path, base_args: argparse.Namespace, mock_github_client: mock.Mock
    ) -> None:
        """Test syncing with a custom commit message."""
        (tmp_path / "Claude.md").write_text("# Claude Guide")
        custom_message = "docs: update agent guidelines"
        base_args.message = custom_message

        with mock.patch("gemini_actions_lab_cli.cli.Path.cwd", return_value=tmp_path):
            with mock.patch("gemini_actions_lab_cli.cli.GitHubClient", return_value=mock_github_client):
                with mock.patch("gemini_actions_lab_cli.cli._require_token", return_value="fake-token"):
                    result = sync_agent(base_args)

        assert result == 0
        # Check that custom message was used
        call_args = mock_github_client.create_commit.call_args
        assert call_args[0][2] == custom_message

    def test_sync_agent_force_update(
        self, tmp_path: Path, base_args: argparse.Namespace, mock_github_client: mock.Mock
    ) -> None:
        """Test syncing with force update flag."""
        (tmp_path / "Claude.md").write_text("# Claude Guide")
        base_args.force = True

        with mock.patch("gemini_actions_lab_cli.cli.Path.cwd", return_value=tmp_path):
            with mock.patch("gemini_actions_lab_cli.cli.GitHubClient", return_value=mock_github_client):
                with mock.patch("gemini_actions_lab_cli.cli._require_token", return_value="fake-token"):
                    result = sync_agent(base_args)

        assert result == 0
        # Check that force flag was passed to update_ref
        call_args = mock_github_client.update_ref.call_args
        assert call_args[1]["force"] is True

    def test_sync_agent_uses_default_branch(
        self, tmp_path: Path, base_args: argparse.Namespace, mock_github_client: mock.Mock
    ) -> None:
        """Test that default branch is used when not specified."""
        (tmp_path / "Claude.md").write_text("# Claude Guide")

        with mock.patch("gemini_actions_lab_cli.cli.Path.cwd", return_value=tmp_path):
            with mock.patch("gemini_actions_lab_cli.cli.GitHubClient", return_value=mock_github_client):
                with mock.patch("gemini_actions_lab_cli.cli._require_token", return_value="fake-token"):
                    result = sync_agent(base_args)

        assert result == 0
        mock_github_client.get_default_branch.assert_called_once_with("owner", "repo")
        mock_github_client.get_ref.assert_called_once_with("owner", "repo", "heads/main")

    def test_sync_agent_blob_content_correct(
        self, tmp_path: Path, base_args: argparse.Namespace, mock_github_client: mock.Mock
    ) -> None:
        """Test that blob content is correctly read from files."""
        claude_content = "# Claude Guide\nThis is a test."
        (tmp_path / "Claude.md").write_text(claude_content)

        with mock.patch("gemini_actions_lab_cli.cli.Path.cwd", return_value=tmp_path):
            with mock.patch("gemini_actions_lab_cli.cli.GitHubClient", return_value=mock_github_client):
                with mock.patch("gemini_actions_lab_cli.cli._require_token", return_value="fake-token"):
                    result = sync_agent(base_args)

        assert result == 0
        # Check that blob was created with correct content
        call_args = mock_github_client.create_blob.call_args_list[0]
        assert call_args[0][2] == claude_content.encode("utf-8")

    def test_sync_agent_tree_entries_correct(
        self, tmp_path: Path, base_args: argparse.Namespace, mock_github_client: mock.Mock
    ) -> None:
        """Test that tree entries are created correctly."""
        (tmp_path / "Claude.md").write_text("# Claude")
        (tmp_path / "GEMINI.md").write_text("# Gemini")

        with mock.patch("gemini_actions_lab_cli.cli.Path.cwd", return_value=tmp_path):
            with mock.patch("gemini_actions_lab_cli.cli.GitHubClient", return_value=mock_github_client):
                with mock.patch("gemini_actions_lab_cli.cli._require_token", return_value="fake-token"):
                    result = sync_agent(base_args)

        assert result == 0
        # Check tree entries
        call_args = mock_github_client.create_tree.call_args
        tree_entries = call_args[0][2]
        assert len(tree_entries) == 2
        assert all(entry["mode"] == "100644" for entry in tree_entries)
        assert all(entry["type"] == "blob" for entry in tree_entries)
        paths = [entry["path"] for entry in tree_entries]
        assert "Claude.md" in paths
        assert "GEMINI.md" in paths

    def test_sync_agent_github_error_handling(
        self, tmp_path: Path, base_args: argparse.Namespace, mock_github_client: mock.Mock
    ) -> None:
        """Test handling of GitHub API errors."""
        (tmp_path / "Claude.md").write_text("# Claude")
        mock_github_client.get_default_branch.side_effect = GitHubError("API Error", status=500)

        with mock.patch("gemini_actions_lab_cli.cli.Path.cwd", return_value=tmp_path):
            with mock.patch("gemini_actions_lab_cli.cli.GitHubClient", return_value=mock_github_client):
                with mock.patch("gemini_actions_lab_cli.cli._require_token", return_value="fake-token"):
                    with pytest.raises(GitHubError):
                        sync_agent(base_args)

    def test_sync_agent_default_commit_message(
        self, tmp_path: Path, base_args: argparse.Namespace, mock_github_client: mock.Mock
    ) -> None:
        """Test that default commit message is used when not specified."""
        (tmp_path / "Claude.md").write_text("# Claude")

        with mock.patch("gemini_actions_lab_cli.cli.Path.cwd", return_value=tmp_path):
            with mock.patch("gemini_actions_lab_cli.cli.GitHubClient", return_value=mock_github_client):
                with mock.patch("gemini_actions_lab_cli.cli._require_token", return_value="fake-token"):
                    result = sync_agent(base_args)

        assert result == 0
        call_args = mock_github_client.create_commit.call_args
        commit_message = call_args[0][2]
        assert "🤖 Sync AI agent guideline files" in commit_message
