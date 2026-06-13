from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


class ConfigValidationError(ValueError):
    pass


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


def _require_number(config: dict[str, Any], section: str, key: str) -> None:
    value = config.get(section, {}).get(key)
    if not isinstance(value, (int, float)):
        raise ConfigValidationError(f"Invalid config value for {section}.{key}: expected number")


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    required_sections = {"defaults", "thresholds", "model_portfolios", "tax_profile"}
    missing_sections = sorted(section for section in required_sections if section not in config)
    if missing_sections:
        raise ConfigValidationError(f"Missing config sections: {', '.join(missing_sections)}")
    if not config["defaults"].get("as_of_date"):
        raise ConfigValidationError("Missing config value for defaults.as_of_date")
    if not config["defaults"].get("target_profile"):
        raise ConfigValidationError("Missing config value for defaults.target_profile")
    for key in ("single_name_threshold", "sector_threshold", "drift_threshold", "high_fee_threshold", "harvest_loss_threshold"):
        _require_number(config, "thresholds", key)
    for key in (
        "federal_marginal_rate",
        "ltcg_rate",
        "state_rate",
        "qualified_dividend_rate",
        "confirm_with_cpa_above",
    ):
        _require_number(config, "tax_profile", key)
    if not isinstance(config["model_portfolios"], dict) or not config["model_portfolios"]:
        raise ConfigValidationError("model_portfolios must define at least one target profile")
    return config


def load_config(
    config_dir: str | Path = "config",
    config_file: str | Path | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config_dir = Path(config_dir)
    defaults = load_yaml(config_dir / "default.yml")
    merged = defaults
    if config_file:
        merged = deep_merge(merged, load_yaml(config_file))
    if cli_overrides:
        merged = deep_merge(merged, {k: v for k, v in cli_overrides.items() if v is not None})
    return validate_config(merged)
