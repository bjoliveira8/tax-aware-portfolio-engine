# Factor Tilt Research for Tax-Aware Portfolio Decision Engine MVP

## Purpose
This document answers one narrow question for the MVP:

**Which factor ideas are robust enough to influence a static model portfolio, without turning the product into an optimizer, alpha engine, or tactical allocator?**

The execution plan is explicit that the product is **not an alpha engine** and must not drift into:

- portfolio optimization
- benchmark-relative performance chasing
- regime-based tactical allocation
- backtesting-driven factor selection
- frequent trading justified by style views

That means factor research here should only support **small, slow-moving structural tilts inside user-owned model portfolios**. It should not create a system that predicts which factor will outperform next.

---

## MVP framing

### What a factor tilt is allowed to do in v1
A factor tilt may:

- slightly change the composition of a static stock allocation sleeve
- influence which broad ETF category is used in a model portfolio
- help explain why one diversified fund role is chosen over another
- affect **new contributions** and **tax-advantaged placement** more than taxable selling

### What a factor tilt is not allowed to do in v1
A factor tilt may not:

- change recommendations based on recent performance
- trigger tactical rebalances when a factor becomes "cheap" or "hot"
- override tax, wash-sale, concentration, fee, or account-menu constraints
- require score optimization across many portfolios
- cause the engine to search for best historical Sharpe ratio
- justify individual stock picks
- justify concentrated thematic bets

This distinction is critical. In MVP, factors can shape the **default static blueprint**, not the **decision engine’s ongoing judgment about the market**.

---

## Decision standard for inclusion

A factor idea is suitable for MVP only if it meets most of these tests:

1. **Persistent enough in long-horizon evidence** to be treated as a structural possibility rather than a short-lived anomaly.
2. **Simple to express using low-cost diversified funds**, not custom multi-asset optimization.
3. **Low turnover implementation** is feasible.
4. **Understandable by a household investor** in plain English.
5. **Compatible with tax-aware behavior**, especially buy-and-hold and contribution-led rebalancing.
6. **Not dependent on market timing**, valuation timing, or frequent re-estimation.
7. **Does not require the engine to forecast returns**.

Ideas that fail those tests may still be academically interesting, but they are out of scope for this product version.

---

## High-level conclusion

For this MVP, the most defensible stance is:

1. **Keep the core model portfolios market-cap broad and simple.**
2. **Allow at most modest structural equity tilts**, not an elaborate factor stack.
3. **Prefer factors with long research histories and intuitive economic stories**, especially those implementable through diversified index-like vehicles.
4. **Make factor tilts optional and bounded**, so the product remains primarily an asset-allocation and tax-efficiency tool.

The strongest MVP choice is therefore:

- **Core default:** no required factor tilt beyond broad market exposure.
- **Permitted modest tilt:** a small **value** tilt, preferably paired with **small-cap value** exposure if used at all.
- **Secondary optional tilt:** a mild **quality / profitability bias** only when it is available through broad, low-turnover funds and does not complicate the product.
- **Exclude** momentum, low-volatility, carry, multifactor optimization, smart-beta rotation, and tactical factor timing from v1.

---

## Candidate factors

## 1) Market beta / broad market exposure

### Why it belongs
This is not a "tilt" in the usual sense, but it is the baseline against which all tilts should be judged.

Broad market-cap-weighted exposure has the properties the MVP needs:

- very low complexity
- low fees
- low turnover
- high tax efficiency when implemented with broad ETFs
- easy explanation
- no forecasting requirement

### MVP role
This should remain the **dominant equity foundation** in every static model portfolio.

### Practical implication
If factor sleeves are included, they should be **additive and modest**, not replacements for the broad diversified core.

---

## 2) Value

### Why value is a serious MVP candidate
Value is one of the few factor ideas with:

- very long academic and practitioner history
- intuitive economic rationale
- evidence across multiple markets and long periods, though not consistently in every decade
- practical implementation via diversified ETFs and index funds

The broad intuition is simple: cheaper companies relative to fundamentals have historically delivered higher long-run returns than expensive companies, with long droughts and meaningful tracking error.

### Why it fits a static model better than a tactical model
Value works best in this product only if treated as:

- a **long-horizon belief**
- a **small strategic bias**
- something the investor must be willing to hold through multi-year underperformance

It does **not** fit as a signal for buying when spreads look attractive or reducing when value has recently outperformed. That would become tactical factor timing.

