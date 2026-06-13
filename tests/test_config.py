from pathlib import Path

from app.config import load_config
from data.loaders import load_account_menus_csv

ROOT = Path(__file__).resolve().parents[1]


def test_config_precedence(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default.yml").write_text("thresholds:\n  drift_threshold: 0.05\n", encoding="utf-8")
    override = tmp_path / "override.yml"
    override.write_text("thresholds:\n  drift_threshold: 0.08\n", encoding="utf-8")
    config = load_config(config_dir, override, {"thresholds": {"drift_threshold": 0.12}})
    assert config["thresholds"]["drift_threshold"] == 0.12


def _write_standalone_config(config_dir: Path):
    config_dir.mkdir()
    (config_dir / "thresholds.yml").write_text("single_name_threshold: 0.11\ndrift_threshold: 0.05\n", encoding="utf-8")
    (config_dir / "model_portfolios.yml").write_text("balanced:\n  us_equity: 0.6\n", encoding="utf-8")
    (config_dir / "tax_assumptions.yml").write_text("federal_marginal_rate: 0.37\n", encoding="utf-8")
    (config_dir / "account_menus.yml").write_text("IRA-X:\n  universe: menu\n  allowed_instruments: [FOO]\n", encoding="utf-8")
    (config_dir / "default.yml").write_text("defaults:\n  target_profile: balanced\n", encoding="utf-8")


def test_multifile_aggregation(tmp_path: Path):
    config_dir = tmp_path / "config"
    _write_standalone_config(config_dir)
    config = load_config(config_dir)
    # Every standalone file contributes its own namespace.
    assert config["thresholds"]["single_name_threshold"] == 0.11
    assert config["model_portfolios"]["balanced"]["us_equity"] == 0.6
    assert config["tax_profile"]["federal_marginal_rate"] == 0.37
    assert config["account_menus"]["IRA-X"]["allowed_instruments"] == ["FOO"]
    assert config["defaults"]["target_profile"] == "balanced"


def test_precedence_across_files(tmp_path: Path):
    # A key that ORIGINATES in a standalone file is overridden by --config, then by CLI flags.
    config_dir = tmp_path / "config"
    _write_standalone_config(config_dir)
    override = tmp_path / "override.yml"
    override.write_text("thresholds:\n  single_name_threshold: 0.13\n", encoding="utf-8")
    # standalone (0.11) < --config file (0.13)
    assert load_config(config_dir, override)["thresholds"]["single_name_threshold"] == 0.13
    # --config file < CLI override (0.20)
    config = load_config(config_dir, override, {"thresholds": {"single_name_threshold": 0.20}})
    assert config["thresholds"]["single_name_threshold"] == 0.20


def test_menu_source_single_truth():
    # The committed account_menus.yml must agree with the authoritative runtime CSV (no two
    # disagreeing sources). IRA-1 was the historical divergence.
    config = load_config(ROOT / "config")
    csv_menus = {menu.account_id: menu for menu in load_account_menus_csv(ROOT / "data/mock_account_menus.csv")}
    yaml_ira = config["account_menus"]["IRA-1"]["allowed_instruments"]
    assert yaml_ira == csv_menus["IRA-1"].allowed_instruments == ["FXNAX"]
