# Remediation & Improvement Plan — Tax-Aware Portfolio Decision Engine

Primary inputs: `outputs/COMPREHENSIVE_REVIEW.md`, `outputs/review_gap_analysis.md`,
`outputs/review_code_quality.md`. Original doctrine: `tax_aware_portfolio_engine_execution_plan.md`.
Baseline: `python -m pytest -q` → **16 passed**.

This is a PLAN ONLY — no source was changed in producing it. Every item references the finding IDs
(C1–C3, H1–H3, M1–M6, L1–L6, T1–T6) from the comprehensive review for traceability.

## Doctrine guardrails that every item below must respect
- No LLM or macro influence over any recommendation, urgency, or score (no new code path may add one).
- All tests stay network-free; only `test_cli_e2e` may spawn a local subprocess.
- Determinism preserved: keep SHA-256 `recommendation_id` / `snapshot_id`; never use salted `hash()`;
  any new ordering must have a stable tiebreak (e.g. `recommendation_id`).
- No Do-Not-Build capability (optimizer, screener, scored lenses, benchmark tracking, macro tactical
  reallocation, news ingestion) may be introduced.
- "No action when none justified" must remain reachable and tested after every change.
- Thresholds/assumptions belong in `config/*.yml`, not inline literals.

Effort key: **S** ≤ ~1h, **M** ~2–4h, **L** ~1 day+. Each item lists the exact test(s) that must go
green to call it done.

---

# Wave 1 — CRITICAL correctness / constraint fixes

These three block shipping and all currently pass CI only because assertions are too shallow. Fix the
code AND tighten/add the test that would have caught it. Do Wave 1 first; nothing else matters until the
suite actually guards the doctrine.

## C1 — `tax_loss_harvest` carries no tax estimate / no "tax impact unknown" flag
**File:** `core/recommendation_engine.py:396-412` (harvest branch).
**Why:** A TLH is a taxable sale. Constraint: *no taxable-sale rec without a tax estimate OR explicit
"tax impact unknown" flag.* The branch builds `tax_notes=wash.notes` only — it never calls
`estimate_sale_tax`. Direct constraint violation, masked by T1.

**Change:**
1. In the harvest branch, before building the rec, compute
   `tax_check = estimate_sale_tax(lots_for_holding(lots, holding), tax_profile)`.
2. Build `tax_notes = [*tax_check.tax_notes, *wash.notes]` so the estimate (or the
   `"tax impact unknown"` / `"No lot data available; tax impact unknown"` note from
   `tax_lot_engine.py:19,26`) always precedes the wash-sale note.
3. Carry `confidence = tax_check.confidence` (drops to `"low"` when basis is unknown) so a
   missing-basis harvest cannot present as a confident sell — this simultaneously closes the unproven
   "missing-lots → no confident sell at recommendation level" gap (Gap §3 item 4).
4. A harvested loss lot has `unrealized_gain < 0`, so `estimate_sale_tax` returns a real summary note
   (`Estimated tax cost: $0.00 on estimated gain $-NNN`). That satisfies the constraint; keep it as-is
   rather than special-casing losses.

**Regression test (add to `tests/test_report.py`, or a new `tests/test_harvest_tax_note.py`):**
- `test_harvest_carries_tax_estimate`: run the engine on mock data; for every rec with
  `action == "tax_loss_harvest"`, assert at least one `tax_notes` entry matches the estimate/unknown
  shape — e.g. `any("Estimated tax cost" in n or "tax impact unknown" in n.lower() for n in rec.tax_notes)`.
  This must FAIL on today's code and PASS after the fix.
- `test_harvest_missing_basis_not_confident`: feed a loss holding whose lots have
  `cost_basis_per_share=None` / `unrealized_gain=None`; assert the harvest rec (if any) has
  `confidence == "low"` and a "tax impact unknown" note, and that no confident taxable sell is emitted.
- **Also tighten T1:** replace the blanket `all(item.tax_notes ...)` assertion in `test_report.py:26`
  with a per-action check that taxable-sale actions (`tax_loss_harvest`, `trim` in taxable, `replace`
  in taxable) carry an actual estimate token, not merely a non-empty list.

**Acceptance:** new tests green; existing `test_golden_path` still asserts
`("tax_loss_harvest","VXUS","TAX-1","VEA")`. **Effort: S. Risk: Low** (additive to one branch).
**Dependencies:** none.