### Risks and caveats
A value tilt introduces:

- long periods of underperformance relative to cap-weighted broad equity
- behavior risk, because users may abandon the tilt after disappointment
- implementation variation, because "value" definitions differ widely
- possible tax inefficiency if implemented with high-turnover active funds

### MVP verdict
**Include as an optional modest structural tilt.**

### MVP implementation pattern
- Express through a **diversified, low-cost value or small-cap value ETF/fund**.
- Keep the tilt **small relative to the total equity allocation**.
- Favor use in **tax-advantaged accounts** if the chosen fund is less tax-efficient than the broad-market core.
- Never force taxable sales solely to create a value tilt.
- Prefer funding the tilt through:
  - new contributions
  - rebalancing inside IRA/Roth/HSA/401(k)
  - initial portfolio construction

### Recommended guardrails
- Treat value as a **slow static sleeve**, not an active recommendation engine.
- Do not compare multiple value funds with optimizer logic.
- Do not dynamically scale the tilt based on valuation spreads, macro regime, or trailing returns.

---

## 3) Small size, especially small-cap value

### Why it is relevant
The size factor by itself is less clean than value in practical implementation, but **small-cap value** has historically been one of the more persistent combined factor expressions in the literature and in practitioner portfolios.

The MVP should think about size mainly in this combined form, not as a standalone "own more small caps" rule.

### Why it can fit the MVP
A modest small-cap value sleeve can be justified as:

- a long-horizon diversification of equity style exposure
- a structural complement to cap-weighted large-cap-heavy indexes
- a simple, one-fund implementation in static models

### Why caution is needed
Small-cap value can bring:

- deeper and longer tracking-error pain
- higher volatility than broad market exposure
- wider fund dispersion in fees, liquidity, and methodology
- potential tax-efficiency concerns versus broad total-market ETFs

### MVP verdict
**Include only as the preferred expression of a value tilt, not as a separate independent tilt.**

In practice, that means the model portfolio should not have separate knobs for:

- value
- size
- small-cap

Instead, if the product wants a factor sleeve at all, **small-cap value is the cleanest single sleeve to represent that choice**.

### MVP implementation pattern
- Use **one diversified small-cap value sleeve** rather than several overlapping factor funds.
- Cap the sleeve at a modest share of equities.
- Place it preferentially in **tax-advantaged space** when possible.
- If tax-advantaged capacity is limited, it is acceptable to omit the tilt rather than force a tax-inefficient taxable reshuffle.

---

## 4) Quality / profitability

### Why it is attractive conceptually
Quality or profitability exposures have a decent evidence base and a very intuitive story:

- profitable firms
- healthier balance sheets
- more durable businesses
- less junk exposure

This can be easier for users to understand than some academic factor labels.

### Why it is less clean for MVP than value
Quality is harder for MVP because:

- definitions vary significantly by index provider
- many funds blend quality with growth or low volatility
- implementation can quietly become a style bet that is hard to explain
- some quality funds are less tax-efficient or more expensive than the MVP should tolerate

### MVP verdict
**Allow only as a secondary optional tilt, and only if implemented simply.**

It should not be a required part of v1 model portfolios. It is acceptable for synthesis to defer it if simplicity pressure is high.

### MVP implementation pattern
If included at all:

- use one broad, diversified, rules-based quality/profitability sleeve
- keep it modest
- avoid combining it with several other factor products
- do not let it displace the broad-market core

### Why it is optional rather than core
The product’s main value comes from tax and portfolio hygiene. Adding quality too early risks increasing complexity without materially improving the MVP’s main decision quality.

---

## 5) Momentum

### Why momentum is powerful in research
Momentum has one of the strongest empirical records among major factors. That makes it tempting.

### Why it should be excluded from MVP
Momentum is a poor fit for this product version because it usually implies:

- higher turnover
- more implementation complexity
- more tax friction in taxable accounts
- stronger need for disciplined periodic reconstitution
- a product posture closer to an alpha engine or tactical allocator

Even if expressed through an ETF, a momentum sleeve naturally invites questions like:

- when should the weight increase?
- when should it be cut?
- what if momentum leadership reverses?

Those are exactly the questions the MVP should refuse to answer.

### MVP verdict
**Exclude from v1 static models.**

