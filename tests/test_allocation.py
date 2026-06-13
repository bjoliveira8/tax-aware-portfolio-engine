from pathlib import Path

from core.allocation import current_allocation, drift_report, target_allocation
from core.asset_location_engine import evaluate_asset_location
from data.loaders import CsvDataProvider, load_security_master_csv

ROOT = Path(__file__).resolve().parents[1]


def test_allocation_and_location_behavior():
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", ROOT / "data/mock_tax_lots.csv", ROOT / "data/mock_account_menus.csv")
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    current = current_allocation(result.holdings, master)
    target = target_allocation({"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05})
    assert round(sum(current.values()), 6) == 1.0
    assert round(sum(target.values()), 6) == 1.0
    report = drift_report(current, target)
    assert report["us_equity"]["difference"] > 0
    locations = evaluate_asset_location(result.holdings, master, {holding.account_id: holding.account_type for holding in result.holdings})
    assert any(item["ticker"] == "BND" and item["action"] == "relocate" for item in locations)
