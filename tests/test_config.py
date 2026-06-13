from pathlib import Path

from app.config import load_config


def test_config_precedence(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default.yml").write_text("thresholds:\n  drift_threshold: 0.05\n", encoding="utf-8")
    override = tmp_path / "override.yml"
    override.write_text("thresholds:\n  drift_threshold: 0.08\n", encoding="utf-8")
    config = load_config(config_dir, override, {"thresholds": {"drift_threshold": 0.12}})
    assert config["thresholds"]["drift_threshold"] == 0.12
