from datetime import date
from pathlib import Path

from core.recommendation_engine import generate_recommendations
from data.loaders import CsvDataProvider, load_security_master_csv
from data.schemas import TaxProfile

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {"single_name_threshold": 0.15, "sector_threshold": 0.35, "drift_threshold": 0.05, "high_fee_threshold": 0.0040, "harvest_loss_threshold": -500.0}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}


def test_action_engine_behaviors():
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", ROOT / "data/mock_tax_lots.csv", ROOT / "data/mock_account_menus.csv")
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    analysis = generate_recommendations(result.holdings, result.tax_lots, result.account_menus, master, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    recommendations = analysis["recommendations"]
    assert any(item.action == "tax_loss_harvest" and item.ticker == "VXUS" for item in recommendations)
    assert any(item.action == "do_nothing_due_to_tax_cost" and item.ticker in {"VTI", "us_equity"} for item in recommendations)
    # Account-menu constraint: no surviving recommendation may name a replacement instrument the
    # destination account cannot hold (after reconciliation a menu-block may be superseded by a
    # higher-priority directional action, but a forbidden instrument must never be recommended).
    menu_map = {menu.account_id: menu for menu in result.account_menus}
    for item in recommendations:
        menu = menu_map.get(item.account_id)
        if item.replacement_ticker and menu and menu.universe == "menu":
            assert item.replacement_ticker in (menu.allowed_instruments or [])
    # Reconciliation: at most one directional action per concrete (ticker, account_id) position.
    from collections import Counter
    directional = Counter(
        (item.ticker, item.account_id)
        for item in recommendations
        if item.account_id is not None and item.action != "hold"
    )
    assert all(count == 1 for count in directional.values())


def test_relocate_respects_menu():
    # A relocate names a destination account TYPE (not a concrete instrument), so it must disclose
    # that the destination account's menu has to be confirmed at execution -- never silently
    # implying a buy of an instrument an account may not hold.
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", ROOT / "data/mock_tax_lots.csv", ROOT / "data/mock_account_menus.csv")
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    analysis = generate_recommendations(result.holdings, result.tax_lots, result.account_menus, master, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    relocates = [item for item in analysis["recommendations"] if item.action == "relocate"]
    assert relocates  # BND relocate exists on mock data
    for item in relocates:
        assert any("menu" in note.lower() for note in item.rationale)
