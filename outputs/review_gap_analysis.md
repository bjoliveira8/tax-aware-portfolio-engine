# Gap Analysis — Tax-Aware Portfolio Decision Engine

Scope: identify MISSING / incomplete / partially-implemented parts of the execution plan vs. the
current codebase. Code quality and bugs are out of scope (separate agent). All 16 existing tests pass
(`pytest -q` → `16 passed`). CLI `--help` lists the `analyze` command.

Legend: **Implemented** = present + has a test verifying the criterion; **Partial** = present but a
criterion is unverified-by-test or only partially built; **Missing** = feature absent.

---

## 1. Phase-by-Phase Coverage

### Phase 0 — Repository & Orientation — **Partial**
- Skeleton present: `pyproject.toml` (pinned-ish: `PyYAML>=6.0`), `app/cli.py`, `app/config.py`,
  `core/`, `data/`, `reporting/`, `tests/`, `outputs/`, `research/`, DataProvider interface
  (`core/provider.py:18` `DataProvider` Protocol + `IngestionResult`).
- `python -m app.cli --help` runs and lists `analyze` — **met** (verified manually; no dedicated test
  but covered indirectly by `tests/test_cli_e2e.py`).
- Config precedence test passes (`tests/test_config.py:7`) — **met** for defaults < file < CLI flag.
- `pytest` 0 failures — **met**.
- **GAP (config precedence is only half-built):** The plan requires `config/` to contain
  `default.yml, model_portfolios.yml, tax_assumptions.yml, thresholds.yml, account_menus.yml` and a
  precedence chain `defaults < file < CLI flag`. All five files exist, BUT `app/config.py:30 load_config`
  reads ONLY `config_dir/default.yml` (`config.py:36`). The other four files are **never loaded** —
  `default.yml` simply duplicates their content (compare `config/thresholds.yml`,
  `config/model_portfolios.yml`, `config/tax_assumptions.yml` to the same keys inside `default.yml`).
  `config/account_menus.yml` is entirely orphaned (menus are loaded from
  `data/mock_account_menus.csv` instead, and the YAML disagrees with the CSV — see Phase 6).
  So the four standalone config files are dead files; editing them has no effect. The precedence test
  uses a synthetic `default.yml` in tmp_path and does not exercise multi-file aggregation.

### Phase 1 — Research Spike — **Implemented**
- `research/research_synthesis.md` exists, non-empty (27 lines), states chosen MVP libraries, patterns
  to borrow, excluded-from-MVP, and the explicit "no optimizer and no backtest in v1" decision
  (`research_synthesis.md:26-27`).
- All four source files exist and are non-empty: `data_sources.md` (454), `tax_rules.md` (362),
  `reporting.md` (626), `factor_tilts.md` (514).
- No test asserts these files exist, but the plan's Phase 1 criteria are doc-existence checks, not
  code; considered met.

### Phase 2 — Ingestion Foundation — **Implemented**
- `Holding`/`TaxLot` schemas (`data/schemas.py:13,26`); loaders (`data/loaders.py`); account-type parser
  (`loaders.py:35 parse_account_type` + alias map); ticker normalization (`loaders.py:31`); mock data
  (`mock_holdings.csv`, `mock_tax_lots.csv`, `mock_account_menus.csv`) all present.
- Invalid tickers flagged — `tests/test_ingestion.py` asserts "Invalid ticker flagged".
- Missing cost basis loads + marks "tax impact unknown" — verified `test_ingestion.py`.
- Account types map correctly — `test_ingestion.py` asserts `parse_account_type("Roth IRA")=="roth_ira"`.
- Total market value equals sum — `test_ingestion.py` asserts total `195500.00`.
- **Minor GAP:** Exit criterion "CLI prints: total value, accounts detected, warnings list" is
  implemented (`cli.py:69-72`) but NOT asserted by any test (`test_cli_e2e.py` only checks
  "Total value:" substring and report existence; it does not assert the accounts/warnings lines).
  Counts as Partial-on-that-line; feature present.

### Phase 3 — Exposure & Overlap (KEYSTONE) — **Implemented**
- `core/overlap_engine.py` present with `overlap_score` tiers (1.0 / 0.7 / 0.4 / 0) and look-through
  override (`overlap_engine.py:18-45`). Exposure breakdown + concentration (`:47,59`).
- Single name > threshold flagged — `tests/test_overlap.py` (VTI flagged).
- Account-level concentration computed separately — `test_overlap.py` asserts
  `account_concentration["TAX-1"]["VTI"] > 0.35`.
