from pathlib import Path

import pytest

from core.allocation import _normalized_rounded, current_allocation, drift_report, target_allocation
from core.asset_location_engine import evaluate_asset_location
from data.loaders import CsvDataProvider, load_security_master_csv

ROOT = Path(__file__).resolve().parents[1]


def test_allocation_and_location_behavior():
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", ROOT / "data/mock_tax_lots.csv", ROOT / "data/mock_account_menus.csv")
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    current = current_allocation(result.holdings, master)
    target = target_allocation({"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05})
    assert sum(current.values()) == pytest.approx(1.0, abs=1e-5)
    assert sum(target.values()) == pytest.approx(1.0, abs=1e-5)
    report = drift_report(current, target)
    assert report["us_equity"]["difference"] > 0
    locations = evaluate_asset_location(result.holdings, master, {holding.account_id: holding.account_type for holding in result.holdings})
    assert any(item["ticker"] == "BND" and item["action"] == "relocate" for item in locations)


def test_normalization_is_proportional_not_masked():
    # Input that does NOT sum to 1 must be normalized proportionally (ratios preserved), and a
    # warning must be surfaced -- not silently absorbed into the last key.
    with pytest.warns(UserWarning):
        normalized = _normalized_rounded({"a": 2.0, "b": 2.0})
    assert normalized == {"a": 0.5, "b": 0.5}
    with pytest.warns(UserWarning):
        skewed = _normalized_rounded({"a": 3.0, "b": 1.0})
    assert skewed["a"] == pytest.approx(0.75)
    assert skewed["b"] == pytest.approx(0.25)


def test_target_allocation_normalizes_unnormalized_model():
    target = target_allocation({"us_equity": 60, "taxable_bond": 40})  # weights, not fractions
    assert target["us_equity"] == pytest.approx(0.6)
    assert target["taxable_bond"] == pytest.approx(0.4)
