# Codex Review: Property vs Shares Model

Prepared: 2026-05-11  
Source reviewed: `for-codex-review-2026-05-11.md`

## Summary

The design is directionally strong, but I would not trust v1 for a real allocation decision until five issues are fixed:

1. Upfront cash equality
2. Depreciation and capital works handling
3. Medicare levy treatment
4. Interest-rate stress modelling
5. The imminent 2026-27 Budget regime risk

Also note: the Budget is scheduled for **Tuesday 12 May 2026 at 7:30pm AEST**, not 13 May.

## D.1 AU Tax Accuracy

| Priority | Comment | Logic | Pros | Cons / Tradeoff |
|---|---|---|---|---|
| P0 | List the actual 2025-26 resident brackets in `config.py`. | FY2026 means 2025-26: $0-$18,200 nil; $18,201-$45,000 16%; $45,001-$135,000 30%; $135,001-$190,000 37%; $190,001+ 45%, excluding 2% Medicare levy. | Prevents hidden tax-rate drift. | Needs yearly update. |
| P0 | Negative gearing is currently correct, but politically unstable this week. | ATO still allows net rental losses against other income, but Budget changes are actively expected. | Current-law mode is valid. | Add a visible "law pending" warning until Budget details are known. |
| P0 | Franking-credit refundability is correct for eligible individuals. | ATO says excess franking credits can be refunded to Australian-resident individuals after tax/Medicare liabilities. | Good to model refunds. | Must apply anti-avoidance eligibility rules only if later modelling specific trades. |
| P0 | CGT 50% discount is correct for an Australian resident holding more than 12 months. | Applies to both shares and property for this user. | Fair symmetric treatment. | Budget may change CGT discount. Add regime toggle soon. |
| P1 | SA stamp duty bands are correct, but property upfront capital is under-specified. | $700k SA property duty is about **$32,330** before conveyancing, inspection, and loan costs. Shares should start with the same total upfront cash, not just the deposit. | Huge fairness improvement. | Makes property look worse, but honestly. |
| P1 | SA land tax should use taxable site value, not a fixed 60% proxy if an address is known. | 2025-26 general threshold is $833k; rates are progressive above that. RevenueSA says site value can be found via SAILIS / assessment data. | Better SA-specific accuracy. | Abstract mode still needs a proxy; expose it as editable. |
| P1 | Selling costs wording is wrong. | Selling costs increase cost base / reduce capital gain; do not call it "cost-base reduction." | Avoids tax confusion. | Minor wording fix. |
| P0 | Depreciation model is too blunt. | Second-hand Div 40 plant deductions are restricted post-2017; capital works may still apply, but claimed capital works generally affects CGT cost base. | Prevents overstating property after-tax returns. | Requires split: Div 40, Div 43, and terminal adjustment. |

## D.2 Defaults

| Priority | Comment | Logic | Pros | Cons / Tradeoff |
|---|---|---|---|---|
| P1 | Property capital growth mean of 5.5% nominal is plausible but should be scenario-based. | Long-run national dwelling price growth is around mid-single digits, but Adelaide and single-property dispersion is large. | Base case is not crazy. | One property is not "the market"; add low/base/high presets. |
| P1 | Share total return mean of 8.5% and volatility of 15% is defensible if the portfolio is diversified. | Vanguard's 30-year Australian chart shows Australian shares around 10%+ annualised; 8.5% is conservative for equities. | Conservative default is good. | Define the portfolio: ASX-only, global, or blended. |
| P2 | Rental-yield volatility of 0.3 percentage points is probably too tight. | Rents and yields can move materially, especially in small markets. | Avoids over-noising rent. | Understates rental stress; use 0.5-0.8 percentage points or a mean-reverting model. |
| P2 | Vacancy volatility of 1 week is okay for Adelaide today, but stress should be harsher. | Adelaide vacancy has been very tight, but investor risk is tenant default, turnover, and repairs, not only market vacancy. | Simple. | Add "bad tenant year" event. |
| P0 | Loan-rate volatility of 0.5 percentage points per year is too tame. | RBA cash rate rose about 4 percentage points from May 2022 to late 2023. | Base model remains stable. | Add rate shock paths: +2%, +4%, and higher-for-longer. |
| P1 | Property-shares correlation of 0.3 is a weak eyeball default. | Housing/equity correlation is regime-dependent and can change in crises. | Fine as a slider default. | Do not imply precision; include -0.1 / 0.3 / 0.6 scenarios. |
| P1 | Franked portion of dividends at 70% needs portfolio presets. | ASX-heavy portfolios may be higher; global ETFs much lower. | Useful middle default. | Misleading unless tied to portfolio mix. |

## D.3 Fairness Modelling

| Priority | Comment | Logic | Pros | Cons / Tradeoff |
|---|---|---|---|---|
| P0 | Fix upfront-capital symmetry first. | Property cash outlay is deposit + stamp duty + buying costs + initial repairs. Shares must receive the same initial cash. | Removes biggest property bias. | User may dislike seeing stamp duty drag so clearly. |
| P0 | Symmetric reinvestment is conceptually right, but rename it. | It is really "equal outside-cash contributions." Property positive cashflow belongs inside the property strategy; it is not a subsidy. | Clearer for mom-and-dad users. | Slightly more explanation needed. |
| P1 | Show total outside cash contributed. | Mode A otherwise becomes hard to interpret: property plus annual top-ups vs shares dollar-cost averaging. | Makes affordability visible. | Adds one more headline metric. |
| P1 | Mode B is useful but dangerous without margin-call modelling. | Leveraged shares are not just "same exposure"; margin loans have forced-sale/cash-call risk. | Good fairness lens. | Hide under advanced until margin mechanics exist. |
| P2 | Mode C is academically useful, not a main decision mode. | Unlevered direct property vs unlevered shares answers asset quality, not the real investor choice. | Useful sanity check. | Keep it, but do not make it prominent. |

