from __future__ import annotations

from datetime import date
from typing import cast

from core.allocation import current_allocation, drift_report, target_allocation
from core.asset_location_engine import evaluate_asset_location
from core.etf_replacement import is_compatible_replacement, rank_replacements
from core.overlap_engine import OverlapEngine
from core.tax_lot_engine import estimate_sale_tax, lots_for_holding
from core.wash_sale_guard import WashSaleGuard
from data.schemas import ActionType, AccountMenu, Holding, Recommendation, SecurityMetadata, TaxLot, TaxProfile

PRIORITY_RANK = {
    "relocate": 0,
    "redirect_contributions": 1,
    "trim": 2,
    "tax_loss_harvest": 3,
    "replace": 4,
    "rebalance": 5,
    "add": 6,
    "do_nothing_due_to_tax_cost": 7,
    "hold": 8,
}
URGENCY_RANK = {"high": 0, "medium": 1, "low": 2}
EXECUTABLE_ACTIONS = {"trim", "replace", "relocate", "rebalance", "add", "tax_loss_harvest"}
BLOCKED_ACTIONS = {"do_nothing_due_to_tax_cost"}
ADVISORY_ACTIONS = {"hold", "redirect_contributions"}


def _merge_text(existing: list[str], incoming: list[str]) -> list[str]:
    merged: list[str] = []
    for item in [*existing, *incoming]:
        if item and item not in merged:
            merged.append(item)
    return merged


def _action_class(action: str) -> str:
    if action in EXECUTABLE_ACTIONS:
        return "executable"
    if action in BLOCKED_ACTIONS:
        return "blocked"
    return "advisory"


def reconcile_recommendations(recommendations: list[Recommendation]) -> list[Recommendation]:
    reconciled: dict[tuple[str | None, str], Recommendation] = {}
    for rec in recommendations:
        key = (rec.account_id, rec.ticker)
        current = reconciled.get(key)
        if current is None:
            reconciled[key] = rec
            continue
        current_class = _action_class(current.action)
        new_class = _action_class(rec.action)
        current_rank = PRIORITY_RANK.get(current.action, 99)
        new_rank = PRIORITY_RANK.get(rec.action, 99)
        if current.action == rec.action:
            current.rationale = _merge_text(current.rationale, rec.rationale)
            current.risks = _merge_text(current.risks, rec.risks)
            current.tax_notes = _merge_text(current.tax_notes, rec.tax_notes)
            continue
        if current_class == "executable":
            if new_class == "executable" and new_rank < current_rank:
                rec.rationale = _merge_text(rec.rationale, current.rationale)
                rec.risks = _merge_text(rec.risks, current.risks)
                rec.tax_notes = _merge_text(rec.tax_notes, current.tax_notes)
                reconciled[key] = rec
            elif new_class != "executable":
                current.rationale = _merge_text(current.rationale, rec.rationale)
                current.risks = _merge_text(current.risks, rec.risks)
                current.tax_notes = _merge_text(current.tax_notes, rec.tax_notes)
            continue
        if new_class == "executable":
            rec.rationale = _merge_text(rec.rationale, current.rationale)
            rec.risks = _merge_text(rec.risks, current.risks)
            rec.tax_notes = _merge_text(rec.tax_notes, current.tax_notes)
            reconciled[key] = rec
            continue
        if current_class == "blocked" and new_class == "advisory":
            current.rationale = _merge_text(current.rationale, rec.rationale)
            current.risks = _merge_text(current.risks, rec.risks)
            current.tax_notes = _merge_text(current.tax_notes, rec.tax_notes)
            continue
        if current_class == "advisory" and new_class == "blocked":
            rec.rationale = _merge_text(rec.rationale, current.rationale)
            rec.risks = _merge_text(rec.risks, current.risks)
            rec.tax_notes = _merge_text(rec.tax_notes, current.tax_notes)
            reconciled[key] = rec
            continue
        current.rationale = _merge_text(current.rationale, rec.rationale)
        current.risks = _merge_text(current.risks, rec.risks)
        current.tax_notes = _merge_text(current.tax_notes, rec.tax_notes)
    return list(reconciled.values())


def menu_allows(menu_map: dict[str, AccountMenu], account_id: str, ticker: str) -> bool:
    menu = menu_map.get(account_id)
    if not menu or menu.universe == "open" or menu.allowed_instruments is None:
        return True
    return ticker in menu.allowed_instruments


