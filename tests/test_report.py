from datetime import date
from pathlib import Path

from core.recommendation_engine import generate_recommendations
from data.loaders import CsvDataProvider, load_security_master_csv
from data.schemas import TaxProfile
from reporting.process_log import build_process_log
from reporting.report_generator import render_report

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {"single_name_threshold": 0.15, "sector_threshold": 0.35, "drift_threshold": 0.05, "high_fee_threshold": 0.0040, "harvest_loss_threshold": -500.0}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}


def test_report_and_process_log(tmp_path: Path):
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", ROOT / "data/mock_tax_lots.csv", ROOT / "data/mock_account_menus.csv")
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    analysis = generate_recommendations(result.holdings, result.tax_lots, result.account_menus, master, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    recommendations = analysis["recommendations"]
    process_log = build_process_log(recommendations, analysis, 24.0, "2026-06-01")
    report = render_report(analysis, recommendations, process_log, 24.0, tmp_path / "report.md")
    assert "PORTFOLIO GRADE" in report
    assert "Analysis, not financial advice." in report
    assert all(item.rationale for item in recommendations)
    assert all(item.tax_notes for item in recommendations if item.action in {"do_nothing_due_to_tax_cost", "tax_loss_harvest", "replace", "trim", "relocate"})
