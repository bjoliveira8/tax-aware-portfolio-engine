# Reporting Research for Tax-Aware Portfolio Decision Engine MVP

## Purpose of the MVP report

The report should answer one practical question for a single household snapshot:

1. **What action, if any, is justified now?**
2. **Why is that action justified?**
3. **What would make the action wrong or unnecessary?**
4. **What tax or account constraints limit what can be done?**

This argues for an **action-first, offline CLI report** that is compact, deterministic, and traceable to rules. The report should optimize for:

- quick review in a terminal
- low cognitive load
- visible math for scores and flags
- explicit uncertainty labels
- strong support for the correct MVP outcome: **“No action is justified.”**

The report is not a performance dashboard, not a backtest, and not an optimizer output.

---

## MVP reporting principles

### 1. Lead with decisions, not diagnostics
The first screen should tell the user whether to act. Diagnostics support the action decision rather than competing with it.

### 2. Present only metrics that can change a portfolio decision
Every metric shown should tie to one of the MVP jobs:

- asset location
- fee reduction
- concentration control
- rebalancing discipline
- wash-sale-safe tax loss harvesting
- explicit no-action conclusion when change is not justified

If a metric does not change or validate one of those decisions, it should stay out of the main report.

### 3. Separate **state**, **risk**, and **action**
The report should distinguish:

- **portfolio state**: what exists now
- **decision risk**: why acting may be costly or constrained
- **recommended action**: what to do, in priority order

This prevents the common failure mode where the user sees a red flag and assumes a trade is required.

### 4. Prefer thresholds and reason codes over dense analytics
For an MVP CLI report, simple rule-based outputs are easier to trust than highly compressed quant summaries.

Good: “US tech concentration exceeds 15% single-name threshold.”

Bad: “Diversification score = 63.2” without context.

### 5. Show the math for any aggregate score
The Phase 7 spec already requires a visible Portfolio Grade breakdown. The report must never print a bare grade with no decomposition.

---

## Recommended report structure

A strong CLI structure is:

1. **Bottom line (3 lines max)**
2. **Priority action list**
3. **Portfolio Grade with visible component math**
4. **Current vs target allocation summary**
5. **Concentration and diversification flags**
6. **Tax-aware findings**
7. **Account-location findings**
8. **Fee and replacement opportunities**
9. **Holdings to challenge**
10. **Process log / discipline record**
11. **Disclosures and blind spots**

This ordering matches the product doctrine: lead with actionable output, then justify it.

---

## Section-by-section design

## 1) Bottom line

This should be the most compressed, high-value part of the report.

### Required patterns

#### If action exists
```text
BOTTOM LINE
- Do these 3 things now.
- Avoid taxable sale of VTI in Account A due to estimated tax drag.
- Use IRA/Roth/HSA space plus new contributions to improve location and reduce drift.
```

#### If no action is justified
```text
BOTTOM LINE
- No action is justified.
- Drift is within tolerance, concentration is acceptable, and tax cost outweighs benefit.
- Continue contributions according to target allocation.
```

### Why this matters
The report should make “no action” look like a valid, evidence-based result rather than an empty run.

---

## 2) Priority action list

This is the operational core of the report.

### Recommended fields per action
Each action line should include:

- priority rank
- action type
- account
- ticker/current holding
- target instrument if applicable
- approximate dollar amount or weight change
- short rationale
- tax note
- confidence/constraint tag

### CLI-friendly format
```text
PRIORITY ACTIONS
1. RELOCATE BND from taxable -> traditional IRA
   Amount: ~$18,000
   Why: tax-inefficient bond income is currently in taxable; IRA capacity available
   Tax note: avoid realizing taxable gain by redirecting future purchases first
   Confidence: high

2. TAX-LOSS HARVEST VXUS -> IXUS in taxable
   Amount: ~$6,500
   Why: realized loss available and replacement preserves broad ex-US exposure
   Tax note: wash-sale check passed across all accounts for 61-day window
   Confidence: medium

3. DO NOTHING on concentrated gain-heavy VTI position
   Why: overweight exists, but estimated tax drag makes taxable trim unattractive now
   Tax note: short/long-term gain estimate blocks sell recommendation
   Confidence: high
```

### Design choice
Include **protective non-actions** in the action list when they are decision-relevant. “Do nothing due to tax cost” is a real recommendation in this domain.

---

## 3) Portfolio Grade

The grade is useful as a summary of process quality, not investment brilliance.

### Required MVP rubric
Use the Phase 7 weights exactly:

- allocation_fit: 30
- concentration: 20
- tax_efficiency: 20
- fee_drag: 15
- diversification: 15

Total = 100

