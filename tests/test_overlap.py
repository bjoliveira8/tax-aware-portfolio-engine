from pathlib import Path

from core.overlap_engine import OverlapEngine
from data.loaders import CsvDataProvider, load_security_master_csv

ROOT = Path(__file__).resolve().parents[1]


def test_overlap_and_concentration_flags():
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", ROOT / "data/mock_tax_lots.csv", ROOT / "data/mock_account_menus.csv")
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    engine = OverlapEngine(master)
    flags = engine.concentration_flags(result.holdings, 0.15, 0.35)
    assert any(item["ticker"] == "VTI" for item in flags["single_name_flags"])
    assert flags["account_concentration"]["TAX-1"]["VTI"] > 0.35
    assert engine.overlap_score("BND", "AGG") == 1.0
