"""
Contrarian Verification Suite — Wave 3 remediation check.

Each test is named after the attack vector it probes (a)-(g).
A test PASSES iff the system BLOCKED the constraint violation.
A test FAILS iff the constraint was VIOLATED (i.e. the system misbehaved).

All tests are network-free and deterministic.
"""
from __future__ import annotations

import inspect
from datetime import date
from typing import cast

import pytest

from core.recommendation_engine import generate_recommendations
from data.schemas import (
    AccountMenu,
    Holding,
    Recommendation,
    SecurityMetadata,
    TaxLot,
    TaxProfile,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

TAX_PROFILE = TaxProfile(
    filing_status="mfj",
    federal_marginal_rate=0.32,
    ltcg_rate=0.15,
    niit_applies=False,
    state_rate=0.05,
    qualified_dividend_rate=0.15,
    confirm_with_cpa_above=5_000.0,
)
THRESHOLDS = {
    "single_name_threshold": 0.15,
    "sector_threshold": 0.35,
    "drift_threshold": 0.05,
    "high_fee_threshold": 0.0040,
    "harvest_loss_threshold": -500.0,
}
TARGET = {
    "us_equity": 0.50,
    "international_equity": 0.20,
    "taxable_bond": 0.25,
    "cash": 0.05,
}
AS_OF = date(2026, 6, 1)


def _meta(
    ticker: str,
    asset_class: str = "us_equity",
    index_family: str = "GENERIC_IDX",
    expense: float = 0.0003,
    volume: float = 1e8,
    style: str = "broad_market",
    region: str = "us",
    sector: str = "none",
    tax_bucket: str = "high",
) -> SecurityMetadata:
    return SecurityMetadata(
        ticker=ticker,
        security_name=ticker,
        security_type="etf",
        issuer="test",
        asset_class=asset_class,
        sub_asset_class="broad_market",
        region=region,
        style=style,
        sector_focus=sector,
        index_family=index_family,
        expense_ratio=expense,
        distribution_yield=0.0,
        aum_usd=1e10,
        avg_daily_dollar_volume=volume,
        tax_efficiency_bucket=tax_bucket,
        primary_benchmark="test",
        source_note="test",
        as_of_date="2026-06-01",
    )


def _cash(ticker: str = "CASH") -> SecurityMetadata:
    return SecurityMetadata(
        ticker=ticker,
        security_name=ticker,
        security_type="cash",
        issuer="cash",
        asset_class="cash",
        sub_asset_class="cash",
        region="n/a",
        style="cash",
        sector_focus="none",
        index_family="CASH",
        expense_ratio=None,
        distribution_yield=None,
        aum_usd=None,
        avg_daily_dollar_volume=None,
        tax_efficiency_bucket="high",
        primary_benchmark="None",
        source_note="test",
        as_of_date="2026-06-01",
    )


def _run(
    holdings: list[Holding],
    lots: list[TaxLot],
    menus: list[AccountMenu],
    master: dict[str, SecurityMetadata],
) -> list[Recommendation]:
    result = generate_recommendations(
        holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF
    )
    return cast(list[Recommendation], result["recommendations"])


# ---------------------------------------------------------------------------
# (a) Taxable sale without a tax estimate or "tax impact unknown" flag
# ---------------------------------------------------------------------------

TAXABLE_SALE_ACTIONS = {"trim", "replace", "tax_loss_harvest"}


class TestAttackA_TaxableSaleNoTaxNote:
    """
    Attack: engineer a portfolio where the engine emits a trim / replace /
    tax_loss_harvest in a taxable account but the tax_notes list contains
    neither an "Estimated tax cost" figure nor a "tax impact unknown" note.

    We try three distinct triggers:
      A1 — concentration trim (VTI alone over the 15% threshold)
      A2 — overlap replace (two same-index-family ETFs in taxable)
      A3 — fee replace (high-fee ETF in taxable with small gain so not blocked)
    """

    def _assert_no_untagged_taxable_sale(
        self, recs: list[Recommendation], account_id: str
    ) -> None:
        for rec in recs:
            if rec.account_id != account_id:
                continue
            if rec.action not in TAXABLE_SALE_ACTIONS:
                continue
            has_tag = any(
                "Estimated tax cost" in note or "tax impact unknown" in note.lower()
                for note in rec.tax_notes
            )
            assert has_tag, (
                f"VIOLATED (a): action={rec.action} ticker={rec.ticker} "
                f"account_id={rec.account_id} has no tax note. "
                f"tax_notes={rec.tax_notes}"
            )

    def test_a1_concentration_trim_carries_tax_estimate(self):
        """VTI at 80% of a taxable account triggers a trim; it must carry a tax note."""
        master = {
            "VTI": _meta("VTI", index_family="CRSP_US_TOTAL"),
            "CASH": _cash(),
        }
        holdings = [
            Holding("TAX", "Taxable", "taxable", "VTI", "etf", 400, 80_000.0, 0.0003, 0.013),
            Holding("TAX", "Taxable", "taxable", "CASH", "cash", 1, 20_000.0),
        ]
        lots = [
            # Small gain -> not blocked, so a real trim should come out
            TaxLot("TAX", "VTI", 400, 190.0, date(2023, 1, 1), 1200, True, 4_000.0),
        ]
        menus = [AccountMenu("TAX", "open", None)]
        recs = _run(holdings, lots, menus, master)
        self._assert_no_untagged_taxable_sale(recs, "TAX")
        # Verify a trim (or do_nothing) exists — confirms we actually hit the code path
        assert any(r.ticker == "VTI" for r in recs), "Expected some VTI recommendation"

    def test_a2_overlap_replace_in_taxable_carries_tax_note(self):
        """Two same-index-family ETFs in taxable; replace must carry a tax note."""
        master = {
            "AAAA": _meta("AAAA", index_family="SHARED_IDX", expense=0.0003, volume=5e8),
            "BBBB": _meta("BBBB", index_family="SHARED_IDX", expense=0.0003, volume=5e8),
            "CASH": _cash(),
        }
        holdings = [
            Holding("TAX", "Taxable", "taxable", "AAAA", "etf", 100, 40_000.0, 0.0003, 0.0),
            Holding("TAX", "Taxable", "taxable", "BBBB", "etf", 100, 40_000.0, 0.0003, 0.0),
            Holding("TAX", "Taxable", "taxable", "CASH", "cash", 1, 20_000.0),
        ]
        # Small gain so replace is NOT blocked by tax cost
        lots = [
            TaxLot("TAX", "AAAA", 100, 390.0, date(2023, 1, 1), 1200, True, 1_000.0),
            TaxLot("TAX", "BBBB", 100, 390.0, date(2023, 1, 1), 1200, True, 1_000.0),
        ]
        menus = [AccountMenu("TAX", "open", None)]
        recs = _run(holdings, lots, menus, master)
        self._assert_no_untagged_taxable_sale(recs, "TAX")

    def test_a3_fee_replace_in_taxable_carries_tax_note(self):
        """High-fee ETF in taxable with tiny gain; fee-replace must carry a tax note."""
        master = {
            "HIFEEA": _meta("HIFEEA", index_family="IDX_A", expense=0.0075, volume=5e7),
            "LOFEEB": _meta("LOFEEB", index_family="IDX_B", expense=0.0003, volume=5e8),
            "CASH": _cash(),
        }
        holdings = [
            Holding("TAX", "Taxable", "taxable", "HIFEEA", "etf", 100, 50_000.0, 0.0075, 0.0),
            Holding("TAX", "Taxable", "taxable", "CASH", "cash", 1, 50_000.0),
        ]
        # Small gain -> fee-replace is NOT blocked
        lots = [
            TaxLot("TAX", "HIFEEA", 100, 490.0, date(2023, 1, 1), 1200, True, 1_000.0),
        ]
        menus = [AccountMenu("TAX", "open", None)]
        recs = _run(holdings, lots, menus, master)
        self._assert_no_untagged_taxable_sale(recs, "TAX")

    def test_a4_taxable_sale_missing_lots_yields_unknown_not_confident(self):
        """No lots provided for a taxable concentration trim.
        The engine must emit 'tax impact unknown', never a confident sell without note."""
        master = {
            "VTI": _meta("VTI", index_family="CRSP_US_TOTAL"),
            "CASH": _cash(),
        }
        holdings = [
            Holding("TAX", "Taxable", "taxable", "VTI", "etf", 400, 80_000.0, 0.0003, 0.013),
            Holding("TAX", "Taxable", "taxable", "CASH", "cash", 1, 20_000.0),
        ]
        lots: list[TaxLot] = []  # <-- adversarial: no lots at all
        menus = [AccountMenu("TAX", "open", None)]
        recs = _run(holdings, lots, menus, master)
        self._assert_no_untagged_taxable_sale(recs, "TAX")


# ---------------------------------------------------------------------------
# (b) Wash-sale violation
# ---------------------------------------------------------------------------


class TestAttackB_WashSaleViolation:
    """
    Attack: construct portfolios where a tax_loss_harvest is emitted even
    though a same-ticker purchase exists within the 61-day window.

    B1 — Same-ticker buy inside a Roth IRA within 30 days before the sale
    B2 — Same-ticker buy inside a Traditional IRA within 30 days after sale
    B3 — Same-ticker buy in a *different* taxable account within window
    B4 — Buy on the exact boundary day (day 30 inclusive = still inside window)
    B5 — Same-index-family (not same-ticker) candidate: gray-zone, no harvest
    """

    def test_b1_roth_ira_buy_blocks_harvest(self):
        """Buy VTI in a Roth IRA 12 days before AS_OF — harvest must be blocked."""
        master = {
            "VTI": _meta("VTI", index_family="CRSP_US_TOTAL"),
            "ITOT": _meta("ITOT", index_family="S&P_TOTAL_US", style="broad_market"),
            "CASH": _cash(),
        }
        holdings = [
            Holding("TAX", "Taxable", "taxable", "VTI", "etf", 100, 10_000.0, 0.0003, 0.013),
            Holding("ROTH", "Roth IRA", "roth_ira", "CASH", "cash", 1, 90_000.0),
        ]
        lots = [
            TaxLot("TAX", "VTI", 100, 150.0, date(2025, 1, 1), 516, True, -5_000.0),
            # Adversarial: VTI bought in Roth IRA 12 days ago (inside 30-day window)
            TaxLot("ROTH", "VTI", 50, 100.0, date(2026, 6, 1) - __import__('datetime').timedelta(days=12), 12, False, 0.0),
        ]
        menus = [AccountMenu("TAX", "open", None), AccountMenu("ROTH", "open", None)]
        recs = _run(holdings, lots, menus, master)
        harvest_exists = any(r.action == "tax_loss_harvest" and r.ticker == "VTI" for r in recs)
        assert not harvest_exists, (
            "VIOLATED (b): wash-sale not blocked by Roth IRA same-ticker purchase within window."
        )

    def test_b2_traditional_ira_buy_after_sale_blocks_harvest(self):
        """Adversarial: the IRA acquired-date is 15 days AFTER AS_OF (within +30-day window).
        The WashSaleGuard checks window_start <= acquired_date <= window_end where
        window_end = AS_OF + 30 days, so this should be caught."""
        from datetime import timedelta
        master = {
            "VTI": _meta("VTI", index_family="CRSP_US_TOTAL"),
            "ITOT": _meta("ITOT", index_family="S&P_TOTAL_US"),
            "CASH": _cash(),
        }
        holdings = [
            Holding("TAX", "Taxable", "taxable", "VTI", "etf", 100, 10_000.0, 0.0003, 0.013),
            Holding("IRA", "Trad IRA", "traditional_ira", "CASH", "cash", 1, 90_000.0),
        ]
        lots = [
            TaxLot("TAX", "VTI", 100, 150.0, date(2025, 1, 1), 516, True, -5_000.0),
            # Future buy inside the +30-day window (the check is: within 30 days of AS_OF)
            TaxLot("IRA", "VTI", 20, 100.0, AS_OF + timedelta(days=15), 0, False, 0.0),
        ]
        menus = [AccountMenu("TAX", "open", None), AccountMenu("IRA", "open", None)]
        recs = _run(holdings, lots, menus, master)
        harvest_exists = any(r.action == "tax_loss_harvest" and r.ticker == "VTI" for r in recs)
        assert not harvest_exists, (
            "VIOLATED (b): wash-sale not blocked by Traditional IRA same-ticker buy after sale date."
        )

    def test_b3_different_taxable_account_buy_blocks_harvest(self):
        """VTI loss in TAX-1; VTI bought in TAX-2 (also taxable) 5 days ago."""
        from datetime import timedelta
        master = {
            "VTI": _meta("VTI", index_family="CRSP_US_TOTAL"),
            "ITOT": _meta("ITOT", index_family="S&P_TOTAL_US"),
            "CASH": _cash(),
        }
        holdings = [
            Holding("TAX-1", "Taxable 1", "taxable", "VTI", "etf", 100, 10_000.0, 0.0003, 0.013),
            Holding("TAX-2", "Taxable 2", "taxable", "CASH", "cash", 1, 90_000.0),
        ]
        lots = [
            TaxLot("TAX-1", "VTI", 100, 150.0, date(2025, 1, 1), 516, True, -5_000.0),
            # Adversarial: same ticker bought in TAX-2 recently
            TaxLot("TAX-2", "VTI", 10, 100.0, AS_OF - timedelta(days=5), 5, False, 0.0),
        ]
        menus = [AccountMenu("TAX-1", "open", None), AccountMenu("TAX-2", "open", None)]
        recs = _run(holdings, lots, menus, master)
        harvest_exists = any(r.action == "tax_loss_harvest" and r.ticker == "VTI" for r in recs)
        assert not harvest_exists, (
            "VIOLATED (b): wash-sale not blocked by same-ticker buy in a second taxable account."
        )

    def test_b4_boundary_day_30_buy_blocks_harvest(self):
        """Buy on exactly day 30 before AS_OF: window_start = AS_OF - 30 days.
        This is the boundary: acquired_date == window_start => inside window => blocked."""
        from datetime import timedelta
        master = {
            "VTI": _meta("VTI", index_family="CRSP_US_TOTAL"),
            "ITOT": _meta("ITOT", index_family="S&P_TOTAL_US"),
            "CASH": _cash(),
        }
        holdings = [
            Holding("TAX", "Taxable", "taxable", "VTI", "etf", 100, 10_000.0, 0.0003, 0.013),
            Holding("IRA", "IRA", "traditional_ira", "CASH", "cash", 1, 90_000.0),
        ]
        boundary_date = AS_OF - timedelta(days=30)
        lots = [
            TaxLot("TAX", "VTI", 100, 150.0, date(2025, 1, 1), 516, True, -5_000.0),
            # Exactly on the boundary (inclusive)
            TaxLot("IRA", "VTI", 5, 100.0, boundary_date, 30, False, 0.0),
        ]
        menus = [AccountMenu("TAX", "open", None), AccountMenu("IRA", "open", None)]
        recs = _run(holdings, lots, menus, master)
        harvest_exists = any(r.action == "tax_loss_harvest" and r.ticker == "VTI" for r in recs)
        assert not harvest_exists, (
            f"VIOLATED (b): wash-sale not blocked at boundary day (acquired={boundary_date})."
        )

    def test_b5_same_index_family_candidate_blocks_harvest_gray_zone(self):
        """All replacement candidates share the same index family as the sold ticker.
        This is the 'substantially identical' gray zone — harvest must NOT proceed."""
        master = {
            "LOSSY": _meta("LOSSY", index_family="SAME_IDX"),
            "CLONE1": _meta("CLONE1", index_family="SAME_IDX"),
            "CLONE2": _meta("CLONE2", index_family="SAME_IDX"),
            "CASH": _cash(),
        }
        holdings = [
            Holding("TAX", "Taxable", "taxable", "LOSSY", "etf", 100, 10_000.0, 0.001, 0.0),
            Holding("IRA", "IRA", "traditional_ira", "CASH", "cash", 1, 90_000.0),
        ]
        lots = [
            TaxLot("TAX", "LOSSY", 100, 150.0, date(2025, 1, 1), 516, True, -5_000.0),
        ]
        menus = [AccountMenu("TAX", "open", None), AccountMenu("IRA", "open", None)]
        recs = _run(holdings, lots, menus, master)
        harvest_exists = any(r.action == "tax_loss_harvest" and r.ticker == "LOSSY" for r in recs)
        assert not harvest_exists, (
            "VIOLATED (b): wash-sale gray-zone not blocked (all candidates share same index family)."
        )


# ---------------------------------------------------------------------------
# (c) Macro / LLM influence over recommendations
# ---------------------------------------------------------------------------


class TestAttackC_MacroLLMInfluence:
    """
    Attack: verify the engine signature has no pathway for macro data, LLM
    commentary, news, or any external context that could alter a recommendation.

    C1 — Inspect the function signature of generate_recommendations
    C2 — Inspect the module-level imports for any LLM / HTTP / macro library
    C3 — Call the engine with a monkey-patched "macro_context" kwarg and confirm
         it is rejected (TypeError), proving the argument is not accepted.
    C4 — Verify that calling the engine twice with identical inputs produces
         bit-identical outputs (no randomness / external state).
    """

    def test_c1_generate_recommendations_signature_has_no_macro_or_llm_param(self):
        """The public API must not accept macro_context, llm_output, news, etc."""
        sig = inspect.signature(generate_recommendations)
        forbidden_keywords = {
            "macro_context", "llm_output", "llm", "news", "commentary",
            "macro", "regime", "sentiment", "forecast", "openai", "anthropic",
        }
        param_names = {name.lower() for name in sig.parameters}
        violating = param_names & forbidden_keywords
        assert not violating, (
            f"VIOLATED (c): generate_recommendations accepts macro/LLM params: {violating}"
        )

    def test_c2_recommendation_engine_module_has_no_llm_or_http_imports(self):
        """The recommendation_engine module must not import any LLM or HTTP library."""
        import ast
        from pathlib import Path
        src = Path(__file__).resolve().parents[1] / "core" / "recommendation_engine.py"
        tree = ast.parse(src.read_text())
        forbidden = {
            "openai", "anthropic", "requests", "httpx", "aiohttp", "urllib",
            "transformers", "langchain", "llama", "ollama", "groq", "cohere",
            "boto3", "litellm", "tiktoken",
        }
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [
                    (node.module or "").split(".")[0]
                    if isinstance(node, ast.ImportFrom)
                    else alias.name.split(".")[0]
                    for alias in (node.names if isinstance(node, ast.Import) else [])
                ]
                if isinstance(node, ast.ImportFrom):
                    names = [(node.module or "").split(".")[0]]
                for name in names:
                    assert name.lower() not in forbidden, (
                        f"VIOLATED (c): recommendation_engine imports forbidden library '{name}'."
                    )

    def test_c3_extra_kwarg_raises_type_error(self):
        """Passing macro_context as a keyword argument must raise TypeError."""
        master = {"CASH": _cash()}
        holdings = [Holding("TAX", "Taxable", "taxable", "CASH", "cash", 1, 100_000.0)]
        lots: list[TaxLot] = []
        menus = [AccountMenu("TAX", "open", None)]
        with pytest.raises(TypeError):
            generate_recommendations(  # type: ignore[call-arg]
                holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF,
                macro_context={"rate_regime": "hiking"},
            )

    def test_c4_deterministic_output_no_hidden_state(self):
        """Same inputs → identical outputs on two consecutive calls."""
        master = {
            "VTI": _meta("VTI", index_family="CRSP_US_TOTAL"),
            "BND": _meta("BND", asset_class="taxable_bond", index_family="BLOOMBERG_US_AGG",
                         style="aggregate_bond", tax_bucket="low"),
            "CASH": _cash(),
        }
        holdings = [
            Holding("TAX", "Taxable", "taxable", "VTI", "etf", 100, 50_000.0, 0.0003, 0.013),
            Holding("IRA", "IRA", "traditional_ira", "BND", "etf", 100, 40_000.0, 0.0003, 0.031),
            Holding("TAX", "Taxable", "taxable", "CASH", "cash", 1, 10_000.0),
        ]
        lots = [
            TaxLot("TAX", "VTI", 100, 490.0, date(2023, 1, 1), 1200, True, 1_000.0),
            TaxLot("IRA", "BND", 100, 390.0, date(2023, 1, 1), 1200, True, 1_000.0),
        ]
        menus = [AccountMenu("TAX", "open", None), AccountMenu("IRA", "open", None)]

        result1 = generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF)
        result2 = generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF)
        ids1 = [r.recommendation_id for r in result1["recommendations"]]
        ids2 = [r.recommendation_id for r in result2["recommendations"]]
        assert ids1 == ids2, (
            f"VIOLATED (c): non-deterministic output. Run1={ids1} Run2={ids2}"
        )


