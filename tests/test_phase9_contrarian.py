from datetime import date
from pathlib import Path
from typing import cast

from core.recommendation_engine import generate_recommendations
from data.loaders import load_security_master_csv
from data.schemas import AccountMenu, Holding, Recommendation, TaxLot, TaxProfile

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {
    "single_name_threshold": 0.15,
    "sector_threshold": 0.35,
    "drift_threshold": 0.05,
    "high_fee_threshold": 0.0040,
    "harvest_loss_threshold": -500.0,
}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}
AS_OF = date(2026, 6, 1)
MASTER = load_security_master_csv(ROOT / "data/security_master.csv")


def recs(holdings: list[Holding], lots: list[TaxLot], menus: list[AccountMenu]) -> list[Recommendation]:
    analysis = generate_recommendations(holdings, lots, menus, MASTER, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF)
    return cast(list[Recommendation], analysis["recommendations"])


def test_attack_taxable_sale_without_estimate_note_is_blocked_by_explicit_estimate():
    holdings = [
        Holding("TAX-ATTACK", "Taxable", "taxable", "AAPL", "stock", 100, 20000, None, 0.005),
        Holding("IRA-ATTACK", "IRA", "traditional_ira", "BND", "etf", 100, 80000, 0.0003, 0.031),
    ]
    lots = [
        TaxLot("TAX-ATTACK", "AAPL", 100, 190, date(2024, 1, 1), 882, True, 1000.0),
        TaxLot("IRA-ATTACK", "BND", 100, 790, date(2024, 1, 1), 882, True, 1000.0),
    ]
    menus = [AccountMenu("TAX-ATTACK", "open", None), AccountMenu("IRA-ATTACK", "open", None)]

    recommendations = recs(holdings, lots, menus)
    trim = next(item for item in recommendations if item.action == "trim" and item.ticker == "AAPL")

    assert any("Estimated tax cost:" in note for note in trim.tax_notes)


def test_attack_wash_sale_bypass_fails_same_ticker_recent_buy_is_blocked():
    holdings = [
        Holding("TAX-LOSS", "Taxable", "taxable", "VTI", "etf", 100, 10000, 0.0003, 0.013),
        Holding("RET-01", "Roth", "roth_ira", "CASH", "cash", 1, 90000, None, 0.0),
    ]
    lots = [
        TaxLot("TAX-LOSS", "VTI", 100, 150, date(2025, 1, 1), 516, True, -5000.0),
        TaxLot("RET-01", "VTI", 10, 100, date(2026, 5, 20), 12, False, 0.0),
    ]
    menus = [AccountMenu("TAX-LOSS", "open", None), AccountMenu("RET-01", "open", None)]

    recommendations = recs(holdings, lots, menus)

    assert not any(item.action == "tax_loss_harvest" and item.ticker == "VTI" for item in recommendations)
    blocked = next(item for item in recommendations if item.ticker == "VTI" and item.action == "hold")
    assert any("Same ticker buy in window" in note for note in blocked.tax_notes)


def test_attack_macro_llm_influence_fails_engine_has_no_influence_inputs():
    holdings = [
        Holding("TAX-B", "Balanced Taxable", "taxable", "VTI", "etf", 100, 25000, 0.0003, 0.013),
        Holding("TAX-B", "Balanced Taxable", "taxable", "ITOT", "etf", 100, 25000, 0.0003, 0.013),
        Holding("TAX-B", "Balanced Taxable", "taxable", "VTV", "etf", 100, 25000, 0.0004, 0.022),
        Holding("TAX-B", "Balanced Taxable", "taxable", "SCHB", "etf", 100, 25000, 0.0003, 0.013),
        Holding("TAX-B", "Balanced Taxable", "taxable", "VXUS", "etf", 200, 20000, 0.0007, 0.028),
        Holding("TAX-B", "Balanced Taxable", "taxable", "VEA", "etf", 200, 20000, 0.0005, 0.027),
        Holding("IRA-B", "Balanced IRA", "traditional_ira", "BND", "etf", 180, 25000, 0.0003, 0.031),
        Holding("IRA-B", "Balanced IRA", "traditional_ira", "IEF", "etf", 180, 25000, 0.0015, 0.028),
        Holding("TAX-B", "Balanced Taxable", "taxable", "CASH", "cash", 1, 10000, None, 0.0),
    ]
    lots = [
        TaxLot("TAX-B", "VTI", 100, 240, date(2024, 1, 1), 882, True, 1000.0),
        TaxLot("TAX-B", "ITOT", 100, 240, date(2024, 1, 1), 882, True, 1000.0),
        TaxLot("TAX-B", "VTV", 100, 240, date(2024, 1, 1), 882, True, 1000.0),
        TaxLot("TAX-B", "SCHB", 100, 240, date(2024, 1, 1), 882, True, 1000.0),
        TaxLot("TAX-B", "VXUS", 200, 96, date(2024, 1, 1), 882, True, 800.0),
        TaxLot("TAX-B", "VEA", 200, 96, date(2024, 1, 1), 882, True, 800.0),
        TaxLot("IRA-B", "BND", 180, 136, date(2024, 1, 1), 882, True, 520.0),
        TaxLot("IRA-B", "IEF", 180, 136, date(2024, 1, 1), 882, True, 520.0),
    ]
    menus = [AccountMenu("TAX-B", "open", None), AccountMenu("IRA-B", "menu", ["BND", "IEF"])]

    recommendations = recs(holdings, lots, menus)
    assert len(recommendations) == 1
    assert recommendations[0].rationale == ["No action is justified."]


