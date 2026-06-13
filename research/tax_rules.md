# Tax Rules for the Tax-Aware Portfolio Decision Engine MVP

## Purpose and scope

This document defines the **MVP tax logic** for a personal, offline portfolio audit tool. The goal is not to provide legal or individualized tax advice. The goal is to produce **conservative, auditable decision rules** that help the engine decide when to:

- prefer one account over another for a given asset,
- avoid harmful taxable sales,
- identify potential tax-loss harvesting opportunities,
- block or warn on wash-sale risk across all accounts, and
- choose replacement ETFs that are similar enough for portfolio continuity but different enough to avoid obvious wash-sale problems.

This file intentionally focuses on **simple, explainable patterns** suitable for synthesis into a deterministic rules engine. It excludes edge-case tax law coverage that would be hard to verify offline.

## MVP operating principles

1. **Taxable sales are the highest-risk action.** The engine should prefer no action, contribution redirection, or tax-advantaged trades over realizing gains in taxable accounts.
2. **Tax-loss harvesting requires strict wash-sale screening across every account.** This includes taxable, traditional IRA, Roth IRA, 401(k), HSA, and spouse-linked accounts if they are present in the imported dataset.
3. **Unknown tax data must reduce confidence, not be guessed.** Missing lots or cost basis should prevent confident sell recommendations.
4. **Account location is expressed as forward-looking placement logic, not forced unwinds.** In MVP, location improvements should usually be framed as `relocate`, `redirect contributions`, or `buy future lots in better account types`.
5. **Replacement recommendations must be conservative.** In taxable accounts, replacement ETFs should avoid same-ticker and same-index-family swaps.
6. **The tool is an audit assistant, not a tax preparer.** It can estimate tax character and risk, but not produce tax forms or guarantee compliance.

## Chosen MVP patterns

### 1) Account location hierarchy

Use a simple asset-location ranking based on ordinary-income drag, qualified-dividend treatment, expected turnover, and expected long-run appreciation.

#### Preferred placement by asset type

| Asset type / exposure | Preferred account type(s) | Why |
|---|---|---|
| Taxable bond funds, REIT funds, high-yield income funds | Traditional IRA / 401(k), then Roth if needed | Interest and non-qualified income are tax-inefficient in taxable accounts |
| Broad, low-turnover US equity ETF | Taxable, Roth, HSA | Usually tax-efficient because of low turnover and qualified-dividend potential |
| Broad, low-turnover international equity ETF | Taxable or Roth/HSA depending on user target | Often reasonably tax-efficient; foreign tax credit may favor taxable in some cases |
| Small-cap value / higher-turnover equity funds | IRA / 401(k), or Roth for high expected growth | More turnover and distributions can reduce taxable efficiency |
| High-growth equity with long horizon | Roth IRA / Roth 401(k) / HSA | Highest expected future appreciation benefits most from tax-free growth |
| Cash / settlement assets | Any | Tax impact usually secondary to liquidity need |

#### MVP location rules

- **Rule A:** Flag bond-heavy or income-heavy funds held in taxable as candidates for relocation to tax-advantaged accounts.
- **Rule B:** Prefer placing highest expected growth assets in **Roth/HSA** space, subject to account menu constraints.
- **Rule C:** Prefer placing tax-efficient broad equity ETFs in taxable accounts when tax-advantaged space is scarce.
- **Rule D:** If a better location exists but moving would require a large realized taxable gain, recommend **redirecting new money** or **using tax-advantaged rebalancing** first.
- **Rule E:** In California or New Jersey, attach an HSA note that state tax treatment may differ from federal treatment.

### 2) Lot-aware holding-period logic

The engine should evaluate tax lots independently before any taxable sale recommendation.

#### Holding period definitions for MVP

- **Short-term:** held **365 days or less** at the proposed sale date.
- **Long-term:** held **more than 365 days** at the proposed sale date.

