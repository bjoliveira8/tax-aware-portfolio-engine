# Code Quality & Bug-Hunt Review — Tax-Aware Portfolio Decision Engine

Scope: bug-hunting and code-quality only (feature-completeness owned by a separate agent).
Test status confirmed: `python -m pytest -q` → 16 passed.

---

## CRITICAL findings (correctness / constraint violations)

### C1. `tax_loss_harvest` recommendation carries NO tax estimate and NO "tax impact unknown" flag
File: `core/recommendation_engine.py:396-412`

A tax-loss harvest is a taxable sale. The Non-Negotiable Constraint states: *"No taxable-sale
recommendation without a tax estimate OR an explicit 'tax impact unknown' flag."* The harvest branch
builds the recommendation with `tax_notes=wash.notes` only — it never calls `estimate_sale_tax`. Observed
on mock data:

```
tax_loss_harvest VXUS TAX-1 | tax_notes: ['61-day wash-sale check passed across all accounts.']
tax_loss_harvest ARKK TAX-1 | tax_notes: ['61-day wash-sale check passed across all accounts.']
tax_loss_harvest BND  TAX-1 | tax_notes: ['AGG shares same index family ...; gray zone.', ...]
```

None of these carry a tax estimate or an "unknown" flag. This is a direct constraint violation. (The
test `tests/test_report.py` asserts `tax_notes` is non-empty for harvests, but a wash-sale note is not a
tax estimate, so the test passes while the constraint is still violated — see T1.)

### C2. `evaluate_asset_location` crashes on `account_type == "other"` (and any type absent from a priority list)
File: `core/asset_location_engine.py:6-11, 24`

`location_priority` returns 6-element lists; none of the three branches include `"other"`. Line 24 calls
`preferred.index(current_type)`, which raises `ValueError: 'other' is not in list` for any holding in an
`other` account. `other` is a documented `AccountType` (schemas.py:8). Reproduced:

```
CRASH: ValueError 'other' is not in list
```

The whole `generate_recommendations` pipeline (and the CLI) aborts for any portfolio containing an
`other`-type account. Use `preferred.index(current_type) if current_type in preferred else -1`, or
append the missing types.

### C3. Concentration is computed per-holding-row on TOTAL-portfolio weight, not aggregated per ticker
File: `core/overlap_engine.py:64-70` and `recommendation_engine.py:133-134`

`concentration_flags` iterates each holding row and flags `weight = market_value/total` individually.
A ticker split across two accounts is never summed, so true single-name concentration is **understated**
(a name that is 12% in taxable + 10% in IRA = 22% total is never flagged). Conversely the same ticker in
two accounts produces **two** single-name flags. Then `recommendation_engine.py:133-134` resolves each
flag with `next(hold for hold in holdings if hold.ticker == item["ticker"])` — it ignores `account_id`
and grabs the *first* matching holding. This is order-dependent and can attribute the wrong account/tax
treatment to the trim/block. Demonstrated: with the same ticker in TAX and IRA, the holding chosen flips
purely based on list order, changing whether a taxable tax-cost block is applied. This is both a
correctness bug and a potential constraint risk (could pick the tax-advantaged row and skip the tax
check that the taxable position needed).

---

## HIGH findings

### H1. Cash is treated as a relocatable asset, producing nonsensical "relocate CASH" recommendations
File: `core/asset_location_engine.py` + `recommendation_engine.py:92-129`

`CASH` (asset_class `cash`) falls into the default location branch whose top preference is `taxable`.
Cash held in a Roth or HSA therefore has `preferred.index(roth_ira)=1 > 0` and is flagged for relocation
*out of* the tax-advantaged account *into* taxable. Observed on mock data:

```
relocate CASH ROTH-1 ...
relocate CASH HSA-1  ... ('CA/NJ users should confirm HSA state tax treatment.')
```

Recommending moving cash from a Roth/HSA to a taxable account is backwards and not a real location
improvement. Cash (and individual stocks with no location thesis) should be excluded from
`evaluate_asset_location`.

### H2. Same position yields multiple contradictory recommendations (no cross-category reconciliation)
File: `core/recommendation_engine.py` (whole flow)

Each analysis stage appends independently; dedup at line 414 only collapses identical
`recommendation_id`s. On mock data a single holding gets mutually inconsistent advice:

- `FXNAX (IRA-1)`: `trim` (concentration) AND `hold/menu-block-fee` AND `hold/menu-block-overlap`
  simultaneously — "trim it" and "hold it" at once.
