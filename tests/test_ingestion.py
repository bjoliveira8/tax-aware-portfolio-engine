from pathlib import Path

from data.loaders import CsvDataProvider, parse_account_type, portfolio_summary

ROOT = Path(__file__).resolve().parents[1]


def test_ingestion_flags_invalid_and_missing_basis(tmp_path: Path):
    holdings = tmp_path / "holdings.csv"
    holdings.write_text(
        "account_id,account_name,account_type,ticker,asset_type,shares,market_value,expense_ratio,dividend_yield\nA,Acct,taxable,bad!,etf,1,100,0.001,0.01\n",
        encoding="utf-8",
    )
    lots = tmp_path / "lots.csv"
    lots.write_text(
        "account_id,ticker,shares,cost_basis_per_share,acquired_date,holding_period_days,market_price\nA,BAD!,1,,2025-01-01,400,100\n",
        encoding="utf-8",
    )
    menus = tmp_path / "menus.csv"
    menus.write_text("account_id,universe,allowed_instruments\nA,open,\n", encoding="utf-8")
    result = CsvDataProvider().load(holdings, lots, menus)
    assert any("Invalid ticker flagged" in warning for warning in result.warnings)
    assert any("tax impact unknown" in warning for warning in result.warnings)


def test_account_types_and_summary():
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", ROOT / "data/mock_tax_lots.csv", ROOT / "data/mock_account_menus.csv")
    assert parse_account_type("Roth IRA") == "roth_ira"
    summary = portfolio_summary(result.holdings)
    assert round(summary["total_market_value"], 2) == 195500.00
    assert summary["accounts_detected"] == ["HSA-1", "IRA-1", "ROTH-1", "TAX-1"]