- Two same-index-family ETFs → overlap 1.0 — `test_overlap.py` asserts `overlap_score("BND","AGG")==1.0`.
- **GAP (untested criterion):** "Sector > threshold (default 35%) is flagged." The code computes
  `sector_flags` (`overlap_engine.py:70`) but **no test asserts a sector flag fires.** Also, in the
  mock security_master nearly all `sector_focus` values are `none` (only AAPL/ARKK = `technology`), so
  sector concentration is not meaningfully exercised anywhere. Sector-flagging is effectively
  unverified.

### Phase 4 — Tax & Wash-Sale Engine — **Partial**
- `core/tax_lot_engine.py` (short/long per lot, unrealized gain, configurable drag via TaxProfile,
  "do nothing due to tax cost") and `core/wash_sale_guard.py` (±30-day window across ALL accounts,
  same-ticker block, same-index-family gray zone, safe-replacement suggestion) present.
- Tested criteria (in `tests/test_tax.py`, `test_actions.py`, `test_phase9_contrarian.py`):
  - Large short-term gain suppresses sell — covered by `test_tax.py` (`blocked_by_tax_cost is True`)
    though via the embedded-gain path, see note.
  - Loss flagged for harvest only when wash-sale-clean — `test_tax.py` (VXUS clean), `test_actions.py`
    (VXUS harvest fires).
  - Same-ticker buy in ANY account blocks harvest — `test_phase9_contrarian.py`
    (`test_attack_wash_sale_bypass...`) and `test_tax.py` (VTI Roth purchase blocks).
  - Substantially-identical buy in IRA/Roth in-window flagged as permanent loss — `test_tax.py` asserts
    `wash_sale_blocked_retirement_account_purchase`.
- **GAP (untested criterion):** "The same overweight in a Roth trims with NO tax warning." There is NO
  test that asserts a Roth/tax-advantaged trim carries no tax warning. The code path exists
  (`recommendation_engine.py:156-157` sets `["No tax warning in tax-advantaged account."]`) but is
  unverified.
- **GAP (untested criterion):** "Missing lots produce 'tax impact unknown', never a confident sell."
  `estimate_sale_tax` returns the "tax impact unknown" note when basis/unrealized is None
  (`tax_lot_engine.py:19,26`), but no test feeds missing-lot data into the recommendation engine to
  assert that no confident sell is produced. Ingestion-level "tax impact unknown" warning is tested;
  the recommendation-level guarantee is not.
- **GAP (untested criterion):** "A taxable sale above `confirm_with_cpa_above` prints a 'confirm with a
  tax professional' note." Code emits this note (`tax_lot_engine.py:37-38`) but no test asserts the
  string surfaces on an actual taxable-sale recommendation.
- **Note on short-term-gain semantics:** the "large short-term gain suppresses" rule is implemented
  with an ad hoc threshold (`confirm_with_cpa_above / 4`, `tax_lot_engine.py:34`) not described in the
  plan; functionally present, just undocumented.
- **GAP (missing engine capability):** Plan calls for "specific-lot vs FIFO" lot selection. The engine
  sums ALL lots for a holding (`estimate_sale_tax` iterates every lot; `lots_for_holding` returns all);
  there is **no specific-lot vs FIFO selection logic** and no test for it. Feature largely absent.

### Phase 5 — Allocation & Asset Location — **Partial**
- `core/allocation.py` (current/target/drift with signed difference); `core/asset_location_engine.py`
  (tax-inefficient → tax-advantaged; growth → Roth/HSA; HSA CA/NJ note at `asset_location_engine.py:33`;
  relocate vs redirect_contributions at `:32`; never forces taxable sale). Model portfolios present
  (conservative/balanced/aggressive). Golden-path test exists (`tests/test_golden_path.py`).
- Tested: allocations sum to 100% + sign correct (`test_allocation.py`); bond fund in taxable flagged
  for relocation — `test_allocation.py` asserts BND relocate; golden path asserts BND relocate +
  VXUS harvest + VTI do-nothing.
- **GAP (untested criterion):** "Sub-threshold deviation produces NO trade." No allocation-level test
  feeds a within-tolerance drift and asserts no rebalance/add rec is emitted. (The no-action balanced
  test covers the whole pipeline, but not the isolated drift sub-threshold behavior.)
- **GAP (untested criterion):** "A growth asset is preferred in Roth/HSA." `location_priority`
  (`asset_location_engine.py:9-11`) prefers Roth/HSA for `small_value`/`large_growth`, but no test
  asserts a growth asset is steered to Roth/HSA.
