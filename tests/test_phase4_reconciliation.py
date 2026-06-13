from datetime import date
from pathlib import Path

from core.recommendation_engine import generate_recommendations
from core.wash_sale_guard import WashSaleGuard
from data.loaders import CsvDataProvider, load_security_master_csv
from data.schemas import Recommendation, TaxLot, TaxProfile
from reporting.process_log import build_process_log
from reporting.report_generator import render_report

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {"single_name_threshold": 0.15, "sector_threshold": 0.35, "drift_threshold": 0.05, "high_fee_threshold": 0.0040, "harvest_loss_threshold": -500.0}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}


def test_retirement_account_wash_sale_detected_without_account_id_substring():
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    guard = WashSaleGuard(master)
    lots = [
        TaxLot("ACCT-1", "VTI", 10, 200.0, date(2026, 5, 20), 12, False, 100.0, "roth_ira"),
    ]
    blocked = guard.check_harvest("VTI", date(2026, 6, 1), lots, ["ITOT"])
    assert blocked.status == "wash_sale_blocked_retirement_account_purchase"


def test_same_holding_cannot_emit_multiple_executable_actions():
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", ROOT / "data/mock_tax_lots.csv", ROOT / "data/mock_account_menus.csv")
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    analysis = generate_recommendations(result.holdings, result.tax_lots, result.account_menus, master, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    executable_actions = {"trim", "replace", "relocate", "rebalance", "add", "tax_loss_harvest"}
    by_holding: dict[tuple[str | None, str], list[str]] = {}
    for rec in analysis["recommendations"]:
        if rec.action not in executable_actions or rec.account_id is None:
            continue
        by_holding.setdefault((rec.account_id, rec.ticker), []).append(rec.action)
    assert all(len(actions) <= 1 for actions in by_holding.values())


def test_report_renders_executable_blocked_and_observation_sections(tmp_path: Path):
    recommendations = [
        Recommendation("exec-1", "trim", "BND", "TAX-1", None, 0.30, 5000.0, ["Reduce concentration."], [], ["Tax reviewed."], "high", "high"),
        Recommendation("blocked-1", "do_nothing_due_to_tax_cost", "AAPL", "TAX-1", None, 0.20, None, ["Sale blocked by tax cost."], [], ["Estimated tax cost too high."], "high", "medium"),
        Recommendation("obs-1", "hold", "FXNAX", "IRA-1", None, None, None, ["Menu blocks replacement."], [], ["Observation only."], "medium", "low"),
    ]
    analysis = {
        "drift_report": {"taxable_bond": {"current_weight": 0.30, "target_weight": 0.25, "difference": 0.05}},
        "concentration": {"single_name_flags": [], "sector_flags": [], "account_concentration": {}},
    }
    process_log = build_process_log(recommendations, analysis, 12.0, "2026-06-01")
    report = render_report(analysis, recommendations, process_log, 12.0, tmp_path / "report.md")
    assert "EXECUTABLE ACTIONS" in report
    assert "BLOCKED ACTIONS" in report
    assert "OBSERVATIONS" in report