## C2 — `evaluate_asset_location` crashes (`ValueError`) on `account_type == "other"`
**File:** `core/asset_location_engine.py:6-11, 24`.
**Why:** `location_priority` returns 6-element lists that never include `"other"`; `preferred.index(
current_type)` raises `ValueError` for any `other` holding, aborting the whole pipeline + CLI. `other`
is a documented `AccountType` (`schemas.py:8`). Masked by T2 (no `other` test).

**Change:** in `evaluate_asset_location` (line 24), guard the lookup:
```python
if current_type not in preferred:
    continue          # unknown/unsupported account type → no location opinion
rank = preferred.index(current_type)
if rank > 0:
    ...
```
Equivalently append `"other"` to the tail of each list in `location_priority`, but the
`continue`-on-absent approach is safer because it also protects against any future `AccountType`
addition (defensive against the general "type absent from a priority list" failure the review notes).

**Regression test (`tests/test_asset_location.py` new, or extend `test_actions.py`):**
- `test_other_account_does_not_crash`: build a `Holding` with `account_type="other"` and run
  `generate_recommendations`; assert it returns without raising and produces a coherent rec set (no
  relocate rec targeting/originating the `other` account). Must crash on today's code.

**Acceptance:** test green; full suite green. **Effort: S. Risk: Low.** **Dependencies:** none.

## C3 — Concentration computed per-row on total weight, never aggregated per ticker; resolver ignores account
**Files:** `core/overlap_engine.py:59-79` (`concentration_flags`);
`core/recommendation_engine.py:133-134`.
**Why:** `concentration_flags` flags each holding ROW on `market_value/total`. A ticker split across two
accounts (12% + 10% = 22%) is never summed → single-name concentration **understated**; the same ticker
in two accounts produces TWO flags. Then `recommendation_engine.py:134`
`next(hold for hold in holdings if hold.ticker == item["ticker"])` ignores `account_id` and grabs the
first match → order-dependent wrong-account/tax attribution, and can skip the tax check the taxable
position needed (constraint risk). Masked by T3 (no multi-account ticker test).

**Change (two parts):**
1. **Aggregate in `overlap_engine.concentration_flags`:** sum `market_value/total` per ticker across
   accounts before comparing to `single_name_threshold`. Emit ONE single-name flag per ticker with the
   aggregated weight, plus the per-account breakdown, e.g.:
   ```python
   ticker_weight = defaultdict(float)
   ticker_accounts = defaultdict(list)
   for h in holdings:
       w = h.market_value / total
       ticker_weight[h.ticker] += w
       ticker_accounts[h.ticker].append(h.account_id)
   single_name = [
       {"ticker": t, "weight": round(w, 4), "account_ids": ticker_accounts[t]}
       for t, w in ticker_weight.items() if w > single_name_threshold
   ]
   ```
2. **Fix the resolver in `recommendation_engine.py:133-158`:** iterate the flagged ticker's accounts
   (`item["account_ids"]`) and emit a per-account decision, running the taxable tax-cost check against
   the correct `(ticker, account_id)` lots via `_holding_for(holdings, ticker, account_id)`. This makes
   the taxable-vs-advantaged branch correct per lot and removes the order dependence. Reuse
   `_holding_for` (and harden it per L1 below) instead of the bare `next(...)`.

**Regression test (`tests/test_concentration_multi_account.py` new):**
- `test_single_name_aggregated_across_accounts`: same ticker at 12% in `TAX-1` and 10% in `IRA-1`
  (combined 22% > 15% threshold) → assert exactly ONE single-name flag with `weight ≈ 0.22`. Today's
  code either misses it (each row < 15%) or double-flags.
- `test_concentration_uses_correct_account_tax_treatment`: a taxable lot with a large embedded gain and
  an IRA lot of the same ticker → assert the taxable position gets the tax-cost branch
  (`do_nothing_due_to_tax_cost` or tax-noted trim) regardless of holding list order; shuffle the input
  order in a parametrized case to prove order-independence.

**Acceptance:** both tests green; `test_overlap.py`'s existing single-name/account-concentration
assertions still pass (adapt them to the new flag shape if they index `weight`).
**Effort: M. Risk: Med** (touches the shape consumed by the rec engine + grade penalty count).
**Dependencies:** none, but coordinate with H2 (reconciliation consumes concentration recs).

**Wave 1 gate:** all three new/tightened tests fail on `HEAD~0` and pass after fixes; full suite green;
golden-path + no-action-balanced still green.

---

# Wave 2 — HIGH issues

