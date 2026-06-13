"""T6 / L2 / L6: degenerate inputs are handled gracefully, not with crashes or silent corruption."""
from datetime import date
from pathlib import Path

from core.recommendation_engine import generate_recommendations
from data.loaders import blended_fee_drag_bps, load_security_master_csv
from data.schemas import AccountMenu, Holding, TaxLot, TaxProfile

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {"single_name_threshold": 0.15, "sector_threshold": 0.35, "drift_threshold": 0.05, "high_fee_threshold": 0.0040, "harvest_loss_threshold": -500.0}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}
MASTER = load_security_master_csv(ROOT / "data/security_master.csv")


def _run(holdings, lots, menus):
    return generate_recommendations(holdings, lots, menus, MASTER, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))


def test_empty_portfolio_yields_no_action():
    analysis = _run([], [], [])
    recs = analysis["recommendations"]
    assert len(recs) == 1 and recs[0].thesis_key == "no-action"


def test_zero_and_negative_market_value_no_crash():
    holdings = [
        Holding("TAX-1", "Taxable", "taxable", "VTI", "etf", 0, 0.0, 0.0003, 0.013),
        Holding("TAX-1", "Taxable", "taxable", "BND", "etf", -1, -100.0, 0.0003, 0.031),
    ]
    lots = [
        TaxLot("TAX-1", "VTI", 0, 100.0, date(2022, 1, 1), 1200, True, 0.0),
        TaxLot("TAX-1", "BND", -1, 100.0, date(2022, 1, 1), 1200, True, 0.0),
    ]
    analysis = _run(holdings, lots, [AccountMenu("TAX-1", "open", None)])
    assert analysis["recommendations"]  # returned without raising / div-by-zero


def test_all_none_basis_no_confident_sell():
    holdings = [
        Holding("TAX-1", "Taxable", "taxable", "VTI", "etf", 100, 60000.0, 0.0003, 0.013),
        Holding("TAX-1", "Taxable", "taxable", "BND", "etf", 100, 40000.0, 0.0003, 0.031),
    ]
    lots = [
        TaxLot("TAX-1", "VTI", 100, None, date(2022, 1, 1), 1200, True, None),
        TaxLot("TAX-1", "BND", 100, None, date(2022, 1, 1), 1200, True, None),
    ]
    recs = _run(holdings, lots, [AccountMenu("TAX-1", "open", None)])["recommendations"]
    for rec in recs:
        if rec.action in {"trim", "replace", "tax_loss_harvest"} and rec.account_id == "TAX-1":
            assert rec.confidence == "low"
            assert any("tax impact unknown" in note.lower() for note in rec.tax_notes)


def test_unknown_ticker_warns_not_crashes():
    holdings = [
        Holding("TAX-1", "Taxable", "taxable", "NOTREAL", "etf", 100, 50000.0, 0.0003, 0.0),
        Holding("TAX-1", "Taxable", "taxable", "VTI", "etf", 100, 50000.0, 0.0003, 0.013),
    ]
    lots = [
        TaxLot("TAX-1", "NOTREAL", 100, 100.0, date(2022, 1, 1), 1200, True, 0.0),
        TaxLot("TAX-1", "VTI", 100, 100.0, date(2022, 1, 1), 1200, True, 0.0),
    ]
    analysis = _run(holdings, lots, [AccountMenu("TAX-1", "open", None)])
    assert "NOTREAL" in analysis["unknown_securities"]
    assert not any(r.ticker == "NOTREAL" for r in analysis["recommendations"])


def test_fee_drag_excludes_none_expense():
    holdings = [
        Holding("TAX-1", "Taxable", "taxable", "VTI", "etf", 100, 50000.0, 0.0010, 0.013),
        Holding("ROTH-1", "Roth", "roth_ira", "CASH", "cash", 1, 50000.0, None, 0.0),
    ]
    # Cash (None expense) must not dilute the blended fee: result is 10 bps, not 5.
    assert blended_fee_drag_bps(holdings) == 10.0
