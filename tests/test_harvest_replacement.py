from datetime import date

from core.recommendation_engine import generate_recommendations
from data.schemas import AccountMenu, Holding, SecurityMetadata, TaxLot, TaxProfile

TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {"single_name_threshold": 0.15, "sector_threshold": 0.35, "drift_threshold": 0.05, "high_fee_threshold": 0.0040, "harvest_loss_threshold": -500.0}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}


def _meta(ticker, index_family, expense, volume, style="broad_market", sector="none"):
    return SecurityMetadata(
        ticker=ticker, security_name=ticker, security_type="etf", issuer="x",
        asset_class="us_equity", sub_asset_class="broad_market", region="us",
        style=style, sector_focus=sector, index_family=index_family,
        expense_ratio=expense, distribution_yield=0.0, aum_usd=1e10,
        avg_daily_dollar_volume=volume, tax_efficiency_bucket="high",
        primary_benchmark="x", source_note="test", as_of_date="2026-06-01",
    )


def _bond(ticker):
    return SecurityMetadata(
        ticker=ticker, security_name=ticker, security_type="etf", issuer="x",
        asset_class="taxable_bond", sub_asset_class="aggregate_bond", region="us",
        style="aggregate_bond", sector_focus="none", index_family="BOND_IDX",
        expense_ratio=0.0003, distribution_yield=0.0, aum_usd=1e10,
        avg_daily_dollar_volume=1e8, tax_efficiency_bucket="low",
        primary_benchmark="x", source_note="test", as_of_date="2026-06-01",
    )


def _scenario(volume_low, volume_high):
    # LOW is listed BEFORE HIGH so the pre-H3 "first safe replacement" would wrongly pick LOW.
    master = {
        "LOSSY": _meta("LOSSY", "LOSSY_IDX", 0.001, 9e8),
        "LOW": _meta("LOW", "LOW_IDX", 0.0009, volume_low, style="value"),       # overlap 0.4
        "HIGH": _meta("HIGH", "HIGH_IDX", 0.0003, volume_high, style="broad_market"),  # overlap 0.7
        "BOND": _bond("BOND"),
    }
    holdings = [
        Holding("TAX-1", "Taxable", "taxable", "LOSSY", "etf", 100, 10000.0, 0.001, 0.0),
        Holding("IRA-1", "IRA", "traditional_ira", "BOND", "etf", 100, 90000.0, 0.0003, 0.0),
    ]
    lots = [
        TaxLot("TAX-1", "LOSSY", 100, 150.0, date(2025, 1, 1), 500, True, -5000.0),
        TaxLot("IRA-1", "BOND", 100, 900.0, date(2024, 1, 1), 800, True, 0.0),
    ]
    menus = [AccountMenu("TAX-1", "open", None), AccountMenu("IRA-1", "open", None)]
    analysis = generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    return analysis["recommendations"]


def test_harvest_replacement_is_ranked():
    # Both candidates liquid; HIGH has higher overlap (0.7) and lower fee than LOW (0.4).
    recs = _scenario(volume_low=2e7, volume_high=9e8)
    harvest = next(r for r in recs if r.action == "tax_loss_harvest" and r.ticker == "LOSSY")
    assert harvest.replacement_ticker == "HIGH"  # chosen by rank, not by insertion order


def test_harvest_no_replacement_when_none_suitable():
    # Every candidate is illiquid (< $5M/day): no harvest should be recommended.
    recs = _scenario(volume_low=1e6, volume_high=1e6)
    assert not any(r.action == "tax_loss_harvest" and r.ticker == "LOSSY" for r in recs)
    hold = next(r for r in recs if r.ticker == "LOSSY" and r.action == "hold")
    assert any("no wash-safe replacement" in note.lower() for note in hold.rationale)
