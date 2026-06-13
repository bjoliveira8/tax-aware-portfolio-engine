from __future__ import annotations

from dataclasses import dataclass

from data.schemas import Holding, TaxLot, TaxProfile


@dataclass(slots=True)
class TaxTradeAnalysis:
    estimated_tax_cost: float | None
    estimated_gain: float | None
    blocked_by_tax_cost: bool
    tax_notes: list[str]
    confidence: str


def estimate_sale_tax(lots: list[TaxLot], tax_profile: TaxProfile) -> TaxTradeAnalysis:
    if not lots:
        return TaxTradeAnalysis(None, None, False, ["No lot data available; tax impact unknown"], "low")
    estimated_gain = 0.0
    tax_cost = 0.0
    tax_notes: list[str] = []
    blocked = False
    for lot in lots:
        if lot.cost_basis_per_share is None or lot.unrealized_gain is None:
            return TaxTradeAnalysis(None, None, False, ["tax impact unknown"], "low")
        estimated_gain += lot.unrealized_gain
        if lot.unrealized_gain > 0:
            rate = tax_profile.ltcg_rate if lot.is_long_term else tax_profile.federal_marginal_rate
            if tax_profile.niit_applies:
                rate += 0.038
            rate += tax_profile.state_rate
            tax_cost += lot.unrealized_gain * rate
            if not lot.is_long_term and lot.unrealized_gain > tax_profile.confirm_with_cpa_above / 4:
                blocked = True
                tax_notes.append("Large short-term gain suppresses taxable sale.")
    if tax_cost > tax_profile.confirm_with_cpa_above:
        tax_notes.append("Confirm with a tax professional before acting.")
    if estimated_gain > tax_profile.confirm_with_cpa_above:
        blocked = True
        tax_notes.append("Embedded taxable gain is above the configured caution threshold.")
    estimated_cost = round(tax_cost, 2)
    estimated_gain = round(estimated_gain, 2)
    summary_note = f"Estimated tax cost: ${estimated_cost:,.2f} on estimated gain ${estimated_gain:,.2f}."
    return TaxTradeAnalysis(estimated_cost, estimated_gain, blocked, [summary_note, *tax_notes], "high")


def lots_for_holding(lots: list[TaxLot], holding: Holding) -> list[TaxLot]:
    return [lot for lot in lots if lot.account_id == holding.account_id and lot.ticker == holding.ticker]
