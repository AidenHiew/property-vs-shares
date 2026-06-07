# Property vs Shares Model — Design Spec

*Date: 2026-05-10. Status: design draft, awaiting user approval. Author: Claude (Opus, brainstorming with the user). Project root: `/Users/aidenmacmini/AI Project/Financial Modeling/`.*

---

## 1. Purpose

A personal-use Monte Carlo simulator that lets the user honestly compare investing the same capital in **leveraged Australian residential investment property** versus **Australian / global shares** over a multi-decade horizon, under realistic AU tax rules and with explicit handling of the fairness traps that make most existing calculators misleading.

The user is in Adelaide, SA. The user is making a real ongoing allocation decision (property vs shares). The tool exists to settle that question for the user's own situation, not to be sold or shipped publicly. Monetisation, SEO, AFSL disclaimers, and account systems are out of scope by design.

The signature features (which no existing AU tool offers together) are:

- **Probability framing** — the headline output is "P(property beats shares)" across 5,000 Monte Carlo trials, not a single fake terminal-wealth number.
- **Three normalisation modes** — the user can switch between "same deposit / different leverage" (realistic), "same total exposure / same leverage on both" (fair fight), and "same equity + same leverage" (asset-quality comparison).
- **Symmetric reinvestment-of-cashflow** — whichever strategy generates spare cash in a given year, that cash is invested into the *other asset class* of that strategy, so both strategies deploy identical total capital over time. No silent subsidy.
- **Year-by-year cashflow stress visualisation** — see the squeeze in year 7 when rates rise, not just the end-state number.

## 2. Scope

### In v1

