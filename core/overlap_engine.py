from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from data.schemas import Holding, SecurityMetadata


class OverlapEngine:
    def __init__(self, security_master: dict[str, SecurityMetadata], lookthrough_dir: str | Path | None = None):
        self.security_master = security_master
        self.lookthrough_dir = Path(lookthrough_dir) if lookthrough_dir else None

    def metadata_for(self, ticker: str) -> SecurityMetadata:
        return self.security_master[ticker]

    def overlap_score(self, ticker_a: str, ticker_b: str) -> float:
        if self.lookthrough_dir:
            lookthrough_score = self._lookthrough_overlap(ticker_a, ticker_b)
            if lookthrough_score is not None:
                return round(lookthrough_score, 4)
        a = self.metadata_for(ticker_a)
        b = self.metadata_for(ticker_b)
        if a.index_family and a.index_family == b.index_family:
            return 1.0
        if a.asset_class == b.asset_class and a.region == b.region and (a.style == b.style or a.sector_focus == b.sector_focus):
            return 0.7
        if a.asset_class == b.asset_class and a.region == b.region:
            return 0.4
        return 0.0

    def _lookthrough_overlap(self, ticker_a: str, ticker_b: str) -> float | None:
        path_a = self.lookthrough_dir / f"{ticker_a}.csv"
        path_b = self.lookthrough_dir / f"{ticker_b}.csv"
        if not path_a.exists() or not path_b.exists():
            return None

        def load(path: Path) -> dict[str, float]:
            with path.open("r", encoding="utf-8") as handle:
                return {row["constituent"]: float(row["weight"]) for row in csv.DictReader(handle)}

        first = load(path_a)
        second = load(path_b)
        return min(sum(min(weight, second.get(name, 0.0)) for name, weight in first.items()), 1.0)

    def exposure_breakdown(self, holdings: list[Holding]) -> dict[str, dict[str, float]]:
        total = sum(item.market_value for item in holdings) or 1.0
        by_asset = defaultdict(float)
        by_sector = defaultdict(float)
        by_region = defaultdict(float)
        for holding in holdings:
            meta = self.metadata_for(holding.ticker)
            by_asset[meta.asset_class] += holding.market_value / total
            by_sector[meta.sector_focus] += holding.market_value / total
            by_region[meta.region] += holding.market_value / total
        return {"asset_class": dict(by_asset), "sector": dict(by_sector), "region": dict(by_region)}

    def concentration_flags(self, holdings: list[Holding], single_name_threshold: float, sector_threshold: float) -> dict[str, object]:
        total = sum(item.market_value for item in holdings) or 1.0
        single_name = []
        by_account = defaultdict(lambda: defaultdict(float))
        sector_totals = defaultdict(float)
        for holding in holdings:
            weight = holding.market_value / total
            if weight > single_name_threshold:
                single_name.append({"ticker": holding.ticker, "weight": round(weight, 4)})
            by_account[holding.account_id][holding.ticker] += holding.market_value
            sector_totals[self.metadata_for(holding.ticker).sector_focus] += weight
        sector_flags = [{"sector": sector, "weight": round(weight, 4)} for sector, weight in sector_totals.items() if weight > sector_threshold]
        account_concentration = {}
        for account_id, positions in by_account.items():
            account_total = sum(positions.values()) or 1.0
            account_concentration[account_id] = {ticker: round(value / account_total, 4) for ticker, value in positions.items()}
        return {
            "single_name_flags": single_name,
            "sector_flags": sector_flags,
            "account_concentration": account_concentration,
        }

    def redundant_pairs(self, holdings: list[Holding], minimum_score: float = 1.0) -> list[tuple[str, str, float]]:
        pairs: list[tuple[str, str, float]] = []
        tickers = sorted({item.ticker for item in holdings})
        for idx, ticker in enumerate(tickers):
            for other in tickers[idx + 1 :]:
                score = self.overlap_score(ticker, other)
                if score >= minimum_score:
                    pairs.append((ticker, other, score))
        return pairs
