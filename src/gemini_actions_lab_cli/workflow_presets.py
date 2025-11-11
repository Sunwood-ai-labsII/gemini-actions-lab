"""Workflow presets for common sync scenarios."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def _load_presets() -> dict[str, Any]:
    """Load workflow presets from YAML file.
    
    Returns:
        Dictionary of preset configurations.
    """
    if yaml is None:
        raise ImportError(
            "PyYAML is required to load workflow presets. "
            "Install it with: pip install pyyaml"
        )
    
    # プリセットファイルのパスを取得 🎯
    presets_file = Path(__file__).parent / "workflow_presets.yml"
    
    if not presets_file.exists():
        raise FileNotFoundError(f"Presets file not found: {presets_file}")
    
    with open(presets_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    return data.get("presets", {})


# プリセット定義をYAMLから読み込み 🎯
try:
    WORKFLOW_PRESETS = _load_presets()
except (ImportError, FileNotFoundError) as e:
    # フォールバック: YAMLが読めない場合は空の辞書
    WORKFLOW_PRESETS = {}
    import warnings
    warnings.warn(f"Failed to load workflow presets: {e}", UserWarning)


def get_preset_workflows(preset_name: str) -> tuple[list[str], bool, list[str] | None, list[str] | None]:
    """Get workflow list, use_remote flag, prompts, and agents for a preset.

    Args:
        preset_name: Name of the preset to retrieve.

    Returns:
        Tuple of (workflow_list, use_remote_flag, prompt_files, agent_files).
        prompt_files and agent_files can be None if not specified in the preset.

    Raises:
        KeyError: If preset_name doesn't exist.
    """
    if preset_name not in WORKFLOW_PRESETS:
        available = ", ".join(sorted(WORKFLOW_PRESETS.keys()))
        raise KeyError(
            f"Unknown preset '{preset_name}'. Available presets: {available}"
        )

    preset = WORKFLOW_PRESETS[preset_name]
    workflows = preset["workflows"]
    use_remote = preset["use_remote"]
    prompts = preset.get("prompts")  # Optional
    agents = preset.get("agents")    # Optional

    return workflows, use_remote, prompts, agents


def list_presets() -> list[tuple[str, str]]:
    """List all available presets with their descriptions.
    
    Returns:
        List of (preset_name, description) tuples.
    """
    return [
        (name, preset["description"])
        for name, preset in sorted(WORKFLOW_PRESETS.items())
    ]

