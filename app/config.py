from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    path = Path(path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


# Standalone config files are the canonical source of truth for each namespace. default.yml is
# layered on top as the override file, so editing any standalone file changes engine behavior.
STANDALONE_FILES = {
    "thresholds.yml": "thresholds",
    "model_portfolios.yml": "model_portfolios",
    "tax_assumptions.yml": "tax_profile",
    "account_menus.yml": "account_menus",
}


def load_config(
    config_dir: str | Path = "config",
    config_file: str | Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the merged config with precedence: standalone files < default.yml < --config file < CLI flags."""
    config_dir = Path(config_dir)
    merged: dict[str, Any] = {}
    for filename, namespace in STANDALONE_FILES.items():
        data = load_yaml(config_dir / filename)
        if data:
            merged[namespace] = data
    merged = deep_merge(merged, load_yaml(config_dir / "default.yml"))
    if config_file:
        merged = deep_merge(merged, load_yaml(config_file))
    if cli_overrides:
        merged = deep_merge(merged, {k: v for k, v in cli_overrides.items() if v is not None})
    return merged