### Reason for exclusion language
Momentum is not excluded because it lacks evidence. It is excluded because its implementation and user expectations are too close to active timing behavior for this MVP.

---

## 6) Low volatility / minimum volatility

### Why it appeals to investors
Low-volatility strategies are attractive because they sound like a way to keep equity exposure while reducing downside pain.

### Why it is not a good MVP fit
In this product, low-volatility funds create several problems:

- they can be sector-distorted, especially toward defensives
- they can become interest-rate-sensitive in unintuitive ways
- they are easy to confuse with a substitute for proper stock/bond allocation
- they can encourage product sprawl without improving the tax-aware decision engine

Most importantly, the MVP already has a simpler and more defensible way to lower risk: **increase bond allocation in the user-owned static model**.

### MVP verdict
**Exclude from v1.**

### Reason for exclusion language
If the goal is lower total portfolio volatility, use the stock/bond mix. Do not introduce a separate low-volatility factor sleeve in the first release.

---

## 7) Multifactor funds

### Why they are tempting
Multifactor products can package value, quality, size, and momentum in one vehicle, which sounds efficient.

### Why they should be excluded from MVP
For this MVP, multifactor products create hidden complexity:

- opaque methodology differences across providers
- less transparent attribution for why the fund belongs in the portfolio
- temptation to compare and optimize among smart-beta funds
- difficult tradeoffs between factor purity, taxes, fees, and overlap

This drifts away from the product doctrine of simple, explainable, deterministic recommendations.

### MVP verdict
**Exclude as a first-class design choice in v1.**

It is better to have either:

- no factor sleeve, or
- one small explicit small-cap value sleeve

than a black-box multifactor allocation.

---

## 8) Dividend, income, yield, or covered-call style exposures

### Why they are poor candidates
These strategies are commonly marketed as factors or style tilts, but for this product they are usually poor structural choices because they often:

- sacrifice tax efficiency in taxable accounts
- create misleading comfort around income distributions
- overlap heavily with sector bets or equity-income product design
- drift into outcome engineering instead of portfolio hygiene

Covered-call products are especially unsuitable due to complexity and path-dependent tradeoffs.

### MVP verdict
**Exclude from v1 model portfolios.**

---

## 9) Thematic, sector, ESG, or macro-expression tilts

### Why they are out of scope
These are generally not robust factor tilts in the sense needed here. They usually represent:

- narratives
- preferences
- sector concentration
- macro bets
- political or values overlays

Any of those may matter to an individual investor, but they do not belong in the MVP’s rules-based static factor research.

### MVP verdict
**Exclude from factor-tilt logic in v1.**

If ever supported later, they should be explicit user constraints or preference overlays, not hidden inside a factor model.

---

## Chosen MVP pattern

## Recommended hierarchy

### Tier 1: default model portfolio stance
Use **broad market-cap-weighted funds only** for the official default static model portfolios.

Reason:

- simplest to explain
- cheapest to implement
- most tax-efficient core
- least likely to create false precision
- fully aligned with the product’s primary mission

### Tier 2: permitted optional enhancement
Allow a **single modest small-cap value sleeve** as an optional strategic tilt inside the equity allocation.

Reason:

- strongest practical factor candidate for long-horizon static use
- simpler than juggling separate value, size, quality, and momentum products
- understandable as a long-run diversifying style bias

### Tier 3: optional future candidate, not required now
A **small quality/profitability sleeve** may be considered only if the implementation remains simple and tax-aware.

Reason:

- plausible evidence base
- intuitive explanation
- but adds more complexity than the MVP strictly needs

---

## Concrete static portfolio guidance

The engine needs guidance concrete enough for synthesis, but not so prescriptive that it becomes an optimizer.

## Recommended portfolio construction rules

1. **Start with stock/bond allocation first.**
   - Risk level should come primarily from the equity/fixed-income mix, not factor engineering.

2. **Use broad cap-weighted funds as the core of each equity sleeve.**
   - Example sleeve categories: US equity, international equity, bonds, cash.

3. **If a factor tilt is used, keep it within equities only.**
   - Do not build factor logic into bonds, alternatives, or tactical cash shifts.

4. **Use at most one dedicated factor sleeve in v1.**
   - Preferred sleeve: small-cap value.

5. **Keep the sleeve modest.**
   - It should be large enough to matter philosophically, but small enough that the portfolio still behaves primarily like a standard diversified allocation.
   - A reasonable synthesis constraint is to define a hard cap on the factor sleeve as a minority share of equities rather than solving for an optimal percentage.

