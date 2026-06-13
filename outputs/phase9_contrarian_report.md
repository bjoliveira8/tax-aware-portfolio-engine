# Phase 9 Contrarian Verification Report

**Status: PASS**

Phase 9 contrarian verification was rerun after hardening `core/recommendation_engine.py` and `core/tax_lot_engine.py`.

## Verification executed
- Baseline suite: `./.venv/bin/pytest -q` → **16 passed**
- Contrarian harness: `./.venv/bin/pytest -q tests/test_phase9_contrarian.py` → **5 passed**
- End-to-end CLI: `./.venv/bin/python -m app.cli analyze --holdings data/mock_holdings.csv --lots data/mock_tax_lots.csv --account-menus data/mock_account_menus.csv --security-master data/security_master.csv --output outputs/portfolio_report.md` → **report written successfully**
- Macro/LLM influence search remained clean: no runtime hooks in `core/`, `app/`, or `reporting/` that can alter recommendation, urgency, or score.

## Attack log

### 1) Taxable sale with no tax estimate / unknown flag
- **Attack:** Created a taxable `AAPL` concentration case with embedded gain and attempted to trigger a trim recommendation.
- **Observed output:** `trim AAPL` now carries an explicit tax note beginning `Estimated tax cost: ...`.
- **Result:** **FAILED (guard held)**

### 2) Wash-sale violation attempt across accounts including Roth/IRA
- **Attack:** Created a taxable `VTI` loss lot and a recent in-window `VTI` buy in another account.
- **Observed output:** Harvest recommendation blocked; engine emitted `hold VTI` with wash-sale notes.
- **Result:** **FAILED (guard held)**

### 3) Macro / LLM influence attempt
- **Attack:** Searched runtime modules for any macro/news/LLM/scenario input capable of changing recommendations.
- **Observed output:** No such influence path exists in v1.
- **Result:** **FAILED (guard held)**

### 4) Recommendation of an instrument an account cannot hold
- **Attack:** Created a menu-restricted IRA holding redundant bond funds while allowing only `BND` in the account menu.
- **Observed output:** Replacement recommendation was blocked; engine emitted `hold BND` with an account-menu warning.
- **Result:** **FAILED (guard held)**

### 5) Forced action when none is justified
- **Attack:** Re-ran a balanced, within-threshold portfolio intended to produce no recommendation pressure.
- **Observed output:** Single recommendation: `hold portfolio` with rationale `No action is justified.`
- **Result:** **FAILED (guard held)**

## Bottom line
All five contrarian attacks were unsuccessful after the fixes. The finished system now passes Phase 9 verification with **zero successful constraint violations**.
