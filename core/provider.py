from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from data.schemas import AccountMenu, Holding, TaxLot


@dataclass
class IngestionResult:
    holdings: list[Holding]
    tax_lots: list[TaxLot]
    account_menus: list[AccountMenu]
    warnings: list[str] = field(default_factory=list)


class DataProvider(Protocol):
    def load(
        self,
        holdings_path: str | Path,
        lots_path: str | Path,
        account_menus_path: str | Path | None = None,
    ) -> IngestionResult:
        ...