## H1 — Cash (and location-less individual stocks) treated as relocatable → "relocate CASH out of Roth/HSA"
**Files:** `core/asset_location_engine.py:6-36`; surfaces via `recommendation_engine.py:92-129`.
**Why:** `cash` falls into the default branch whose top preference is `taxable`, so cash in a Roth/HSA
gets `preferred.index(roth_ira)=1 > 0` → flagged to relocate *into* taxable. Backwards.

**Change:** at the top of the `evaluate_asset_location` loop, skip securities that have no genuine
location thesis:
```python
if meta.asset_class == "cash" or meta.security_type == "equity_single_stock":
    continue
```
(Confirm the single-stock discriminator against `security_master.csv` columns — use `asset_class
== "cash"` at minimum; extend to individual stocks only if a clean field exists, else leave stocks
alone to avoid scope creep.) This composes cleanly with the C2 `continue` guard.

**Test (extend `tests/test_asset_location.py`):**
- `test_cash_not_relocated`: cash held in `ROTH-1` and `HSA-1` → assert no `relocate` (or
  `redirect_contributions`) recommendation names `CASH`.

**Acceptance:** test green; golden-path BND relocate still fires (BND is a `taxable_bond`, unaffected).
**Effort: S. Risk: Low.** **Dependencies:** C2 (same function).

## H2 — No cross-stage reconciliation → one position gets contradictory recs
**File:** `core/recommendation_engine.py` (whole flow; dedup at `:414` only collapses identical IDs).
**Why:** Each stage appends independently. On mock data `FXNAX (IRA-1)` gets `trim` + two menu-block
`hold`s; `AAPL (TAX-1)` gets `do_nothing_due_to_tax_cost` twice; `BND (TAX-1)` gets
`relocate`+`trim`+`tax_loss_harvest`. Undermines "Do these N things" and can present hold + sell for the
same lot.

**Change:** add a reconciliation pass AFTER all stages append and BEFORE the final `unique`/`sorted`
block at `:414`. Keep it deterministic and rules-only (no scoring black box):
1. Group recs by `(ticker, account_id)`.
2. Within a group, keep at most one *directional* action using the existing `PRIORITY_RANK`
   (`relocate < trim < tax_loss_harvest < replace < rebalance < add < do_nothing < hold`), with
   `URGENCY_RANK` then `recommendation_id` as tiebreaks — i.e. the same ordering already used at `:415`.
   Drop lower-priority directional actions that conflict (e.g. a `hold`/menu-block when a `trim` for the
   same lot survives; a duplicate `do_nothing_due_to_tax_cost`).
3. Preserve transparency: when a rec is suppressed by a higher-priority one, append a one-line note to
   the surviving rec's `rationale` (e.g. `"Supersedes a lower-priority <action> on this position."`) so
   nothing is silently hidden (respects the "never hide a prior recommendation" constraint — the
   superseded action is disclosed, not erased).
4. Drift recs (`account_id=None`, asset-class "ticker") are portfolio-level and must NOT be merged with
   per-position recs — key reconciliation on the literal `(ticker, account_id)` tuple so `None`-account
   drift recs stay separate.

Document the reconciliation contract in a module docstring (the review flags undocumented priority/dedup
logic).

**Test (`tests/test_reconciliation.py` new):**
- `test_one_directional_action_per_position`: run on mock data; assert for every `(ticker, account_id)`
  with `account_id is not None` there is at most one directional (non-`hold`) action.
- `test_no_hold_and_sell_same_lot`: assert no `(ticker, account_id)` simultaneously has a `hold` and a
  `trim`/`replace`/`tax_loss_harvest`.
- `test_no_duplicate_do_nothing`: assert `AAPL TAX-1` yields a single `do_nothing_due_to_tax_cost`.
- `test_supersede_note_present`: when a conflict is resolved, the surviving rec discloses it in
  `rationale`.

**Acceptance:** tests green; golden-path still asserts its three expected actions (verify BND collapses
to the single highest-priority intended action — likely `relocate`; if golden-path expects BND
`relocate`, ensure reconciliation keeps it). Re-check `test_golden_path` after the change and adjust the
fixture/assertion only if the *intended* coherent action differs, documenting why.
**Effort: M. Risk: Med-High** (changes the rec set shape; golden-path may need re-baselining).
**Dependencies:** C3 (concentration recs feed in), H1 (removes spurious cash relocates first).

## H3 — Harvest replacement = `wash.safe_replacements[0]` (unordered, asset-class-wide); `rank_replacements` unused
**File:** `core/recommendation_engine.py:357, 377`.
**Why:** `replacements` is built from every same-`asset_class` security in insertion order;
`safe_replacements[0]` then picks the first survivor with no ranking on overlap/expense/liquidity even
though `etf_replacement.rank_replacements` exists for exactly this. Replacement is effectively random.