Worked example: if property becomes positively geared from year 6, the property strategy should hold "property + accumulated surplus invested in liquid assets." The shares strategy holds its share portfolio. That is comparable as total strategy wealth, as long as both strategies had equal initial and external cash contributions.

## D.4 Missed / Underweighted Items

| Priority | Comment | Logic | Pros | Cons / Tradeoff |
|---|---|---|---|---|
| P0 | DRP dividends are still taxable each year. | ATO treats reinvested dividends as assessable income. | Must be modelled for shares accuracy. | Requires annual tax drag. |
| P0 | Add cash-buffer / serviceability failure. | A "winning" property path is useless if year-7 cashflow forces sale. | Better real-life decision support. | More complex Monte Carlo state. |
| P1 | Rent and costs need explicit inflation/escalation. | Rent, rates, insurance, maintenance, and strata do not stay flat. | Improves realism. | Adds assumptions; use editable defaults. |
| P1 | Single-property idiosyncratic risk is missing. | Shares are diversified; one Adelaide property has suburb, tenant, building, and maintenance concentration risk. | More honest comparison. | Hard to parameterise; add stress events. |
| P1 | Include major capex events. | Roof, hot water, aircon, vacancy plus repaint can dominate a year's cashflow. | Better mom-and-dad realism. | Use simple probability/event model. |
| P2 | Offset account exclusion is okay, but make it explicit. | Offset is a third strategy and can matter for liquidity. | Avoids scope creep. | Add later if the user actually has offset cash. |
| P2 | Ownership structure assumed individual. | Spouse split, trust, or company ownership can change tax and land tax. | Fine for v1 personal tool. | Put assumption visibly in UI. |

## D.5 Architecture / Build Risk

| Priority | Comment | Logic | Pros | Cons / Tradeoff |
|---|---|---|---|---|
| P0 | Use external calculators for golden tests. | If AI writes both tax code and tests, both can share the same mistake. | Stronger validation. | Manual setup work. |
| P1 | Start a git repo before coding. | Tax-model changes need traceability. | Cheap safety. | None. |
| P1 | Move `scratch.ipynb` to `notebooks/` or exclude outputs. | Keeps production folder clean. | Less accidental stale-state confusion. | Minor housekeeping. |
| P1 | Streamlit + NumPy is fine, but cache by scenario hash. | 5,000 trials x 30 years x 2 strategies is not large, but reruns can feel sluggish. | Responsive UI. | Need deterministic seeds. |
| P1 | Add "assumptions panel" as a first-class UI element. | Non-savvy users need to see what drives the answer. | Builds trust. | Takes screen space. |

## UI Refinement

The main screen should not lead with a single winner. Lead with:

1. Chance property ends ahead
2. Median after-tax wealth
3. Worst-year cash needed
4. Total outside cash contributed
5. Break-even property growth required

For a day-to-day investor, the most useful warning is not "property wins 53%." It is:

> This scenario needs up to $18k extra cash in a bad year; if you cannot fund that, the property path may fail before the long-term return arrives.

## Recommended Fix Order

| Order | Fix | Why |
|---|---|---|
| 1 | Equalise upfront cash: deposit + stamp duty + buying costs. | Biggest fairness issue. |
| 2 | Split depreciation into Div 40, Div 43, and terminal CGT adjustment. | Biggest tax accuracy issue. |
| 3 | Add explicit annual tax on dividends, including DRP. | Biggest shares-side tax issue. |
| 4 | Add cashflow failure / serviceability threshold. | Biggest real-world risk issue. |
| 5 | Add rate shock scenarios. | Biggest stress-test issue. |
| 6 | Add Budget 2026-27 regime toggle after the Budget is released. | Biggest law-change issue. |
| 7 | Improve UI around assumptions and affordability metrics. | Biggest usability issue. |

## Sources

- [ATO resident tax rates](https://www.ato.gov.au/tax-rates-and-codes/tax-rates-australian-residents)
- [ATO negative gearing](https://www.ato.gov.au/forms-and-instructions/rental-properties-2014/other-tax-considerations/negative-gearing)
- [ATO franking credits](https://www.ato.gov.au/individuals-and-families/investments-and-assets/shares-funds-and-trusts/investing-in-shares/refund-of-franking-credits-for-individuals)
- [ATO CGT discount](https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-discount)
- [ATO cost base](https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt/cost-base-of-asset)
- [ATO dividend reinvestment plans](https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/shares-and-similar-investments/dividend-reinvestment-plans)
- [RevenueSA stamp duty](https://www.revenuesa.sa.gov.au/stamp-duty/rate-of-stamp-duty)
- [RevenueSA land tax](https://revenuesa.sa.gov.au/landtax/rates-and-thresholds)
- [Budget.gov.au](https://budget.gov.au/)
- [RBA cash rate](https://www.rba.gov.au/statistics/cash-rate/)
- [Vanguard 2025 index chart](https://fund-docs.vanguard.com/AU-Vanguard_Index_Chart_poster.pdf)