def build_recommendation(
    action: str,
    ticker: str,
    account_id: str | None,
    target_weight: float | None,
    current_weight: float | None,
    trade_amount: float | None,
    rationale: list[str],
    risks: list[str],
    tax_notes: list[str],
    confidence: str,
    urgency: str,
    thesis_key: str,
    replacement_ticker: str | None = None,
) -> Recommendation:
    return Recommendation(
        recommendation_id=Recommendation.build_id(action, ticker, account_id, thesis_key),
        action=cast(ActionType, action),
        ticker=ticker,
        account_id=account_id,
        target_weight=target_weight,
        current_weight=current_weight,
        trade_amount=trade_amount,
        rationale=rationale,
        risks=risks,
        tax_notes=tax_notes,
        confidence=confidence,
        urgency=urgency,
        replacement_ticker=replacement_ticker,
        thesis_key=thesis_key,
    )


def _holding_for(holdings: list[Holding], ticker: str, account_id: str) -> Holding:
    return next(item for item in holdings if item.ticker == ticker and item.account_id == account_id)


def generate_recommendations(
    holdings: list[Holding],
    lots: list[TaxLot],
    menus: list[AccountMenu],
    security_master: dict[str, SecurityMetadata],
    thresholds: dict[str, float],
    tax_profile: TaxProfile,
    model_portfolio: dict[str, float],
    as_of_date: date,
) -> dict[str, object]:
    if not holdings:
        empty_recommendation = build_recommendation(
            "hold",
            "portfolio",
            None,
            None,
            None,
            None,
            ["No holdings loaded; analysis aborted."],
            [],
            ["Load holdings before requesting portfolio actions."],
            "high",
            "low",
            "no-holdings",
        )
        return {
            "recommendations": [empty_recommendation],
            "current_allocation": {},
            "target_allocation": target_allocation(model_portfolio),
            "drift_report": {},
            "concentration": {"single_name_flags": [], "sector_flags": [], "account_concentration": {}},
        }

    overlap_engine = OverlapEngine(security_master)
    wash_guard = WashSaleGuard(security_master)
    total = sum(item.market_value for item in holdings) or 1.0
    account_types = {holding.account_id: holding.account_type for holding in holdings}
    menu_map = {menu.account_id: menu for menu in menus}
    recommendations: list[Recommendation] = []

    current = current_allocation(holdings, security_master)
    target = target_allocation(model_portfolio)
    drift = drift_report(current, target)

    # account location
    for suggestion in evaluate_asset_location(holdings, security_master, account_types):
        if suggestion["current_account_type"] == "taxable":
            holding = _holding_for(holdings, suggestion["ticker"], suggestion["account_id"])
            tax_check = estimate_sale_tax(lots_for_holding(lots, holding), tax_profile)
            if tax_check.blocked_by_tax_cost:
                recommendations.append(
                    build_recommendation(
                        "do_nothing_due_to_tax_cost",
                        suggestion["ticker"],
                        suggestion["account_id"],
                        None,
                        None,
                        None,
                        ["Location is suboptimal but taxable sale cost is too high."],
                        ["Allocation drift may persist until contributions or tax-advantaged trades fix it."],
                        tax_check.tax_notes,
                        "high",
                        "medium",
                        "tax-cost-block-location",
                    )
                )
                continue
        recommendations.append(
            build_recommendation(
                suggestion["action"],
                suggestion["ticker"],
                suggestion["account_id"],
                None,
                None,
                None,
                [suggestion["reason"], "Use tax-advantaged trades or redirect contributions instead of forcing taxable sale."],
                [],
                [suggestion.get("note", "Forward-looking location improvement only.")],
                "high",
                "medium",
                f"asset-location-{suggestion['ticker']}",
            )
        )

    # concentration
    concentration = overlap_engine.concentration_flags(holdings, thresholds["single_name_threshold"], thresholds["sector_threshold"])
    for item in concentration["single_name_flags"]:
        holding = next(hold for hold in holdings if hold.ticker == item["ticker"])
        tax_check = estimate_sale_tax(lots_for_holding(lots, holding), tax_profile) if holding.account_type == "taxable" else None
        if holding.account_type == "taxable":
            if tax_check.blocked_by_tax_cost:
                recommendations.append(
                    build_recommendation(
                        "do_nothing_due_to_tax_cost",
                        holding.ticker,
                        holding.account_id,
                        None,
                        item["weight"],
                        None,
                        [f"{holding.ticker} exceeds single-name concentration threshold."],
                        ["Taxable trim is blocked by estimated tax drag; use new money elsewhere."],
                        tax_check.tax_notes,
                        "high",
                        "high",
                        "concentration-tax-block",
                    )
                )
                continue
            trim_tax_notes = tax_check.tax_notes
        else:
            trim_tax_notes = ["No tax warning in tax-advantaged account."]
        recommendations.append(
            build_recommendation(
                "trim",
                holding.ticker,
                holding.account_id,
                None,
                item["weight"],
                holding.market_value * 0.1,
                [f"{holding.ticker} exceeds single-name concentration threshold."],
                [],
                trim_tax_notes,
                "high",
                "high",
                f"concentration-trim-{holding.ticker}",
            )
        )

    # overlap redundancy
    for first, second, score in overlap_engine.redundant_pairs(holdings):
        holding = next(item for item in holdings if item.ticker == second)
        if not menu_allows(menu_map, holding.account_id, first):
            recommendations.append(
                build_recommendation(
                    "hold",
                    second,
                    holding.account_id,
                    None,
                    None,
                    None,
                    [f"{first} and {second} are redundant, but the account menu cannot hold {first}."],
                    ["Use an allowed menu option or simplify in another account."],
                    ["Instrument blocked by account menu."],
                    "high",
                    "low",
                    f"menu-block-overlap-{second}",
                )
            )
            continue
        if holding.account_type == "taxable":
            tax_check = estimate_sale_tax(lots_for_holding(lots, holding), tax_profile)
            if tax_check.blocked_by_tax_cost:
                recommendations.append(
                    build_recommendation(
                        "do_nothing_due_to_tax_cost",
                        second,
                        holding.account_id,
                        None,
                        None,
                        None,
                        [f"{first} and {second} are redundant same-index-family holdings."],
                        ["Fee or redundancy cleanup deferred due to tax cost."],
                        tax_check.tax_notes,
                        "medium",
                        "low",
                        f"redundant-tax-block-{second}",
                    )
                )
                continue
        recommendations.append(
            build_recommendation(
                "replace",
                second,
                holding.account_id,
                None,
                None,
                holding.market_value,
                [f"{first} and {second} are redundant same-index-family holdings.", f"Overlap score = {score:.1f}."],
                [],
                ["Prefer simplifying inside tax-advantaged accounts." if holding.account_type != "taxable" else "Taxable sale reviewed for overlap cleanup."],
                "medium",
                "medium",
                f"redundant-replace-{second}",
                replacement_ticker=first,
            )
        )

    # fee replacements
    for holding in holdings:
        meta = security_master[holding.ticker]
        if (meta.expense_ratio or 0.0) < thresholds["high_fee_threshold"]:
            continue
        candidates = [ticker for ticker, candidate_meta in security_master.items() if candidate_meta.asset_class == meta.asset_class and ticker != holding.ticker]
        ranked = rank_replacements(holding.ticker, candidates, security_master, overlap_engine)
        if not ranked:
            continue
        best = ranked[0]
        if best["overlap"] < 0.4 or not best["liquidity_ok"] or best["fee_delta"] <= 0:
            continue
        replacement = str(best["ticker"])
        if holding.account_type == "taxable":
            tax_check = estimate_sale_tax(lots_for_holding(lots, holding), tax_profile)
            if tax_check.blocked_by_tax_cost:
                recommendations.append(
                    build_recommendation(
                        "do_nothing_due_to_tax_cost",
                        holding.ticker,
                        holding.account_id,
                        None,
                        None,
                        None,
                        ["Lower-fee replacement exists, but taxable gain makes the swap unattractive."],
                        [],
                        tax_check.tax_notes,
                        "medium",
                        "low",
                        f"fee-tax-block-{holding.ticker}",
                    )
                )
                continue
        if not menu_allows(menu_map, holding.account_id, replacement):
            recommendations.append(
                build_recommendation(
                    "hold",
                    holding.ticker,
                    holding.account_id,
                    None,
                    None,
                    None,
                    ["Lower-fee replacement exists but destination account menu does not allow it."],
                    ["Use permitted menu options or future contributions instead."],
                    ["Instrument blocked by account menu."],
                    "high",
                    "low",
                    f"menu-block-fee-{holding.ticker}",
                )
            )
            continue
        recommendations.append(
            build_recommendation(
                "replace",
                holding.ticker,
                holding.account_id,
                None,
                None,
                holding.market_value,
                [f"{holding.ticker} has elevated fee drag.", f"Replacement candidate {replacement} offers similar exposure."],
                ["Replacement requires similar exposure and adequate liquidity."],
                ["Tax-aware replacement reviewed."],
                "medium",
                "medium",
                f"fee-replace-{holding.ticker}",
                replacement_ticker=replacement,
            )
        )

    # drift
    for asset_class, info in drift.items():
        diff = info["difference"]
        if abs(diff) < thresholds["drift_threshold"]:
            continue
        if diff > 0 and asset_class == "us_equity":
            gain_heavy = any(
                h.account_type == "taxable" and security_master[h.ticker].asset_class == asset_class
                for h in holdings
            )
            if gain_heavy:
                recommendations.append(
                    build_recommendation(
                        "do_nothing_due_to_tax_cost",
                        asset_class,
                        None,
                        info["target_weight"],
                        info["current_weight"],
                        None,
                        [f"{asset_class} is overweight but contributions can fix drift without a taxable sale."],
                        [],
                        ["Fix drift via contributions + tax-advantaged accounts."],
                        "high",
                        "medium",
                        f"drift-taxable-block-{asset_class}",
                    )
                )
                continue
        recommendations.append(
            build_recommendation(
                "rebalance" if diff > 0 else "add",
                asset_class,
                None,
                info["target_weight"],
                info["current_weight"],
                abs(diff) * total,
                [f"{asset_class} is {'overweight' if diff > 0 else 'underweight'} versus target."],
                [],
                ["Use rebalancing discipline."],
                "medium",
                "low",
                f"drift-{asset_class}",
            )
        )

    # tax-loss harvest and menu blocks
    for holding in holdings:
        if holding.account_type != "taxable":
            continue
        meta = security_master[holding.ticker]
        holding_lots = lots_for_holding(lots, holding)
        loss_lots = [lot for lot in holding_lots if lot.unrealized_gain is not None and lot.unrealized_gain < thresholds["harvest_loss_threshold"]]
        if not loss_lots:
            continue
        replacements = [
            ticker
            for ticker, candidate in security_master.items()
            if is_compatible_replacement(meta, candidate)
        ]
        wash = wash_guard.check_harvest(holding.ticker, as_of_date, lots, replacements)
        if wash.status != "wash_sale_clean":
            recommendations.append(
                build_recommendation(
                    "hold",
                    holding.ticker,
                    holding.account_id,
                    None,
                    None,
                    None,
                    ["Loss exists but wash-sale rules block a harvest recommendation."],
                    [],
                    wash.notes,
                    "medium",
                    "low",
                    f"wash-blocked-{holding.ticker}",
                )
            )
            continue
        replacement = wash.safe_replacements[0] if wash.safe_replacements else None
        if replacement and not menu_allows(menu_map, holding.account_id, replacement):
            recommendations.append(
                build_recommendation(
                    "hold",
                    holding.ticker,
                    holding.account_id,
                    None,
                    None,
                    None,
                    ["Harvest candidate exists but replacement is blocked by account menu."],
                    [],
                    ["Account menu prevents replacement instrument."],
                    "medium",
                    "low",
                    f"harvest-menu-block-{holding.ticker}",
                )
            )
            continue
        recommendations.append(
            build_recommendation(
                "tax_loss_harvest",
                holding.ticker,
                holding.account_id,
                None,
                None,
                holding.market_value,
                ["Realized loss available and wash-sale screen passed."],
                [],
                wash.notes,
                "high",
                "high",
                f"tax-loss-harvest-{holding.ticker}",
                replacement_ticker=replacement,
            )
        )

    unique = {rec.recommendation_id: rec for rec in recommendations}
    ordered = sorted(
        reconcile_recommendations(list(unique.values())),
        key=lambda rec: (PRIORITY_RANK.get(rec.action, 99), URGENCY_RANK.get(rec.urgency, 9), rec.recommendation_id),
    )
    if not ordered:
        ordered = [
            build_recommendation(
                "hold",
                "portfolio",
                None,
                None,
                None,
                None,
                ["No action is justified."],
                [],
                ["Drift is within tolerance and tax cost outweighs benefit."],
                "high",
                "low",
                "no-action",
            )
        ]
    return {
        "recommendations": ordered,
        "current_allocation": current,
        "target_allocation": target,
        "drift_report": drift,
        "concentration": concentration,
    }