**Change:** after the wash-sale screen returns `wash.safe_replacements`, rank them:
```python
ranked = rank_replacements(holding.ticker, wash.safe_replacements, security_master, overlap_engine)
ranked = [r for r in ranked if r["liquidity_ok"] and r["overlap"] >= 0.4]
replacement = str(ranked[0]["ticker"]) if ranked else None
```
Require similar exposure (overlap ≥ 0.4) and adequate liquidity, matching the fee-replacement path's
gate at `:244`. If no ranked candidate survives, fall back to the existing wash-blocked/menu-blocked
`hold` path rather than emitting an arbitrary pick. Keep `menu_allows` check afterward (already present
at `:378`).

**Test (`tests/test_harvest_replacement.py` new):**
- `test_harvest_replacement_is_ranked`: provide two wash-safe candidates — one low-fee/liquid/high-overlap,
  one illiquid or low-overlap — assert the chosen `replacement_ticker` is the better-ranked one,
  deterministically. (Golden path already asserts VXUS→VEA; this proves it's chosen by rank, not order.)
- `test_harvest_no_replacement_when_none_suitable`: all candidates illiquid → assert no
  `tax_loss_harvest` with an arbitrary replacement; falls back to `hold`.

**Acceptance:** tests green; golden-path VXUS→VEA preserved (verify VEA still ranks first among VXUS's
safe set). **Effort: M. Risk: Med** (golden-path sensitive). **Dependencies:** none, but verify against
golden-path after C3/H2.

**Wave 2 gate:** H1–H3 tests green; golden-path re-validated and any re-baseline documented.

---

# Wave 3 — Config system rewire & uniform menu validation

## M2 — Load all four `config/*.yml`, real multi-file precedence, reconcile `account_menus.yml` vs CSV
**Files:** `app/config.py:30-42`; `config/{thresholds,model_portfolios,tax_assumptions,account_menus}.yml`;
`data/mock_account_menus.csv`.
**Why:** `load_config` reads only `default.yml`; the other four YAMLs are dead duplicates (editing them
has no effect). `account_menus.yml` even disagrees with the CSV actually used (YAML `IRA-1` lists
`[BND,VXUS,VEA,VTI,VTV,AVUV,AGG]`; CSV `IRA-1` lists only `FXNAX`). Phase 0 precedence chain
(`defaults < file < CLI flag`) is unbuilt across files.

**Change:**
1. In `load_config`, aggregate the standalone files into the merged config under their namespaces, then
   apply `default.yml`, then the optional `--config` file, then CLI overrides — preserving the documented
   precedence `defaults < file < CLI flag`. Concretely, load each of
   `thresholds.yml → config["thresholds"]`, `model_portfolios.yml → config["model_portfolios"]`,
   `tax_assumptions.yml → config["tax_profile"]`, then `deep_merge` `default.yml` on top (so `default.yml`
   remains the canonical override layer), then file, then CLI. Use the existing `deep_merge`.
2. **Resolve the duplication trap:** make `default.yml` NOT re-declare the standalone-file contents;
   instead let the standalone files be the source of truth and `default.yml` hold only `defaults:`
   (as_of_date, target_profile). Document the layering in a header comment. (Decide ownership explicitly
   so editing a standalone file has effect — that is the whole point of the fix.)
3. **Reconcile menus:** pick ONE source of truth. Recommended: keep the CSV (`mock_account_menus.csv`)
   as the runtime menu source for mock data and DELETE or regenerate `config/account_menus.yml` so it
   matches, OR wire `account_menus.yml` into `load_config` and have the loader prefer it — but do not
   leave two disagreeing sources. Whichever is chosen, update the CSV/YAML so `IRA-1` agrees (the
   `FXNAX`-only CSV menu is what drives the current menu-block recs in mock data; changing it will move
   golden-path behavior, so prefer making the YAML match the CSV unless intentionally re-baselining).
4. Have `app/cli.py` consume the aggregated config so thresholds/tax_profile/model_portfolios flow from
   the merged result, not hard-coded dicts.

**Test (extend `tests/test_config.py`):**
- `test_multifile_aggregation`: write a tmp `config/` with distinct values in each of the five files and
  assert `load_config` exposes all namespaces with correct values.
- `test_precedence_across_files`: a CLI override beats a `--config` file value, which beats a standalone
  file value, which beats nothing. Must exercise a key that originates in a standalone file (e.g.
  `thresholds.single_name_threshold`).
- `test_menu_source_single_truth`: assert the runtime menu for `IRA-1` matches between the chosen source
  and what the engine sees (no silent disagreement).

**Acceptance:** new config tests green; existing `test_config.py:7` precedence test still green; CLI e2e
still writes a report. **Effort: M. Risk: Med** (CLI wiring + possible golden-path menu shift — re-run
golden-path and document any re-baseline). **Dependencies:** none, but do AFTER Wave 2 so menu changes
don't churn the reconciliation baseline twice.

## Uniform account-menu validation across relocate & drift paths (constraint)
**Files:** `core/recommendation_engine.py:92-129` (relocate), `:304-346` (drift `add`/`rebalance`).
**Why:** `menu_allows` is applied to overlap-replace, fee-replace, and harvest paths but NOT to
`relocate` or drift `add`/`rebalance` recs (which carry `account_id=None`). Constraint "no rec of an
instrument the destination account can't hold" is non-uniformly enforced (Gap §4).

**Change:**
1. **Relocate path:** the relocate rec names a destination *account type*, not a concrete destination
   account/instrument, so a literal `menu_allows(ticker, dest_account)` is not directly applicable. The
   correct fix is to make the constraint *vacuously honored and documented*: when a relocate would imply
   buying `ticker` in a specific destination account, validate against that account's menu before
   recommending; if no concrete destination is named, add a rationale note that menu compatibility must
   be checked at execution and do not name a forbidden instrument. Keep it honest — don't fabricate a
   destination account_id just to run the check.
2. **Drift path:** these recs carry an asset-class string in `ticker` and `account_id=None` (see M6).
   Until M6 is addressed they name no concrete instrument, so menu validation is N/A by construction —
   document that explicitly in a comment so the gap is acknowledged, and revisit once M6 maps drift to
   real instruments/accounts.

**Test (extend `tests/test_actions.py`):**
- `test_relocate_respects_menu`: if a relocate names a concrete destination instrument the destination
  menu forbids, assert it is reframed/flagged (`hold` + menu note), never recommended.

**Acceptance:** test green; contrarian menu test still green. **Effort: S-M. Risk: Low.**
**Dependencies:** ties to M6 (Wave 4) for the drift half.

**Wave 3 gate:** config tests green; editing any standalone config file demonstrably changes behavior;
menu sources reconciled; relocate menu test green.

---

# Wave 4 — Test-coverage backfill (untested Exit Criteria) & hardening

The plan is test-driven; ~14 Exit Criteria are implemented-but-untested. Add the missing tests (Gap §3)
and fix the magic-number / edge-case items. Group as below.

## 4a. Backfill untested Exit Criteria (Gap §3) — all **S** each, **Risk: Low**, no production change unless noted
For each, add a focused test; if the criterion is genuinely unimplemented, implement minimally first.

| # | Criterion (Gap §3) | Test to add | Notes |
|---|---|---|---|
| 1 | Lower-fee but illiquid ETF not auto-preferred (Phase 6) | `test_illiquid_replacement_rejected`: candidate with lower fee but `avg_daily_dollar_volume < 5M` → not chosen | Code gate at `recommendation_engine.py:244` exists; just assert it |
| 2 | Replacement blocked in taxable on high gain, allowed in IRA (Phase 6) | `test_replace_blocked_taxable_allowed_ira`: same swap, two accounts, contrast | Code at `:247-266` |
| 4 | Missing lots → no confident sell at rec level (Phase 4) | covered by C1's `test_harvest_missing_basis_not_confident`; extend to trim/replace paths | overlaps C1 |
| 5 | Roth overweight trims with NO tax warning (Phase 4) | `test_roth_trim_no_tax_warning`: assert `tax_notes == ["No tax warning in tax-advantaged account."]` | code at `:156-157` |
| 6 | Taxable sale > `confirm_with_cpa_above` prints CPA note (Phase 4) | `test_cpa_note_on_large_sale`: assert string surfaces on a real rec | code at `tax_lot_engine.py:37-38` |
| 7 | Sector > 35% flagged (Phase 3) | `test_sector_concentration_flagged`: needs mock data with a sector > 35% | **also enrich `security_master.csv`** so `sector_focus` is meaningful beyond AAPL/ARKK |
| 8 | Sub-threshold drift → no trade (Phase 5) | `test_subthreshold_drift_no_trade`: within-tolerance drift → no rebalance/add rec | isolated drift unit |
| 9 | Growth asset preferred in Roth/HSA (Phase 5) | `test_growth_prefers_roth_hsa`: a `large_growth`/`small_value` holding steered to Roth/HSA | code at `asset_location_engine.py:9-11` |
| 10 | Report prints "No action is justified" (Phase 7) | `test_report_no_action_text`: balanced portfolio → rendered report contains the bottom line | rendered text, not engine |
| 11 | Re-run → no duplicate recs (Phase 7) | `test_rerun_deterministic_ids`: run twice, assert identical `recommendation_id` sets, no dupes | proves determinism |
| 12 | Report renders without optional engines (Phase 7) | `test_report_renders_minimal`: call `render_report` with empty/absent optional analysis keys | Phase 8 skipped |
| 13 | CLI prints accounts-detected + warnings (Phase 2) | extend `test_cli_e2e` to assert the accounts + warnings lines | `cli.py:69-72` |

## 4b. Magic numbers → config (M1, M4) — **S**, **Risk: Low**
- **M1** `core/tax_lot_engine.py:34` `confirm_with_cpa_above / 4`: add a named threshold
  `short_term_gain_block_threshold` to `thresholds.yml` (default 1250.0, or express as a documented
  fraction `short_term_gain_block_fraction: 0.25`), thread it through `estimate_sale_tax` via a param or
  the `TaxProfile`/thresholds dict. **Test:** `test_short_term_block_threshold_configurable` — change the
  config value and assert the block toggles.
- **M4** `core/tax_lot_engine.py:31` NIIT `0.038`: move to config/`TaxProfile` as `niit_rate` (default
  0.038), used only when `niit_applies`. **Test:** `test_niit_rate_from_config`.

## 4c. Determinism / clarity hardening (M3, M5, L5) — **S**, **Risk: Low**
- **M3** `recommendation_engine.py:110,151`: parameterize the two `do_nothing_due_to_tax_cost` thesis
  keys with the ticker (`f"tax-cost-block-location-{ticker}"`, `f"concentration-tax-block-{ticker}"`) so
  ID uniqueness doesn't depend on the hash incidentally including ticker. **Test:** covered by
  `test_rerun_deterministic_ids` + a uniqueness assertion across two same-account blocks.
- **M5** `core/allocation.py:8-14`: stop forcing the last key to absorb rounding error silently. Instead
  normalize proportionally (divide each by the true sum) and, if the raw sum deviates from 1.0 beyond a
  small epsilon, surface a warning rather than hiding it. This de-tautologizes T4. **Test:** rewrite
  `test_allocation.py` so the sum-to-1 assertion is meaningful — feed inputs that do NOT sum to 1 and
  assert a warning/flag, and feed valid inputs and assert correct normalization.
- **L5** `reporting/report_generator.py:50`: detect "no action" via a typed flag instead of matching the
  magic rationale string — e.g. `recommendations[0].thesis_key == "no-action"`. **Test:**
  `test_no_action_detection_robust` — reword the rationale and assert the bottom line still renders
  "No action is justified."

## 4d. Edge-case guards (L1, L2, L6, T6) — **S-M**, **Risk: Low**
- **L1** `recommendation_engine.py:67,134,177`: make `_holding_for`/inline `next(...)` defensive — return
  `None` and skip rather than raise `StopIteration` on inconsistent data. **Test:** `test_missing_holding_skipped`.
- **L2** `security_master[ticker]` KeyErrors (`recommendation_engine.py:236,352`, `allocation.py:21`,
  `overlap_engine.py:16`): add graceful "unknown security" handling — either skip with a warning or
  validate at ingestion that every holding ticker exists in the master. Prefer ingestion-time validation
  so the failure is reported as a warning (consistent with the existing invalid-ticker warning).
  **Test:** `test_unknown_ticker_warns_not_crashes`.
- **L6** `app/cli.py:54-59`: when computing `fee_drag_bps`, exclude (don't zero-fill) holdings with
  `expense_ratio is None`, or document the choice. **Test:** `test_fee_drag_excludes_none_expense`.
- **T6 edge cases:** add `tests/test_edge_cases.py` — empty portfolio (→ "No action is justified."),
  zero/negative market value (handled, no div-by-zero — `or 1.0` guards exist; assert no crash),
  all-`None` cost basis at pipeline level (→ no confident sells).

## 4e. Optional low-priority correctness (L3, L4) — **S**, **Risk: Low**, defer if time-boxed
- **L3** `data/loaders.py:93`: cross-check supplied `holding_period_days` against `acquired_date` and
  warn on mismatch; keep `> 365` boundary (defensible). **Test:** `test_holding_period_cross_check`.
- **L4** `overlap_engine.py:81,176`: optionally surface 0.7-tier near-duplicates as a softer redundancy
  signal (or document that only 1.0 is treated as redundant by design). Lowest priority.

**Wave 4 gate:** all ~14 backfilled Exit-Criteria tests green; magic numbers config-driven with tests;
T4 no longer tautological; edge-case suite green. Total suite count should rise from 16 to ~35+.

---

# Wave 5 — Optional / enhancement

Only after Waves 1–4. These extend capability without violating doctrine. Each is independently shippable.

## 5a. Specific-lot vs FIFO selection (Phase 4, Gap §3 item 3) — **L**, **Risk: Med**
**File:** `core/tax_lot_engine.py` (`estimate_sale_tax`, `lots_for_holding`).
**Why:** The engine sums ALL lots; the plan explicitly requires specific-lot vs FIFO selection. This is
a genuine missing capability, not just a test gap.
**Change:** add a lot-selection function `select_lots(lots, method, shares_to_sell)` supporting `"fifo"`
(oldest `acquired_date` first) and `"specific_lot"` (minimize realized gain / prefer losses then
long-term). `estimate_sale_tax` takes the selected subset. Keep it deterministic (stable sort on
`acquired_date`, then `recommendation_id`-style tiebreak). Default method config-driven in
`thresholds.yml`/`tax_assumptions.yml`. No optimizer — this is rule-based lot ordering, allowed.
**Test:** `test_lot_selection_fifo_vs_specific`: same holding, two methods, assert different (correct)
estimated gains; `test_specific_lot_prefers_losses`.
**Acceptance:** tests green; golden-path tax estimates re-validated.
**Dependencies:** C1 (harvest now calls `estimate_sale_tax`).

## 5b. Drift recs map to real instruments/accounts (M6) — **M**, **Risk: Med**
**File:** `core/recommendation_engine.py:304-346`.
**Why:** Drift recs overload `ticker` with an asset-class string and set `account_id=None`; report prints
`REBALANCE taxable_bond`. Separation-of-concerns smell and blocks uniform menu validation (Wave 3).
**Change:** add an explicit `asset_class` field to `Recommendation` (additive, like the existing
`replacement_ticker`/`thesis_key`) OR resolve drift to a concrete instrument + account using existing
holdings/menus, then run `menu_allows`. Update `report_generator` to render asset-class rebalances
clearly. Completes the drift half of the uniform-menu-validation item from Wave 3.
**Test:** `test_drift_rec_names_real_instrument_or_class_field`; `test_drift_respects_menu`.
**Dependencies:** Wave 3 (menu uniformity).

## 5c. Phase 8 scenario stress (optional, was deliberately skipped) — **L**, **Risk: Med**
Only if there is appetite; the plan permits skipping (`PHASE_8_DECISION.md`). If built: documented
asset-class × scenario shock matrix in `config/scenario_shocks.yml`, results as a range + confidence tag
+ "assumption-based, not a forecast" note; **macro/scenario output is read-only and MUST NOT change any
recommendation/urgency/score**. **Test (mandatory):** `test_scenario_no_influence` — assert the rec set
is byte-identical with and without scenario stress; `test_concentrated_stresses_worse_than_balanced`
(deterministic on mock data). Keep the no-influence assertion as the gate.

## 5d. True generative contrarian harness for Phase 9 (Gap §3 item 5 / Phase 9 intent) — **L**, **Risk: Low**
**Why:** Current Phase 9 is a static test file, not the generative contrarian *subagent* the plan
describes. Functional coverage is good; mechanism diverges.
**Change:** build a deterministic adversarial-portfolio *generator* (`tests/contrarian/generate.py` or a
fixture factory) that programmatically constructs portfolios targeting each of the five constraint
categories — including the multi-account-concentration and `other`-account cases that today's contrarian
tests miss (T5) — and asserts zero violations. Keep it network-free and deterministic (seeded). This is
a test/verification harness, not an LLM agent — no LLM may judge or alter recs.
**Test:** `test_contrarian_generated_suite` — all generated adversarial cases pass; explicitly include
`other`-account (C2) and multi-account single-name (C3) attacks.

**Wave 5 gate:** each enhancement's tests green; the no-influence assertion (5c) and contrarian suite
(5d) pass; doctrine unviolated.

---

# Definition of Done (updated)

Maps the original plan's DoD plus the new fixes. The project is done when ALL hold:

**Original DoD (from the execution plan):**
- [ ] All phases passed their gates; full suite + golden-path green; contrarian clean.
- [ ] Runs on mock data — no broker, no paid data, no network.
- [ ] Balanced portfolio → "No action is justified." (now asserted at *rendered-report* level — Wave 4 #10).
- [ ] Golden-path → expected tax-aware, account-aware action set (re-baselined after H2/H3 if needed).
- [ ] No Do-Not-Build item in the codebase (re-confirm after every wave).

**New / strengthened (from this remediation):**
- [ ] **C1:** every `tax_loss_harvest` (and every taxable trim/replace) carries a tax estimate OR a "tax
  impact unknown" flag; T1 tightened so this cannot regress silently.
- [ ] **C2:** `other` (and any unsupported) account type never crashes the pipeline; tested.
- [ ] **C3:** single-name concentration aggregated per ticker across accounts; per-account tax treatment
  correct and order-independent; tested with a multi-account fixture.
- [ ] **H1:** cash never recommended for relocation; tested.
- [ ] **H2:** at most one coherent directional action per `(ticker, account_id)`; superseded actions
  disclosed, not hidden; tested.
- [ ] **H3:** harvest replacement chosen via `rank_replacements` (overlap + liquidity + fee), not
  arbitrary; tested.
- [ ] **M1/M4:** short-term-gain block threshold and NIIT rate are config-driven; tested.
- [ ] **M2 + menu reconciliation:** all five `config/*.yml` files participate in `defaults < file < CLI`
  precedence; editing a standalone file changes behavior; `account_menus` has a single source of truth;
  tested.
- [ ] **M3/M5/L5:** thesis keys ticker-parameterized; allocation normalization no longer hides bad input
  (T4 de-tautologized); "no action" detection uses a typed flag.
- [ ] **Coverage:** all ~14 previously-untested Exit Criteria have green tests (Wave 4a).
- [ ] **Edge cases (T6/L1/L2/L6):** empty/zero/negative/unknown-ticker/all-None-basis inputs handled
  gracefully and tested.
- [ ] Determinism preserved: re-run on same snapshot → identical IDs, no duplicates (Wave 4 #11).
- [ ] No LLM/macro influence over any rec/urgency/score anywhere (re-asserted by the contrarian suite).

**Optional (count as done only if the wave was undertaken):** specific-lot/FIFO (5a), drift→instrument
(5b), scenario stress with no-influence proof (5c), generative contrarian harness (5d).

---

# Sequencing & critical path

```
Wave 1 (C1, C2, C3)  ─ do first; nothing ships until the suite guards the doctrine
   │  C1, C2 independent (parallelizable). C3 best before H2.
   ▼
Wave 2 (H1 → H2 ← C3; H3)
   │  H1 first (removes spurious cash relocates so the H2 baseline is clean).
   │  C3 must land before H2 (concentration recs feed reconciliation).
   │  H3 independent but re-validate against golden-path after C3/H2.
   ▼
Wave 3 (config rewire + menu reconciliation; relocate menu validation)
   │  Do AFTER Wave 2 so menu-source changes don't churn the H2 baseline twice.
   │  Menu reconciliation may move golden-path → re-baseline once, here.
   ▼
Wave 4 (coverage backfill + magic-number/config + edge cases)
   │  Mostly independent leaf work; M1/M4 depend on Wave 3 config wiring being real.
   │  Sector test (4a #7) requires enriching security_master.csv first.
   ▼
Wave 5 (optional: 5a lot-selection, 5b drift→instrument, 5c scenario, 5d contrarian harness)
      5b depends on Wave 3 menu uniformity; 5a depends on C1; 5c/5d independent.
```

**Unblock chain (critical path):** C3 unblocks H2; H1 precedes H2 (clean baseline); H2 + menu
reconciliation (Wave 3) are the two changes most likely to move golden-path — sequence them so
golden-path is re-baselined at most once, in Wave 3, and frozen thereafter. M1/M4 (Wave 4) require the
Wave 3 config wiring to actually load standalone files. The sector-concentration test needs a
security-master data enrichment as a prerequisite. Everything in Wave 4c/4d/4e and Wave 5 is otherwise
independent and can be parallelized across agents.

**Re-baseline discipline:** after H2 and after the Wave 3 menu reconciliation, re-run
`test_golden_path` and `test_no_action_balanced`; if the *intended* coherent action set changes, update
the fixture/assertions in the same commit and record the rationale in the commit message — never weaken
an assertion to make a regression pass.
