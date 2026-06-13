from datetime import date
from pathlib import Path

from core.recommendation_engine import generate_recommendations
from data.loaders import load_security_master_csv
from data.schemas import AccountMenu, Holding, Recommendation, SecurityMetadata, TaxLot, TaxProfile
from reporting.process_log import build_process_log
from reporting.report_generator import render_report

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {"single_name_threshold": 0.15, "sector_threshold": 0.35, "drift_threshold": 0.05, "high_fee_threshold": 0.0040, "harvest_loss_threshold": -500.0}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}


def _sector_concentrated_analysis():
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    tech_template = master["AAPL"]
    master["TECHX"] = SecurityMetadata(
        ticker="TECHX",
        security_name="Tech X",
        security_type="stock",
        issuer="TechX",
        asset_class=tech_template.asset_class,
        sub_asset_class=tech_template.sub_asset_class,
        region=tech_template.region,
        style=tech_template.style,
        sector_focus=tech_template.sector_focus,
        index_family="TECHX_SINGLE",
        expense_ratio=None,
        distribution_yield=0.0,
        aum_usd=1_000_000.0,
        avg_daily_dollar_volume=1_000_000.0,
        tax_efficiency_bucket="medium",
        primary_benchmark="Custom Tech Benchmark",
        source_note="test",
        as_of_date="2026-06-01",
    )
    master["TECHY"] = SecurityMetadata(
        ticker="TECHY",
        security_name="Tech Y",
        security_type="stock",
        issuer="TechY",
        asset_class=tech_template.asset_class,
        sub_asset_class=tech_template.sub_asset_class,
        region=tech_template.region,
        style=tech_template.style,
        sector_focus=tech_template.sector_focus,
        index_family="TECHY_SINGLE",
        expense_ratio=None,
        distribution_yield=0.0,
        aum_usd=1_000_000.0,
        avg_daily_dollar_volume=1_000_000.0,
        tax_efficiency_bucket="medium",
        primary_benchmark="Custom Tech Benchmark",
        source_note="test",
        as_of_date="2026-06-01",
    )
    holdings = [
        Holding("TAX-1", "Taxable", "taxable", "AAPL", "stock", 50, 10000, None, 0.0),
        Holding("TAX-2", "Taxable 2", "taxable", "TECHX", "stock", 50, 10000, None, 0.0),
        Holding("TAX-3", "Taxable 3", "taxable", "TECHY", "stock", 50, 10000, None, 0.0),
        Holding("IRA-1", "IRA", "traditional_ira", "VXUS", "etf", 100, 20000, 0.0007, 0.028),
        Holding("IRA-1", "IRA", "traditional_ira", "BND", "etf", 100, 20000, 0.0003, 0.031),
        Holding("TAX-1", "Taxable", "taxable", "CASH", "cash", 1, 5000, None, 0.0),
        Holding("ROTH-1", "Roth", "roth_ira", "CASH", "cash", 1, 5000, None, 0.0),
    ]
    lots = [
        TaxLot("TAX-1", "AAPL", 50, 150, date(2024, 1, 1), 882, True, 2500.0),
        TaxLot("TAX-2", "TECHX", 50, 150, date(2024, 1, 1), 882, True, 2500.0),
        TaxLot("TAX-3", "TECHY", 50, 150, date(2024, 1, 1), 882, True, 2500.0),
    ]
    menus = [
        AccountMenu("TAX-1", "open", None),
        AccountMenu("TAX-2", "open", None),
        AccountMenu("TAX-3", "open", None),
        AccountMenu("IRA-1", "open", None),
        AccountMenu("ROTH-1", "open", None),
    ]
    return generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))


def test_empty_holdings_do_not_generate_normal_action_plan(tmp_path: Path):
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    analysis = generate_recommendations([], [], [], master, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    report = render_report(analysis, analysis["recommendations"], [], 0.0, tmp_path / "empty.md")
    assert analysis["recommendations"][0].rationale == ["No holdings loaded; analysis aborted."]
    assert "Do these" not in report
    assert "No holdings loaded" in report


def test_sector_concentration_cannot_fall_through_to_no_action():
    analysis = _sector_concentrated_analysis()
    recommendations = analysis["recommendations"]
    assert analysis["concentration"]["sector_flags"]
    assert not (len(recommendations) == 1 and recommendations[0].rationale == ["No action is justified."])


def test_process_log_flags_derive_from_analysis_state():
    analysis = _sector_concentrated_analysis()
    process_log = build_process_log(analysis["recommendations"], analysis, 12.0, "2026-06-01")
    assert process_log
    assert all(entry.concentration_within_limits is False for entry in process_log)


def test_report_actionable_count_excludes_non_actions(tmp_path: Path):
    recommendations = [
        Recommendation("r1", "hold", "VTI", "TAX-1", None, None, None, ["Observe only."], [], ["None"], "high", "low"),
        Recommendation("r2", "do_nothing_due_to_tax_cost", "AAPL", "TAX-1", None, None, None, ["Too expensive to trim."], [], ["Estimated tax cost is high."], "high", "medium"),
        Recommendation("r3", "trim", "VXUS", "TAX-1", None, 0.25, 1000.0, ["Concentration reduction."], [], ["Tax reviewed."], "high", "high"),
    ]
    analysis = {
        "drift_report": {
            "us_equity": {"current_weight": 0.5, "target_weight": 0.5, "difference": 0.0},
            "international_equity": {"current_weight": 0.2, "target_weight": 0.2, "difference": 0.0},
        },
        "concentration": {"single_name_flags": [], "sector_flags": [], "account_concentration": {}},
    }
    process_log = build_process_log(recommendations, analysis, 10.0, "2026-06-01")
    report = render_report(analysis, recommendations, process_log, 10.0, tmp_path / "report.md")
    assert "Do these 1 things now." in report