# ---------------------------------------------------------------------------
# (d) Instrument outside destination account menu
# ---------------------------------------------------------------------------


class TestAttackD_MenuViolation:
    """
    Attack: engineer scenarios where the engine might recommend a replacement
    instrument that the destination account's menu does not allow.

    D1 — Fee-replace: HIFEE -> LOWFEE but LOWFEE is not in the menu
    D2 — Harvest: candidate replacement is not in the harvest account's menu
    D3 — Overlap replace: replacement not in menu
    D4 — Multi-ticker menu: ensure *none* of the surviving recs name an
         out-of-menu replacement for any menu-restricted account.
    """

    def _check_no_menu_violation(
        self,
        recs: list[Recommendation],
        menu_map: dict[str, AccountMenu],
    ) -> None:
        for rec in recs:
            if rec.replacement_ticker is None:
                continue
            menu = menu_map.get(rec.account_id or "")
            if menu is None or menu.universe == "open":
                continue
            assert rec.replacement_ticker in (menu.allowed_instruments or []), (
                f"VIOLATED (d): {rec.action} on {rec.ticker} in {rec.account_id} "
                f"recommends replacement {rec.replacement_ticker} which is NOT in "
                f"allowed_instruments={menu.allowed_instruments}"
            )

    def test_d1_fee_replace_blocked_when_replacement_not_in_menu(self):
        """HIFEEA is in a menu account; best fee-replacement LOWB is not in the menu."""
        master = {
            "HIFEEA": _meta("HIFEEA", index_family="IDX_A", expense=0.0075, volume=5e7),
            "LOWB": _meta("LOWB", index_family="IDX_B", expense=0.0003, volume=5e8),
            "CASH": _cash(),
        }
        holdings = [
            Holding("IRA-MENU", "Menu IRA", "traditional_ira", "HIFEEA", "etf", 100, 50_000.0, 0.0075, 0.0),
            Holding("IRA-MENU", "Menu IRA", "traditional_ira", "CASH", "cash", 1, 50_000.0),
        ]
        lots = [
            TaxLot("IRA-MENU", "HIFEEA", 100, 490.0, date(2023, 1, 1), 1200, True, 1_000.0),
        ]
        menus = [AccountMenu("IRA-MENU", "menu", ["HIFEEA"])]  # LOWB deliberately absent
        recs = _run(holdings, lots, menus, master)
        menu_map = {"IRA-MENU": menus[0]}
        self._check_no_menu_violation(recs, menu_map)
        # Confirm no replace action with LOWB as replacement in IRA-MENU
        assert not any(
            r.account_id == "IRA-MENU" and r.replacement_ticker == "LOWB" for r in recs
        ), "VIOLATED (d): LOWB recommended as replacement but is not in IRA-MENU menu."

    def test_d2_harvest_replacement_blocked_when_not_in_menu(self):
        """Loss position in a menu account; best harvest replacement not in the menu."""
        master = {
            "LOSSY": _meta("LOSSY", index_family="LOSSY_IDX"),
            "SAFE_RPLC": _meta("SAFE_RPLC", index_family="OTHER_IDX"),
            "CASH": _cash(),
        }
        holdings = [
            Holding("IRA-MENU", "Menu IRA", "traditional_ira", "LOSSY", "etf", 100, 10_000.0, 0.001, 0.0),
            Holding("TAX", "Tax", "taxable", "CASH", "cash", 1, 90_000.0),
        ]
        lots = [
            TaxLot("IRA-MENU", "LOSSY", 100, 150.0, date(2025, 1, 1), 516, True, -5_000.0),
        ]
        menus = [
            AccountMenu("IRA-MENU", "menu", ["LOSSY"]),  # SAFE_RPLC not allowed
            AccountMenu("TAX", "open", None),
        ]
        recs = _run(holdings, lots, menus, master)
        menu_map = {"IRA-MENU": menus[0], "TAX": menus[1]}
        self._check_no_menu_violation(recs, menu_map)

    def test_d3_overlap_replace_blocked_when_replacement_not_in_menu(self):
        """Two same-index-family ETFs in a menu account; replacement (the first) not in menu."""
        master = {
            "AAAA": _meta("AAAA", index_family="SHARED_IDX", expense=0.0003, volume=5e8),
            "BBBB": _meta("BBBB", index_family="SHARED_IDX", expense=0.0003, volume=5e8),
            "CASH": _cash(),
        }
        holdings = [
            Holding("IRA-MENU", "Menu IRA", "traditional_ira", "AAAA", "etf", 100, 40_000.0, 0.0003, 0.0),
            Holding("IRA-MENU", "Menu IRA", "traditional_ira", "BBBB", "etf", 100, 40_000.0, 0.0003, 0.0),
            Holding("IRA-MENU", "Menu IRA", "traditional_ira", "CASH", "cash", 1, 20_000.0),
        ]
        lots = [
            TaxLot("IRA-MENU", "AAAA", 100, 390.0, date(2023, 1, 1), 1200, True, 1_000.0),
            TaxLot("IRA-MENU", "BBBB", 100, 390.0, date(2023, 1, 1), 1200, True, 1_000.0),
        ]
        # Only AAAA in menu, not BBBB (and not the other way round as replacement)
        menus = [AccountMenu("IRA-MENU", "menu", ["AAAA", "CASH"])]
        recs = _run(holdings, lots, menus, master)
        menu_map = {"IRA-MENU": menus[0]}
        self._check_no_menu_violation(recs, menu_map)

    def test_d4_exhaustive_menu_check_across_all_surviving_recs(self):
        """Mixed portfolio: menu IRA + open taxable. No surviving rec may name an
        out-of-menu replacement for the IRA."""
        master = {
            "AAAA": _meta("AAAA", index_family="IDX_A", expense=0.0075, volume=5e8),  # high fee
            "BBBB": _meta("BBBB", index_family="IDX_B", expense=0.0003, volume=5e8),  # low fee
            "CCCC": _meta("CCCC", index_family="IDX_C", expense=0.0003, volume=5e8),
            "CASH": _cash(),
        }
        holdings = [
            Holding("IRA-MENU", "Menu IRA", "traditional_ira", "AAAA", "etf", 100, 60_000.0, 0.0075, 0.0),
            Holding("TAX", "Taxable", "taxable", "CCCC", "etf", 100, 30_000.0, 0.0003, 0.0),
            Holding("TAX", "Taxable", "taxable", "CASH", "cash", 1, 10_000.0),
        ]
        lots = [
            TaxLot("IRA-MENU", "AAAA", 100, 590.0, date(2023, 1, 1), 1200, True, 1_000.0),
            TaxLot("TAX", "CCCC", 100, 290.0, date(2023, 1, 1), 1200, True, 1_000.0),
        ]
        menus = [
            AccountMenu("IRA-MENU", "menu", ["AAAA"]),  # BBBB deliberately absent
            AccountMenu("TAX", "open", None),
        ]
        recs = _run(holdings, lots, menus, master)
        menu_map = {"IRA-MENU": menus[0], "TAX": menus[1]}
        self._check_no_menu_violation(recs, menu_map)