- **GAP (untested criterion):** "Relocation never recommends realizing a large taxable gain when
  contributions can fix the drift." This is enforced via `do_nothing_due_to_tax_cost`
  (`recommendation_engine.py:96-113`) and golden path asserts VTI do-nothing, so partially covered;
  acceptable.
- **GAP (criterion only partially surfaced):** "report must surface the human-capital caveat." The
  caveat text exists in the report (`report_generator.py:85`) but is asserted nowhere; and the plan
  places it under Phase 5 build. Present, untested.

### Phase 6 — Action Engine — **Partial**
- `core/etf_replacement.py` (`rank_replacements`: expense ratio, liquidity floor $5M/day, AUM,
  distribution-yield penalty, overlap; `etf_replacement.py:7-34`). `core/recommendation_engine.py`
  merges location → concentration → overlap → fee → drift → harvest with the plan's priority order
  (`PRIORITY_RANK` at `:13` and section ordering). Deterministic `recommendation_id` via
  `Recommendation.build_id` (`schemas.py:73`). Menu validation `menu_allows` (`:26`).
- Tested (`test_actions.py`, `test_golden_path.py`, `test_phase9_contrarian.py`):
  - Taxable tax drag blocks rebalance / tax-advantaged preferred — golden path VTI do-nothing.
  - Instrument not in destination menu reframed/flagged — `test_actions.py` + contrarian menu test.
  - Sub-threshold deviation → no action — `test_no_action_balanced.py`.
  - Golden-path full shape — `test_golden_path.py` (VXUS→VEA harvest, VTI do-nothing, BND relocate).
- **GAP (untested criterion):** "A lower-fee but illiquid ETF is not auto-preferred; replacement
  requires similar exposure." The `liquidity_ok` gate (`recommendation_engine.py:244`) and overlap
  floor exist, but NO test feeds an illiquid lower-fee candidate and asserts it is rejected. The
  priority is unverified. (FXNAX is the only high-fee holding in mock data; whether its replacement
  fires at all is not asserted.)
- **GAP (untested criterion):** "Replacement is blocked in a taxable account on a high gain, allowed in
  an IRA." No test exercises the same replacement in taxable (blocked) vs IRA (allowed) to contrast.
  The taxable-block code exists (`:247-266`) but the IRA-allowed contrast is unverified.
- **Note:** The plan says "Validate every target instrument against the destination AccountMenu." Menu
  checking is applied to overlap-replace and fee-replace and harvest paths, but NOT to the asset-
  location `relocate` path nor the drift `add`/`rebalance` path (those emit asset-class-level recs with
  `account_id=None` and no menu check). Partial coverage of the constraint (see Section 4).

### Phase 7 — Report & Process Log — **Implemented (with untested criteria)**
- `reporting/report_generator.py`: 3-line bottom line ("Do these N things" / "No action is justified"),
  Portfolio Grade rubric with component breakdown shown (`GRADE_WEIGHTS` 30/20/20/15/15,
  `compute_grade` shows components), risks/current-vs-target/process log/blind-spot disclosure,
  "Analysis, not financial advice." line. `reporting/process_log.py` records thesis, invalidation rule,
  process metrics; no outcome/benchmark returns.
- Tested (`test_report.py`): "PORTFOLIO GRADE" prints; "Analysis, not financial advice." prints; every
  rec has rationale; tax-touching actions carry tax notes.
- **GAP (untested criterion):** "Report generates even if optional engines are absent." No test removes
  the (already-absent) scenario/macro engine and asserts the report still renders. Trivially true since
  Phase 8 was skipped, but unasserted.
- **GAP (untested criterion):** "The report prints 'No action is justified' when correct." The
  recommendation engine's no-action path is tested (`test_no_action_balanced.py`), but NO test asserts
  the rendered REPORT text contains the "No action is justified." bottom line.
- **GAP (untested criterion):** "Re-running on the same snapshot produces no duplicate recommendations
  (deterministic IDs)." Dedup exists (`recommendation_engine.py:414` `unique` dict keyed by id), and
  `snapshot_id_for` is deterministic, but NO test runs the pipeline twice and asserts identical IDs /
  no duplicates.
- **Minor:** Grade component-breakdown printing is shown but not asserted line-by-line (only the
  "PORTFOLIO GRADE" header is asserted).

