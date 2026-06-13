# Data Sources Research for Tax-Aware Portfolio Decision Engine MVP

## Goal
Choose an MVP data stack for:
- historical and current prices
- ETF metadata and expense ratios
- ticker classification for overlap / asset-location logic
- optional macro context

The MVP must stay **offline-friendly, deterministic in tests, and mock-first**. This research therefore prefers libraries and patterns that separate **data acquisition** from **analysis**, and treats live downloads as an optional refresh step rather than a runtime dependency.

---

## Selection Criteria

1. **Deterministic tests**: unit tests must never depend on network responses, website scraping stability, or changing vendor payloads.
2. **Simple Python ergonomics**: CSV/Parquet/JSON snapshots should load cleanly into pandas-based pipelines.
3. **Good enough coverage for ETFs and mutual-fund-like portfolio audits**: the engine is not doing intraday trading or factor research.
4. **Low operational complexity**: no paid market-data contract or API gateway required for v1.
5. **Traceability**: every recommendation should be explainable from a local snapshot.

---

## Domain 1: Prices

### Options considered

#### 1) `yfinance`
**Pros**
- Very common in Python workflows.
- Easy access to daily adjusted price history.
- Also exposes some fund metadata in one library.
- Good enough for personal-investor ETF price histories.

**Cons**
- Not a contractual data source; upstream behavior can change.
- Some metadata fields are inconsistently populated across tickers.
- Network calls are slow and nondeterministic for tests.

**MVP fit**
- Good as a **snapshot builder**, not as an always-live runtime dependency.

#### 2) `pandas-datareader`
**Pros**
- Familiar interface.
- Can connect to multiple sources.

**Cons**
- More useful as a connector layer than as a complete solution.
- Source quality still depends on the upstream provider.
- Less compelling than directly using the specific provider libraries needed.

**MVP fit**
- Not necessary for v1.

#### 3) `yahooquery`
**Pros**
- Broader Yahoo data access than `yfinance` in some cases.
- Useful for pulling quote and fund fields in batches.

**Cons**
- Same fundamental dependency risk as other Yahoo-based tools.
- Extra surface area the MVP does not need.

**MVP fit**
- Reasonable alternative, but not the simplest default.

#### 4) Direct vendor APIs (Polygon, Alpha Vantage, Tiingo, IEX, etc.)
**Pros**
- Cleaner contracts and more stable schemas.
- Better long-term production path.

**Cons**
- API keys, quotas, and vendor-specific integration work.
- Unnecessary complexity for an offline-first MVP.

**MVP fit**
- Excluded from v1.

### Recommendation for prices
Use **`yfinance` only in an optional refresh/snapshot script** and make the analysis engine read **local canonical snapshots** only.

### Canonical v1 pattern
- Runtime analysis input: `data/prices/<as_of_date>/prices.parquet` or `prices.csv`
- Columns:
  - `date`
  - `ticker`
  - `close`
  - `adj_close`
  - `currency`
  - `data_source`
  - `as_of_date`
- Product code consumes a `PriceProvider` interface backed by local files.
- Tests use tiny fixture snapshots with fixed values.

### Why this is right for v1
The portfolio engine mostly needs:
- current portfolio valuation cross-checks
- simple historical context for drift / reporting
- deterministic inputs for tests

It does **not** need intraday bars, order-book data, or vendor-grade execution timestamps.

---

## Domain 2: ETF metadata and expense ratios

### Data needed
For v1, the engine mainly needs:
- fund name
- asset class / broad category
- expense ratio
- issuer
- index family or benchmark name when available
- fund type (ETF, mutual fund, stock, bond fund, cash proxy)
- optional yield / AUM / average volume if used later in replacement logic

### Options considered

#### 1) `yfinance` fund metadata
**Pros**
- Same library as price snapshotting.
- Can often retrieve long name, category-like fields, fund family, and some summary stats.
- Minimal dependency count.

**Cons**
- Field completeness is inconsistent.
- Some ETF fields are missing or messy.
- Mutual fund / ETF metadata can vary by ticker.

**MVP fit**
- Acceptable as one raw input, but should not be trusted as the sole source of truth.

#### 2) Manual curated security master (CSV/JSON)
**Pros**
- Fully deterministic.
- Perfect for the exact set of holdings present in mock and early real portfolios.
- Lets the project normalize ambiguous vendor fields into a small, stable schema.

**Cons**
- Requires manual maintenance.
- Not broad-market complete.

**MVP fit**
- Excellent. This should be the **authoritative runtime source**.

#### 3) Third-party ETF/fund libraries or websites
Examples: wrappers around ETF.com, fund sponsor pages, scraped tables.