### Recommended display
```text
PORTFOLIO GRADE: 78 / 100
- Allocation fit:   24 / 30   (moderate drift; underweight bonds, overweight US equity)
- Concentration:    11 / 20   (single-name and sector concentration above threshold)
- Tax efficiency:   16 / 20   (taxable bonds and gain-friction reduce score)
- Fee drag:         12 / 15   (one high-fee fund flagged)
- Diversification:  15 / 15   (broad ETF core otherwise acceptable)
```

### Reporting guidance
- Round to whole numbers unless fractional points add meaning.
- Always attach plain-English reasons to point loss.
- Avoid percentile framing or benchmark-like framing.
- The grade should summarize the current setup, not forecast outcomes.

### Good use of the grade
- compress current state
- justify why action is or is not needed
- compare future snapshots on process quality

### Bad use of the grade
- implying expected return
- implying market timing skill
- comparing to an external benchmark

---

## 4) Useful MVP metrics

Only include metrics that support an action or verify that no action is needed.

### A. Portfolio construction metrics
These are core.

- total portfolio market value
- value by account
- value by account type
- current asset allocation by major asset class
- target allocation by major asset class
- drift in percentage points by asset class
- number of holdings
- largest position weight
- largest sector weight
- largest issuer or same-index-family overlap cluster

### B. Tax-aware metrics
These are core because the engine is tax-aware.

- taxable vs tax-advantaged asset location summary
- estimated realized gain/loss by proposed taxable trade
- count/value of lots with missing cost basis
- count/value of harvestable loss lots
- wash-sale status for each harvest candidate: clean / blocked / gray zone
- short-term gain exposure on proposed sales
- long-term gain exposure on proposed sales
- taxable income-style holdings in taxable accounts (bond funds, REIT-like funds if present)

### C. Fee metrics
These are core because fee drag is an MVP job.

- weighted-average expense ratio for entire portfolio
- weighted-average expense ratio by account
- estimated annual fee drag in dollars
- highest-fee holding(s)
- fee difference for any replacement candidate

### D. Actionability metrics
These are critical for a CLI report.

- actions recommended count
- actions blocked by tax cost count
- actions blocked by account-menu constraints count
- actions deferred because contribution flow can solve drift count
- confidence tier per recommendation

---

## 5) Metrics to exclude from MVP main report

These may be interesting, but they do not earn their place in v1.

### Exclude entirely from MVP
- Sharpe ratio
- Sortino ratio
- beta
- tracking error
- information ratio
- factor regression outputs
- drawdown history
- VaR/CVaR
- Monte Carlo projections
- benchmark-relative excess return
- realized performance attribution
- optimizer efficiency frontier outputs

### Why exclude
They either:

- require time-series and backtest machinery outside scope
- imply forecast precision the product does not claim
- create cognitive overload for a portfolio audit tool
- do not directly improve action quality for location, fees, concentration, drift, or wash-sale safety

---

## 6) Portfolio-grade inputs and concrete scoring logic

The grade should be reproducible from snapshot data. Below is a practical MVP scoring pattern.

## Allocation fit (30)
Goal: reward portfolios that are close enough to the target without forcing micro-trades.

### Inputs
- current asset-class weights
- target asset-class weights
- drift threshold from config

### Suggested scoring pattern
- Start at 30.
- For each tracked asset class, subtract points based on absolute deviation from target.
- Ignore deviations inside the no-trade band.
- Cap penalty so one asset class cannot drive the score below zero by itself.

### Example logic
- 0 penalty inside threshold
- small penalty for 1x–2x threshold drift
- larger penalty beyond 2x threshold

### Reporting line
“Allocation fit lost 6 points because US equity is +11 pts above target and bonds are -9 pts below target.”

## Concentration (20)
Goal: reflect avoidable single-name, sector, or account-level concentration risk.

### Inputs
- largest position weight
- largest sector weight
- account-level concentration measures
- overlap/redundancy flags

### Suggested scoring pattern
- Start at 20.
- Deduct for single positions over threshold.
- Deduct for sector concentration over threshold.
- Deduct for redundant same-index-family holdings where complexity adds no diversification.

### Reporting line
“Concentration lost 9 points due to 22% in a single stock and 41% in one sector.”

## Tax efficiency (20)
Goal: reward tax-appropriate placement and avoidable tax friction.

### Inputs
- asset location mismatches
- bond/ordinary-income exposure in taxable
- gain-friction that prevents rational cleanup
- missing basis uncertainty
- blocked harvest opportunities due to wash-sale conflicts

### Suggested scoring pattern
- Start at 20.
- Deduct for clearly tax-inefficient assets in taxable when sheltered capacity exists.
- Deduct for material unknown basis because it reduces confidence.
- Deduct when avoidable wash-sale conflicts prevent harvests.
- Do not deduct simply because the portfolio has embedded gains; embedded gains are a state, not necessarily a mistake.

