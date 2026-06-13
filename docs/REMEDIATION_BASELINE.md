# Remediation Baseline

- Workspace: `/Users/clawbot/Desktop/Hermes/tax-aware-portfolio-engine-remediation`
- Source repo: `bjoliveira8/tax-aware-portfolio-engine`
- Baseline SHA: `f6a7af4940ea1f575b148be0cfdd81c46308edd5`
- Test baseline: `python -m pytest -q` → `16 passed`
- CLI baseline: `python -m app.cli analyze --holdings data/mock_holdings.csv --lots data/mock_tax_lots.csv --account-menus data/mock_account_menus.csv --security-master data/security_master.csv --output outputs/remediation_baseline_report.md`
- CLI baseline stdout:
  - `Total value: $195,500.00`
  - `Accounts detected: HSA-1, IRA-1, ROTH-1, TAX-1`
  - `Warnings: []`

This baseline proves the current golden path passes before remediation work starts.
