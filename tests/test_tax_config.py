"""M1/M4: the short-term-gain block threshold and NIIT rate are config-driven, not magic numbers."""
from datetime import date

from core.tax_lot_engine import estimate_sale_tax
from data.schemas import TaxLot, TaxProfile


def _short_term_lot(gain):
    return TaxLot("TAX-1", "X", 10, 100.0, date(2026, 1, 1), 100, False, gain)


def test_short_term_block_threshold_configurable():
    gain = 2000.0
    # confirm_with_cpa_above = 5000; fraction 0.25 -> block above 1250 -> 2000 is blocked.
    strict = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000, short_term_gain_block_fraction=0.25)
    assert estimate_sale_tax([_short_term_lot(gain)], strict).blocked_by_tax_cost
    # fraction 0.5 -> block above 2500 -> 2000 is NOT blocked.
    lenient = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000, short_term_gain_block_fraction=0.5)
    assert not estimate_sale_tax([_short_term_lot(gain)], lenient).blocked_by_tax_cost


def test_niit_rate_from_config():
    lot = TaxLot("TAX-1", "X", 10, 100.0, date(2020, 1, 1), 2000, True, 1000.0)
    no_niit = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
    with_niit = TaxProfile("mfj", 0.32, 0.15, True, 0.05, 0.15, 5000, niit_rate=0.10)
    base = estimate_sale_tax([lot], no_niit).estimated_tax_cost
    bumped = estimate_sale_tax([lot], with_niit).estimated_tax_cost
    # Adding a 10% NIIT to a $1000 gain adds $100 of tax.
    assert bumped == round(base + 100.0, 2)