**Pros**
- Rich detail when they work.

**Cons**
- Scraping fragility.
- Terms-of-use risk.
- Schema drift.
- Hard to make deterministic offline.

**MVP fit**
- Excluded from v1.

### Recommendation for ETF metadata
Use a **local curated security master** as the runtime truth, optionally seeded or refreshed from `yfinance` plus manual cleanup.

### Canonical v1 schema
Store as `data/reference/security_master.csv` with at least:
- `ticker`
- `security_name`
- `security_type`
- `issuer`
- `asset_class`
- `sub_asset_class`
- `region`
- `style`
- `sector_focus`
- `index_family`
- `expense_ratio`
- `distribution_yield` (nullable)
- `aum_usd` (nullable)
- `avg_daily_dollar_volume` (nullable)
- `tax_efficiency_bucket`
- `primary_benchmark`
- `source_note`
- `as_of_date`

### Why this is right for v1
Expense ratio and benchmark family drive replacement and overlap logic. Those are exactly the kinds of fields that should be **normalized once** and then used deterministically everywhere else.

---

## Domain 3: Ticker classification for overlap, concentration, and asset location

### Data needed
The execution plan already implies a taxonomy with fields such as:
- asset class
- region
- style / sector
- index family
- weighted look-through if available

### Options considered

#### 1) Vendor-provided categories from `yfinance`
**Pros**
- Fast starting point.

**Cons**
- Categories are too inconsistent for rules-based overlap scoring.
- Index family often needs manual normalization.

**MVP fit**
- Useful as seed data only.

#### 2) Hand-curated taxonomy map
**Pros**
- Most reliable for deterministic overlap rules.
- Easy to align with the exact `overlap_score` tiers in the build spec.
- Easy to test.

**Cons**
- Manual effort.

**MVP fit**
- Best v1 choice.

#### 3) Full holdings look-through from issuer reports
**Pros**
- Highest-fidelity overlap analysis.

**Cons**
- Harder ingestion and normalization problem.
- More moving parts than the MVP needs.
- Portfolio constituent files differ by issuer and frequency.

**MVP fit**
- Optional enhancement later, not core v1.

### Recommendation for classification
Adopt a **two-layer model**:

1. **Authoritative local taxonomy map** for all tickers in scope.
2. Optional **look-through override files** only when manually added for a few major ETFs.

### Canonical v1 files
- `data/reference/security_master.csv` for ticker-level classification
- optional `data/reference/lookthrough/<ticker>.csv` for constituent weights

### Suggested classification buckets
Keep buckets small and stable. Example controlled vocabularies:

- `security_type`: stock, etf, mutual_fund, bond_fund, cash, cash_equivalent, other
- `asset_class`: us_equity, international_equity, emerging_equity, taxable_bond, muni_bond, tips, reit, cash
- `region`: us, developed_ex_us, emerging_markets, global, n/a
- `style`: broad_market, large_blend, large_growth, large_value, small_blend, small_value, sector, aggregate_bond, short_treasury, intermediate_treasury, inflation_linked, real_estate
- `sector_focus`: technology, health_care, financials, energy, utilities, industrials, consumer, communication, materials, real_estate, none
- `tax_efficiency_bucket`: high, medium, low

### Why this is right for v1
The engine does not need perfect institutional classification. It needs **stable, testable classifications** that support:
- concentration checks
- redundancy detection
- replacement safety
- asset-location heuristics

A local taxonomy map is the cleanest way to get there.

---

## Domain 4: Macro data

### Intended use in this product
The spec is explicit: macro/news/commentary is **read-only context** and may never modify recommendation scores or urgency. That sharply limits what the MVP needs.

### Options considered

#### 1) `fredapi`
**Pros**
- Clean access to FRED macro series.
- Strong fit for rates, inflation, unemployment, yield-curve context.
- Widely used and conceptually stable.

**Cons**
- Requires API access for refresh.
- Network dependency if used live.

**MVP fit**
- Good optional snapshot source.

#### 2) `pandas-datareader` with FRED
**Pros**
- Familiar if already using pandas-datareader.

**Cons**
- Adds an extra abstraction without clear benefit over `fredapi`.

**MVP fit**
- Fine, but not preferred.

#### 3) No macro integration at all in v1
**Pros**
- Simplest possible scope.

**Cons**
- Loses useful explanatory context in reports.

**MVP fit**
- Viable, but a tiny local macro snapshot is cheap and useful.

### Recommendation for macro data
Use **`fredapi` only for optional offline snapshot generation**, then load a local macro snapshot file at runtime.

