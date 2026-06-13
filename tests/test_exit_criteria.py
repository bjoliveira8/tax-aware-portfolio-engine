"""Backfill tests for plan Exit Criteria that were implemented but previously unverified."""
from datetime import date
from pathlib import Path

from core.asset_location_engine import evaluate_asset_location
from core.overlap_engine import OverlapEngine
from core.recommendation_engine import generate_recommendations
from data.loaders import CsvDataProvider, load_security_master_csv
from data.schemas import AccountMenu, Holding, SecurityMetadata, TaxLot, TaxProfile
from reporting.process_log import build_process_log
from reporting.report_generator import render_report

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {"single_name_threshold": 0.15, "sector_threshold": 0.35, "drift_threshold": 0.05, "high_fee_threshold": 0.0040, "harvest_loss_threshold": -500.0}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}
MASTER = load_security_master_csv(ROOT / "data/security_master.csv")


def _equity(ticker, index_family, expense, volume, style="broad_market", sector="none"):
    return SecurityMetadata(
        ticker=ticker, security_name=ticker, security_type="etf", issuer="x",
        asset_class="us_equity", sub_asset_class="broad_market", region="us",
        style=style, sector_focus=sector, index_family=index_family,
        expense_ratio=expense, distribution_yield=0.0, aum_usd=1e10,
        avg_daily_dollar_volume=volume, tax_efficiency_bucket="high",
        primary_benchmark="x", source_note="t", as_of_date="2026-06-01",
    )


def _run(holdings, lots, menus, master=MASTER):
    return generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))["recommendations"]


# 1. Lower-fee but illiquid ETF must not be auto-preferred over a liquid one.
def test_illiquid_replacement_rejected():
    master = {
        "HIFEE": _equity("HIFEE", "HF", 0.010, 9e8),
        "ILLIQ": _equity("ILLIQ", "IL", 0.001, 1e6),   # cheapest but illiquid
        "LIQ": _equity("LIQ", "LQ", 0.002, 9e8),       # slightly pricier but liquid
        "FILL": _equity("FILL", "FL", 0.0003, 9e8, style="value", sector="financials"),
    }
    holdings = [
        Holding("TAX-1", "Taxable", "taxable", "HIFEE", "etf", 100, 10000.0, 0.010, 0.0),
        Holding("TAX-1", "Taxable", "taxable", "FILL", "etf", 100, 90000.0, 0.0003, 0.0),
    ]
    lots = [
        TaxLot("TAX-1", "HIFEE", 100, 100.0, date(2022, 1, 1), 1200, True, 0.0),
        TaxLot("TAX-1", "FILL", 100, 900.0, date(2022, 1, 1), 1200, True, 0.0),
    ]
    menus = [AccountMenu("TAX-1", "open", None)]
    recs = _run(holdings, lots, menus, master)
    replace = next(r for r in recs if r.action == "replace" and r.ticker == "HIFEE")
    assert replace.replacement_ticker == "LIQ"  # never the cheaper illiquid candidate


# 2. A replacement blocked by tax cost in taxable is allowed in an IRA.
def _bond(ticker, index_family, expense, volume=9e8):
    return SecurityMetadata(
        ticker=ticker, security_name=ticker, security_type="etf", issuer="x",
        asset_class="taxable_bond", sub_asset_class="aggregate_bond", region="us",
        style="aggregate_bond", sector_focus="none", index_family=index_family,
        expense_ratio=expense, distribution_yield=0.0, aum_usd=1e10,
        avg_daily_dollar_volume=volume, tax_efficiency_bucket="low",
        primary_benchmark="x", source_note="t", as_of_date="2026-06-01",
    )


