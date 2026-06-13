from datetime import date
from pathlib import Path

from core.recommendation_engine import generate_recommendations
from data.loaders import load_security_master_csv
from data.schemas import AccountMenu, Holding, TaxLot, TaxProfile

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {"single_name_threshold": 0.15, "sector_threshold": 0.35, "drift_threshold": 0.05, "high_fee_threshold": 0.0040, "harvest_loss_threshold": -500.0}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}


def _master():
    return load_security_master_csv(ROOT / "data/security_master.csv")


def test_other_account_does_not_crash():
    # "other" is a documented AccountType; it must never abort the pipeline.
    holdings = [
        Holding("OTHER-1", "Misc", "other", "BND", "etf", 100, 7000.0, 0.0003, 0.031),
        Holding("TAX-1", "Taxable", "taxable", "VTI", "etf", 100, 25000.0, 0.0003, 0.013),
    ]
    lots = [
        TaxLot("OTHER-1", "BND", 100, 70.0, date(2024, 1, 10), 800, True, 0.0),
        TaxLot("TAX-1", "VTI", 100, 180.0, date(2022, 10, 1), 974, True, 7000.0),
    ]
    menus = [AccountMenu("OTHER-1", "open", None), AccountMenu("TAX-1", "open", None)]
    analysis = generate_recommendations(holdings, lots, menus, _master(), THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    recs = analysis["recommendations"]
    assert recs  # returned without raising
    # No relocate should originate from or target the unsupported "other" account.
    assert not any(r.action == "relocate" and r.account_id == "OTHER-1" for r in recs)


def test_cash_not_relocated():
    # Cash has no asset-location thesis; it must never be flagged for relocation out of Roth/HSA.
    holdings = [
        Holding("ROTH-1", "Roth", "roth_ira", "CASH", "cash", 1, 8000.0, None, 0.0),
        Holding("HSA-1", "HSA", "hsa", "CASH", "cash", 1, 5000.0, None, 0.0),
        Holding("TAX-1", "Taxable", "taxable", "VTI", "etf", 100, 25000.0, 0.0003, 0.013),
    ]
    lots = [
        TaxLot("ROTH-1", "CASH", 1, 8000.0, date(2024, 1, 1), 800, True, 0.0),
        TaxLot("HSA-1", "CASH", 1, 5000.0, date(2024, 1, 1), 800, True, 0.0),
        TaxLot("TAX-1", "VTI", 100, 180.0, date(2022, 10, 1), 974, True, 7000.0),
    ]
    menus = [AccountMenu("ROTH-1", "open", None), AccountMenu("HSA-1", "open", None), AccountMenu("TAX-1", "open", None)]
    analysis = generate_recommendations(holdings, lots, menus, _master(), THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    recs = analysis["recommendations"]
    assert not any(r.ticker == "CASH" and r.action in {"relocate", "redirect_contributions"} for r in recs)
