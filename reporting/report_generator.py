from __future__ import annotations

from pathlib import Path

from data.schemas import Recommendation

GRADE_WEIGHTS = {
    "allocation_fit": 30,
    "concentration": 20,
    "tax_efficiency": 20,
    "fee_drag": 15,
    "diversification": 15,
}


def compute_grade(
    drift_report: dict[str, dict[str, float]],
    concentration: dict[str, object],
    fee_drag_bps: float,
    tax_drag_flags: int,
    overlap_count: int,
) -> dict[str, object]:
    drift_penalty = min(sum(abs(item["difference"]) for item in drift_report.values()) * 100, 30)
    concentration_penalty = min((len(concentration["single_name_flags"]) * 5) + (len(concentration["sector_flags"]) * 5), 20)
    tax_penalty = min(tax_drag_flags * 4, 20)
    fee_penalty = min(fee_drag_bps / 10, 15)
    diversification_penalty = min(overlap_count * 5, 15)
    components = {
        "allocation_fit": round(max(0, GRADE_WEIGHTS["allocation_fit"] - drift_penalty)),
        "concentration": round(max(0, GRADE_WEIGHTS["concentration"] - concentration_penalty)),
        "tax_efficiency": round(max(0, GRADE_WEIGHTS["tax_efficiency"] - tax_penalty)),
        "fee_drag": round(max(0, GRADE_WEIGHTS["fee_drag"] - fee_penalty)),
        "diversification": round(max(0, GRADE_WEIGHTS["diversification"] - diversification_penalty)),
    }
    return {"score": sum(components.values()), "components": components}


def render_report(
    analysis: dict[str, object],
    recommendations: list[Recommendation],
    process_log: list[object],
    fee_drag_bps: float,
    output_path: str | Path,
) -> str:
    drift_report = analysis["drift_report"]
    concentration = analysis["concentration"]
    overlap_count = len(concentration["single_name_flags"])
    tax_drag_flags = sum(1 for item in recommendations if item.action == "do_nothing_due_to_tax_cost")
    grade = compute_grade(drift_report, concentration, fee_drag_bps, tax_drag_flags, overlap_count)
    if len(recommendations) == 1 and recommendations[0].thesis_key == "no-action":
        bottom_line = [
            "No action is justified.",
            "Drift is within tolerance, concentration is acceptable, and tax cost outweighs benefit.",
            "Continue contributions according to target allocation.",
        ]
    else:
        actionable = [item for item in recommendations if item.action != "hold"]
        bottom_line = [
            f"Do these {len(actionable)} things now." if actionable else "No action is justified.",
            "Protect taxable gains unless tax-aware math says otherwise.",
            "Use tax-advantaged accounts and contributions first.",
        ]
    lines = ["BOTTOM LINE"] + [f"- {line}" for line in bottom_line] + [""]
    lines.append("PRIORITY ACTIONS")
    for idx, rec in enumerate(recommendations, start=1):
        target = f" -> {rec.replacement_ticker}" if rec.replacement_ticker else ""
        lines.append(f"{idx}. {rec.action.upper()} {rec.ticker}{target}")
        lines.append(f"   Why: {'; '.join(rec.rationale)}")
        lines.append(f"   Tax note: {'; '.join(rec.tax_notes) if rec.tax_notes else 'None'}")
        lines.append(f"   Confidence: {rec.confidence} | Urgency: {rec.urgency}")
    lines += ["", f"PORTFOLIO GRADE: {grade['score']} / 100"]
    for key, weight in GRADE_WEIGHTS.items():
        pretty = key.replace("_", " ").title()
        lines.append(f"- {pretty}: {grade['components'][key]} / {weight}")
    lines += ["", "CURRENT VS TARGET"]
    for asset_class, info in drift_report.items():
        lines.append(
            f"- {asset_class}: current {info['current_weight']:.2%} | target {info['target_weight']:.2%} | diff {info['difference']:+.2%}"
        )
    lines += ["", "PROCESS LOG"]
    for entry in process_log:
        lines.append(f"- {entry.recommendation_id}: {entry.action} | {entry.thesis}")
    lines += [
        "",
        "Blind spots: target allocation is a user-owned assumption; stable professional income is bond-like human capital outside this model.",
        "Analysis, not financial advice.",
    ]
    text = "\n".join(lines) + "\n"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")
    return text
