"""Tests for workflow presets."""

from __future__ import annotations

import pytest

from gemini_actions_lab_cli.workflow_presets import (
    get_preset_workflows,
    list_presets,
    WORKFLOW_PRESETS,
)


class TestWorkflowPresets:
    """Tests for workflow preset functionality."""

    def test_get_preset_workflows_returns_correct_data(self) -> None:
        """get_preset_workflows returns workflows and use_remote flag."""
        workflows, use_remote = get_preset_workflows("pr-review")
        
        assert isinstance(workflows, list)
        assert len(workflows) == 3
        assert "pr-review-kozaki-remote.yml" in workflows
        assert "pr-review-onizuka-remote.yml" in workflows
        assert "pr-review-yukimura-remote.yml" in workflows
        assert use_remote is True

    def test_get_preset_workflows_gemini_cli(self) -> None:
        """gemini-cli preset returns correct workflows."""
        workflows, use_remote = get_preset_workflows("gemini-cli")
        
        assert len(workflows) == 2
        assert "gemini-cli.yml" in workflows
        assert "gemini-jp-cli.yml" in workflows
        assert use_remote is False

    def test_get_preset_workflows_raises_on_unknown_preset(self) -> None:
        """get_preset_workflows raises KeyError for unknown preset."""
        with pytest.raises(KeyError, match="Unknown preset 'nonexistent'"):
            get_preset_workflows("nonexistent")

    def test_list_presets_returns_all_presets(self) -> None:
        """list_presets returns all available presets."""
        presets = list_presets()
        
        assert isinstance(presets, list)
        assert len(presets) == len(WORKFLOW_PRESETS)
        
        # Check format
        for name, description in presets:
            assert isinstance(name, str)
            assert isinstance(description, str)
            assert name in WORKFLOW_PRESETS

    def test_all_presets_have_required_fields(self) -> None:
        """All presets have workflows, description, and use_remote fields."""
        for name, preset in WORKFLOW_PRESETS.items():
            assert "workflows" in preset, f"Preset {name} missing 'workflows'"
            assert "description" in preset, f"Preset {name} missing 'description'"
            assert "use_remote" in preset, f"Preset {name} missing 'use_remote'"
            
            assert isinstance(preset["workflows"], list)
            assert isinstance(preset["description"], str)
            assert isinstance(preset["use_remote"], bool)
            assert len(preset["workflows"]) > 0

    def test_preset_workflows_have_yml_extension(self) -> None:
        """All preset workflow files have .yml extension."""
        for name, preset in WORKFLOW_PRESETS.items():
            for workflow in preset["workflows"]:
                assert workflow.endswith(".yml"), \
                    f"Preset {name} has workflow without .yml: {workflow}"
