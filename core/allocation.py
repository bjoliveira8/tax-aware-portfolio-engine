from __future__ import annotations

from collections import defaultdict

from data.schemas import Holding, SecurityMetadata


def _normalized_rounded(values: dict[str, float]) -> dict[str, float]:
    rounded = {key: round(value, 6) for key, value in values.items()}
    if not rounded:
        return rounded
    keys = list(rounded)
    rounded[keys[-1]] = round(1.0 - sum(rounded[key] for key in keys[:-1]), 6)
    return rounded


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
