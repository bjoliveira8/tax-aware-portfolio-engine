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
    # VTI is broad-market equity that belongs in taxable, so it is not relocated away; a
    # concentration trim survives as a genuine taxable sale and must carry a tax estimate.
    holdings = [
        Holding("TAX-ATTACK", "Taxable", "taxable", "VTI", "etf", 100, 20000, 0.0003, 0.013),
        Holding("IRA-ATTACK", "IRA", "traditional_ira", "BND", "etf", 100, 80000, 0.0003, 0.031),
    ]
    lots = [
        TaxLot("TAX-ATTACK", "VTI", 100, 190, date(2024, 1, 1), 882, True, 1000.0),
        TaxLot("IRA-ATTACK", "BND", 100, 790, date(2024, 1, 1), 882, True, 1000.0),
    ]
    menus = [AccountMenu("TAX-ATTACK", "open", None), AccountMenu("IRA-ATTACK", "open", None)]

    recommendations = recs(holdings, lots, menus)
    trim = next(item for item in recommendations if item.action == "trim" and item.ticker == "VTI")
    assert any("Estimated tax cost:" in note for note in trim.tax_notes)

    # General invariant: no surviving taxable-account sale may lack a tax estimate / unknown flag.
    for item in recommendations:
        if item.account_id == "TAX-ATTACK" and item.action in {"trim", "replace", "tax_loss_harvest"}:
            assert any("Estimated tax cost" in note or "tax impact unknown" in note.lower() for note in item.tax_notes)


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
    # The real constraint: no surviving recommendation may name a replacement instrument the
    # destination account cannot hold. (A menu-block hold may be superseded by a higher-priority
    # directional action during reconciliation, but the forbidden instrument must never appear.)
    menu_map = {menu.account_id: menu for menu in menus}
    for item in recommendations:
        menu = menu_map.get(item.account_id)
        if item.replacement_ticker and menu and menu.universe == "menu":
            assert item.replacement_ticker in (menu.allowed_instruments or [])
    # AGG is not in IRA-MENU's menu, so it must never be recommended as a replacement there.
    assert not any(item.account_id == "IRA-MENU" and item.replacement_ticker == "AGG" for item in recommendations)


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
