"""Workflow presets for common sync scenarios."""

from __future__ import annotations

# プリセット定義 🎯
WORKFLOW_PRESETS = {
    "pr-review": {
        "description": "PR review workflows (Kozaki, Onizuka, Yukimura)",
        "workflows": [
            "pr-review-kozaki-remote.yml",
            "pr-review-onizuka-remote.yml",
            "pr-review-yukimura-remote.yml",
        ],
        "use_remote": True,
    },
    "gemini-cli": {
        "description": "Gemini CLI workflows (English and Japanese)",
        "workflows": [
            "gemini-cli.yml",
            "gemini-jp-cli.yml",
        ],
        "use_remote": False,
    },
    "release": {
        "description": "Release automation workflows",
        "workflows": [
            "gemini-release-notes-remote.yml",
        ],
        "use_remote": True,
    },
    "imagen": {
        "description": "Image generation workflows",
        "workflows": [
            "imagen4-issue-trigger-and-commit.yml",
            "imagen4-generate-and-commit.yml",
        ],
        "use_remote": False,
    },
    "basic": {
        "description": "Basic workflows for new repositories",
        "workflows": [
            "gemini-cli.yml",
            "gemini-jp-cli.yml",
            "pr-review-kozaki-remote.yml",
        ],
        "use_remote": False,  # CLI は workflows、PR review は remote から
    },
    "full-remote": {
        "description": "All remote workflows",
        "workflows": [
            "pr-review-kozaki-remote.yml",
            "pr-review-onizuka-remote.yml",
            "pr-review-yukimura-remote.yml",
            "gemini-release-notes-remote.yml",
            "example-remote-script.yml",
            "huggingface-space-deploy-remote.yml",
        ],
        "use_remote": True,
    },
}


def get_preset_workflows(preset_name: str) -> tuple[list[str], bool]:
    """Get workflow list and use_remote flag for a preset.
    
    Args:
        preset_name: Name of the preset to retrieve.
        
    Returns:
        Tuple of (workflow_list, use_remote_flag).
        
    Raises:
        KeyError: If preset_name doesn't exist.
    """
    if preset_name not in WORKFLOW_PRESETS:
        available = ", ".join(sorted(WORKFLOW_PRESETS.keys()))
        raise KeyError(
            f"Unknown preset '{preset_name}'. Available presets: {available}"
        )
    
    preset = WORKFLOW_PRESETS[preset_name]
    return preset["workflows"], preset["use_remote"]


def list_presets() -> list[tuple[str, str]]:
    """List all available presets with their descriptions.
    
    Returns:
        List of (preset_name, description) tuples.
    """
    return [
        (name, preset["description"])
        for name, preset in sorted(WORKFLOW_PRESETS.items())
    ]
