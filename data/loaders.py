from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from core.provider import IngestionResult
from data.schemas import AccountMenu, Holding, SecurityMetadata, TaxLot

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9._-]{0,9}$")
ACCOUNT_TYPE_ALIASES = {
    "brokerage": "taxable",
    "taxable": "taxable",
    "trad 401k": "traditional_401k",
    "traditional_401k": "traditional_401k",
    "401k": "traditional_401k",
    "roth 401k": "roth_401k",
    "roth_401k": "roth_401k",
    "trad ira": "traditional_ira",
    "traditional_ira": "traditional_ira",
    "ira": "traditional_ira",
    "roth ira": "roth_ira",
    "roth_ira": "roth_ira",
    "hsa": "hsa",
    "other": "other",
}


class InputValidationError(ValueError):
    pass


def normalize_ticker(value: str) -> str:
    return value.strip().upper()


def parse_account_type(value: str) -> str:
    return ACCOUNT_TYPE_ALIASES.get(value.strip().lower(), "other")


def _to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def load_holdings_csv(path: str | Path) -> tuple[list[Holding], list[str]]:
    holdings: list[Holding] = []
    warnings: list[str] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            ticker = normalize_ticker(row["ticker"])
            if not TICKER_RE.match(ticker):
                warnings.append(f"Invalid ticker flagged: {ticker}")
            holdings.append(
                Holding(
                    account_id=row["account_id"],
                    account_name=row["account_name"],
                    account_type=parse_account_type(row["account_type"]),
                    ticker=ticker,
                    asset_type=row["asset_type"],
                    shares=float(row["shares"]),
                    market_value=float(row["market_value"]),
                    expense_ratio=_to_float(row.get("expense_ratio")),
                    dividend_yield=_to_float(row.get("dividend_yield")),
                )
            )
    return holdings, warnings


def load_tax_lots_csv(
    path: str | Path,
    as_of_date: date | None = None,
    account_types: dict[str, str] | None = None,
) -> tuple[list[TaxLot], list[str]]:
    as_of = as_of_date or date(2026, 6, 1)
    lots: list[TaxLot] = []
    warnings: list[str] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            ticker = normalize_ticker(row["ticker"])
            acquired_date = datetime.strptime(row["acquired_date"], "%Y-%m-%d").date()
            holding_period_days = int(row.get("holding_period_days") or (as_of - acquired_date).days)
            basis = _to_float(row.get("cost_basis_per_share"))
            if basis is None:
                warnings.append(f"Missing cost basis for {ticker} in {row['account_id']}; tax impact unknown")
            market_price = _to_float(row.get("market_price"))
            unrealized_gain = None
            if basis is not None and market_price is not None:
                unrealized_gain = (market_price - basis) * float(row["shares"])
            lots.append(
                TaxLot(
                    account_id=row["account_id"],
                    ticker=ticker,
                    shares=float(row["shares"]),
                    cost_basis_per_share=basis,
                    acquired_date=acquired_date,
                    holding_period_days=holding_period_days,
                    is_long_term=holding_period_days > 365,
                    unrealized_gain=unrealized_gain,
                    account_type=account_types.get(row["account_id"], "other") if account_types else "other",
                )
            )
    return lots, warnings


def load_account_menus_csv(path: str | Path) -> list[AccountMenu]:
    menus: list[AccountMenu] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            allowed = [normalize_ticker(item) for item in row["allowed_instruments"].split("|")] if row.get("allowed_instruments") else None
            menus.append(AccountMenu(account_id=row["account_id"], universe=row["universe"], allowed_instruments=allowed))
    return menus


def load_security_master_csv(path: str | Path) -> dict[str, SecurityMetadata]:
    data: dict[str, SecurityMetadata] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            data[row["ticker"]] = SecurityMetadata(
                ticker=row["ticker"],
                security_name=row["security_name"],
                security_type=row["security_type"],
                issuer=row["issuer"],
                asset_class=row["asset_class"],
                sub_asset_class=row["sub_asset_class"],
                region=row["region"],
                style=row["style"],
                sector_focus=row["sector_focus"],
                index_family=row["index_family"],
                expense_ratio=_to_float(row.get("expense_ratio")),
                distribution_yield=_to_float(row.get("distribution_yield")),
                aum_usd=_to_float(row.get("aum_usd")),
                avg_daily_dollar_volume=_to_float(row.get("avg_daily_dollar_volume")),
                tax_efficiency_bucket=row["tax_efficiency_bucket"],
                primary_benchmark=row["primary_benchmark"],
                source_note=row["source_note"],
                as_of_date=row["as_of_date"],
            )
    return data


def validate_ingestion(result: IngestionResult, security_master: dict[str, SecurityMetadata]) -> None:
    errors: list[str] = []
    holding_tickers = {holding.ticker for holding in result.holdings}
    lot_tickers = {lot.ticker for lot in result.tax_lots}
    unknown_holdings = sorted(ticker for ticker in holding_tickers if ticker not in security_master)
    if unknown_holdings:
        errors.append(f"Unknown tickers in holdings: {', '.join(unknown_holdings)}")
    unknown_lots = sorted(ticker for ticker in lot_tickers if ticker not in security_master)
    if unknown_lots:
        errors.append(f"Unknown tickers in tax lots: {', '.join(unknown_lots)}")
    if result.account_menus:
        menu_accounts = {menu.account_id for menu in result.account_menus}
        holding_accounts = {holding.account_id for holding in result.holdings}
        missing_menu_coverage = sorted(account for account in holding_accounts if account not in menu_accounts)
        if missing_menu_coverage:
            errors.append(f"Missing account menu coverage for accounts: {', '.join(missing_menu_coverage)}")
    if errors:
        raise InputValidationError("; ".join(errors))


class CsvDataProvider:
    def __init__(self, as_of_date: date | None = None):
        self.as_of_date = as_of_date

    def load(self, holdings_path: str | Path, lots_path: str | Path, account_menus_path: str | Path | None = None) -> IngestionResult:
        holdings, holding_warnings = load_holdings_csv(holdings_path)
        account_types = {holding.account_id: holding.account_type for holding in holdings}
        lots, lot_warnings = load_tax_lots_csv(lots_path, as_of_date=self.as_of_date, account_types=account_types)
        menus = load_account_menus_csv(account_menus_path) if account_menus_path else []
        return IngestionResult(holdings=holdings, tax_lots=lots, account_menus=menus, warnings=holding_warnings + lot_warnings)


def portfolio_summary(holdings: list[Holding]) -> dict[str, object]:
    total = sum(item.market_value for item in holdings)
    accounts = defaultdict(float)
    for item in holdings:
        accounts[item.account_id] += item.market_value
    return {
        "total_market_value": total,
        "accounts_detected": sorted(accounts),
        "account_values": dict(accounts),
    }