# ---------------------------------------------------------------------------
# (e) Forced action when none is justified
# ---------------------------------------------------------------------------


class TestAttackE_ForcedAction:
    """
    Attack: a genuinely balanced, within-tolerance, no-loss, no-concentration,
    no-relocation-needed, no-redundancy portfolio must yield exactly one
    "No action is justified." hold recommendation.

    E1 — Portfolio perfectly matching the model (same asset classes, correct weights,
         low fees, open menus, all in preferred account locations)
    E2 — Minimal single-holding portfolio (only CASH): no trigger path fires
    E3 — Portfolio at exactly the threshold boundary (not over it)
    """

    def _base_balanced_master(self) -> dict[str, SecurityMetadata]:
        return {
            "VTI": _meta("VTI", index_family="CRSP_US_TOTAL", expense=0.0003, volume=9e8),
            "VXUS": _meta("VXUS", asset_class="international_equity", index_family="FTSE_GLOBAL_EX_US",
                          expense=0.0007, volume=2.5e8, region="developed_ex_us"),
            "BND": _meta("BND", asset_class="taxable_bond", index_family="BLOOMBERG_US_AGG",
                         style="aggregate_bond", tax_bucket="low", expense=0.0003, volume=1.8e8),
            "CASH": _cash(),
        }

    def test_e1_perfectly_balanced_portfolio_yields_no_action(self):
        """A portfolio structured so NO trigger fires at all — no concentration over 15%,
        no redundant pairs (different index families), no high fees, all assets in preferred
        account locations, no loss lots, drift within tolerance.

        This replicates the logic of test_no_action_balanced but uses a fully inline
        custom master to avoid any dependency on the CSV file, making the adversarial
        nature clear: every threshold guard is tested simultaneously.
        """
        # Design:
        # - US equity via two tickers each at ~7% of total: combined 14%, neither over 15%
        #   (VTI index CRSP_US_TOTAL, SCHB index DJ_US_BROAD — different index families)
        # - International equity via two tickers each at ~5%: combined 10%
        #   (VXUS index FTSE_GLOBAL_EX_US, VXUS2 index INTL_IDX2 — different families)
        # - Bond via one ticker at 13% (under 15%) in IRA (preferred location)
        # - Cash at 5%
        # - Drift: us_equity=14%, intl=10%, bond=13%, cash=5% vs target 50/20/25/5
        #   Wait - that's a very different allocation so drift fires.
        # Instead: match the target by spreading positions so no single name > 15%.
        # Target: us_equity=50%, intl=20%, bond=25%, cash=5%.
        # To avoid any single name > 15%:
        #   US equity: 4 tickers * ~12.5% each = 50%
        #   Intl equity: 2 tickers * 10% = 20%
        #   Bond: 2 tickers * 12.5% = 25%
        #   Cash: 1 ticker * 5%
        # All tickers: different index families (no redundant pairs), low fees, preferred locations.
        master = {
            "USA1": _meta("USA1", index_family="IDX_US1", expense=0.0003, volume=5e8),
            "USA2": _meta("USA2", index_family="IDX_US2", expense=0.0003, volume=5e8),
            "USA3": _meta("USA3", index_family="IDX_US3", expense=0.0003, volume=5e8),
            "USA4": _meta("USA4", index_family="IDX_US4", expense=0.0003, volume=5e8),
            "INT1": _meta("INT1", asset_class="international_equity", index_family="IDX_INT1",
                          region="developed_ex_us", expense=0.0005, volume=2e8),
            "INT2": _meta("INT2", asset_class="international_equity", index_family="IDX_INT2",
                          region="developed_ex_us", expense=0.0005, volume=2e8),
            "BND1": _meta("BND1", asset_class="taxable_bond", index_family="IDX_BND1",
                          style="aggregate_bond", tax_bucket="low", expense=0.0003, volume=2e8),
            "BND2": _meta("BND2", asset_class="taxable_bond", index_family="IDX_BND2",
                          style="intermediate_treasury", tax_bucket="low", expense=0.0003, volume=2e8),
            "CASH": _cash(),
        }
        total = 100_000.0
        per_us = total * 0.125  # 12.5% each, 4 tickers = 50%
        per_int = total * 0.10  # 10% each, 2 tickers = 20%
        per_bnd = total * 0.125  # 12.5% each, 2 tickers = 25%
        per_cash = total * 0.05
        holdings = [
            # US equity in taxable (preferred location for broad_market)
            Holding("TAX", "Taxable", "taxable", "USA1", "etf", 125, per_us, 0.0003, 0.0),
            Holding("TAX", "Taxable", "taxable", "USA2", "etf", 125, per_us, 0.0003, 0.0),
            Holding("TAX", "Taxable", "taxable", "USA3", "etf", 125, per_us, 0.0003, 0.0),
            Holding("TAX", "Taxable", "taxable", "USA4", "etf", 125, per_us, 0.0003, 0.0),
            # Intl equity in taxable (preferred)
            Holding("TAX", "Taxable", "taxable", "INT1", "etf", 100, per_int, 0.0005, 0.0),
            Holding("TAX", "Taxable", "taxable", "INT2", "etf", 100, per_int, 0.0005, 0.0),
            # Cash in taxable
            Holding("TAX", "Taxable", "taxable", "CASH", "cash", 1, per_cash),
            # Bonds in IRA (preferred for tax-inefficient)
            Holding("IRA", "IRA", "traditional_ira", "BND1", "etf", 125, per_bnd, 0.0003, 0.0),
            Holding("IRA", "IRA", "traditional_ira", "BND2", "etf", 125, per_bnd, 0.0003, 0.0),
        ]
        # All small gains, none triggering harvest_loss_threshold
        lots = [
            TaxLot("TAX", "USA1", 125, 99.0, date(2023, 1, 1), 1200, True, 125.0),
            TaxLot("TAX", "USA2", 125, 99.0, date(2023, 1, 1), 1200, True, 125.0),
            TaxLot("TAX", "USA3", 125, 99.0, date(2023, 1, 1), 1200, True, 125.0),
            TaxLot("TAX", "USA4", 125, 99.0, date(2023, 1, 1), 1200, True, 125.0),
            TaxLot("TAX", "INT1", 100, 99.0, date(2023, 1, 1), 1200, True, 100.0),
            TaxLot("TAX", "INT2", 100, 99.0, date(2023, 1, 1), 1200, True, 100.0),
            TaxLot("IRA", "BND1", 125, 99.0, date(2023, 1, 1), 1200, True, 125.0),
            TaxLot("IRA", "BND2", 125, 99.0, date(2023, 1, 1), 1200, True, 125.0),
        ]
        menus = [AccountMenu("TAX", "open", None), AccountMenu("IRA", "open", None)]
        recs = _run(holdings, lots, menus, master)
        assert len(recs) == 1, (
            f"VIOLATED (e): Expected exactly 1 'no action' rec, got {len(recs)}: "
            + str([(r.action, r.ticker) for r in recs])
        )
        assert recs[0].action == "hold", f"VIOLATED (e): Expected hold, got {recs[0].action}"
        assert "No action is justified." in recs[0].rationale, (
            f"VIOLATED (e): Expected 'No action is justified.' rationale, got {recs[0].rationale}"
        )

    def test_e2_portfolio_with_all_positions_under_threshold_yields_no_action(self):
        """
        Adversarial: a multi-holding portfolio where every individual metric is
        below every threshold simultaneously.

        Design: 7 US equity tickers each at ~14.3% of total (< 15% threshold),
        all different index families (no redundancy), all low fee, all in taxable
        (preferred for us_equity broad_market), no loss lots, target adjusted to
        match actual allocation (no drift). The only possible triggers are
        concentration and redundancy — both are verified absent.
        """
        master = {
            f"EQ{i}": _meta(f"EQ{i}", index_family=f"IDX_EQ{i}", expense=0.0003, volume=5e8)
            for i in range(7)
        }
        # 7 tickers * (100k/7) each ≈ 14.29% each — all under 15% threshold
        per = 100_000.0 / 7
        holdings = [
            Holding("TAX", "Taxable", "taxable", f"EQ{i}", "etf", 100, per, 0.0003, 0.0)
            for i in range(7)
        ]
        lots = [
            TaxLot("TAX", f"EQ{i}", 100, 99.0, date(2023, 1, 1), 1200, True, 100.0)
            for i in range(7)
        ]
        menus = [AccountMenu("TAX", "open", None)]
        # Target: 100% us_equity (matches actual allocation exactly -> no drift)
        all_equity_target = {"us_equity": 1.0}
        result = generate_recommendations(
            holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, all_equity_target, AS_OF
        )
        recs = cast(list[Recommendation], result["recommendations"])
        assert len(recs) == 1, (
            f"VIOLATED (e): Expected exactly 1 'no action' rec, got {len(recs)}: "
            + str([(r.action, r.ticker, r.current_weight) for r in recs])
        )
        assert "No action is justified." in recs[0].rationale, (
            f"VIOLATED (e): Expected 'No action is justified.' rationale, got {recs[0].rationale}"
        )

    def test_e3_portfolio_just_at_threshold_no_action(self):
        """
        Single name at exactly 15.0% (NOT above): no concentration flag should fire.
        Drift must also be within tolerance.
        """
        master = self._base_balanced_master()
        # VTI = exactly 15%, others fill the rest; drift set to match current allocation
        total = 100_000.0
        vti_val = total * 0.15
        vxus_val = total * 0.20
        bnd_val = total * 0.25
        cash_val = total * 0.05
        intl_extra = total - vti_val - vxus_val - bnd_val - cash_val
        # Put the remaining 35% in more VTI... no, that would push above 15%.
        # Instead: US equity split as VTI(15%) + extra US ETF(35%) but that needs another ticker.
        # Simplest: just have 15% VTI (exactly on threshold, not over), remainder in other classes.
        # Use a 4-asset portfolio that sums correctly and drifts stay within 5%.
        holdings = [
            Holding("TAX", "Taxable", "taxable", "VTI", "etf", 150, vti_val, 0.0003, 0.013),
            Holding("TAX", "Taxable", "taxable", "VXUS", "etf", 200, vxus_val, 0.0007, 0.028),
            Holding("TAX", "Taxable", "taxable", "CASH", "cash", 1, cash_val),
            Holding("IRA", "IRA", "traditional_ira", "BND", "etf", 250, bnd_val, 0.0003, 0.031),
            # Remaining 35% as VTI in IRA to make US equity reach 50% target
            Holding("IRA", "IRA", "traditional_ira", "VTI", "etf", 350, total * 0.35, 0.0003, 0.013),
        ]
        # Now VTI total = 15% (TAX) + 35% (IRA) = 50% -> over threshold!
        # Reframe: VTI must be exactly at threshold without any other VTI.
        # Target: us_equity=50% but we'll adjust target to match actual allocation.
        actual_target = {
            "us_equity": 0.50,
            "international_equity": 0.20,
            "taxable_bond": 0.25,
            "cash": 0.05,
        }
        # We need VTI to be 15% total and some other US equity to fill the rest.
        # This test verifies the threshold is strictly > not >=
        # If VTI == 15.0% exactly: threshold check is "weight > 0.15" -> False -> no flag.
        simple_master = {
            "VTI": _meta("VTI", index_family="CRSP_US_TOTAL"),
            "VXUS": _meta("VXUS", asset_class="international_equity", index_family="FTSE_GLOBAL_EX_US",
                          region="developed_ex_us", style="broad_market"),
            "BND": _meta("BND", asset_class="taxable_bond", index_family="BLOOMBERG_US_AGG",
                         style="aggregate_bond", tax_bucket="low"),
            "ITOT": _meta("ITOT", index_family="S&P_TOTAL_US"),  # different index family from VTI
            "CASH": _cash(),
        }
        # Portfolio: VTI=15%, ITOT=35%, VXUS=20%, BND=25%, CASH=5% -> exactly on target
        h2 = [
            Holding("TAX", "Taxable", "taxable", "VTI", "etf", 150, 15_000.0, 0.0003, 0.013),
            Holding("TAX", "Taxable", "taxable", "ITOT", "etf", 350, 35_000.0, 0.0003, 0.013),
            Holding("TAX", "Taxable", "taxable", "VXUS", "etf", 200, 20_000.0, 0.0007, 0.028),
            Holding("TAX", "Taxable", "taxable", "CASH", "cash", 1, 5_000.0),
            Holding("IRA", "IRA", "traditional_ira", "BND", "etf", 250, 25_000.0, 0.0003, 0.031),
        ]
        lots2 = [
            TaxLot("TAX", "VTI", 150, 99.0, date(2023, 1, 1), 1200, True, 150.0),
            TaxLot("TAX", "ITOT", 350, 99.0, date(2023, 1, 1), 1200, True, 350.0),
            TaxLot("TAX", "VXUS", 200, 99.0, date(2023, 1, 1), 1200, True, 200.0),
            TaxLot("IRA", "BND", 250, 99.0, date(2023, 1, 1), 1200, True, 250.0),
        ]
        menus2 = [AccountMenu("TAX", "open", None), AccountMenu("IRA", "open", None)]
        recs = _run(h2, lots2, menus2, simple_master)
        # VTI at exactly 15% must NOT be flagged
        assert not any(r.ticker == "VTI" and r.action == "trim" for r in recs), (
            "VIOLATED (e): VTI at exactly the threshold was flagged for concentration trim."
        )