- `AAPL (TAX-1)`: `do_nothing_due_to_tax_cost` emitted twice (once from the location block, once from the
  concentration block).
- `BND (TAX-1)`: `relocate` + `trim` + `tax_loss_harvest` all at once.

There is no priority/conflict resolution to ensure one coherent action per (ticker, account). This
undermines the report's "Do these N things" bottom line and risks presenting a hold and a sell for the
same lot.

### H3. Harvest replacement chosen from `wash.safe_replacements[0]` but candidate set is unordered/asset-class-wide
File: `core/recommendation_engine.py:357, 377`

`replacements` is built from every same-`asset_class` security via a dict comprehension over
`security_master.items()` (insertion-ordered, effectively arbitrary). `wash.safe_replacements[0]` then
picks the first survivor with no ranking on overlap quality, expense ratio, or liquidity (even though
`etf_replacement.rank_replacements` exists for exactly this). The "substantially-different replacement"
is essentially random among the safe set. For BND it happened to pick IEF, but nothing guarantees a
sensible choice.

---

## MEDIUM findings

### M1. Magic number `confirm_with_cpa_above / 4` for the short-term-gain block
File: `core/tax_lot_engine.py:34`

The short-term-gain suppression threshold is hard-coded as `confirm_with_cpa_above / 4` (=$1,250 with
defaults). The plan says thresholds live in `thresholds.yml`; this one is invented inline and
undocumented. Should be a named, config-driven threshold.

### M2. Config files in `config/` are largely dead/duplicated
Files: `config/thresholds.yml`, `config/model_portfolios.yml`, `config/tax_assumptions.yml`,
`config/account_menus.yml` vs `app/config.py:36`

`load_config` only reads `config/default.yml`. All other YAML files (thresholds, model_portfolios,
tax_assumptions, account_menus) are never loaded — `default.yml` re-declares the same data. These files
are dead config; editing them has no effect, which is a maintenance trap. `account_menus.yml` is also
never used (menus come from a CSV).

### M3. Hard-coded thesis keys for the two `do_nothing_due_to_tax_cost` blocks
File: `core/recommendation_engine.py:110` (`"tax-cost-block-location"`) and `:151`
(`"concentration-tax-block"`)

Unlike the other thesis keys these are not parameterized by ticker. They are saved from collision only
because `Recommendation.build_id` also hashes the ticker. Fragile-by-accident; should be
`f"...-{ticker}"` for consistency and to survive any future change to the ID scheme.

### M4. NIIT rate hard-coded as `0.038`
File: `core/tax_lot_engine.py:31`

`rate += 0.038` — another magic literal that belongs in the `TaxProfile`/config rather than inline.

### M5. `_normalized_rounded` silently forces the last dict key to absorb all rounding error
File: `core/allocation.py:8-14`

It overwrites the last key with `1.0 - sum(others)`. If allocations don't actually sum to ~1 (e.g.
partial data, or a target that intentionally doesn't total 1), this masks the discrepancy by dumping it
into whatever key happens to be last (dict-insertion-ordered). It guarantees the "sums to 100%" test
passes regardless of input validity, which is a tautology risk for `test_allocation.py`.

### M6. Drift engine keys recommendations by `asset_class` string in the `ticker` field
File: `core/recommendation_engine.py:331-345`

Drift recommendations set `ticker=asset_class` (e.g. `ticker="taxable_bond"`) and `account_id=None`. The
`Recommendation.ticker` field is thereby overloaded to sometimes hold an asset class, which the report
prints as `REBALANCE taxable_bond`. Mixing semantic types in one field is a separation-of-concerns smell
and could confuse any downstream consumer that assumes `ticker` is a real instrument.

---

## LOW findings

### L1. `_holding_for` / `next(...)` raise `StopIteration` if data is inconsistent
File: `core/recommendation_engine.py:67, 134, 177`

`_holding_for` and the inline `next(...)` generators assume the holding always exists. A suggestion or
flag referencing a ticker/account not present in `holdings` raises an uncaught `StopIteration`. Low
likelihood given current flow, but no defensive handling.

### L2. `security_master[holding.ticker]` will `KeyError` on any ticker missing from the master
File: `core/recommendation_engine.py:236, 352`; `core/allocation.py:21`; `core/overlap_engine.py:16`

Ingestion accepts any holding/ticker (only warns on regex-invalid tickers), but every downstream engine
indexes `security_master[ticker]` directly. A valid-looking ticker with no master entry crashes the
whole analysis. No graceful "unknown security" handling.

### L3. `is_long_term` uses `> 365`; boundary day 365 treated as short-term
File: `data/loaders.py:93`

