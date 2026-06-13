from datetime import date
from pathlib import Path

from core.asset_location_engine import evaluate_asset_location
from core.overlap_engine import OverlapEngine
from core.recommendation_engine import generate_recommendations
from data.loaders import CsvDataProvider, load_security_master_csv
from data.schemas import Holding, TaxProfile

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {"single_name_threshold": 0.15, "sector_threshold": 0.35, "drift_threshold": 0.05, "high_fee_threshold": 0.0040, "harvest_loss_threshold": -500.0}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}


def test_split_positions_trigger_single_name_concentration():
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    engine = OverlapEngine(master)
    holdings = [
        Holding("TAX-1", "Taxable", "taxable", "VTI", "etf", 50, 12000, 0.0003, 0.013),
        Holding("ROTH-1", "Roth", "roth_ira", "VTI", "etf", 50, 12000, 0.0003, 0.013),
        Holding("IRA-1", "IRA", "traditional_ira", "BND", "etf", 400, 56000, 0.0003, 0.031),
    ]
    flags = engine.concentration_flags(holdings, 0.15, 0.35)
    assert any(item["ticker"] == "VTI" and item["weight"] >= 0.30 for item in flags["single_name_flags"])


def test_cash_location_advice_is_not_broad_equity_relocation():
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    holdings = [Holding("ROTH-1", "Roth", "roth_ira", "CASH", "cash", 1, 5000, None, 0.0)]
    suggestions = evaluate_asset_location(holdings, master, {"ROTH-1": "roth_ira"})
    assert suggestions
    assert suggestions[0]["action"] == "redirect_contributions"
    assert "broad equity" not in suggestions[0]["reason"].lower()


def test_golden_path_rejects_unsafe_single_stock_replacements():
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", ROOT / "data/mock_tax_lots.csv", ROOT / "data/mock_account_menus.csv")
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    analysis = generate_recommendations(result.holdings, result.tax_lots, result.account_menus, master, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    recommendations = analysis["recommendations"]
    assert not any(item.ticker == "ARKK" and item.replacement_ticker == "AAPL" for item in recommendations)


def test_contribution_redirects_are_preserved_as_advisory_actions():
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", ROOT / "data/mock_tax_lots.csv", ROOT / "data/mock_account_menus.csv")
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    analysis = generate_recommendations(result.holdings, result.tax_lots, result.account_menus, master, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    recommendations = analysis["recommendations"]
    assert any(item.action == "redirect_contributions" and item.ticker == "CASH" for item in recommendations)
