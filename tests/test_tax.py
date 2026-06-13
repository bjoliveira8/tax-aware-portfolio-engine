from datetime import date
from pathlib import Path

from core.tax_lot_engine import estimate_sale_tax
from core.wash_sale_guard import WashSaleGuard
from data.loaders import CsvDataProvider, load_security_master_csv
from data.schemas import TaxProfile

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)


def test_tax_cost_and_wash_sale_rules():
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", ROOT / "data/mock_tax_lots.csv", ROOT / "data/mock_account_menus.csv")
    vti_lots = [lot for lot in result.tax_lots if lot.ticker == "VTI" and lot.account_id == "TAX-1"]
    analysis = estimate_sale_tax(vti_lots, TAX_PROFILE)
    assert analysis.estimated_tax_cost is not None
    assert analysis.blocked_by_tax_cost is True

    guard = WashSaleGuard(load_security_master_csv(ROOT / "data/security_master.csv"))
    blocked = guard.check_harvest("VTI", date(2026, 6, 1), result.tax_lots, ["ITOT"])
    assert blocked.status == "wash_sale_blocked_retirement_account_purchase"

    clean = guard.check_harvest("VXUS", date(2026, 6, 1), result.tax_lots, ["VEA"])
    assert clean.status == "wash_sale_clean"
