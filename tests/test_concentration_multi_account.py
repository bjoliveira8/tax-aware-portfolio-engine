from datetime import date
from pathlib import Path

import pytest

from core.overlap_engine import OverlapEngine
from core.recommendation_engine import generate_recommendations
from data.loaders import load_security_master_csv
from data.schemas import AccountMenu, Holding, TaxLot, TaxProfile

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {"single_name_threshold": 0.15, "sector_threshold": 0.35, "drift_threshold": 0.05, "high_fee_threshold": 0.0040, "harvest_loss_threshold": -500.0}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}


def _master():
    return load_security_master_csv(ROOT / "data/security_master.csv")


def test_single_name_aggregated_across_accounts():
    # VTI is 12% in TAX-1 and 10% in IRA-1: neither row crosses 15%, but combined 22% does.
    holdings = [
        Holding("TAX-1", "Taxable", "taxable", "VTI", "etf", 48, 12000.0, 0.0003, 0.013),
        Holding("IRA-1", "IRA", "traditional_ira", "VTI", "etf", 40, 10000.0, 0.0003, 0.013),
        Holding("TAX-1", "Taxable", "taxable", "BND", "etf", 1114, 78000.0, 0.0003, 0.031),
    ]
    engine = OverlapEngine(_master())
    flags = engine.concentration_flags(holdings, 0.15, 0.35)
    vti_flags = [f for f in flags["single_name_flags"] if f["ticker"] == "VTI"]
    assert len(vti_flags) == 1
    assert vti_flags[0]["weight"] == pytest.approx(0.22, abs=0.005)
    assert set(vti_flags[0]["account_ids"]) == {"TAX-1", "IRA-1"}


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_concentration_uses_correct_account_tax_treatment(order):
    # Same ticker held in a taxable account (large embedded gain) and an IRA.
    taxable = Holding("TAX-1", "Taxable", "taxable", "VTI", "etf", 100, 25000.0, 0.0003, 0.013)
    ira = Holding("IRA-1", "IRA", "traditional_ira", "VTI", "etf", 60, 15000.0, 0.0003, 0.013)
    holdings = [[taxable, ira][i] for i in order]
    lots = [
        TaxLot("TAX-1", "VTI", 100, 100.0, date(2022, 1, 1), 1200, True, 15000.0),  # big LT gain -> blocked
        TaxLot("IRA-1", "VTI", 60, 100.0, date(2022, 1, 1), 1200, True, 9000.0),
    ]
    menus = [AccountMenu("TAX-1", "open", None), AccountMenu("IRA-1", "menu", ["VTI"])]
    analysis = generate_recommendations(holdings, lots, menus, _master(), THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    recs = analysis["recommendations"]
    # The taxable position is blocked by tax cost regardless of input order (order-independence).
    assert any(r.action == "do_nothing_due_to_tax_cost" and r.ticker == "VTI" and r.account_id == "TAX-1" for r in recs)
    # The IRA position is correctly treated as tax-advantaged: never tax-cost-blocked and never
    # carries a taxable estimate, no matter the input order. This proves the resolver attributes
    # each account's tax treatment to the correct (ticker, account_id) lots.
    ira_recs = [r for r in recs if r.ticker == "VTI" and r.account_id == "IRA-1"]
    assert ira_recs
    assert all(r.action != "do_nothing_due_to_tax_cost" for r in ira_recs)
    assert all(not any("Estimated tax cost" in note for note in r.tax_notes) for r in ira_recs)
