from pathlib import Path

from app.config import load_config


def test_config_precedence(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default.yml").write_text(
        "defaults:\n  as_of_date: 2026-06-01\n  target_profile: balanced\nthresholds:\n  single_name_threshold: 0.15\n  sector_threshold: 0.35\n  drift_threshold: 0.05\n  high_fee_threshold: 0.004\n  harvest_loss_threshold: -500\nmodel_portfolios:\n  balanced:\n    cash: 1.0\ntax_profile:\n  filing_status: mfj\n  federal_marginal_rate: 0.32\n  ltcg_rate: 0.15\n  niit_applies: false\n  state_rate: 0.05\n  qualified_dividend_rate: 0.15\n  confirm_with_cpa_above: 5000\n",
        encoding="utf-8",
    )
    override = tmp_path / "override.yml"
    override.write_text("thresholds:\n  drift_threshold: 0.08\n", encoding="utf-8")
    config = load_config(config_dir, override, {"thresholds": {"drift_threshold": 0.12}})
    assert config["thresholds"]["drift_threshold"] == 0.12
