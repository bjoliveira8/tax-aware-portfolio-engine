from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from data.schemas import SecurityMetadata, TaxLot


@dataclass(slots=True)
class WashSaleResult:
    status: str
    notes: list[str]
    safe_replacements: list[str]


class WashSaleGuard:
    def __init__(self, security_master: dict[str, SecurityMetadata]):
        self.security_master = security_master

    def check_harvest(
        self,
        ticker: str,
        sale_date: date,
        all_lots: list[TaxLot],
        replacement_candidates: list[str] | None = None,
    ) -> WashSaleResult:
        replacement_candidates = replacement_candidates or []
        window_start = sale_date - timedelta(days=30)
        window_end = sale_date + timedelta(days=30)
        notes: list[str] = []
        for lot in all_lots:
            if lot.ticker == ticker and window_start <= lot.acquired_date <= window_end:
                notes.append(f"Same ticker buy in window: {lot.account_id} on {lot.acquired_date.isoformat()}")
                if lot.account_type in {"traditional_ira", "roth_ira", "traditional_401k", "roth_401k", "hsa"}:
                    return WashSaleResult(
                        "wash_sale_blocked_retirement_account_purchase",
                        notes + ["Permanent loss risk via retirement account purchase."],
                        [],
                    )
                return WashSaleResult("wash_sale_blocked_same_ticker", notes, [])
        source_index = self.security_master[ticker].index_family
        safe: list[str] = []
        for candidate in replacement_candidates:
            if candidate == ticker:
                continue
            meta = self.security_master[candidate]
            if meta.index_family == source_index:
                notes.append(f"{candidate} shares same index family as {ticker}; gray zone.")
                continue
            safe.append(candidate)
        if replacement_candidates and not safe:
            return WashSaleResult(
                "wash_sale_gray_zone_substantially_identical",
                notes or ["Replacement candidates are too close to source exposure."],
                [],
            )
        return WashSaleResult("wash_sale_clean", notes or ["61-day wash-sale check passed across all accounts."], safe)
