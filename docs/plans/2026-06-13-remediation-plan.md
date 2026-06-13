# Tax-Aware Portfolio Engine Remediation Plan

> **For Hermes:** Execute this plan sequentially. Do not advance to the next phase until the current phase is complete and all listed tests pass.

**Goal:** Fix the audited correctness, safety, and pipeline-hardening defects in the offline tax-aware portfolio engine, while proving each repair with verifiable tests.

**Architecture:** Keep the engine offline and deterministic, but insert stronger boundaries: validated ingestion, a normalized analysis/result model, truthful reporting, and policy-constrained recommendation generation. Each phase adds failing tests first, then the minimal code needed to make them pass, followed by a full-suite gate.

**Tech Stack:** Python 3.11, pytest, PyYAML, argparse, CSV fixtures, markdown reporting.

---

## Global execution rules

1. Write failing tests before production changes for each behavior change.
2. Run targeted tests to confirm RED before changing code.
3. Implement the minimal fix.
4. Re-run targeted tests, then `python -m pytest -q`.
5. Only after green tests may the next phase begin.
6. Keep all work offline and fixture-driven.
7. Final acceptance requires the end-to-end CLI run and a full passing suite.

---

## Phase 1 — Truthfulness and hard safety gates

**Objective:** Remove misleading-success states and make report/process-log output faithful to engine state.

**Files likely touched:**
- `core/recommendation_engine.py`
- `reporting/report_generator.py`
- `reporting/process_log.py`
- `app/cli.py`
- `tests/test_report.py`
- `tests/test_cli_e2e.py`
- `tests/test_no_action_balanced.py`
- `tests/test_phase9_contrarian.py`
- new truthfulness/safety tests as needed

**Behaviors to add/fix:**
- Empty holdings must not generate a normal action plan.
- Report “Do these N things now” must exclude passive/blocking actions.
- Process-log booleans must derive from actual engine state, not hardcoded values.
- Sector concentration must prevent false `No action is justified.` outcomes.

**Required tests:**
- Empty holdings returns a safe outcome with explicit messaging and no normal action list.
- Report actionable count excludes `hold` and `do_nothing_due_to_tax_cost`.
- Process log matches real concentration/wash-sale state.
- Sector-concentrated portfolio cannot fall through to `No action is justified.`

**Phase gate:**
- All new safety/truthfulness tests pass.
- `python -m pytest -q` passes.

---

## Phase 2 — Validation and blocking rules

**Objective:** Fail fast on invalid inputs and suppress sale-driven recommendations when required tax/menu data is missing.

**Files likely touched:**
- `data/loaders.py`
- `app/config.py`
- `app/cli.py`
- `core/recommendation_engine.py`
- `core/provider.py`
- `tests/test_ingestion.py`
- `tests/test_config.py`
- new validation CLI tests

**Behaviors to add/fix:**
- Unknown tickers fail validation before analysis.
- Invalid target profile/config types fail with clear CLI errors, not raw tracebacks.
- Missing account-menu coverage is detected and blocks constrained recommendations.
- Missing taxable basis blocks sale-driven taxable actions.

**Required tests:**
- Unknown ticker → non-zero exit and readable validation error.
- Invalid config type → non-zero exit and readable validation error.
- Missing menu coverage → warning/error state that suppresses constrained recommendations.
- Missing taxable basis → no taxable `trim`, `replace`, or `tax_loss_harvest` recommendation.

**Phase gate:**
- All validation/blocking tests pass.
- `python -m pytest -q` passes.

---

## Phase 3 — Recommendation doctrine repairs

**Objective:** Repair concentration aggregation, replacement safety, and asset-location semantics.

**Files likely touched:**
- `core/overlap_engine.py`
- `core/etf_replacement.py`
- `core/asset_location_engine.py`
- `core/recommendation_engine.py`
- `data/schemas.py`
- `tests/test_overlap.py`
- `tests/test_actions.py`
- `tests/test_allocation.py`
- `tests/test_golden_path.py`

**Behaviors to add/fix:**
- Single-name concentration aggregates by ticker across accounts.
- Sector concentration is actionable and reconciled with the no-action control case.
- Replacement candidates require compatible security types/exposures.
- `redirect_contributions` remains advisory, not a relocate/sell instruction.
- Cash is not treated as generic tax-efficient broad equity.

**Required tests:**
- Split positions across accounts can trigger single-name concentration.
- ETF-to-single-stock replacement is rejected.
- Cash does not receive broad-equity relocation rationale.
- Contribution-routing recommendations preserve advisory action type.
- Golden path no longer suggests unsafe replacements like `ARKK -> AAPL`.

**Phase gate:**
- All doctrine-repair tests pass.
- `python -m pytest -q` passes.

---

## Phase 4 — Wash-sale/account metadata normalization and plan reconciliation

**Objective:** Strengthen tax-rule modeling and recommendation structure so outputs are execution-ready and internally consistent.

**Files likely touched:**
- `data/schemas.py`
- `data/loaders.py`
- `core/wash_sale_guard.py`
- `core/recommendation_engine.py`
- `reporting/report_generator.py`
- `tests/test_tax.py`
- `tests/test_actions.py`
- `tests/test_golden_path.py`

**Behaviors to add/fix:**
- Wash-sale logic uses normalized account types, not substring heuristics.
- Conflicting recommendations on the same holding/account are reconciled into one executable or blocked/advisory outcome.
- Report sections distinguish executable actions, blocked actions, and observations.

**Required tests:**
- Retirement-account wash-sale detection works even when account IDs do not contain `ira`/`roth`.
- Same holding cannot produce contradictory executable actions.
- Report renders blocked/advisory/executable sections distinctly.

**Phase gate:**
- All reconciliation/wash-sale tests pass.
- `python -m pytest -q` passes.

---

## Phase 5 — Final verification and artifact refresh

**Objective:** Prove the remediated engine works end to end and update audit artifacts.

**Files likely touched:**
- `outputs/portfolio_report.md`
- `outputs/phase9_contrarian_report.md`
- `tests/test_cli_e2e.py`
- optional docs summarizing remediation completion

**Required verification steps:**
1. Run full suite: `python -m pytest -q`
2. Run contrarian suite explicitly: `python -m pytest -q tests/test_phase9_contrarian.py`
3. Run CLI end to end:
   ```bash
   python -m app.cli analyze \
     --holdings data/mock_holdings.csv \
     --lots data/mock_tax_lots.csv \
     --account-menus data/mock_account_menus.csv \
     --security-master data/security_master.csv \
     --output outputs/portfolio_report.md
   ```
4. Verify generated report reflects repaired doctrine and no unsafe replacements.

**Final acceptance gate:**
- Full suite passes.
- Contrarian suite passes.
- CLI run succeeds.
- Report file exists and matches repaired behavior.

---

## Completion checklist

- [x] Phase 1 complete with green tests
- [x] Phase 2 complete with green tests
- [x] Phase 3 complete with green tests
- [x] Phase 4 complete with green tests
- [x] Phase 5 final verification complete
- [x] Final state summarized with exact test/CLI outputs
