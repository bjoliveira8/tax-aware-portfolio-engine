from __future__ import annotations

from data.schemas import Holding, SecurityMetadata


def location_priority(meta: SecurityMetadata) -> list[str]:
    if meta.asset_class == "cash":
        return ["taxable", "hsa", "traditional_ira", "traditional_401k", "roth_ira", "roth_401k"]
    if meta.asset_class in {"taxable_bond", "reit"} or meta.tax_efficiency_bucket == "low":
        return ["traditional_ira", "traditional_401k", "roth_ira", "roth_401k", "hsa", "taxable"]
    if meta.style in {"small_value", "large_growth"}:
        return ["roth_ira", "roth_401k", "hsa", "traditional_ira", "traditional_401k", "taxable"]
    return ["taxable", "roth_ira", "roth_401k", "hsa", "traditional_ira", "traditional_401k"]


def evaluate_asset_location(
    holdings: list[Holding],
    security_master: dict[str, SecurityMetadata],
    account_types: dict[str, str],
) -> list[dict[str, str]]:
    suggestions = []
    for holding in holdings:
        meta = security_master[holding.ticker]
        preferred = location_priority(meta)
        current_type = account_types[holding.account_id]
        if preferred.index(current_type) > 0:
            if meta.asset_class == "cash":
                suggestion = {
                    "ticker": holding.ticker,
                    "account_id": holding.account_id,
                    "current_account_type": current_type,
                    "preferred_account_type": preferred[0],
                    "reason": "cash outside taxable should usually be corrected with contribution routing or liquidity policy review, not forced sales",
                    "action": "redirect_contributions",
                    "note": "Confirm the cash balance is intentional for spending, reserves, or near-term deployment.",
                }
            else:
                suggestion = {
                    "ticker": holding.ticker,
                    "account_id": holding.account_id,
                    "current_account_type": current_type,
                    "preferred_account_type": preferred[0],
                    "reason": "tax-inefficient asset held outside preferred account location" if preferred[0] != "taxable" else "tax-efficient broad equity belongs in taxable when space is constrained",
                }
                suggestion["action"] = "relocate" if current_type == "taxable" and preferred[0] != "taxable" else "redirect_contributions"
                if current_type == "hsa":
                    suggestion["note"] = "CA/NJ users should confirm HSA state tax treatment."
            suggestions.append(suggestion)
    return suggestions
