import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from app.config import load_config
from core.recommendation_engine import generate_recommendations
from data.loaders import CsvDataProvider, load_security_master_csv
from data.schemas import TaxProfile

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {"single_name_threshold": 0.15, "sector_threshold": 0.35, "drift_threshold": 0.05, "high_fee_threshold": 0.0040, "harvest_loss_threshold": -500.0}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}


def _run_cli(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "app.cli", "analyze", *args], cwd=cwd, capture_output=True, text=True)


def test_unknown_ticker_fails_fast_with_readable_error(tmp_path: Path):
    holdings = tmp_path / "holdings.csv"
    holdings.write_text((ROOT / "data/mock_holdings.csv").read_text(encoding="utf-8").replace("AAPL", "ZZZZZ", 1), encoding="utf-8")
    result = _run_cli(
        "--holdings",
        str(holdings),
        "--lots",
        str(ROOT / "data/mock_tax_lots.csv"),
        "--account-menus",
        str(ROOT / "data/mock_account_menus.csv"),
        "--security-master",
        str(ROOT / "data/security_master.csv"),
        "--output",
        str(tmp_path / "report.md"),
    )
    assert result.returncode != 0
    assert "Unknown tickers in holdings" in result.stderr
    assert "ZZZZZ" in result.stderr


def test_load_config_rejects_invalid_threshold_type(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default.yml").write_text(
        "defaults:\n  as_of_date: 2026-06-01\n  target_profile: balanced\nthresholds:\n  single_name_threshold: 0.15\n  sector_threshold: 0.35\n  drift_threshold: nope\n  high_fee_threshold: 0.004\n  harvest_loss_threshold: -500\nmodel_portfolios:\n  balanced:\n    cash: 1.0\ntax_profile:\n  filing_status: mfj\n  federal_marginal_rate: 0.32\n  ltcg_rate: 0.15\n  niit_applies: false\n  state_rate: 0.05\n  qualified_dividend_rate: 0.15\n  confirm_with_cpa_above: 5000\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="thresholds.drift_threshold"):
        load_config(config_dir)


def test_missing_menu_coverage_fails_validation(tmp_path: Path):
    menus = tmp_path / "menus.csv"
    menus.write_text("account_id,universe,allowed_instruments\nTAX-1,open,\nROTH-1,menu,VTI|VXUS\nHSA-1,menu,VTI|VXUS\n", encoding="utf-8")
    result = _run_cli(
        "--holdings",
        str(ROOT / "data/mock_holdings.csv"),
        "--lots",
        str(ROOT / "data/mock_tax_lots.csv"),
        "--account-menus",
        str(menus),
        "--security-master",
        str(ROOT / "data/security_master.csv"),
        "--output",
        str(tmp_path / "report.md"),
    )
    assert result.returncode != 0
    assert "Missing account menu coverage" in result.stderr
    assert "IRA-1" in result.stderr


def test_invalid_target_profile_fails_with_readable_error(tmp_path: Path):
    result = _run_cli(
        "--holdings",
        str(ROOT / "data/mock_holdings.csv"),
        "--lots",
        str(ROOT / "data/mock_tax_lots.csv"),
        "--account-menus",
        str(ROOT / "data/mock_account_menus.csv"),
        "--security-master",
        str(ROOT / "data/security_master.csv"),
        "--target-profile",
        "does-not-exist",
        "--output",
        str(tmp_path / "report.md"),
    )
    assert result.returncode != 0
    assert "Unknown target profile" in result.stderr


def test_missing_taxable_basis_blocks_sale_driven_recommendations(tmp_path: Path):
    lots = tmp_path / "lots.csv"
    lots.write_text((ROOT / "data/mock_tax_lots.csv").read_text(encoding="utf-8").replace("TAX-1,ARKK,150,100,2024-08-01,304,60", "TAX-1,ARKK,150,,2024-08-01,304,60"), encoding="utf-8")
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", lots, ROOT / "data/mock_account_menus.csv")
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    analysis = generate_recommendations(result.holdings, result.tax_lots, result.account_menus, master, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    sale_actions = [rec for rec in analysis["recommendations"] if rec.account_id == "TAX-1" and rec.ticker == "ARKK" and rec.action in {"trim", "replace", "tax_loss_harvest"}]
    assert not sale_actions