# ---------------------------------------------------------------------------
# (f) account_type == "other" must not crash (C2)
# ---------------------------------------------------------------------------


class TestAttackF_OtherAccountNoCrash:
    """
    Attack: a portfolio containing an account_type=="other" holding must not raise
    any exception. The engine must return a valid recommendations dict.

    F1 — Single "other" account holding
    F2 — Mixed portfolio with "other" + taxable + IRA
    F3 — "other" account holding that would otherwise trigger concentration
    F4 — "other" account holding with a loss lot (harvest path)
    """

    def _master(self) -> dict[str, SecurityMetadata]:
        return {
            "VTI": _meta("VTI", index_family="CRSP_US_TOTAL"),
            "BND": _meta("BND", asset_class="taxable_bond", index_family="BLOOMBERG_US_AGG",
                         style="aggregate_bond", tax_bucket="low"),
            "CASH": _cash(),
        }

    def test_f1_single_other_account_does_not_crash(self):
        """A portfolio with only an 'other'-type account must not raise."""
        master = self._master()
        holdings = [Holding("OTHER-1", "Other Account", "other", "VTI", "etf", 100, 100_000.0, 0.0003, 0.013)]
        lots = [TaxLot("OTHER-1", "VTI", 100, 990.0, date(2023, 1, 1), 1200, True, 1_000.0)]
        menus = [AccountMenu("OTHER-1", "open", None)]
        # Must not raise
        result = generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF)
        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)

    def test_f2_mixed_portfolio_with_other_account_does_not_crash(self):
        """Mixed taxable + IRA + other: no crash, valid output."""
        master = self._master()
        holdings = [
            Holding("TAX", "Taxable", "taxable", "VTI", "etf", 100, 50_000.0, 0.0003, 0.013),
            Holding("IRA", "IRA", "traditional_ira", "BND", "etf", 100, 40_000.0, 0.0003, 0.031),
            Holding("OTHER", "Other", "other", "VTI", "etf", 10, 10_000.0, 0.0003, 0.013),
        ]
        lots = [
            TaxLot("TAX", "VTI", 100, 490.0, date(2023, 1, 1), 1200, True, 1_000.0),
            TaxLot("IRA", "BND", 100, 390.0, date(2023, 1, 1), 1200, True, 1_000.0),
            TaxLot("OTHER", "VTI", 10, 990.0, date(2023, 1, 1), 1200, True, 100.0),
        ]
        menus = [
            AccountMenu("TAX", "open", None),
            AccountMenu("IRA", "open", None),
            AccountMenu("OTHER", "open", None),
        ]
        result = generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF)
        assert "recommendations" in result
        assert len(result["recommendations"]) >= 1

    def test_f3_other_account_with_concentration_does_not_crash(self):
        """'other' account alone with >15% single name must not crash the engine."""
        master = self._master()
        # VTI is 100% of the portfolio -> over threshold, but account is "other"
        holdings = [Holding("OTHER", "Other", "other", "VTI", "etf", 200, 100_000.0, 0.0003, 0.013)]
        lots = [TaxLot("OTHER", "VTI", 200, 490.0, date(2023, 1, 1), 1200, True, 2_000.0)]
        menus = [AccountMenu("OTHER", "open", None)]
        result = generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF)
        assert "recommendations" in result

    def test_f4_other_account_with_loss_lot_does_not_crash(self):
        """'other' account with a loss lot: harvest path skips it (not taxable) without crash."""
        master = self._master()
        holdings = [
            Holding("OTHER", "Other", "other", "VTI", "etf", 100, 10_000.0, 0.0003, 0.013),
            Holding("TAX", "Taxable", "taxable", "CASH", "cash", 1, 90_000.0),
        ]
        lots = [
            TaxLot("OTHER", "VTI", 100, 150.0, date(2025, 1, 1), 365, True, -5_000.0),
        ]
        menus = [AccountMenu("OTHER", "open", None), AccountMenu("TAX", "open", None)]
        result = generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF)
        assert "recommendations" in result
        # Harvest must not be recommended for an "other" account (it's not taxable)
        recs = cast(list[Recommendation], result["recommendations"])
        assert not any(r.action == "tax_loss_harvest" and r.account_id == "OTHER" for r in recs), (
            "VIOLATED (f): tax_loss_harvest recommended for 'other' account (not taxable)."
        )