#### Lot-level implications

- Short-term gains should be treated as materially more expensive than long-term gains.
- A recommendation engine should prefer:
  1. selling losses before gains,
  2. selling long-term gains before short-term gains if a sale is unavoidable,
  3. leaving short-term gain lots untouched unless there is an exceptional reason.

#### MVP implementation pattern

For each lot:

- compute `holding_period_days`,
- classify `is_long_term`,
- compute unrealized gain/loss if basis is known,
- label lots as:
  - `loss_long_term`
  - `loss_short_term`
  - `gain_long_term`
  - `gain_short_term`
  - `unknown_tax_status`

This taxonomy is sufficient for deterministic trade suppression and harvest screening.

### 3) Taxable-sale guardrails

These rules define when the engine should suppress or downgrade taxable sell recommendations.

#### Guardrail set

- **Guardrail 1: Missing basis or missing lot data**
  - Output `tax impact unknown`.
  - Do not issue a confident sell recommendation.
  - Allow a low-confidence note to verify basis manually.

- **Guardrail 2: Large short-term gain**
  - Suppress non-essential sells in taxable accounts.
  - Prefer no action, contribution redirection, or tax-advantaged rebalancing.

- **Guardrail 3: Large embedded gain, even if long-term**
  - If sale is not required to address a serious portfolio problem, prefer `do_nothing_due_to_tax_cost` or a gradual fix.
  - Example serious problems that may justify stronger language: extreme concentration, account-menu constraints, or an obviously unsuitable/high-fee redundant fund inside a tax-advantaged account. Even then, in taxable accounts the engine should be conservative.

- **Guardrail 4: Small drift alone is not enough**
  - Minor allocation drift should not trigger taxable sells.
  - Drift should first be corrected using new contributions, dividends, and tax-advantaged trades.

- **Guardrail 5: Confirm-with-professional threshold**
  - If an estimated realized gain or tax cost exceeds a configurable `confirm_with_cpa_above` threshold, append a note: `Confirm with a tax professional before acting.`

#### Practical MVP interpretation

Taxable accounts should be biased toward:

- `hold`
- `do_nothing_due_to_tax_cost`
- `redirect contributions`
- `replace only when loss or wash-sale-clean low-gain situation`

They should be biased away from:

- routine gain realization for cosmetic rebalancing,
- same-day “cleanup” trades that ignore lot character,
- ETF replacement solely for small fee savings when gains are large.

## Wash-sale handling

## Rule definition for MVP

A potential tax-loss harvest is blocked if the dataset shows a purchase of the same security within the **61-day wash-sale window** centered on the loss sale:

- **30 days before** the sale date,
- **sale date**, and
- **30 days after** the sale date.

This should be implemented as a practical 61-day screening rule.

### Accounts included in the wash-sale scan

The scan must include **all imported accounts**, not just taxable accounts:

- taxable brokerage
- traditional IRA
- Roth IRA
- traditional 401(k)
- Roth 401(k)
- HSA
- any other account type carrying securities

### Hard blocks

Block the harvest if any of the following occur inside the window:

1. **Same ticker purchased in any account**.
2. **Automatic reinvestment** into the same ticker is expected and not disabled.
3. **A replacement recommendation uses the same ticker**.
4. **An IRA or Roth account buys the same security in-window**. This should be flagged prominently because the disallowed loss is generally not recoverable via basis adjustment in the retirement account.

### Gray-zone handling: substantially identical risk

The IRS does not provide a clean, machine-verifiable definition of “substantially identical” for ETFs. For an MVP personal audit tool, use a conservative rule set:

#### Treat as too risky in taxable replacement logic

- Same ticker.
- Different share class of the same fund.
- Different ETF tracking the **same underlying index family**.
- Mutual fund ↔ ETF versions of the same strategy from the same sponsor when exposure is effectively identical.

#### Potentially acceptable as replacement candidates

