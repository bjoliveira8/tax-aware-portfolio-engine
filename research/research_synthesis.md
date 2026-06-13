# Research Synthesis

## Chosen MVP libraries
- `argparse` for the CLI.
- `PyYAML` for config files with explicit precedence: defaults < file < CLI flag.
- Local CSV snapshots for holdings, tax lots, account menus, and security metadata.
- `dataclasses` for transparent schemas.
- `pytest` for offline deterministic tests.

## Patterns to borrow
- Mock-first ingestion via a `DataProvider` interface.
- Curated local `security_master.csv` for taxonomy, fees, and account-location logic.
- Conservative tax logic: unknown basis lowers confidence; taxable sells require explicit tax notes.
- Action-first reporting with visible grade math and deterministic recommendation IDs.
- Static model portfolios only; contribution-led fixes before taxable unwinds.

## Excluded from MVP
- No brokerage execution, optimizer, or backtest engine.
- No live network dependency in runtime analysis.
- No macro-driven reallocation or factor timing.
- No outcome/benchmark-relative performance tracking.

## Toolchain decision
The MVP is a small Python package with an offline CLI, YAML config, CSV mock data, and a rules-based engine. Runtime analysis stays local and deterministic.

## Explicit decision
There is **no optimizer and no backtest in v1**.