### Canonical v1 macro snapshot
`data/reference/macro_snapshot.csv` with small, human-readable series such as:
- `series_code`
- `series_name`
- `observation_date`
- `value`
- `unit`
- `as_of_date`

Suggested series for narrative context only:
- Fed Funds / short rate proxy
- 10Y Treasury yield
- CPI inflation YoY proxy
- unemployment rate

### Rules for use
- Macro values may appear in report commentary.
- Macro values may not alter action generation, ranking, confidence, or urgency.
- Missing macro data should never block the engine.

---

## Chosen MVP Stack

### Runtime data access
Use **local files only** through narrow provider interfaces:
- `PriceProvider` -> reads local price snapshot
- `SecurityMasterProvider` -> reads local security master
- `MacroProvider` -> reads local macro snapshot or returns empty context

### Snapshot / refresh utilities
Use these only outside unit tests and outside the core recommendation path:
- **`yfinance`** for price history and basic fund metadata seeding
- **`fredapi`** for optional macro snapshot refresh
- **`pandas`** for normalization, validation, and writing canonical CSV/Parquet artifacts

### Storage format
- Prefer **Parquet** for price history if dependency footprint permits.
- Always support **CSV** as the fallback and test fixture format.
- Keep reference tables in CSV for easy human editing.

### Deterministic testing pattern
- Commit small fixture files under `tests/fixtures/`.
- Use explicit `as_of_date` fields in every snapshot.
- Never call `yfinance` or `fredapi` from unit tests.
- Mock provider outputs directly when testing business rules.

---

## Patterns to Borrow

### 1) Security-master-first design
Borrow the common quant/data-engineering pattern of having one **canonical reference table** that normalizes ticker identity and classification before any portfolio logic runs.

Why it matters here:
- prevents repeated ad hoc metadata lookups
- gives overlap and replacement logic stable inputs
- makes audit trails much easier

### 2) Snapshot-based ingestion
Borrow the pattern used in reproducible research pipelines: fetch externally, freeze locally, analyze locally.

Why it matters here:
- makes reports reproducible
- removes network flakiness from tests
- supports offline use and easier debugging

### 3) Provider interface abstraction
Borrow a thin repository/provider pattern:
- one interface per data domain
- file-backed implementation for runtime
- mock implementation for tests

Why it matters here:
- keeps business logic independent from source vendors
- allows future swap to paid APIs without rewriting core engines

### 4) Controlled vocabularies over free text
Borrow the pattern of mapping raw vendor labels into a small internal taxonomy.

Why it matters here:
- overlap scoring requires deterministic buckets
- asset-location rules are easier to reason about and test

---

## Explicit Exclusions for v1

Do **not** make these part of the MVP runtime stack:
- live quote dependencies in the core CLI path
- intraday or real-time market data
- scraping ETF websites or sponsor pages at runtime
- broad holdings-lookthrough ingestion for every ETF
- paid vendor APIs unless later needed for reliability
- automatic classification from LLMs
- macro data that influences recommendations

Also avoid overengineering with:
- a database before local files become painful
- async data pipelines
- event-driven refresh jobs
- benchmark/performance analytics data feeds

---

## Practical v1 Data Contract

If the implementation wants the smallest workable contract, these three local files are enough:

1. `data/reference/security_master.csv`
   - authoritative metadata, expense ratios, classifications, index family
2. `data/prices/<as_of_date>/prices.csv` or `.parquet`
   - daily prices for held and candidate replacement tickers
3. `data/reference/macro_snapshot.csv`
   - optional, report-only macro context

This stack is sufficient for:
- valuation cross-checks
- overlap scoring
- fee comparison
- replacement screening
- asset-location heuristics
- deterministic report generation

---

## Final Recommendation

For the Tax-Aware Portfolio Decision Engine MVP, the best data approach is a **deterministic, mock-first, local-snapshot architecture**:

- **Prices:** `yfinance` for optional snapshot generation; local CSV/Parquet for runtime
- **ETF metadata / expense ratios:** local curated `security_master.csv` as runtime truth, optionally seeded from `yfinance`
- **Ticker classification:** local hand-curated taxonomy in the security master, with optional manual look-through overrides later
- **Macro data:** `fredapi` for optional snapshot generation; local CSV only for read-only report context

This is the most practical v1 because it is:
- cheap
- offline-friendly
- testable
- easy to audit
- aligned with the spec's requirement that recommendations come from deterministic rules rather than unstable external calls

## Concise v1 decision
Use **pandas + local snapshot files + provider interfaces** as the core architecture, with **`yfinance`** and **`fredapi`** limited to optional refresh tooling, not recommendation-time dependencies.