### Reporting line
“Tax efficiency lost 4 points because taxable bond exposure remains and one harvest candidate is blocked by an IRA purchase.”

## Fee drag (15)
Goal: capture low-effort fee savings.

### Inputs
- weighted average expense ratio
- annual dollar fee estimate
- highest-fee holdings relative to similar lower-fee substitutes

### Suggested scoring pattern
- Start at 15.
- Deduct for holdings above configured fee thresholds.
- Deduct more when a lower-fee, similar-exposure substitute exists and tax/account constraints do not block action.

### Reporting line
“Fee drag lost 3 points because one bond fund charges 68 bps versus similar low-cost alternatives below 10 bps.”

## Diversification (15)
Goal: reward broad exposure without pretending to solve portfolio optimization.

### Inputs
- breadth across major asset classes
- overlap cluster analysis
- unnecessary duplication count
- presence/absence of major intended exposures in target portfolio

### Suggested scoring pattern
- Start at 15.
- Deduct for redundant funds that do not materially expand exposure.
- Deduct for missing major target exposures.
- Keep separate from concentration: concentration is about over-weighted risk; diversification is about breadth and redundancy.

### Reporting line
“Diversification lost 2 points because two US large-cap ETFs duplicate the same index family while international equity is missing.”

---

## 7) Portfolio-grade design cautions

### Avoid false precision
Do not print decimals like 78.37/100 unless every subscore truly needs that precision. Whole numbers are enough.

### Avoid double-counting
A single issue should not fully punish multiple components unless it genuinely affects them in different ways.

Example:
- a concentrated single stock may reduce concentration
- it should not automatically slash diversification unless it also crowds out other exposures

### Keep penalties interpretable
Each penalty should map to an observable condition the user can inspect in the report.

---

## 8) Presenting risk without overload

The product needs to show risk, but not as a dense risk model. For MVP, risk should be presented as **decision risk** and **portfolio fragility flags**.

## A. Decision-risk labels for actions
Every recommendation should carry one or more tags:

- **Tax-sensitive**
- **Wash-sale constrained**
- **Menu constrained**
- **Contribution-fix available**
- **High confidence** / **Medium confidence** / **Low confidence**
- **Basis incomplete**

These labels are more useful for a CLI user than advanced statistical risk measures.

## B. Portfolio fragility flags
Use short, threshold-based flags such as:

- single-name concentration above limit
- sector concentration above limit
- taxable ordinary-income drag present
- redundant ETF exposure
- gain-friction locks in current allocation
- missing sheltered exposure capacity

### Why this works
These flags explain *why the portfolio may deserve attention* without forcing the user through a full risk analytics stack.

## C. Optional scenario box only if built later
If Phase 8 is implemented, scenario stress should appear in a separate section with explicit “assumption-based, not a forecast” wording. It should never crowd the top half of the report or affect the recommendation set.

---

## 9) Actionability design for an offline CLI report

Because this is a terminal report, compact formatting matters more than dashboard aesthetics.

### Preferred CLI conventions
- use clear section headers
- keep line width readable in standard terminals
- sort lists by priority and materiality
- cap each section to the most decision-relevant items first
- use indentation rather than wide tables when tables would wrap badly

### Recommended severity vocabulary
Use a small, stable vocabulary:

- **Action now**
- **Worth addressing soon**
- **Monitor / no trade now**
- **Blocked / not actionable**

This is better than a rainbow of labels or too many urgency tiers.

### Recommended confidence vocabulary
- **High**: data complete, rule clear, constraint checked
- **Medium**: recommendation valid but replacement/score depends on weaker metadata or gray-zone substitution logic
- **Low**: basis missing, account restrictions incomplete, or recommendation is mostly diagnostic

---

## 10) Process-log design

The process log should track whether the engine followed a disciplined process, not whether the portfolio beat a benchmark. This matches the spec and avoids v1 scope drift into outcome attribution.

## Process log purpose
For each recommendation, capture:

- what the thesis was
- what condition would invalidate it
- whether the recommendation respected core guardrails
- whether the same issue keeps appearing across snapshots

## Recommended fields
The Phase 7 schema is directionally correct. For MVP reporting, a process log row should effectively communicate:

- date
- snapshot_id
- recommendation_id
- action
- thesis
- invalidation_rule
- fee_drag_bps
- diversification_ok
- wash_sale_clean
- concentration_within_limits

### Recommended additions if allowed later
These would improve auditability, but are not required for the MVP deliverable:

- tax_note_present (boolean)
- estimated_tax_cost_known (boolean)
- account_menu_validated (boolean)
- target_exposure_preserved (boolean)
- status: open / completed / invalidated / deferred