6. **Fund the tilt gradually.**
   - Prioritize new contributions and tax-advantaged rebalancing.
   - Do not realize taxable gains solely to create or maintain the tilt.

7. **Allow omission when implementation quality is poor.**
   - If the available account menu lacks a low-cost, liquid, diversified sleeve, the correct MVP answer is to skip the tilt.

8. **Do not let factor sleeves override portfolio hygiene priorities.**
   - concentration control
   - fee reduction
   - tax efficiency
   - wash-sale safety
   - account-menu compatibility

---

## Interaction with tax-aware logic

This project is not building a pure model-portfolio app. It is building a **tax-aware portfolio decision engine**. That changes how factor tilts must behave.

### Tax-aware implications

#### 1) Factor tilts should rarely justify taxable sells
The expected long-run benefit of a modest factor sleeve is too uncertain to justify immediate taxable gain realization in most cases.

**MVP rule:** if the portfolio is broadly acceptable and embedded gains are material, the engine should prefer staying near the current broad-market structure over forcing a factor alignment trade.

#### 2) Factor sleeves belong preferentially in tax-advantaged accounts when tax efficiency is weaker
Some value or small-cap value implementations may be less tax-efficient than a broad total-market core.

**MVP rule:** if account capacity allows, place the factor sleeve in IRA/Roth/HSA before taxable.

#### 3) Wash-sale safety still dominates harvest logic
A factor sleeve does not create an exception to wash-sale rules.

**MVP rule:** a harvest replacement must first satisfy wash-sale and overlap constraints; factor preferences are subordinate.

#### 4) Contribution-led implementation is the cleanest path
Because factor alignment is lower priority than tax and concentration issues, contributions are the safest mechanism for introducing the tilt.

**MVP rule:** phrase factor-tilt implementation as `redirect contributions` or `add in tax-advantaged account` before considering taxable replacement.

---

## Recommended language for the synthesis doc

The synthesis should be able to say something close to the following:

> Factor research in v1 will not power an optimizer, alpha engine, or tactical allocation system. The official static models will remain broad and simple. The only factor tilt worth allowing in MVP is a modest, optional small-cap value sleeve funded gradually and preferably in tax-advantaged accounts. Quality/profitability is a possible later refinement but not required for launch. Momentum, low-volatility, multifactor smart-beta packages, thematic tilts, and factor timing are excluded from v1.

---

## Explicit exclusions

These exclusions matter because they keep factor logic from swallowing the product.

### Exclude from MVP entirely
- return forecasting by factor
- valuation-based factor timing
- macro-conditioned factor rotation
- optimizer-selected factor weights
- backtest-selected factor combinations
- momentum sleeves
- low-volatility sleeves
- multifactor black-box funds as a core design choice
- sector/thematic tilts marketed as factor exposure
- taxable turnover justified only by style purity

### Exclude from recommendation logic
Even if a static model contains a small factor sleeve, the recommendation engine should **not**:

- score factor opportunity
- detect factor momentum
- tell the user value is now attractive
- recommend increasing or decreasing factor weight because of macro conditions
- compare expected returns across factors
- produce urgency from factor signals

That behavior would violate the project’s "not an alpha engine" constraint.

---

## Final MVP recommendation

## Adopt this stance

1. **Default static model portfolios:** broad market-cap core, no required factor tilt.
2. **Permitted optional tilt:** one modest **small-cap value** sleeve inside equities.
3. **Possible future refinement, not needed now:** a small **quality/profitability** sleeve.
4. **Everything else excluded:** especially momentum, low-volatility, multifactor optimization, and tactical factor allocation.

## Why this is the right balance
This approach preserves:

- simplicity
- explainability
- tax-aware discipline
- low turnover
- compatibility with contribution-led rebalancing
- fidelity to the product’s real edge

And it avoids turning the MVP into something it is not:

- not a smart-beta optimizer
- not a factor timing engine
- not a backtest machine
- not a tactical allocation product

## Bottom line
The MVP should treat factor ideas as **optional, bounded design seasoning** for a static model portfolio, not as an active source of recommendations. If the product uses any factor tilt at launch, the most defensible choice is a **small, optional small-cap value sleeve** implemented conservatively and subordinated to tax, fee, concentration, and account-location rules.