def test_replace_blocked_taxable_allowed_ira():
    # A high-fee bond fund prefers a tax-advantaged account. In the IRA it is in its preferred
    # location (no relocate), so the fee replacement survives. In the taxable account with a big
    # embedded gain the swap is blocked by tax cost.
    master = {
        "HIBOND": _bond("HIBOND", "HB", 0.010),
        "CHEAPBOND": _bond("CHEAPBOND", "CB", 0.0003),
        "FILL": _equity("FILL", "FL", 0.0003, 9e8, style="value", sector="financials"),
    }
    holdings = [
        Holding("TAX-1", "Taxable", "taxable", "HIBOND", "etf", 100, 5000.0, 0.010, 0.0),
        Holding("IRA-1", "IRA", "traditional_ira", "HIBOND", "etf", 100, 5000.0, 0.010, 0.0),
        Holding("TAX-1", "Taxable", "taxable", "FILL", "etf", 100, 90000.0, 0.0003, 0.0),
    ]
    lots = [
        TaxLot("TAX-1", "HIBOND", 100, 1.0, date(2022, 1, 1), 1200, True, 9900.0),   # big gain -> blocked
        TaxLot("IRA-1", "HIBOND", 100, 1.0, date(2022, 1, 1), 1200, True, 9900.0),
        TaxLot("TAX-1", "FILL", 100, 900.0, date(2022, 1, 1), 1200, True, 0.0),
    ]
    menus = [AccountMenu("TAX-1", "open", None), AccountMenu("IRA-1", "open", None)]
    recs = _run(holdings, lots, menus, master)
    taxable = [r for r in recs if r.ticker == "HIBOND" and r.account_id == "TAX-1"]
    ira = [r for r in recs if r.ticker == "HIBOND" and r.account_id == "IRA-1"]
    assert any(r.action == "do_nothing_due_to_tax_cost" for r in taxable)
    assert all(r.action != "replace" for r in taxable)
    assert any(r.action == "replace" for r in ira)


# 5. An overweight position in a Roth trims with NO tax warning.
def test_roth_trim_no_tax_warning():
    # AVUV (small-value) already prefers a Roth, so it is not relocated away; the concentration
    # trim survives and must carry no tax warning in a tax-advantaged account.
    holdings = [
        Holding("ROTH-1", "Roth", "roth_ira", "AVUV", "etf", 100, 30000.0, 0.0025, 0.018),
        Holding("ROTH-1", "Roth", "roth_ira", "CASH", "cash", 1, 10000.0, None, 0.0),
    ]
    lots = [
        TaxLot("ROTH-1", "AVUV", 100, 100.0, date(2022, 1, 1), 1200, True, 20000.0),
        TaxLot("ROTH-1", "CASH", 1, 10000.0, date(2022, 1, 1), 1200, True, 0.0),
    ]
    menus = [AccountMenu("ROTH-1", "open", None)]
    recs = _run(holdings, lots, menus)
    trim = next(r for r in recs if r.action == "trim" and r.ticker == "AVUV")
    assert trim.tax_notes == ["No tax warning in tax-advantaged account."]


# 6. A taxable sale above confirm_with_cpa_above surfaces the CPA note.
def test_cpa_note_on_large_sale():
    holdings = [Holding("TAX-1", "Taxable", "taxable", "VTI", "etf", 100, 60000.0, 0.0003, 0.013)]
    lots = [TaxLot("TAX-1", "VTI", 100, 100.0, date(2022, 1, 1), 1200, True, 50000.0)]
    menus = [AccountMenu("TAX-1", "open", None)]
    recs = _run(holdings, lots, menus)
    notes = [note for r in recs if r.ticker == "VTI" for note in r.tax_notes]
    assert any("Confirm with a tax professional" in note for note in notes)


# 7. A sector above the 35% threshold is flagged.
def test_sector_concentration_flagged():
    master = {
        "T1": _equity("T1", "I1", 0.0003, 9e8, sector="technology"),
        "T2": _equity("T2", "I2", 0.0003, 9e8, sector="technology"),
        "B1": _equity("B1", "I3", 0.0003, 9e8, sector="none", style="value"),
    }
    holdings = [
        Holding("TAX-1", "Taxable", "taxable", "T1", "etf", 1, 30000.0, 0.0003, 0.0),
        Holding("TAX-1", "Taxable", "taxable", "T2", "etf", 1, 30000.0, 0.0003, 0.0),
        Holding("TAX-1", "Taxable", "taxable", "B1", "etf", 1, 40000.0, 0.0003, 0.0),
    ]
    flags = OverlapEngine(master).concentration_flags(holdings, 0.15, 0.35)
    assert any(f["sector"] == "technology" and f["weight"] > 0.35 for f in flags["sector_flags"])


