from __future__ import annotations

from hashlib import sha256

from data.schemas import ProcessLogEntry, Recommendation


def snapshot_id_for(recommendations: list[Recommendation]) -> str:
    joined = "|".join(sorted(item.recommendation_id for item in recommendations))
    return sha256(joined.encode("utf-8")).hexdigest()[:12]


def build_process_log(
    recommendations: list[Recommendation],
    analysis: dict[str, object],
    fee_drag_bps: float,
    run_date: str,
) -> list[ProcessLogEntry]:
    snapshot_id = snapshot_id_for(recommendations)
    concentration = analysis["concentration"]
    concentration_within_limits = not concentration["single_name_flags"] and not concentration["sector_flags"]
    wash_sale_clean = not any(item.thesis_key.startswith("wash-blocked-") for item in recommendations)
    diversification_ok = concentration_within_limits and not any(
        item.thesis_key.startswith("redundant-") for item in recommendations
    )
    return [
        ProcessLogEntry(
            date=run_date,
            snapshot_id=snapshot_id,
            recommendation_id=item.recommendation_id,
            action=item.action,
            thesis="; ".join(item.rationale),
            invalidation_rule="Tax note changes, wash-sale status changes, or drift resolves via contributions.",
            fee_drag_bps=fee_drag_bps,
            diversification_ok=diversification_ok,
            wash_sale_clean=wash_sale_clean,
            concentration_within_limits=concentration_within_limits,
        )
        for item in recommendations
    ]
