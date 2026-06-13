from __future__ import annotations

from core.overlap_engine import OverlapEngine
from data.schemas import SecurityMetadata

FUND_LIKE_TYPES = {"etf", "mutual_fund"}


def is_compatible_replacement(current: SecurityMetadata, candidate: SecurityMetadata) -> bool:
    if current.ticker == candidate.ticker:
        return False
    if current.asset_class != candidate.asset_class:
        return False
    if current.security_type != candidate.security_type and {current.security_type, candidate.security_type} <= FUND_LIKE_TYPES:
        pass
    elif current.security_type != candidate.security_type:
        return False
    return bool(
        (current.index_family and current.index_family == candidate.index_family)
        or current.sub_asset_class == candidate.sub_asset_class
        or (current.region == candidate.region and current.style == candidate.style)
    )


def rank_replacements(
    current_ticker: str,
    candidates: list[str],
    security_master: dict[str, SecurityMetadata],
    overlap_engine: OverlapEngine,
) -> list[dict[str, object]]:
    current = security_master[current_ticker]
    ranked = []
    for candidate in candidates:
        if candidate == current_ticker:
            continue
        meta = security_master[candidate]
        if not is_compatible_replacement(current, meta):
            continue
        overlap = overlap_engine.overlap_score(current_ticker, candidate)
        liquidity_ok = (meta.avg_daily_dollar_volume or 0) >= 5_000_000
        fee_delta = (current.expense_ratio or 0.0) - (meta.expense_ratio or 0.0)
        ranked.append(
            {
                "ticker": candidate,
                "overlap": overlap,
                "fee_delta": round(fee_delta, 4),
                "liquidity_ok": liquidity_ok,
                "aum_usd": meta.aum_usd or 0.0,
                "yield_penalty": round((meta.distribution_yield or 0.0) - (current.distribution_yield or 0.0), 4),
                "tax_efficiency_bucket": meta.tax_efficiency_bucket,
                "score": round((overlap * 10) + fee_delta * 100 - (0 if liquidity_ok else 5) - ((meta.distribution_yield or 0.0) * 2), 4),
            }
        )
    return sorted(ranked, key=lambda item: item["score"], reverse=True)
