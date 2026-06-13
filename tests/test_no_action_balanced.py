from datetime import date
from pathlib import Path

from core.recommendation_engine import generate_recommendations
from data.loaders import CsvDataProvider, load_security_master_csv
from data.schemas import AccountMenu, Holding, TaxLot, TaxProfile

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {"single_name_threshold": 0.15, "sector_threshold": 0.35, "drift_threshold": 0.05, "high_fee_threshold": 0.0040, "harvest_loss_threshold": -500.0}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}


def test_balanced_portfolio_yields_no_action():
    master = load_security_master_csv(ROOT / "data/security_master.csv")
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
    menus = [
        AccountMenu("TAX-B", "open", None),
        AccountMenu("IRA-B", "menu", ["BND", "IEF"]),
    ]
    analysis = generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    recommendations = analysis["recommendations"]
    assert len(recommendations) == 1
    assert recommendations[0].rationale == ["No action is justified."]