The IRS long-term boundary is "more than one year." `holding_period_days > 365` is defensible, but the
holding-period column can also be supplied directly and is trusted without cross-checking against
`acquired_date`, so a stale/incorrect supplied value silently changes tax rate selection.

### L4. `redundant_pairs` only catches `overlap_score == 1.0` (same index family)
File: `core/overlap_engine.py:81` (default `minimum_score=1.0`), called at `:176`

The plan's overlap tiers include 0.7 (same class+region+style). Only exact index-family redundancy
(1.0) is ever surfaced as redundant; 0.7-level near-duplicates are never flagged. Arguably by design,
but it means the look-through/0.7 logic is computed and then ignored for redundancy.

### L5. `report_generator` distinguishes "no action" by matching a magic rationale string
File: `reporting/report_generator.py:50`

`recommendations[0].rationale == ["No action is justified."]` couples the report to an exact string
produced in the engine. A reworded rationale would silently break the "No action" bottom line. A typed
flag (e.g. `action == "hold" and thesis_key == "no-action"`) would be safer.

### L6. `fee_drag_bps` mixes expense ratios that may be `None` and weights by market value only
File: `app/cli.py:54-59`

Reasonable, but holdings with `expense_ratio=None` (cash, individual stocks) are treated as 0% fee,
silently diluting the blended fee-drag number. Acceptable, noted for transparency.

---

## Test-quality assessment

Overall the tests are **behavioral and mostly meaningful** (they exercise the real engine on real mock
data and assert on action shapes), which is good. Weaknesses:

- **T1.** `tests/test_report.py` asserts harvest/sale recommendations have *non-empty* `tax_notes`, but
  does not assert the note contains an actual tax *estimate*. This is why C1 (harvest with no tax
  estimate) passes CI while violating the constraint. The assertion is too weak to enforce the doctrine.
- **T2.** No test covers an `other` account type, so C2 (crash) is undetected.
- **T3.** No test covers a single ticker held across multiple accounts, so C3 (concentration
  understatement / wrong-holding selection) is undetected.
- **T4.** `tests/test_allocation.py` asserts `sum(current.values()) == 1.0` and `sum(target) == 1.0` —
  but `_normalized_rounded` (M5) forces this to be true by construction, so the assertion is close to
  tautological.
- **T5.** The Phase-9 "contrarian" tests are valuable and assert real no-influence / wash-sale / menu
  behavior, but they only probe the happy paths the engine already handles; they don't construct the
  multi-account concentration or `other`-account adversarial cases that expose C2/C3.
- **T6.** No edge-case tests: empty portfolio, zero/negative market value, all-`None` cost basis at the
  pipeline level, ticker missing from the security master (L2).

---

## Overall code-quality verdict

**Strengths**
- Clean module separation (data / core / reporting / app) with a `DataProvider` Protocol enabling
  network-free fixtures — the no-network constraint is structurally respected.
- `recommendation_id` and `snapshot_id` use SHA-256 (`schemas.py:74`, `process_log.py:10`), so they are
  **deterministic across processes** — the salted-`hash()` determinism trap was correctly avoided.
- Tax-impact-unknown handling for missing cost basis is correct (`tax_lot_engine.py:19,26`): it never
  emits a confident sell, satisfying that constraint.
- Wash-sale window is correct (±30 days = 61-day window) and scans all accounts including IRA/Roth, with
  a distinct permanent-loss status for retirement-account repurchases (`wash_sale_guard.py:28-40`).
- Type hints, dataclasses with `slots`, and `from __future__ import annotations` throughout; readable.

**Weaknesses**
- **The harvest path violates the tax-note constraint (C1)** — the single most important defect.
- A guaranteed crash on a documented account type (C2).
- Concentration math is per-row on portfolio-total weight rather than aggregated per ticker, and the
  engine selects holdings by ticker ignoring account (C3) — order-dependent and incorrect.
- No reconciliation between analysis stages, so positions accumulate contradictory recommendations (H2).
- Several magic numbers (`/4`, `0.038`) outside the centralized thresholds the plan mandates (M1, M4).
- Dead/duplicated config files (M2) create a maintenance trap.
- Sparse docstrings across core modules; the engine's priority/dedup logic in particular is undocumented.

**Bottom line:** architecture and determinism are solid, but there is one CRITICAL constraint violation
(C1: harvest without tax estimate), one CRITICAL crash (C2), and one CRITICAL correctness bug in
concentration handling (C3), all of which slip past the current test suite because the assertions are
too shallow.