# 8. Sub-threshold drift produces no rebalance/add trade.
def test_subthreshold_drift_no_trade():
    # Allocation matches target closely (within the 5% drift threshold) across asset classes.
    holdings = [
        Holding("IRA-1", "IRA", "traditional_ira", "VTI", "etf", 1, 50000.0, 0.0003, 0.013),
        Holding("IRA-1", "IRA", "traditional_ira", "VXUS", "etf", 1, 20000.0, 0.0007, 0.028),
        Holding("IRA-1", "IRA", "traditional_ira", "BND", "etf", 1, 25000.0, 0.0003, 0.031),
        Holding("ROTH-1", "Roth", "roth_ira", "CASH", "cash", 1, 5000.0, None, 0.0),
    ]
    lots = [
        TaxLot("IRA-1", "VTI", 1, 100.0, date(2022, 1, 1), 1200, True, 0.0),
        TaxLot("IRA-1", "VXUS", 1, 100.0, date(2022, 1, 1), 1200, True, 0.0),
        TaxLot("IRA-1", "BND", 1, 100.0, date(2022, 1, 1), 1200, True, 0.0),
        TaxLot("ROTH-1", "CASH", 1, 5000.0, date(2022, 1, 1), 1200, True, 0.0),
    ]
    menus = [AccountMenu("IRA-1", "open", None), AccountMenu("ROTH-1", "open", None)]
    recs = _run(holdings, lots, menus)
    assert not any(r.action in {"rebalance", "add"} for r in recs)


# 9. A growth asset is steered to Roth/HSA.
def test_growth_prefers_roth_hsa():
    holdings = [Holding("TAX-1", "Taxable", "taxable", "AVUV", "etf", 1, 10000.0, 0.0025, 0.018)]
    suggestions = evaluate_asset_location(holdings, MASTER, {"TAX-1": "taxable"})
    avuv = next(s for s in suggestions if s["ticker"] == "AVUV")
    assert avuv["preferred_account_type"] in {"roth_ira", "roth_401k", "hsa"}


# 10. The rendered report prints "No action is justified" for a balanced portfolio.
def _no_action_analysis():
    # Canonical balanced portfolio (mirrors test_no_action_balanced): no single name > 15%, no
    # redundancy, no fee issue, all in preferred locations, drift within tolerance.
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
    menus = [AccountMenu("TAX-B", "open", None), AccountMenu("IRA-B", "menu", ["BND", "IEF"])]
    return generate_recommendations(holdings, lots, menus, MASTER, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))


def test_report_no_action_text(tmp_path):
    analysis = _no_action_analysis()
    recs = analysis["recommendations"]
    assert len(recs) == 1 and recs[0].thesis_key == "no-action"
    log = build_process_log(recs, 5.0, True, True, True, "2026-06-01")
    report = render_report(analysis, recs, log, 5.0, tmp_path / "r.md")
    assert "No action is justified." in report


# 11. Re-running on the same snapshot is deterministic (identical IDs, no duplicates).
def test_rerun_deterministic_ids():
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", ROOT / "data/mock_tax_lots.csv", ROOT / "data/mock_account_menus.csv")
    run = lambda: generate_recommendations(result.holdings, result.tax_lots, result.account_menus, MASTER, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))["recommendations"]
    ids_a = [r.recommendation_id for r in run()]
    ids_b = [r.recommendation_id for r in run()]
    assert ids_a == ids_b
    assert len(ids_a) == len(set(ids_a))  # no duplicates


# 12. The report renders even without optional engine outputs.
def test_report_renders_minimal(tmp_path):
    from data.schemas import Recommendation
    rec = Recommendation(
        recommendation_id="abc123", action="hold", ticker="portfolio", account_id=None,
        target_weight=None, current_weight=None, trade_amount=None,
        rationale=["No action is justified."], risks=[], tax_notes=["n/a"],
        confidence="high", urgency="low", thesis_key="no-action",
    )
    analysis = {
        "drift_report": {},
        "concentration": {"single_name_flags": [], "sector_flags": []},
        "current_allocation": {},
        "target_allocation": {},
    }
    log = build_process_log([rec], 0.0, True, True, True, "2026-06-01")
    report = render_report(analysis, [rec], log, 0.0, tmp_path / "r.md")
    assert "No action is justified." in report
    assert "PORTFOLIO GRADE" in report
