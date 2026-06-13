BOTTOM LINE
- Do these 6 things now.
- Protect taxable gains unless tax-aware math says otherwise.
- Use tax-advantaged accounts and contributions first.

EXECUTABLE ACTIONS
1. RELOCATE BND
   Why: tax-inefficient asset held outside preferred account location; Use tax-advantaged trades or redirect contributions instead of forcing taxable sale.; Loss exists but wash-sale rules block a harvest recommendation.
   Tax note: Forward-looking location improvement only.; AGG shares same index family as BND; gray zone.; FXNAX shares same index family as BND; gray zone.
   Confidence: high | Urgency: medium
2. RELOCATE ARKK
   Why: tax-inefficient asset held outside preferred account location; Use tax-advantaged trades or redirect contributions instead of forcing taxable sale.
   Tax note: Forward-looking location improvement only.
   Confidence: high | Urgency: medium
3. TRIM FXNAX
   Why: FXNAX exceeds single-name concentration threshold.; BND and FXNAX are redundant, but the account menu cannot hold BND.; Lower-fee replacement exists but destination account menu does not allow it.
   Tax note: No tax warning in tax-advantaged account.; Instrument blocked by account menu.
   Confidence: high | Urgency: high
4. TAX_LOSS_HARVEST VXUS -> VEA
   Why: Realized loss available and wash-sale screen passed.
   Tax note: 61-day wash-sale check passed across all accounts.
   Confidence: high | Urgency: high
5. REBALANCE taxable_bond
   Why: taxable_bond is overweight versus target.
   Tax note: Use rebalancing discipline.
   Confidence: medium | Urgency: low
6. ADD international_equity
   Why: international_equity is underweight versus target.
   Tax note: Use rebalancing discipline.
   Confidence: medium | Urgency: low

BLOCKED ACTIONS
1. DO_NOTHING_DUE_TO_TAX_COST VTI
   Why: VTI exceeds single-name concentration threshold.
   Tax note: Estimated tax cost: $3,640.00 on estimated gain $18,200.00.; Embedded taxable gain is above the configured caution threshold.
   Confidence: high | Urgency: high
2. DO_NOTHING_DUE_TO_TAX_COST AAPL
   Why: Location is suboptimal but taxable sale cost is too high.; AAPL exceeds single-name concentration threshold.
   Tax note: Estimated tax cost: $2,700.00 on estimated gain $13,500.00.; Embedded taxable gain is above the configured caution threshold.
   Confidence: high | Urgency: medium

OBSERVATIONS
1. REDIRECT_CONTRIBUTIONS CASH
   Why: cash outside taxable should usually be corrected with contribution routing or liquidity policy review, not forced sales; Use tax-advantaged trades or redirect contributions instead of forcing taxable sale.
   Tax note: Confirm the cash balance is intentional for spending, reserves, or near-term deployment.
   Confidence: high | Urgency: medium
2. REDIRECT_CONTRIBUTIONS CASH
   Why: cash outside taxable should usually be corrected with contribution routing or liquidity policy review, not forced sales; Use tax-advantaged trades or redirect contributions instead of forcing taxable sale.
   Tax note: Confirm the cash balance is intentional for spending, reserves, or near-term deployment.
   Confidence: high | Urgency: medium

PORTFOLIO GRADE: 26 / 100
- Allocation Fit: 0 / 30
- Concentration: 0 / 20
- Tax Efficiency: 12 / 20
- Fee Drag: 14 / 15
- Diversification: 0 / 15

CURRENT VS TARGET
- cash: current 6.65% | target 5.00% | diff +1.65%
- international_equity: current 3.32% | target 20.00% | diff -16.68%
- taxable_bond: current 36.83% | target 25.00% | diff +11.83%
- us_equity: current 53.20% | target 50.00% | diff +3.20%

PROCESS LOG
- 36f36b56f95b652e: relocate | tax-inefficient asset held outside preferred account location; Use tax-advantaged trades or redirect contributions instead of forcing taxable sale.; Loss exists but wash-sale rules block a harvest recommendation.
- ed5f7bc8a84c9ba9: relocate | tax-inefficient asset held outside preferred account location; Use tax-advantaged trades or redirect contributions instead of forcing taxable sale.
- 5c758b6c8a3d0e0d: redirect_contributions | cash outside taxable should usually be corrected with contribution routing or liquidity policy review, not forced sales; Use tax-advantaged trades or redirect contributions instead of forcing taxable sale.
- d2a228bd59e90673: redirect_contributions | cash outside taxable should usually be corrected with contribution routing or liquidity policy review, not forced sales; Use tax-advantaged trades or redirect contributions instead of forcing taxable sale.
- f33278ed4eff24e1: trim | FXNAX exceeds single-name concentration threshold.; BND and FXNAX are redundant, but the account menu cannot hold BND.; Lower-fee replacement exists but destination account menu does not allow it.
- 71693e8a5fc271ca: tax_loss_harvest | Realized loss available and wash-sale screen passed.
- b980dfbc4e1b362e: rebalance | taxable_bond is overweight versus target.
- 413edad6abcfdf8c: add | international_equity is underweight versus target.
- e65915ddf018e6fe: do_nothing_due_to_tax_cost | VTI exceeds single-name concentration threshold.
- 56e5bb2b53701bcc: do_nothing_due_to_tax_cost | Location is suboptimal but taxable sale cost is too high.; AAPL exceeds single-name concentration threshold.

Blind spots: target allocation is a user-owned assumption; stable professional income is bond-like human capital outside this model.
Analysis, not financial advice.