### Phase 8 — Optional Context — **Intentionally Not Built (documented)**
- `PHASE_8_DECISION.md` documents the deliberate skip — allowed by the plan ("Decide on your own").
- No `config/scenario_shocks.yml`, no scenario-stress engine, no macro module. Consistent with the
  decision. The Phase 8 exit criteria (tech-unwind stress; macro never changes a rec) are therefore
  N/A. **Not a gap** — but note `outputs/phase9_contrarian_report.md` exists implying Phase 9 ran.

### Phase 9 — Final Verification (Contrarian) — **Partial**
- `tests/test_phase9_contrarian.py` encodes the five adversarial attacks (no-tax-note taxable sale,
  wash-sale bypass, macro/LLM influence, account-menu violation, forced action) and all pass.
- `outputs/phase9_contrarian_report.md` exists (a pass/fail report).
- End-to-end CLI run writes a report — `tests/test_cli_e2e.py`.
- **GAP vs plan intent:** Plan says "Spawn ONE contrarian verification SUBAGENT" that *constructs*
  adversarial portfolios and returns a pass/fail report. What exists is a static test file plus a
  report doc — adequate as verification, but it is a fixed test, not an independent generative
  adversary. The five constraint categories are all represented, so functional coverage is good.

---

## 2. Data Models (`data/schemas.py`)

All 6 required schemas exist with all required fields:

| Schema | Status | Notes |
|---|---|---|
| Holding | Complete | All 9 fields present (`schemas.py:13`). |
| TaxLot | Complete | All 8 fields present (`schemas.py:26`). |
| TaxProfile | Complete | All 7 fields incl. `confirm_with_cpa_above` (`schemas.py:38`). |
| AccountMenu | Complete | `account_id, universe, allowed_instruments` (`schemas.py:49`). |
| Recommendation | Complete+extra | All plan fields + `build_id = sha256(action|ticker|account_id|thesis_key)` matching the spec's hash. Adds `replacement_ticker`, `thesis_key` fields (additive, fine). |
| ProcessLogEntry | Complete | All 11 fields (`schemas.py:79`). |

- `account_type` and `action` Literals match the plan exactly (`schemas.py:8-9`).
- Extra schema `SecurityMetadata` (`schemas.py:93`) is an additive design choice (the security_master),
  not in the plan but not forbidden.
- **No missing schema fields.** Data Models are the most complete part of the build.

---

## 3. Exit Criteria With NO Corresponding Test (unverified — the plan is test-driven)

Prioritized list of criteria that are implemented-but-unverified or unbuilt:

1. **Phase 6:** lower-fee-but-illiquid ETF not auto-preferred — no test. (HIGH: core doctrine.)
2. **Phase 6:** replacement blocked in taxable on high gain, allowed in IRA (contrast) — no test.
3. **Phase 4:** specific-lot vs FIFO selection — **feature absent**, no test. (HIGH.)
4. **Phase 4:** missing lots never produce a confident sell (at recommendation level) — no test.
5. **Phase 4:** Roth overweight trims with NO tax warning — no test.
6. **Phase 4:** taxable sale > `confirm_with_cpa_above` prints "confirm with a tax professional" — no
   test asserting the string on a real recommendation.
7. **Phase 3:** sector > 35% flagged — no test, and mock data barely exercises sector concentration.
8. **Phase 5:** sub-threshold deviation produces NO trade (isolated drift) — no test.
9. **Phase 5:** growth asset preferred in Roth/HSA — no test.
10. **Phase 7:** report prints "No action is justified" (rendered text) — no test.
11. **Phase 7:** re-run produces no duplicate recommendations (deterministic IDs) — no test.
12. **Phase 7:** report generates even if optional engines absent — no test.
13. **Phase 2:** CLI prints accounts-detected + warnings list — not asserted.
14. **Phase 0:** multi-file config aggregation + precedence across the 5 config files — not built / not
    tested (only single default.yml is read).

---

## 4. Non-Negotiable Constraints — enforcement status

