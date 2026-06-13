from datetime import date
from pathlib import Path

from core.recommendation_engine import generate_recommendations
from data.loaders import CsvDataProvider, load_security_master_csv
from data.schemas import AccountMenu, Holding, TaxLot, TaxProfile

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {"single_name_threshold": 0.15, "sector_threshold": 0.35, "drift_threshold": 0.05, "high_fee_threshold": 0.0040, "harvest_loss_threshold": -500.0}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}
ESTIMATE_TOKENS = ("Estimated tax cost", "tax impact unknown")


def _master():
    return load_security_master_csv(ROOT / "data/security_master.csv")


def test_harvest_carries_tax_estimate():
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", ROOT / "data/mock_tax_lots.csv", ROOT / "data/mock_account_menus.csv")
    analysis = generate_recommendations(result.holdings, result.tax_lots, result.account_menus, _master(), THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    harvests = [r for r in analysis["recommendations"] if r.action == "tax_loss_harvest"]
    assert harvests, "golden-path mock data should produce at least one harvest"
    for rec in harvests:
        assert any(token in note for note in rec.tax_notes for token in ESTIMATE_TOKENS), (
            f"harvest on {rec.ticker} carries no tax estimate: {rec.tax_notes}"
        )


def test_harvest_missing_basis_not_confident():
    # A taxable loss position whose cost basis is unknown must never become a confident sell.
    holdings = [
        Holding("TAX-1", "Taxable", "taxable", "ARKK", "etf", 200, 12000.0, 0.0075, 0.0),
        Holding("TAX-1", "Taxable", "taxable", "BND", "etf", 100, 7000.0, 0.0003, 0.031),
    ]
    lots = [
        # No cost basis -> unrealized_gain unknown -> tax impact unknown.
        TaxLot("TAX-1", "ARKK", 200, None, date(2025, 1, 10), 500, True, None),
        TaxLot("TAX-1", "BND", 100, 70.0, date(2024, 1, 10), 800, True, 0.0),
    ]
    menus = [AccountMenu("TAX-1", "open", None)]
    analysis = generate_recommendations(holdings, lots, menus, _master(), THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    arkk = [r for r in analysis["recommendations"] if r.ticker == "ARKK"]
    # No harvest can fire on an unmeasurable loss.
    assert all(r.action != "tax_loss_harvest" for r in arkk)
    # Any sell-type recommendation touching it must be low-confidence and flag the unknown tax impact.
    for rec in arkk:
        if rec.action in {"trim", "replace", "tax_loss_harvest"}:
            assert rec.confidence == "low"
            assert any("tax impact unknown" in note.lower() for note in rec.tax_notes)