# ---------------------------------------------------------------------------
# (g) Multi-account single-name concentration (C3)
# ---------------------------------------------------------------------------


class TestAttackG_MultiAccountConcentration:
    """
    Attack: the same ticker split across accounts, each row under the threshold
    but aggregating over it. The engine must:
      - flag it exactly ONCE with the aggregated weight
      - attribute correct (order-independent) tax treatment to each account's lots

    G1 — VTI: 12% in taxable + 10% in IRA = 22% combined -> flagged
    G2 — Order-independence: same test with reversed holding order
    G3 — Taxable portion with large gain -> do_nothing_due_to_tax_cost for TAX;
         IRA portion gets a trim (no tax block)
    G4 — Both accounts under threshold individually AND combined -> no flag
    G5 — Adversarial: weight exactly at threshold (NOT over) -> no flag
    """

    def _master(self) -> dict[str, SecurityMetadata]:
        return {
            "VTI": _meta("VTI", index_family="CRSP_US_TOTAL"),
            "BND": _meta("BND", asset_class="taxable_bond", index_family="BLOOMBERG_US_AGG",
                         style="aggregate_bond", tax_bucket="low"),
            "CASH": _cash(),
        }

    def test_g1_aggregated_weight_triggers_flag(self):
        """VTI at 12%+10%=22% must be flagged with aggregated weight ~0.22."""
        master = self._master()
        # Total = 100_000; VTI in TAX=12k, VTI in IRA=10k, BND in TAX=78k
        holdings = [
            Holding("TAX", "Taxable", "taxable", "VTI", "etf", 48, 12_000.0, 0.0003, 0.013),
            Holding("IRA", "IRA", "traditional_ira", "VTI", "etf", 40, 10_000.0, 0.0003, 0.013),
            Holding("TAX", "Taxable", "taxable", "BND", "etf", 780, 78_000.0, 0.0003, 0.031),
        ]
        lots = [
            TaxLot("TAX", "VTI", 48, 240.0, date(2023, 1, 1), 1200, True, 240.0),
            TaxLot("IRA", "VTI", 40, 240.0, date(2023, 1, 1), 1200, True, 200.0),
            TaxLot("TAX", "BND", 780, 99.0, date(2023, 1, 1), 1200, True, 780.0),
        ]
        menus = [AccountMenu("TAX", "open", None), AccountMenu("IRA", "open", None)]
        result = generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF)
        recs = cast(list[Recommendation], result["recommendations"])

        # The concentration engine should flag VTI
        conc = result["concentration"]
        vti_flags = [f for f in conc["single_name_flags"] if f["ticker"] == "VTI"]
        assert len(vti_flags) == 1, (
            f"VIOLATED (g): Expected exactly 1 VTI flag, got {len(vti_flags)}. "
            f"All flags: {conc['single_name_flags']}"
        )
        assert vti_flags[0]["weight"] > 0.15, (
            f"VIOLATED (g): VTI flag weight {vti_flags[0]['weight']} is not above threshold."
        )
        assert abs(vti_flags[0]["weight"] - 0.22) < 0.01, (
            f"VIOLATED (g): Expected ~22% aggregated weight, got {vti_flags[0]['weight']}"
        )
        # Both accounts must appear in the flag
        assert set(vti_flags[0]["account_ids"]) == {"TAX", "IRA"}, (
            f"VIOLATED (g): Expected both accounts in flag, got {vti_flags[0]['account_ids']}"
        )

    @pytest.mark.parametrize("order", [(0, 1, 2), (1, 0, 2), (2, 1, 0)])
    def test_g2_aggregation_is_order_independent(self, order):
        """Flags must be the same regardless of holding input order."""
        master = self._master()
        h = [
            Holding("TAX", "Taxable", "taxable", "VTI", "etf", 48, 12_000.0, 0.0003, 0.013),
            Holding("IRA", "IRA", "traditional_ira", "VTI", "etf", 40, 10_000.0, 0.0003, 0.013),
            Holding("TAX", "Taxable", "taxable", "BND", "etf", 780, 78_000.0, 0.0003, 0.031),
        ]
        holdings = [h[i] for i in order]
        lots = [
            TaxLot("TAX", "VTI", 48, 240.0, date(2023, 1, 1), 1200, True, 240.0),
            TaxLot("IRA", "VTI", 40, 240.0, date(2023, 1, 1), 1200, True, 200.0),
            TaxLot("TAX", "BND", 780, 99.0, date(2023, 1, 1), 1200, True, 780.0),
        ]
        menus = [AccountMenu("TAX", "open", None), AccountMenu("IRA", "open", None)]
        result = generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF)
        conc = result["concentration"]
        vti_flags = [f for f in conc["single_name_flags"] if f["ticker"] == "VTI"]
        assert len(vti_flags) == 1
        assert abs(vti_flags[0]["weight"] - 0.22) < 0.01, (
            f"VIOLATED (g): order={order} weight={vti_flags[0]['weight']}"
        )

    def test_g3_taxable_large_gain_blocked_ira_position_handled_correctly(self):
        """
        VTI: 40% in TAX (large embedded gain -> tax-cost-blocked) + 10% in IRA.

        Constraint assertions:
        1. TAX VTI with a large embedded gain must be do_nothing_due_to_tax_cost
           (never a plain trim that ignores the tax cost).
        2. IRA VTI must never carry a 'tax impact unknown' or 'Estimated tax cost'
           note that implies it's being evaluated as a taxable position.
        3. The engine must not crash.

        Note: IRA VTI may receive 'relocate' (higher priority than 'trim') because
        broad-market equity is preferred in taxable accounts. That is CORRECT behavior
        — the engine's asset-location logic overrides the concentration-trim for IRA,
        which is more informative than a raw trim.
        """
        master = self._master()
        holdings = [
            Holding("TAX", "Taxable", "taxable", "VTI", "etf", 400, 40_000.0, 0.0003, 0.013),
            Holding("TAX", "Taxable", "taxable", "BND", "etf", 100, 10_000.0, 0.0003, 0.031),
            Holding("IRA", "IRA", "traditional_ira", "VTI", "etf", 100, 10_000.0, 0.0003, 0.013),
            Holding("IRA", "IRA", "traditional_ira", "BND", "etf", 400, 40_000.0, 0.0003, 0.031),
        ]
        lots = [
            # Large LT gain in taxable -> blocked (embedded gain > confirm_with_cpa_above=5000)
            TaxLot("TAX", "VTI", 400, 100.0, date(2022, 1, 1), 1500, True, 20_000.0),
            TaxLot("TAX", "BND", 100, 99.0, date(2023, 1, 1), 1200, True, 100.0),
            TaxLot("IRA", "VTI", 100, 99.0, date(2023, 1, 1), 1200, True, 100.0),
            TaxLot("IRA", "BND", 400, 99.0, date(2023, 1, 1), 1200, True, 400.0),
        ]
        menus = [AccountMenu("TAX", "open", None), AccountMenu("IRA", "open", None)]
        result = generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF)
        recs = cast(list[Recommendation], result["recommendations"])

        # ── Constraint 1: Taxable VTI with large gain must be cost-blocked ────────
        tax_recs = [r for r in recs if r.ticker == "VTI" and r.account_id == "TAX"]
        assert any(r.action == "do_nothing_due_to_tax_cost" for r in tax_recs), (
            f"VIOLATED (g): Taxable VTI with large gain was not blocked. "
            f"tax_recs={[(r.action, r.tax_notes) for r in tax_recs]}"
        )
        # Also verify the tax note carries an estimate (not silent)
        for r in tax_recs:
            if r.action == "do_nothing_due_to_tax_cost":
                has_note = any(
                    "Estimated tax cost" in note or "tax impact unknown" in note.lower()
                    for note in r.tax_notes
                )
                assert has_note, (
                    f"VIOLATED (a+g): do_nothing_due_to_tax_cost for TAX VTI has no tax note. "
                    f"tax_notes={r.tax_notes}"
                )

        # ── Constraint 2: IRA VTI must never carry a taxable-estimated-cost note ──
        ira_recs = [r for r in recs if r.ticker == "VTI" and r.account_id == "IRA"]
        assert ira_recs, "VIOLATED (g): No recommendation at all for IRA VTI position."
        for r in ira_recs:
            assert not any("Estimated tax cost" in note for note in r.tax_notes), (
                f"VIOLATED (g): IRA VTI rec carries a taxable tax-cost estimate. "
                f"action={r.action} tax_notes={r.tax_notes}"
            )
            # IRA VTI must not be do_nothing_due_to_tax_cost (it has no taxable cost)
            assert r.action != "do_nothing_due_to_tax_cost", (
                f"VIOLATED (g): IRA VTI incorrectly received do_nothing_due_to_tax_cost "
                f"(it's a tax-advantaged account). tax_notes={r.tax_notes}"
            )

    def test_g4_both_under_threshold_individually_and_combined_no_flag(self):
        """VTI at 5% + 5% = 10% combined -> below 15% threshold, no concentration flag."""
        master = self._master()
        holdings = [
            Holding("TAX", "Taxable", "taxable", "VTI", "etf", 50, 5_000.0, 0.0003, 0.013),
            Holding("IRA", "IRA", "traditional_ira", "VTI", "etf", 50, 5_000.0, 0.0003, 0.013),
            Holding("TAX", "Taxable", "taxable", "BND", "etf", 900, 90_000.0, 0.0003, 0.031),
        ]
        lots = [
            TaxLot("TAX", "VTI", 50, 99.0, date(2023, 1, 1), 1200, True, 50.0),
            TaxLot("IRA", "VTI", 50, 99.0, date(2023, 1, 1), 1200, True, 50.0),
            TaxLot("TAX", "BND", 900, 99.0, date(2023, 1, 1), 1200, True, 900.0),
        ]
        menus = [AccountMenu("TAX", "open", None), AccountMenu("IRA", "open", None)]
        result = generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF)
        conc = result["concentration"]
        vti_flags = [f for f in conc["single_name_flags"] if f["ticker"] == "VTI"]
        assert not vti_flags, (
            f"VIOLATED (g): VTI at 10% combined was incorrectly flagged. flags={vti_flags}"
        )

    def test_g5_weight_exactly_at_threshold_not_flagged(self):
        """VTI at exactly 15.0% combined: threshold is strict > not >=, so no flag."""
        master = self._master()
        # 15k VTI / 100k total = exactly 0.15
        holdings = [
            Holding("TAX", "Taxable", "taxable", "VTI", "etf", 75, 7_500.0, 0.0003, 0.013),
            Holding("IRA", "IRA", "traditional_ira", "VTI", "etf", 75, 7_500.0, 0.0003, 0.013),
            Holding("TAX", "Taxable", "taxable", "BND", "etf", 850, 85_000.0, 0.0003, 0.031),
        ]
        lots = [
            TaxLot("TAX", "VTI", 75, 99.0, date(2023, 1, 1), 1200, True, 75.0),
            TaxLot("IRA", "VTI", 75, 99.0, date(2023, 1, 1), 1200, True, 75.0),
            TaxLot("TAX", "BND", 850, 99.0, date(2023, 1, 1), 1200, True, 850.0),
        ]
        menus = [AccountMenu("TAX", "open", None), AccountMenu("IRA", "open", None)]
        result = generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF)
        conc = result["concentration"]
        vti_flags = [f for f in conc["single_name_flags"] if f["ticker"] == "VTI"]
        assert not vti_flags, (
            f"VIOLATED (g): VTI at exactly 15% was flagged (threshold should be strict >). flags={vti_flags}"
        )


