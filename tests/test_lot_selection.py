"""5a: specific-lot vs FIFO selection for partial sales (Phase 4 capability)."""
from datetime import date

from core.tax_lot_engine import estimate_sale_tax, select_lots
from data.schemas import TaxLot, TaxProfile

TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)


def _lots():
    # Three lots of the same ticker: an old big-gain lot, a newer small-gain lot, and a loss lot.
    return [
        TaxLot("TAX-1", "VTI", 10, 100.0, date(2020, 1, 1), 2000, True, 5000.0),   # old, big LT gain
        TaxLot("TAX-1", "VTI", 10, 240.0, date(2024, 1, 1), 800, True, 600.0),     # newer, small gain
        TaxLot("TAX-1", "VTI", 10, 300.0, date(2025, 6, 1), 200, False, -1000.0),  # recent loss
    ]


def test_fifo_orders_oldest_first():
    ordered = select_lots(_lots(), method="fifo")
    assert [lot.acquired_date for lot in ordered] == [date(2020, 1, 1), date(2024, 1, 1), date(2025, 6, 1)]


def test_specific_lot_prefers_losses():
    ordered = select_lots(_lots(), method="specific_lot")
    # Loss lot first (most tax-favorable to realize).
    assert ordered[0].unrealized_gain == -1000.0


def test_lot_selection_fifo_vs_specific_differ_on_partial_sale():
    lots = _lots()
    # Sell 10 shares: FIFO realizes the old big-gain lot; specific-lot realizes the loss lot.
    fifo = estimate_sale_tax(lots, TAX_PROFILE, shares_to_sell=10, method="fifo")
    specific = estimate_sale_tax(lots, TAX_PROFILE, shares_to_sell=10, method="specific_lot")
    assert fifo.estimated_gain == 5000.0
    assert specific.estimated_gain == -1000.0
    assert specific.estimated_tax_cost < fifo.estimated_tax_cost


def test_full_position_estimate_unchanged_by_method():
    # A full-position estimate (no shares_to_sell) sums all lots regardless of method.
    lots = _lots()
    total = estimate_sale_tax(lots, TAX_PROFILE)
    assert total.estimated_gain == 4600.0  # 5000 + 600 - 1000


def test_default_method_from_profile():
    lots = _lots()
    profile = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000, lot_selection_method="specific_lot")
    # No explicit method -> falls back to the profile default (specific_lot -> realizes the loss).
    result = estimate_sale_tax(lots, profile, shares_to_sell=10)
    assert result.estimated_gain == -1000.0