def test_attack_account_menu_violation_is_blocked_for_overlap_replace():
    holdings = [
        Holding("IRA-MENU", "Menu IRA", "traditional_ira", "BND", "etf", 100, 45000, 0.0003, 0.031),
        Holding("IRA-MENU", "Menu IRA", "traditional_ira", "AGG", "etf", 100, 45000, 0.0003, 0.030),
        Holding("TAX-CASH", "Taxable", "taxable", "CASH", "cash", 1, 10000, None, 0.0),
    ]
    lots = [
        TaxLot("IRA-MENU", "BND", 100, 430, date(2024, 1, 1), 882, True, 2000.0),
        TaxLot("IRA-MENU", "AGG", 100, 430, date(2024, 1, 1), 882, True, 2000.0),
        TaxLot("TAX-CASH", "CASH", 1, 10000, date(2024, 1, 1), 882, True, 0.0),
    ]
    menus = [
        AccountMenu("IRA-MENU", "menu", ["BND"]),
        AccountMenu("TAX-CASH", "open", None),
    ]

    recommendations = recs(holdings, lots, menus)
    blocked = next(item for item in recommendations if item.action == "hold" and item.ticker == "BND")
    assert any("account menu" in text.lower() for text in blocked.rationale + blocked.tax_notes)


def test_attack_force_action_when_none_justified_fails_on_balanced_portfolio():
    holdings = [
        Holding("TAX-B", "Balanced Taxable", "taxable", "VTI", "etf", 100, 25000, 0.0003, 0.013),
        Holding("TAX-B", "Balanced Taxable", "taxable", "ITOT", "etf", 100, 25000, 0.0003, 0.013),
        Holding("TAX-B", "Balanced Taxable", "taxable", "VTV", "etf", 100, 25000, 0.0004, 0.022),
        Holding("TAX-B", "Balanced Taxable", "taxable", "SCHB", "etf", 100, 25000, 0.0003, 0.013),
        Holding("TAX-B", "Balanced Taxable", "taxable", "VXUS", "etf", 200, 20000, 0.0007, 0.028),
        Holding("TAX-B", "Balanced Taxable", "taxable", "VEA", "etf", 200, 20000, 0.0005, 0.027),
        Holding("IRA-B", "Balanced IRA", "traditional_ira", "BND", "etf", 180, 25000, 0.0003, 0.031),
        Holding("IRA-B", "Balanced IRA", "traditional_ira", "IEF", "etf", 180, 25000, 0.0015, 0.028),
        Holding("TAX-B", "Balanced Taxable", "taxable", "CASH", "cash", 1, 10000, None, 0.0),
    ]
    lots = [
        TaxLot("TAX-B", "VTI", 100, 240, date(2024, 1, 1), 882, True, 1000.0),
        TaxLot("TAX-B", "ITOT", 100, 240, date(2024, 1, 1), 882, True, 1000.0),
        TaxLot("TAX-B", "VTV", 100, 240, date(2024, 1, 1), 882, True, 1000.0),
        TaxLot("TAX-B", "SCHB", 100, 240, date(2024, 1, 1), 882, True, 1000.0),
        TaxLot("TAX-B", "VXUS", 200, 96, date(2024, 1, 1), 882, True, 800.0),
        TaxLot("TAX-B", "VEA", 200, 96, date(2024, 1, 1), 882, True, 800.0),
        TaxLot("IRA-B", "BND", 180, 136, date(2024, 1, 1), 882, True, 520.0),
        TaxLot("IRA-B", "IEF", 180, 136, date(2024, 1, 1), 882, True, 520.0),
    ]
    menus = [AccountMenu("TAX-B", "open", None), AccountMenu("IRA-B", "menu", ["BND", "IEF"])]

    recommendations = recs(holdings, lots, menus)
    assert len(recommendations) == 1
    assert recommendations[0].action == "hold"
    assert recommendations[0].rationale == ["No action is justified."]