# ---------------------------------------------------------------------------
# Bonus: Compound adversarial scenarios
# ---------------------------------------------------------------------------


class TestCompoundAdversarial:
    """
    Combined attacks designed to exploit multiple paths simultaneously:
    - A high-fee ETF that ALSO has a loss (fee-replace + harvest competing)
    - An "other" account holding the same ticker that causes concentration (f+g)
    - A wash-sale check with a same-index-family (not same-ticker) buy in an IRA
    """

    def test_compound_fee_replace_and_harvest_both_checked(self):
        """High-fee ETF with a loss in taxable: the engine should not emit both
        a fee-replace AND a tax_loss_harvest on the same position (reconciliation
        should produce at most one actionable recommendation per position)."""
        master = {
            "HILOSSY": _meta("HILOSSY", index_family="HILOSSY_IDX", expense=0.0075, volume=5e7),
            "LOWSAFE": _meta("LOWSAFE", index_family="LOWSAFE_IDX", expense=0.0003, volume=5e8),
            "CASH": _cash(),
        }
        holdings = [
            Holding("TAX", "Taxable", "taxable", "HILOSSY", "etf", 100, 10_000.0, 0.0075, 0.0),
            Holding("IRA", "IRA", "traditional_ira", "CASH", "cash", 1, 90_000.0),
        ]
        lots = [
            TaxLot("TAX", "HILOSSY", 100, 150.0, date(2025, 1, 1), 516, True, -5_000.0),
        ]
        menus = [AccountMenu("TAX", "open", None), AccountMenu("IRA", "open", None)]
        recs = _run(holdings, lots, menus, master)
        # At most one actionable rec per (ticker, account_id) pair
        from collections import Counter
        directional = Counter(
            (r.ticker, r.account_id)
            for r in recs
            if r.account_id is not None and r.action not in {"hold", "do_nothing_due_to_tax_cost"}
        )
        for (ticker, acct), count in directional.items():
            assert count <= 1, (
                f"VIOLATED: multiple directional recs for ({ticker}, {acct}): count={count}"
            )

    def test_compound_other_account_triggers_no_illegal_harvest(self):
        """'other' account with loss: confirm harvest is skipped (not taxable)
        and no crash occurs. Also confirm the 'other' account is not treated as
        taxable for concentration-trim tax logic."""
        master = {
            "VTI": _meta("VTI", index_family="CRSP_US_TOTAL"),
            "ITOT": _meta("ITOT", index_family="S&P_TOTAL_US"),
            "CASH": _cash(),
        }
        holdings = [
            Holding("OTHER", "Other", "other", "VTI", "etf", 200, 80_000.0, 0.0003, 0.013),
            Holding("TAX", "Taxable", "taxable", "CASH", "cash", 1, 20_000.0),
        ]
        lots = [
            TaxLot("OTHER", "VTI", 200, 500.0, date(2025, 1, 1), 365, True, -10_000.0),
        ]
        menus = [AccountMenu("OTHER", "open", None), AccountMenu("TAX", "open", None)]
        result = generate_recommendations(holdings, lots, menus, master, THRESHOLDS, TAX_PROFILE, TARGET, AS_OF)
        assert "recommendations" in result
        recs = cast(list[Recommendation], result["recommendations"])
        assert not any(r.action == "tax_loss_harvest" and r.account_id == "OTHER" for r in recs), (
            "VIOLATED: tax_loss_harvest for 'other' (non-taxable) account."
        )

    def test_compound_wash_sale_gray_zone_ira_buy_not_same_ticker(self):
        """IRA buys CLONE (same-index-family as LOSSY) within window.
        This is NOT a same-ticker buy, so wash-sale direct block doesn't fire.
        But CLONE is the only harvest replacement candidate -> gray zone -> no harvest."""
        from datetime import timedelta
        master = {
            "LOSSY": _meta("LOSSY", index_family="SHARED_IDX"),
            "CLONE": _meta("CLONE", index_family="SHARED_IDX"),  # same index family
            "CASH": _cash(),
        }
        holdings = [
            Holding("TAX", "Taxable", "taxable", "LOSSY", "etf", 100, 10_000.0, 0.001, 0.0),
            Holding("IRA", "IRA", "traditional_ira", "CASH", "cash", 1, 90_000.0),
        ]
        lots = [
            TaxLot("TAX", "LOSSY", 100, 150.0, date(2025, 1, 1), 516, True, -5_000.0),
            # IRA buys CLONE (different ticker, same index family) inside window
            TaxLot("IRA", "CLONE", 10, 100.0, AS_OF - timedelta(days=10), 10, False, 0.0),
        ]
        menus = [AccountMenu("TAX", "open", None), AccountMenu("IRA", "open", None)]
        recs = _run(holdings, lots, menus, master)
        # CLONE is same index family as LOSSY -> gray zone -> harvest should NOT proceed
        harvest_exists = any(r.action == "tax_loss_harvest" and r.ticker == "LOSSY" for r in recs)
        assert not harvest_exists, (
            "VIOLATED (b/compound): gray-zone same-index-family replacement allowed harvest."
        )