- Two operating modes: **Abstract / parametric** (sliders for everything, no specific property) and **Specific property** (enter a real listing's price, rent, etc.).
- AU tax engine, FY2026 rules, **South Australia only** for state-level taxes.
- Investment property only. User is assumed to be renting their own home throughout the horizon (so accommodation cost is symmetric and nets out of the comparison).
- Monte Carlo with 5,000 trials, configurable μ and σ on five random variables, optional correlation between property and shares.
- Three leverage-normalisation modes (see §6).
- Symmetric reinvestment of cashflow between strategies.
- Streamlit web UI run locally on the user's laptop.

### Explicitly out of v1 (and why)

| Excluded | Reason |
|---|---|
| Place-of-residence (PPOR) modelling | Different tax treatment (imputed rent, CGT exemption); a separate tool. |
| Other states' stamp duty / land tax | User is SA-resident; adding 7 other state regimes is busywork until needed. |
| SMSF property purchase | Different product, different rules (LRBA, etc.). |
| Medicare Levy / MLS | Out for the same reason as TaxBite v1 — this is a comparison tool, not a tax estimator. |
| HECS / HELP repayments | Doesn't change the comparison materially. |
| Capital works deduction recapture on sale | Modest impact, complex to model correctly. |
| LMI (Lender's Mortgage Insurance) | Assumed user has 20 % deposit; LMI scenarios deferred. |
| Specific share / ETF product selection (Pearler, Stake, Vanguard, etc.) | Generic share returns only. No product recommendations. |
| Fat-tailed / regime-switching return models | Independent normal draws are good enough for personal-decision precision. |
| **Budget-2026 negative gearing changes** | **Federal Budget is May 13. v1 ships with current FY2026 rules only. v1.1 adds a regime toggle once the actual law is known.** |

## 3. Architecture

### File layout

```
Financial Modeling/
├── 2026-05-10-property-vs-shares-design.md   # this spec
├── market-research-property-vs-shares.md     # market scan (already exists)
└── property-vs-shares/                       # the actual app
    ├── README.md                             # how to run it
    ├── requirements.txt                      # numpy, pandas, streamlit, plotly, pytest
    ├── config.py                             # constants: TRIALS=5000, defaults, AU tax brackets
    ├── model/
    │   ├── __init__.py
    │   ├── tax.py                            # MTR, neg gearing, franking, CGT, stamp duty, land tax
    │   ├── property_strategy.py              # year-by-year property cashflow + terminal sale
    │   ├── shares_strategy.py                # year-by-year shares cashflow + terminal sale
    │   ├── monte_carlo.py                    # the 5000-trial loop, vectorised in numpy
    │   └── normalisation.py                  # the three "fair fight" modes
    ├── app.py                                # Streamlit UI; imports from model/
    ├── scratch.ipynb                         # dev notebook (not for end-user)
    └── tests/
        ├── test_tax.py                       # worked examples for each tax function
        ├── test_property_strategy.py         # known-good cashflow scenarios
        ├── test_shares_strategy.py
        └── test_normalisation.py
```

### Module responsibilities

- **`config.py`** — all magic numbers and defaults in one place. Tax brackets, default μ/σ for each random variable, default holding costs, default correlation, `TRIALS = 5000`. When tax law changes, this is the file you mostly edit.
- **`model/tax.py`** — pure functions. `marginal_tax(income, brackets)`, `franking_credit_refund(grossed_dividends, mtr)`, `cgt_payable(gain, holding_period_years, mtr)`, `sa_stamp_duty(price)`, `sa_land_tax(unimproved_value)`. No I/O, no globals, fully testable.
- **`model/property_strategy.py`** — given a single Monte Carlo trial's random draws, produces a 30-year cashflow series plus terminal sale-and-tax event for one property scenario.
- **`model/shares_strategy.py`** — same, for shares.
- **`model/monte_carlo.py`** — vectorised 5,000-trial runner. Returns the full distribution of terminal wealth and year-by-year cashflows for both strategies.
- **`model/normalisation.py`** — applies whichever of the three "fair fight" rules to make the strategies comparable.
- **`app.py`** — Streamlit-only. UI, sliders, charts, layout. Imports `model.*` and feeds outputs to Plotly. No business logic in this file.
- **`scratch.ipynb`** — Claude's working notebook for developing and validating the model. The user never opens this.
- **`tests/`** — `pytest` with worked examples. Catches regressions when tax rules change. Each tax function has at least one ATO-cross-checked test case.

This separation matters for one reason: when the May 13 Budget changes negative gearing, we update **one function** in `model/tax.py`, the tests prove the unchanged scenarios still produce identical numbers, and the Streamlit app continues to work without UI changes.

## 4. Inputs

All defaults are pre-loaded from `config.py` to AU-realistic values so the tool is usable on first launch with zero configuration.

### 4.1 User profile

| Input | Default | Notes |
|---|---|---|
| Marginal tax rate | 37 % | FY2026 brackets pre-loaded; user's MTR is selected from a dropdown |
| State | SA | Only SA implemented in v1 |
| Investment horizon | 25 years | Slider 5–40 |

### 4.2 Property scenario

Two sub-modes, switchable in the UI:

**Abstract mode** (sliders only):

| Input | Default | Range |
|---|---|---|
| Purchase price | $700,000 | $300k–$2m |
| Deposit | $140,000 (20 %) | 5–50 % |
| Loan rate | 6.0 % | 3–10 % |
| Loan term | 30 yrs | 15–30 |
| Interest-only period | 5 yrs | 0–10 (then converts to P&I) |
| Gross rental yield | 4.0 % | 2–7 % |
| Vacancy | 2 weeks/yr | 0–8 |
| Management fee | 7 % of rent | 0–10 |
| Maintenance + insurance + rates | 1.2 % of value/yr | 0.5–3 |
| Annual depreciation deduction | $0 | 0–$15,000 (user supplies QS estimate or guesses) |
| Capital growth μ / σ | 5.5 % / 8 % | configurable |
| Selling costs at exit | 2.5 % of sale price | agent + legal |

**Specific-property mode** (when user has a real listing in mind):

Same fields, but pre-populated by the listing details the user enters once. UI shows a panel: "Modelling: 14 Example St, Adelaide — $720k, 4.1 % gross yield, $X stamp duty calculated."

### 4.3 Shares scenario

| Input | Default | Range |
|---|---|---|
| Initial capital | (derived — see §6 normalisation) | — |
| Total return μ / σ | 8.5 % / 15 % | configurable |
| Dividend yield (of total return) | 3.5 % | 1–6 % |
| Franked portion of dividends | 70 % | 0–100 % (AU-tilted default) |
| Management expense ratio (MER) | 0.20 % | 0.05–1 % |
| Brokerage per trade | $10 | trivial but included |
| Margin loan rate (fair-fight modes only) | 7.5 % | 5–12 % |
| Dividend reinvestment (DRP) | On | toggle |

### 4.4 Macro / shared

| Input | Default | Notes |
|---|---|---|
| CPI (for "show in today's dollars" toggle) | 2.5 % | RBA target midpoint |
| Property–shares return correlation | 0.3 | not zero, not one |
| Show outputs in | Nominal | toggle: nominal / real |

## 5. Tax engine

All implemented in `model/tax.py` as pure functions, with worked-example tests against ATO-published outcomes.

### Implemented in v1

- **Marginal income tax** — FY2026 resident brackets.
- **Negative gearing** — net rental loss (rent − all deductible costs − loan interest − depreciation) deducted against the user's other income at their MTR. Current rules: full deductibility, no quarantining.
- **Franking credits** — gross-up dividends, apply MTR, allow refund of excess imputation credits (standard individual treatment).
- **CGT 50 % discount** — applied to capital gain on any asset held > 12 months, then taxed at MTR. Both property and shares qualify for any reasonable horizon.
- **SA stamp duty** — 2026 SA bands on transfer of investment property.
- **SA land tax** — 2026 SA bands on unimproved land value (rough proxy: 60 % of purchase price unless user overrides).
- **Property holding costs** — fully deductible: management, rates, insurance, maintenance, loan interest, depreciation, land tax.
- **Selling costs** — capitalised into cost base reduction (i.e. reduce the gain).

### Not implemented (clearly labelled in UI as "not modelled")

- Medicare Levy / MLS, HECS, capital works recapture, Div 40 vs Div 43 split, LMI, SMSF mechanics, other states.

### Budget-2026 handling

For v1: only current FY2026 negative gearing rules are implemented. There is **no toggle** in v1 — the user gets the current-rules answer.

For v1.1 (planned for the week after May 13): once the actual Budget changes are known, add a `tax_regime: Literal["fy2026_current", "fy2026_post_budget"]` parameter to the relevant tax functions, expose a radio button in the UI, and write parallel tests for the new regime. Existing tests must continue to pass unchanged for the current regime.

## 6. Comparison engine — the dual view + three normalisation modes

This is the model's signature feature. The user picks which question they're asking; the tool runs the appropriate normalisation.

### Mode A — "Realistic" (the default)

- Property: user-specified deposit, leveraged via mortgage to user-specified purchase price.
- Shares: starts with the **same deposit amount** as the property scenario, no leverage.
- This is what 99 % of people actually do in real life, and is what every other AU calculator shows. Property looks better mostly because of leverage, not because of asset quality.

### Mode B — "Fair fight" (matched total exposure)

- Property: same as Mode A.
- Shares: starts with the **same total dollars at risk** as the property's purchase price, funded by the same equity contribution + a margin loan at the user-specified rate.
- This isolates the asset-quality question by removing the leverage advantage.
- Includes margin call mechanics? **No, deferred.** v1 assumes no margin call (user maintains LVR via cash injection). Realistic for a personal-decision tool; can revisit if results are sensitive to it.

### Mode C — "Asset only" (matched equity + zero leverage on both)

- Both strategies: same starting capital, no borrowing on either side.
- Answers "is residential property a better unleveraged asset than a diversified share portfolio?"
- This is the comparison economists care about; everyone else ignores it.

The UI shows a single radio at the top of the results panel: **Compare in: [Realistic] [Fair fight] [Asset only]**. Re-runs Monte Carlo on switch (sub-second).

### Symmetric reinvestment-of-cashflow

In every mode, in every year, both strategies must deploy **identical total after-tax capital** for the comparison to be fair.

Implementation:

- Compute property strategy's net after-tax cashflow for the year. If it's negative (out of pocket), the user funds it from outside income — we do **not** add this to either strategy's wealth, but we *do* require the shares strategy to "use" the same outside dollars, by adding them to the shares portfolio.
- Concretely: in year *t*, if the property strategy needs $X in to maintain itself, the shares strategy contributes the same $X to the share portfolio in that year. If the property strategy generates $Y of positive cashflow, that $Y is invested into shares *within the property strategy* (so the property strategy ends with house + small share portfolio).
- This is the single most important fairness fix versus existing calculators, and it's the assumption surfaced most prominently in the UI.

## 7. Monte Carlo engine

Implemented in `model/monte_carlo.py`, vectorised in numpy.

### Random variables (per trial, per year)

For every variable below, the **value the user enters in §4 is the mean (μ)**. A new value is drawn each year of each trial using the σ shown here. The user can override σ for each variable in an "advanced" panel.

| Variable | Default μ | Default σ | Distribution |
|---|---|---|---|
| Property capital growth | 5.5 % | 8.0 % | Normal |
| Share total return | 8.5 % | 15.0 % | Normal |
| Rental yield (relative to value) | (= user input) | 0.3 pp | Normal |
| Vacancy weeks | (= user input) | 1 week | Normal, floored at 0 |
| Loan rate | (= user input) | 0.5 pp | Normal, with shock-test override |

### Correlation

Property capital growth and share total return are correlated (default 0.3) via Cholesky decomposition. All other variables are drawn independently.

### Trial count

`TRIALS = 5000` in `config.py`. Hidden from the user. Yields ~±0.5 % standard error on the headline P(property > shares).

### Outputs from the engine

For each Monte Carlo trial, return:

- Terminal after-tax wealth for the property strategy.
- Terminal after-tax wealth for the shares strategy.
- Year-by-year after-tax cashflow series for both.
- Year-by-year wealth-on-paper series for both.

Aggregated across trials, compute and surface:

- **P(property > shares)** — the headline.
- 10th / 50th / 90th percentile terminal wealth for each strategy.
- Median year-by-year cashflow for each strategy.
- Worst-decile cashflow path (the "year 7 squeeze" view).

## 8. Outputs / UI layout

Streamlit single-page layout, top-to-bottom, mobile-irrelevant (this is a desktop tool).

```
┌─────────────────────────────────────────────────────────────┐
│  PROPERTY vs SHARES — your scenario                         │
│  [Realistic] [Fair fight] [Asset only]    [Nominal] [Real]  │
├─────────────────────────────────────────────────────────────┤
│  ⚠ Both strategies deploy the same total capital each year. │
│    When property needs $X to feed negative gearing, shares  │
│    invests the same $X. (Symmetric reinvestment — ON.)      │
├─────────────────────────────────────────────────────────────┤
│  HEADLINE: Property beats shares in 47% of 5,000 simulated  │
│            futures over your 25-year horizon.                │
│                                                              │
│  [Big distribution chart: terminal wealth, both strategies] │
├─────────────────────────────────────────────────────────────┤
│  CASHFLOW STRESS                                             │
│  [Year-by-year cashflow chart, median + worst-decile band]  │
├─────────────────────────────────────────────────────────────┤
│  OTHER ASSUMPTIONS (collapsible)                             │
│  - Negative gearing: current FY2026 rules                    │
│  - Tax: SA, MTR 37%                                          │
│  - 5,000 Monte Carlo trials, correlation 0.3                 │
│  - Buy-and-hold share portfolio (no mid-period rebalancing)  │
├─────────────────────────────────────────────────────────────┤
│  INPUTS (left sidebar — sliders for everything in §4)       │
└─────────────────────────────────────────────────────────────┘
```

The symmetric-reinvestment banner sits **above** the headline and is always visible. It is the single most important fairness assumption and the user must see it before they read the headline number.

Inflation toggle re-renders all dollar figures via the CPI deflator without re-running Monte Carlo.

Mode toggle (Realistic / Fair fight / Asset only) does re-run Monte Carlo (sub-second).

## 9. Testing

`pytest` in `tests/`. Coverage targets:

- Every function in `model/tax.py` has at least one worked-example test cross-checked against an ATO publication or authoritative source. Examples:
  - "$700k SA investment property purchase → stamp duty = $X" (cross-check against RevenueSA calculator)
  - "$50k taxable income, $10k rental loss, MTR 32.5 % → tax saving = $3,250"
  - "$700 fully franked dividend, MTR 19 % → refund = $X"
  - "$200k capital gain, held 5 years, MTR 37 % → CGT = $37,000"
- `model/property_strategy.py` and `model/shares_strategy.py` have at least 3 known-good full-year cashflow tests each, derived from a hand-calculated worked example.
- `model/normalisation.py` has tests proving each mode produces the correct equity / leverage allocation.
- `model/monte_carlo.py` has a determinism test (fixed seed → reproducible output) and a convergence test (5,000 trials gives stable percentiles within ±1 %).

The test suite is the safety net for tax-rule changes. When the May 13 Budget changes negative gearing, all current-rule tests must continue to pass unchanged; new tests for the new regime are added alongside.

## 10. Open assumptions to validate during build

Things flagged as deliberate v1 simplifications, in case they turn out to bite:

1. **Land tax proxy** — using 60 % of purchase price as unimproved land value. Rough; SA-specific override would be cleaner but requires user input the user probably doesn't have.
2. **Single-property assumption** — v1 models one investment property. Portfolio of properties is out of scope.
3. **No margin call modelling in Mode B (Fair fight)** — assumes user maintains LVR via cash if shares fall. Realistic for a personal-decision tool.
4. **Loan rate variability is shared between IO and P&I phases** — same μ/σ throughout the loan life.
5. **Depreciation is a single annual constant** — real depreciation declines over time (Div 40 plant items wear out faster than Div 43 building). v1 uses the user's flat estimate.
6. **No transaction-cost modelling on rebalancing within the share portfolio** — DRP is free in real life; periodic rebalancing isn't modelled.
7. **Buy-and-hold share portfolio** — no mid-period sales, so no CGT events except at the terminal sale. A real investor rebalancing or switching ETFs would trigger interim CGT; v1 ignores this. Effect: small bias in favour of shares.

Each of these is acceptable for v1. If results come back implausible during validation, we revisit.

## 11. v1.1 backlog (deliberately deferred)

- **Budget-2026 regime toggle** — added the week after May 13, once the law is known.
- Other states' stamp duty / land tax (NSW, VIC, QLD first).
- LMI for sub-20 % deposit scenarios.
- Depreciation schedule by property age (Div 40 + Div 43 split).
- Multi-property portfolio mode.
- Margin call mechanics in Mode B.
- Export results to PDF for "I want to show this to my accountant" moments.

## 12. Build effort estimate

- Tax engine + tests: ~1 evening (mostly already-known formulas).
- Property + shares strategy modules + tests: ~1 evening.
- Monte Carlo engine: ~half an evening (numpy vectorisation is the main work).
- Normalisation modes: ~half an evening.
- Streamlit UI: ~1 evening.
- Validation, polish, defaults tuning: ~1 evening.

Total: **~3 evenings of focused build, plus a half-evening for the v1.1 Budget toggle when the time comes.**

---

*End of design spec. Awaiting user review before handing off to writing-plans.*
