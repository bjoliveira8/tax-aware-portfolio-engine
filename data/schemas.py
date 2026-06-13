from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from typing import Literal

AccountType = Literal["taxable", "traditional_401k", "roth_401k", "traditional_ira", "roth_ira", "hsa", "other"]
ActionType = Literal["hold", "add", "trim", "exit", "replace", "relocate", "redirect_contributions", "rebalance", "tax_loss_harvest", "do_nothing_due_to_tax_cost"]
UniverseType = Literal["open", "menu"]


@dataclass(slots=True)
class Holding:
    account_id: str
    account_name: str
    account_type: AccountType
    ticker: str
    asset_type: str
    shares: float
    market_value: float
    expense_ratio: float | None = None
    dividend_yield: float | None = None


@dataclass(slots=True)
class TaxLot:
    account_id: str
    ticker: str
    shares: float
    cost_basis_per_share: float | None
    acquired_date: date
    holding_period_days: int
    is_long_term: bool
    unrealized_gain: float | None = None
    account_type: AccountType = "other"


@dataclass(slots=True)
class TaxProfile:
    filing_status: str
    federal_marginal_rate: float
    ltcg_rate: float
    niit_applies: bool
    state_rate: float
    qualified_dividend_rate: float
    confirm_with_cpa_above: float


@dataclass(slots=True)
class AccountMenu:
    account_id: str
    universe: UniverseType
    allowed_instruments: list[str] | None = None


@dataclass(slots=True)
class Recommendation:
    recommendation_id: str
    action: ActionType
    ticker: str
    account_id: str | None
    target_weight: float | None
    current_weight: float | None
    trade_amount: float | None
    rationale: list[str]
    risks: list[str]
    tax_notes: list[str]
    confidence: str
    urgency: str
    replacement_ticker: str | None = None
    thesis_key: str = ""

    @staticmethod
    def build_id(action: str, ticker: str, account_id: str | None, thesis_key: str) -> str:
        seed = f"{action}|{ticker}|{account_id or 'portfolio'}|{thesis_key}"
        return sha256(seed.encode("utf-8")).hexdigest()[:16]


@dataclass(slots=True)
class ProcessLogEntry:
    date: str
    snapshot_id: str
    recommendation_id: str
    action: str
    thesis: str
    invalidation_rule: str
    fee_drag_bps: float
    diversification_ok: bool
    wash_sale_clean: bool
    concentration_within_limits: bool


@dataclass(slots=True)
class SecurityMetadata:
    ticker: str
    security_name: str
    security_type: str
    issuer: str
    asset_class: str
    sub_asset_class: str
    region: str
    style: str
    sector_focus: str
    index_family: str
    expense_ratio: float | None
    distribution_yield: float | None
    aum_usd: float | None
    avg_daily_dollar_volume: float | None
    tax_efficiency_bucket: str
    primary_benchmark: str
    source_note: str
    as_of_date: str