## Good process-log examples

### Good thesis
“Relocate bond exposure from taxable to IRA because bond income is tax-inefficient in taxable and sheltered capacity exists.”

### Good invalidation rule
“Invalidate if taxable bond exposure falls below threshold or IRA menu/capacity prevents the move.”

### Good non-trade thesis
“Do not trim VTI in taxable because estimated tax drag exceeds drift benefit.”

### Good non-trade invalidation rule
“Invalidate if offsetting losses emerge, contribution flow cannot correct drift, or gain estimate materially changes.”

## What not to log in MVP
- alpha thesis
- macro prediction
- benchmark-relative regret
- realized performance scoreboard
- subjective conviction notes from an LLM

These would weaken the product’s discipline and violate the spirit of the spec.

---

## 11) How recommendations should be explained

Each recommendation should have a short explanation template.

### Explanation template
1. **Problem**: what is wrong or suboptimal
2. **Constraint**: what limits possible fixes
3. **Action**: what to do
4. **Why this action wins**: why it is preferred over alternatives
5. **Invalidation**: what would make this recommendation stale or wrong

### Example
```text
Problem: Bond fund held in taxable creates avoidable ordinary-income tax drag.
Constraint: Large taxable sale would realize gains; IRA has available capacity.
Action: Redirect new bond exposure to traditional IRA and stop adding to taxable position.
Why this wins: improves tax location without forcing a gain realization.
Invalidation: no IRA capacity, menu restriction, or taxable position exits naturally.
```

This structure is readable in a terminal and directly supports process logging.

---

## 12) Handling missing or uncertain data in the report

The report should never hide uncertainty.

### Required uncertainty patterns
- **Tax impact unknown** when basis or lot detail is missing
- **Menu validation incomplete** when destination account permissions are not known
- **Exposure similarity uncertain** when replacement overlap cannot be established confidently
- **Wash-sale gray zone** when same-index-family but not same-ticker substitution needs caution

### Reporting rule
Uncertain items can still appear in diagnostics, but should be downgraded in confidence and should not be presented as clean, urgent actions.

---

## 13) MVP patterns to adopt

### Pattern: rule-driven narrative generation
The report should be composed from deterministic recommendation objects and computed metrics, not free-form prose generation.

### Pattern: show only top offenders
For concentration, fee, and holdings-to-challenge sections, list the top 3–5 items rather than every minor issue.

### Pattern: protective “no trade” messaging
If taxes, wash-sale rules, or thresholds block action, report that clearly as an intentional outcome.

### Pattern: account-scoped actions
Actions should be grouped by account after the global priority list so the user can implement them cleanly.

### Pattern: explicit blind-spot disclosure
End with a compact note such as:

```text
Blind spots: private assets, pension/human capital, future tax-law changes, incomplete cost basis, and any holdings not provided in the input files.
```

---

## 14) MVP exclusions relevant to reporting

These should be explicitly excluded from reporting v1 even if tempting.

### Exclusions
- interactive charts or HTML dashboards
- historical performance sections
- benchmark comparison sections
- optimizer-derived recommended weights
- factor-performance attribution
- news or macro commentary affecting recommendation wording
- personalized behavioral coaching copy
- LLM-authored recommendation summaries

### Reason
The MVP report should remain deterministic, offline, auditable, and tightly aligned with the decision engine’s rule set.

---

## 15) Recommended final report outline for synthesis

```text
TAX-AWARE PORTFOLIO AUDIT

BOTTOM LINE
PRIORITY ACTIONS
PORTFOLIO GRADE
CURRENT VS TARGET ALLOCATION
CONCENTRATION & DIVERSIFICATION FLAGS
TAX-AWARE FINDINGS
ACCOUNT-LOCATION FINDINGS
FEE DRAG & REPLACEMENT OPPORTUNITIES
HOLDINGS TO CHALLENGE
PROCESS LOG
DISCLOSURES / BLIND SPOTS
```

This is the right MVP reporting shape because it is:

- action-first
- compact
- process-auditable
- tax-aware
- safe for offline CLI use
- aligned with the spec’s requirement to justify both action and no-action outcomes

---

## Bottom-line recommendation for the reporting subagent

For the MVP, the report should use a **deterministic, action-first CLI layout** built around a visible Portfolio Grade, a priority-ordered recommendation list, and a process log that tracks discipline rather than returns. The key metrics should be limited to those that directly support asset location, concentration control, fee reduction, drift management, and wash-sale-safe tax actions. Risk should be presented as concise decision-risk tags and fragility flags, not as a full statistical analytics suite. The report must make “No action is justified” feel like a successful, evidence-backed result rather than a missing output.
