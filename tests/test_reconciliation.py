from collections import Counter
from datetime import date
from pathlib import Path

from core.recommendation_engine import generate_recommendations
from data.loaders import CsvDataProvider, load_security_master_csv
from data.schemas import TaxProfile

ROOT = Path(__file__).resolve().parents[1]
TAX_PROFILE = TaxProfile("mfj", 0.32, 0.15, False, 0.05, 0.15, 5000)
THRESHOLDS = {"single_name_threshold": 0.15, "sector_threshold": 0.35, "drift_threshold": 0.05, "high_fee_threshold": 0.0040, "harvest_loss_threshold": -500.0}
TARGET = {"us_equity": 0.5, "international_equity": 0.2, "taxable_bond": 0.25, "cash": 0.05}


def _mock_recs():
    result = CsvDataProvider().load(ROOT / "data/mock_holdings.csv", ROOT / "data/mock_tax_lots.csv", ROOT / "data/mock_account_menus.csv")
    master = load_security_master_csv(ROOT / "data/security_master.csv")
    analysis = generate_recommendations(result.holdings, result.tax_lots, result.account_menus, master, THRESHOLDS, TAX_PROFILE, TARGET, date(2026, 6, 1))
    return analysis["recommendations"]


def test_one_directional_action_per_position():
    recs = _mock_recs()
    directional = Counter(
        (r.ticker, r.account_id)
        for r in recs
        if r.account_id is not None and r.action != "hold"
    )
    assert all(count == 1 for count in directional.values()), directional


def test_no_hold_and_sell_same_lot():
    recs = _mock_recs()
    by_position: dict[tuple[str, str], set[str]] = {}
    for r in recs:
        if r.account_id is None:
            continue
        by_position.setdefault((r.ticker, r.account_id), set()).add(r.action)
    sell_actions = {"trim", "replace", "tax_loss_harvest"}
    for actions in by_position.values():
        assert not ("hold" in actions and actions & sell_actions)


def test_no_duplicate_do_nothing():
    recs = _mock_recs()
    aapl = [r for r in recs if r.ticker == "AAPL" and r.account_id == "TAX-1"]
    assert sum(1 for r in aapl if r.action == "do_nothing_due_to_tax_cost") <= 1


def test_supersede_note_present():
    # BND in the taxable account accrues relocate + trim + harvest across stages; the survivor
    # (highest priority = relocate) must disclose that it superseded lower-priority actions.
    recs = _mock_recs()
    bnd = next(r for r in recs if r.ticker == "BND" and r.account_id == "TAX-1")
    assert bnd.action == "relocate"
    assert any("Supersedes a lower-priority" in note for note in bnd.rationale)