- Broad US total-market ETF replaced by a broad US large-cap ETF.
- S&P 500 ETF replaced by a broad total-market ETF.
- One international developed-markets ETF replaced by a broader international ex-US ETF.
- Duration- or issuer-different bond ETFs, if exposure remains close enough for portfolio role.

The replacement should preserve the portfolio’s economic role **without being an obvious same-index substitute**.

### MVP wash-sale decision output

For each harvest candidate, output one of:

- `wash_sale_blocked_same_ticker`
- `wash_sale_blocked_retirement_account_purchase`
- `wash_sale_gray_zone_substantially_identical`
- `wash_sale_clean`
- `wash_sale_unknown_future_activity` if future scheduled purchases or reinvestment settings are not known

If status is anything except `wash_sale_clean`, the engine should not issue a confident harvest recommendation.

## Safe replacement logic

The replacement engine needs a simple and explainable rule system that balances portfolio continuity with wash-sale safety.

### Replacement objectives

A replacement should:

1. keep the investor exposed to the intended asset class,
2. avoid obvious wash-sale issues,
3. avoid materially worse fees/liquidity,
4. fit the destination account menu, and
5. avoid creating a new concentration or overlap problem.

### MVP replacement criteria

A replacement is acceptable only if all are true:

- **Exposure role match:** same broad portfolio role (for example: US large blend, total US equity, developed ex-US, intermediate bonds).
- **Not same ticker.**
- **Not same index family** in taxable accounts for harvest replacements.
- **Expense ratio not materially worse** than current holding unless needed for menu constraints.
- **Sufficient liquidity / AUM** relative to the current fund for a retail investor workflow.
- **Destination account can hold it**.

### Suggested replacement pattern library

These are category-level patterns, not hardcoded tickers:

- US broad market ↔ US large-cap broad market
- S&P 500 ↔ total US market
- Developed international ↔ total international ex-US
- Aggregate bond ↔ intermediate Treasury or broad intermediate bond, if role remains defensive
- REIT exposure ↔ broad real estate ETF with distinct index methodology

### Replacement exclusions for MVP

Do **not** auto-recommend replacements that require subtle legal judgment, such as:

- leveraged/inverse substitutes,
- derivative-heavy products,
- synthetic ETFs with unusual structures,
- active ETFs whose overlap to the sold fund cannot be clearly explained,
- same-index-family clones used to shave a few basis points.

## ETF tax efficiency assumptions

The MVP does not need a full tax-distribution model. It only needs simple proxies to rank likely taxable efficiency.

### Tax-efficiency proxies to use

Prefer ETFs/funds that tend to have:

- low turnover,
- broad index exposure,
- lower historical capital gain distribution tendency,
- qualified-dividend-heavy equity income rather than ordinary-interest income,
- ETF structure rather than higher-distribution mutual fund structure when exposure is otherwise comparable.

### Tax-inefficiency proxies to use

Treat the following as relatively tax-inefficient in taxable accounts:

- taxable bond funds,
- REIT funds,
- high-turnover active funds,
- funds with frequent capital gain distributions,
- high-yield income strategies with mostly non-qualified distributions.

### Important caveat

ETF tax efficiency is a **proxy**, not a guarantee. The engine should phrase this as relative ranking, not certainty.

## Decision patterns by account type

### Taxable account

Primary concerns:

- realized gains,
- holding period,
- qualified vs ordinary income character,
- wash-sale risk,
- ETF tax efficiency.

MVP behavior:

- be conservative on sells,
- prefer tax-loss harvesting only when wash-sale-clean,
- prefer contribution-driven rebalance,
- prefer relocating future purchases rather than forcing gain realization.

### Traditional tax-deferred account (401(k), traditional IRA)

Primary concerns:

- no immediate capital gains tax on trades,
- best location for tax-inefficient assets,
- account menu restrictions may dominate.

MVP behavior:

- permit more aggressive rebalancing and fund replacement,
- prioritize moving bonds and other tax-inefficient assets here,
- still respect expense ratio, liquidity, and redundancy checks.

### Roth / HSA

Primary concerns:

- limited tax-advantaged growth space is valuable,
- generally strongest location for highest expected growth assets,
- wash-sale purchases here can still taint taxable TLH if the same security is bought in-window.

MVP behavior:

- prioritize growth-oriented placements,
- allow low-tax-friction rebalancing within the account,
- include these accounts in wash-sale scans.

## Recommended deterministic scoring/ordering influence

Tax logic should not create opaque scores, but it should influence recommendation priority and suppression.

Suggested order of tax-related decision effects:

1. **Block** illegal or clearly unsafe actions.
2. **Suppress** taxable sells with high short-term or high absolute tax cost.
3. **Prefer** tax-advantaged account trades over taxable trades.
4. **Prefer** contribution redirects over realized-gain corrections.
5. **Promote** wash-sale-clean loss harvesting when portfolio exposure can be safely maintained.
6. **Defer** small fee or drift improvements if they require meaningful taxable realization.

## Concrete MVP recommendation language patterns

The report layer should use standardized language so behavior is auditable.

### Examples of acceptable output framing

- `Hold: taxable sale would likely realize a short-term gain; use future contributions to reduce drift instead.`
- `Relocate future bond purchases to traditional IRA/401(k); current taxable position appears tax-inefficient.`
- `Tax-loss harvest candidate identified, but blocked by same-ticker purchase in Roth IRA within wash-sale window.`
- `Potential replacement available with similar portfolio role, but taxable sale not recommended because embedded gain appears high.`
- `Tax impact unknown: missing cost basis for one or more lots. Verify basis before considering a sale.`
- `Large estimated tax impact. Confirm with a tax professional before acting.`

## Exclusions from MVP

The following should be explicitly excluded from v1 tax logic:

1. **Exact tax-form preparation** (Form 8949 / Schedule D output).
2. **Household-level legal attribution rules** beyond accounts explicitly imported into the dataset.
3. **Options, short sales, straddles, futures, PFICs, MLP K-1 handling, or collectibles taxation**.
4. **State-by-state tax optimization** beyond a narrow HSA warning for CA/NJ.
5. **Average-cost, specific-lot election verification at the broker level** beyond a user-supplied configuration choice.
6. **Dividend-qualified holding-period testing** at transaction-level precision.
7. **Corporate actions and basis adjustments** such as spin-offs, mergers, return of capital, or wash-sale carryovers from external systems.
8. **Automatic prediction of substantially identical status** beyond the conservative rules defined here.
9. **Tax alpha forecasting** or optimization based on future bracket changes.

## Synthesis-ready MVP rule set

For build purposes, the tax engine can be summarized in a compact deterministic policy:

1. **Classify each lot** as short-term, long-term, loss, gain, or unknown.
2. **Never issue a confident taxable sell** when cost basis is unknown.
3. **Suppress taxable sells** when gains are short-term or estimated tax cost is large relative to the benefit.
4. **Prefer tax-advantaged accounts** for bonds, REITs, and other tax-inefficient assets.
5. **Prefer Roth/HSA space** for highest expected growth assets.
6. **Use taxable space** for broad, low-turnover equity ETFs when tax-advantaged space is limited.
7. **Allow tax-loss harvesting only if wash-sale-clean across all accounts** over a 61-day window.
8. **Treat same ticker and same index-family replacement as blocked/unsafe** in taxable harvest scenarios.
9. **Recommend contribution redirection or tax-advantaged rebalancing before taxable sales** for ordinary drift correction.
10. **Escalate large estimated tax consequences** with a `confirm with a tax professional` note.

This rule set is narrow enough for an MVP, conservative enough for a personal audit tool, and concrete enough to implement without relying on an LLM for judgment.