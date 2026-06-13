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


def select_lots(lots: list[TaxLot], method: str = "fifo", shares_to_sell: float | None = None) -> list[TaxLot]:
    """Order (and optionally subset) tax lots for a sale by a deterministic, rule-based method.

    - "fifo": oldest lots first (by acquired_date, ticker tiebreak).
    - "specific_lot": minimize realized gain -- realize losses first, then the smallest gains,
      preferring long-term lots to avoid short-term rates.

    This is rule-based lot ordering, not an optimizer. When shares_to_sell is given, whole lots are
    accumulated in the chosen order until the share count is covered.
    """
    if method == "specific_lot":
        ordered = sorted(
            lots,
            key=lambda lot: (
                lot.unrealized_gain if lot.unrealized_gain is not None else 0.0,
                0 if lot.is_long_term else 1,
                lot.acquired_date,
                lot.ticker,
            ),
        )
    else:
        ordered = sorted(lots, key=lambda lot: (lot.acquired_date, lot.ticker))
    if shares_to_sell is None:
        return ordered
    selected: list[TaxLot] = []
    remaining = shares_to_sell
    for lot in ordered:
        if remaining <= 0:
            break
        selected.append(lot)
        remaining -= lot.shares
    return selected


def estimate_sale_tax(
    lots: list[TaxLot],
    tax_profile: TaxProfile,
    shares_to_sell: float | None = None,
    method: str | None = None,
) -> TaxTradeAnalysis:
    # For a partial sale, select which lots are realized (specific-lot vs FIFO). A full-position
    # estimate (shares_to_sell is None) sums every lot, so lot ordering is immaterial and behavior
    # is unchanged from before this capability existed.
    if shares_to_sell is not None:
        lots = select_lots(lots, method or tax_profile.lot_selection_method, shares_to_sell)
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
                rate += tax_profile.niit_rate
            rate += tax_profile.state_rate
            tax_cost += lot.unrealized_gain * rate
            short_term_block = tax_profile.confirm_with_cpa_above * tax_profile.short_term_gain_block_fraction
            if not lot.is_long_term and lot.unrealized_gain > short_term_block:
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
