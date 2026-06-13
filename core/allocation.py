from __future__ import annotations

import warnings
from collections import defaultdict

from data.schemas import Holding, SecurityMetadata


def _normalized_rounded(values: dict[str, float]) -> dict[str, float]:
    """Normalize proportionally so the weights genuinely sum to 1.

    Earlier code forced the last key to absorb all rounding error, which masked invalid inputs and
    made "sums to 1" tautological. Here we divide by the true total; if the raw input deviates from
    1.0 beyond a small epsilon we surface a warning rather than silently hiding it.
    """
    if not values:
        return {}
    raw_total = sum(values.values())
    if raw_total <= 0:
        return {key: 0.0 for key in values}
    if abs(raw_total - 1.0) > 1e-6:
        warnings.warn(f"Allocation weights summed to {raw_total:.6f}; normalizing proportionally.", stacklevel=2)
    return {key: round(value / raw_total, 6) for key, value in values.items()}


def current_allocation(holdings: list[Holding], security_master: dict[str, SecurityMetadata]) -> dict[str, float]:
    total = sum(item.market_value for item in holdings) or 1.0
    alloc = defaultdict(float)
    for holding in holdings:
        alloc[security_master[holding.ticker].asset_class] += holding.market_value / total
    return _normalized_rounded(dict(alloc))


def target_allocation(model: dict[str, float]) -> dict[str, float]:
    total = sum(model.values()) or 1.0
    return _normalized_rounded({key: value / total for key, value in model.items()})


def drift_report(current: dict[str, float], target: dict[str, float]) -> dict[str, dict[str, float]]:
    classes = sorted(set(current) | set(target))
    report = {}
    for asset_class in classes:
        cur = current.get(asset_class, 0.0)
        tgt = target.get(asset_class, 0.0)
        report[asset_class] = {
            "current_weight": round(cur, 6),
            "target_weight": round(tgt, 6),
            "difference": round(cur - tgt, 6),
        }
    return report