| Constraint | Status | Evidence |
|---|---|---|
| No execution / trading / options / crypto / leverage / margin / shorts | Enforced (by absence) | No such code anywhere; actions limited to the Literal set. |
| LLM may never create/modify a recommendation/urgency/score | Enforced (by absence) | No LLM code in repo; engine is pure rules. Contrarian test `test_attack_macro_llm_influence`. |
| Macro/news read-only, no influence | Enforced (by absence) | No macro engine (Phase 8 skipped). Documented in `PHASE_8_DECISION.md`. |
| No taxable-sale rec without tax estimate OR "tax impact unknown" flag | Mostly enforced | `estimate_sale_tax` attaches notes; trims/relocates carry tax_notes. Verified by contrarian + report tests. GAP: not proven for the missing-lots → no-confident-sell path. |
| No TLH without 61-day wash-sale check across ALL accounts incl IRA/Roth | Enforced | `wash_sale_guard.check_harvest` ±30 days over all lots; verified by `test_tax.py` + contrarian. |
| No rec of instrument destination account can't hold | Partially enforced | `menu_allows` applied to overlap-replace, fee-replace, harvest-replacement. **NOT applied** to `relocate` (asset-location) recs nor drift `add`/`rebalance` recs (account_id=None, no menu check). The relocate path names no concrete instrument/destination, so arguably lower risk, but the constraint is not uniformly enforced. |
| No forced rec when none justified | Enforced | No-action fallback (`recommendation_engine.py:419-435`); verified `test_no_action_balanced.py` + contrarian. |
| No black-box scores; grade/stress show math | Partially enforced | Grade shows component breakdown (`report_generator.py:72-74`). Scenario stress N/A (not built). |
| Never hide a prior recommendation | Not demonstrable | No persistence/history of prior runs exists; each run is stateless. Nothing hides recs, but there is also no mechanism that retains prior ones — constraint is vacuously satisfied, not actively enforced. |
| Never send holdings/cost basis to cloud LLM; local only | Enforced (by absence) | No network calls in runtime; deps = PyYAML only. Tests never touch network. |
| Never skip tests; unit tests never touch network | Enforced | 16 tests pass; only `test_cli_e2e` spawns a subprocess (local). No network. |

---

## 5. Do-Not-Build List — leakage check

| Forbidden item | Present? | Evidence |
|---|---|---|
| Individual-stock candidate screener | No | No screener; AAPL handled only as an existing holding/concentration flag. |
| Portfolio optimizer (MVO/BL/HRP/CVaR) | No | No optimization code; synthesis explicitly excludes it. |
| Investor "lenses" moving a score/decision | No | None. |
| Outcome / benchmark-relative performance tracking | No | Process log explicitly records process metrics only (`process_log.py`); no returns tracking. |
| Macro-driven tactical reallocation | No | Phase 8 skipped; no regime/timing code. |
| News / YouTube ingestion | No | None. |

**Result: clean. No Do-Not-Build item leaked into the codebase.**

---

## 6. Definition of Done — checklist

| DoD item | Status | Notes |
|---|---|---|
| All phases passed gates; full suite + golden-path green; contrarian clean | Partial | Tests green (16 pass) incl. golden-path + contrarian. BUT several phase Exit Criteria have no test (Section 3), so "gates met" is weaker than the test-driven plan intends. |
| Runs on mock data, no broker, no paid data, no network | Met | CLI runs offline on mock CSVs; PyYAML-only dependency. |
| On a balanced portfolio outputs "No action is justified." | Met | `test_no_action_balanced.py` (engine level). Report-text level untested. |
| On golden-path portfolio produces expected tax-aware action set | Met | `test_golden_path.py` asserts VXUS→VEA harvest, VTI do-nothing, BND relocate. |
| No Do-Not-Build item in codebase | Met | Section 5. |

---

## Top Gaps, Prioritized

1. **Config system half-wired (Phase 0):** `app/config.py` reads only `default.yml`; the four other
   `config/*.yml` files (`thresholds`, `model_portfolios`, `tax_assumptions`, `account_menus`) are dead
   — never loaded. `account_menus.yml` even disagrees with the CSV actually used. Multi-file precedence
   is unbuilt and untested.
2. **Specific-lot vs FIFO selection (Phase 4) is absent** — the engine always sums all lots; the plan
   explicitly requires lot-selection logic.
3. **Account-menu validation is not uniform (Constraint):** not applied to relocate/drift recommendation
   paths.
4. **~14 Exit Criteria are implemented-but-untested** (Section 3), most notably: illiquid-replacement
   rejection, Roth-trim-no-tax-warning, missing-lots-no-confident-sell, sector>35% flag, deterministic
   no-duplicate re-run, and the rendered "No action is justified" report text. In a test-driven plan,
   these gates are effectively unverified.
5. **Phase 9 is a static test file, not a generative contrarian subagent** — functionally covers all
   five attack categories, but diverges from the plan's "spawn a subagent" intent.

Strong points (no gaps): Data Models complete; Do-Not-Build clean; research synthesis present;
overlap/concentration keystone, golden-path, and core no-action doctrine implemented and tested.
