# Property vs Shares Model — Review Packet

*Prepared 2026-05-11 for cross-check by Codex / GPT. Self-contained: no external context needed.*

---

## 0. What this is, and what we want from you

**Context for the reviewer:**

A non-technical Adelaide-based user (founder; works with AI assistants for code) has been brainstorming a personal-use Monte Carlo tool to compare investing in **leveraged Australian residential investment property** vs **shares**. It is *not* a commercial product — no SEO, no AFSL disclaimers, no monetisation. It is a tool the user will run on their own laptop to make a real allocation decision.

The brainstorming was done with Claude (Opus). This packet contains:

1. The market research that informed the build/no-build decision (§A)
2. The full design spec (§B)
3. A log of the key decisions and the rationale behind each one (§C)
4. **Explicit review prompts — what we want you to push back on (§D)**

**Your job is to find gaps and challenge weak reasoning — not to validate.** If the design is coherent and you have nothing substantive to add, say so. But assume there *are* things missed and look for them. The user explicitly asked for "cross-check everything so we don't miss anything."

Be especially aggressive about:
- **AU tax accuracy** — Claude is reasonably good on AU tax but not infallible; spot-check the specifics.
- **Fairness modelling** — the symmetric reinvestment policy and the three normalisation modes are the model's signature feature. If they're broken, the whole thing is broken.
- **Defaults** — μ and σ values for capital growth, share returns, etc. — are they defensible against published AU long-run data?
- **Things we haven't even thought of** — the most valuable feedback is "you forgot X entirely."

---

## A. Market Research (informed the build/no-build decision)

*Original file: `Financial Modeling/market-research-property-vs-shares.md` (dated 2026-05-10).*

### A.1 Existing Tools — Australia, direct competitors

- **[Best ETFs Australia — Property v Shares v Offset Calculator](https://www.bestetfs.com.au/tools/property-shares-offset/)** — run by **The Rask Group**. The closest direct competitor. Free, three-way side-by-side comparison (property / shares / offset), models negative gearing, franking, CGT, stamp duty, leverage, depreciation. Charts plus risk/liquidity ratings. Funnels to paid "Rask Core" membership. Recently maintained.
- **[austax.tools — Negative Gearing Calculator](https://austax.tools/negative-gearing-calculator/)** — 1–30 yr property vs ETF projection with CGT, selling costs, year-by-year gearing flip. Uses 2025-26 ATO rates. Free.
- **[Property Tax Tools](https://propertytaxtools.com.au/calculators/investment-property-calculator/)** — ROI / CAGR / cash-on-cash, separate franking-credits calc. Free, well-maintained.
- **[InvestmentPropertyCalculator.com.au](https://www.investmentpropertycalculator.com.au/)** — downloadable Excel; dated UI but comprehensive.
- **[Your Mortgage](https://www.yourmortgage.com.au/calculators/negative-gearing)**, **[YIP Magazine](https://www.yourinvestmentpropertymag.com.au/calculators/negative-gearing)**, **[Savings.com.au](https://www.savings.com.au/calculators/negative-gearing-calculator)**, **[TMS Financial](https://www.tmsfinancial.com.au/negative-gearing-calculator/)** — all single-purpose negative-gearing calcs, lead-gen for brokers / accountants.
- **[Moneysmart (ASIC)](https://moneysmart.gov.au/)** — has compound-interest, managed-funds-fee, mortgage and super calcs but **no property-vs-shares comparison tool**.
- **Big banks / Domain / PropTrack / CoreLogic** — mortgage and yield calcs only; no head-to-head shares comparison.
- **Sharesight / Pearler / Stake** — portfolio trackers, not comparison calculators.
- **Blogs**: Aussie Firebug and Strong Money Australia cover the debate qualitatively; AFB has a super-vs-outside-super calc but no full P-vs-S simulator.

### A.2 Gaps in the market

The Rask tool covers the hardest tax mechanics. Real gaps:

- **Sequence-of-returns / Monte Carlo** — everything uses flat-% growth. No distributions or downside scenarios.
- **Land tax by state** — SA-specific thresholds rarely modelled; tools assume NSW or generic.
- **SMSF property** — barely covered outside paid accountant tools.
- **Cashflow-over-time visualisation** — most show end-state numbers, not the year-7 squeeze.
- **Honest sensitivity analysis** — rate-shock / vacancy-shock / return-shock toggles are rare.
- **Mobile UX** — desktop-form-heavy and hostile on phones.

### A.3 Monetisation reality check

Donations + ads is essentially fake revenue at realistic year-1 traffic. Finance-niche RPMs are good ($30–50) but you need tens of thousands of monthly sessions to clear coffee money, and SEO incumbents will outrank a new domain for years. Realistic 12-month outcome: sub-$200/month from AdSense + maybe one $50 PayPal donation.

**ASIC carve-out for generic financial calculators (Instrument 2026/41 + RG 244)** means no AFSL needed if the tool doesn't recommend specific products and includes appropriate disclaimers. Well-trodden, not a blocker.

### A.4 Verdict

**The space is saturated for the obvious version.** Rask already does the 80 % case competently and has SEO + brand. There is a narrow opening for a Monte Carlo / sensitivity-first tool with state-specific accuracy and cashflow-stress visualisation. **Donation + ads monetisation is fake revenue at any realistic year-1 traffic level.** Build it as a personal tool / portfolio piece, not as a money-maker.

**User's response to research:** chose to build for personal use only. No monetisation. The model's signature features (Monte Carlo + symmetric reinvestment + dual-view leverage normalisation) are direct responses to the gaps identified above.

---

## B. Design Spec (the actual proposal)

*Original file: `Financial Modeling/2026-05-10-property-vs-shares-design.md`.*

### B.1 Purpose

A personal-use Monte Carlo simulator that lets the user honestly compare investing the same capital in leveraged AU residential investment property vs AU/global shares over a multi-decade horizon, under realistic AU tax rules and with explicit handling of fairness traps.

User context: Adelaide SA, real ongoing allocation decision, hobby + real-money. No public ship.

Signature features (none of which existing AU tools offer together):

- **Probability framing** — headline output is "P(property beats shares)" across 5,000 Monte Carlo trials, not a single fake terminal-wealth number.
- **Three normalisation modes** — "same deposit / different leverage" (realistic), "same total exposure / same leverage on both" (fair fight), "same equity + zero leverage on both" (asset-quality only).
- **Symmetric reinvestment-of-cashflow** — whichever strategy generates spare cash, the other strategy invests the same dollars. No silent subsidy.
- **Year-by-year cashflow stress** — see the year-7 squeeze when rates rise.

### B.2 Scope

**In v1:**
- Two operating modes: abstract/parametric and specific-property (real listing).
- AU tax engine, FY2026 rules, **South Australia only** for state-level taxes.
- Investment property only. User assumed renting their own home throughout horizon.
- Monte Carlo with 5,000 trials, configurable μ/σ on five random variables, optional correlation between property and shares.
- Three leverage-normalisation modes.
- Symmetric reinvestment of cashflow.
- Streamlit local web UI.

**Explicitly out of v1:**

| Excluded | Reason |
|---|---|
| PPOR modelling | Different tax treatment (imputed rent, CGT exemption); separate tool |
| Other states' stamp duty / land tax | User is SA; adding 7 other state regimes is busywork |
| SMSF property | Different rules (LRBA etc.) |
| Medicare Levy / MLS | Comparison tool, not tax estimator |
| HECS | Doesn't change comparison materially |
| Capital works recapture on sale | Modest impact, complex to model correctly |
| LMI | Assumed 20 % deposit |
| Specific share / ETF product selection | Generic share returns only |
| Fat-tailed / regime-switching return models | Independent normal draws good enough for personal-decision precision |
| **Budget-2026 negative gearing changes** | **Federal Budget May 13. v1 ships current FY2026 rules. v1.1 adds regime toggle once law is known.** |

### B.3 Architecture

**File layout:**

```
Financial Modeling/
├── 2026-05-10-property-vs-shares-design.md
├── market-research-property-vs-shares.md
├── for-codex-review-2026-05-11.md   (this file)
└── property-vs-shares/
    ├── README.md
    ├── requirements.txt              # numpy, pandas, streamlit, plotly, pytest
    ├── config.py                     # TRIALS=5000, defaults, AU tax brackets
    ├── model/
    │   ├── __init__.py
    │   ├── tax.py                    # MTR, neg gearing, franking, CGT, stamp duty, land tax
    │   ├── property_strategy.py
    │   ├── shares_strategy.py
    │   ├── monte_carlo.py            # vectorised numpy
    │   └── normalisation.py          # the three "fair fight" modes
    ├── app.py                        # Streamlit UI; imports from model/
    ├── scratch.ipynb                 # Claude's dev notebook
    └── tests/
        ├── test_tax.py               # worked examples
        ├── test_property_strategy.py
        ├── test_shares_strategy.py
        └── test_normalisation.py
```

**Module responsibilities:**

- `config.py` — all magic numbers in one place. When tax law changes, mostly edit this.
- `model/tax.py` — pure functions, no I/O. `marginal_tax`, `franking_credit_refund`, `cgt_payable`, `sa_stamp_duty`, `sa_land_tax`.
- `model/property_strategy.py` — given one Monte Carlo trial's draws, produces 30-year cashflow + terminal sale event.
- `model/shares_strategy.py` — same, for shares.
- `model/monte_carlo.py` — vectorised 5,000-trial runner.
- `model/normalisation.py` — applies whichever of the three "fair fight" rules.
- `app.py` — Streamlit UI only. No business logic.
- `tests/` — pytest with worked examples cross-checked against ATO sources.

### B.4 Inputs (with defaults pre-loaded)

**User profile:**
- Marginal tax rate: 37 % (FY2026 brackets pre-loaded; selected from dropdown)
- State: SA (only SA in v1)
- Investment horizon: 25 years (slider 5–40)

**Property scenario (abstract mode):**

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
| Annual depreciation deduction | $0 | 0–$15,000 (user supplies) |
| Capital growth μ / σ | 5.5 % / 8 % | configurable |
| Selling costs at exit | 2.5 % of sale price | agent + legal |

**Specific-property mode:** same fields, pre-populated by listing details. UI shows a panel: "Modelling: 14 Example St, Adelaide — $720k, 4.1 % yield, $X stamp duty calculated."

**Shares scenario:**

| Input | Default | Range |
|---|---|---|
| Initial capital | (derived — see normalisation) | — |
| Total return μ / σ | 8.5 % / 15 % | configurable |
| Dividend yield (of total return) | 3.5 % | 1–6 % |
| Franked portion of dividends | 70 % | 0–100 % (AU-tilted) |
| MER | 0.20 % | 0.05–1 % |
| Brokerage per trade | $10 | included for completeness |
| Margin loan rate (fair-fight modes) | 7.5 % | 5–12 % |
| Dividend reinvestment (DRP) | On | toggle |

**Macro / shared:**

- CPI (for "today's dollars" toggle): 2.5 % (RBA midpoint)
- Property–shares return correlation: 0.3
- Display mode: nominal / real toggle

### B.5 Tax engine

**Implemented in v1, in `model/tax.py` as pure functions:**

- Marginal income tax — FY2026 resident brackets.
- Negative gearing — net rental loss deducted against other income at MTR. Current rules: full deductibility, no quarantining.
- Franking credits — gross-up dividends, apply MTR, allow refund of excess imputation credits (standard individual treatment).
- CGT 50 % discount — applied to capital gain on assets held > 12 months, then taxed at MTR. Both property and shares qualify.
- SA stamp duty — 2026 SA bands.
- SA land tax — 2026 SA bands on unimproved land value (proxy: 60 % of purchase price).
- Property holding costs — fully deductible: management, rates, insurance, maintenance, loan interest, depreciation, land tax.
- Selling costs — capitalised into cost-base reduction.

**Not implemented:** Medicare Levy / MLS, HECS, capital works recapture, Div 40 vs Div 43 split, LMI, SMSF, other states.

**Budget-2026 handling:** v1 ships current FY2026 rules only, no toggle. v1.1 adds `tax_regime: Literal["fy2026_current", "fy2026_post_budget"]` parameter and UI radio after May 13.

### B.6 Comparison engine — three normalisation modes

**Mode A — "Realistic" (default)**
- Property: user-specified deposit, leveraged via mortgage to user-specified purchase price.
- Shares: starts with the same deposit amount, no leverage.
- What 99 % of people actually do. Property looks better mostly because of leverage, not asset quality.

**Mode B — "Fair fight" (matched total exposure)**
- Property: same as Mode A.
- Shares: starts with the same total dollars at risk as the property's purchase price, funded by same equity + margin loan at user-specified rate.
- Isolates the asset-quality question by removing leverage advantage.
- No margin call modelling in v1 (assumes user maintains LVR via cash injection).

**Mode C — "Asset only" (matched equity + zero leverage on both)**
- Both strategies: same starting capital, no borrowing.
- "Is residential property a better unleveraged asset than a diversified share portfolio?"

**UI:** single radio at top of results panel. Re-runs Monte Carlo on switch (sub-second).

### B.7 Symmetric reinvestment of cashflow

In every mode, in every year, both strategies must deploy **identical total after-tax capital** for the comparison to be fair.

Implementation:
- Compute property strategy's net after-tax cashflow for the year. If negative, the user funds it from outside income — we don't add this to either strategy's wealth, but require shares strategy to "use" the same outside dollars by adding them to the share portfolio.
- Concretely: in year t, if property strategy needs $X to maintain itself, shares strategy contributes the same $X to the share portfolio. If property strategy generates $Y of positive cashflow, $Y is invested into shares *within the property strategy* (so property strategy ends with house + small share portfolio).
- Single most important fairness fix versus existing calculators. Surfaced as a permanent banner above the headline.

### B.8 Monte Carlo engine

**Random variables (per trial, per year):**

For every variable, the value the user enters in §B.4 is the mean (μ). A new value is drawn each year of each trial using the σ shown here. User can override σ in an "advanced" panel.

| Variable | Default μ | Default σ | Distribution |
|---|---|---|---|
| Property capital growth | 5.5 % | 8.0 % | Normal |
| Share total return | 8.5 % | 15.0 % | Normal |
| Rental yield (relative to value) | (= user input) | 0.3 pp | Normal |
| Vacancy weeks | (= user input) | 1 week | Normal, floored at 0 |
| Loan rate | (= user input) | 0.5 pp | Normal, with shock-test override |

**Correlation:** property capital growth and share total return correlated (default 0.3) via Cholesky decomposition. Other variables independent.

**Trial count:** `TRIALS = 5000` in `config.py`. Hidden from user. Yields ±~0.5 % standard error on headline P(property > shares).

**Outputs from the engine:**
- Per trial: terminal after-tax wealth for both strategies; year-by-year cashflow series for both; year-by-year wealth-on-paper series for both.
- Aggregated: P(property > shares); 10/50/90 percentile terminal wealth per strategy; median year-by-year cashflow per strategy; worst-decile cashflow path.

### B.9 UI layout (Streamlit)

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
│  INPUTS (left sidebar — sliders for everything in §B.4)     │
└─────────────────────────────────────────────────────────────┘
```

Inflation toggle re-renders dollar figures via CPI deflator without re-running Monte Carlo. Mode toggle re-runs Monte Carlo (sub-second).

### B.10 Testing

`pytest` in `tests/`. Coverage targets:

- Every function in `model/tax.py` has at least one worked-example test cross-checked against ATO publication. Examples:
  - "$700k SA investment property → stamp duty = $X" (cross-check RevenueSA calculator)
  - "$50k income, $10k rental loss, MTR 32.5 % → tax saving = $3,250"
  - "$700 fully franked dividend, MTR 19 % → refund = $X"
  - "$200k capital gain, held 5 years, MTR 37 % → CGT = $37,000"
- `model/property_strategy.py` and `model/shares_strategy.py` — at least 3 known-good full-year cashflow tests each.
- `model/normalisation.py` — tests proving each mode produces correct equity / leverage allocation.
- `model/monte_carlo.py` — determinism test (fixed seed) and convergence test (5000 trials → ±1 % stable percentiles).

### B.11 Open assumptions (deliberate v1 simplifications)

1. **Land tax proxy** — using 60 % of purchase price as unimproved land value. SA-specific override would be cleaner.
2. **Single-property assumption** — portfolio of properties out of scope.
3. **No margin call modelling in Mode B** — assumes user maintains LVR via cash if shares fall.
4. **Loan rate variability shared between IO and P&I phases** — same μ/σ throughout loan life.
5. **Depreciation as single annual constant** — real depreciation declines over time (Div 40 vs Div 43).
6. **No transaction costs on rebalancing within share portfolio** — DRP free; periodic rebalancing not modelled.
7. **Buy-and-hold share portfolio** — no mid-period sales, so no CGT events except at terminal sale. Small bias in favour of shares.

### B.12 v1.1 backlog (deliberately deferred)

- Budget-2026 regime toggle (week of May 13 or after).
- Other states' stamp duty / land tax (NSW, VIC, QLD first).
- LMI for sub-20 % deposit scenarios.
- Depreciation schedule by property age.
- Multi-property portfolio mode.
- Margin call mechanics in Mode B.
- PDF export.

### B.13 Build effort estimate

- Tax engine + tests: ~1 evening
- Property + shares strategy modules + tests: ~1 evening
- Monte Carlo engine: ~half evening
- Normalisation modes: ~half evening
- Streamlit UI: ~1 evening
- Validation, polish, defaults tuning: ~1 evening

Total: ~3 evenings of focused build.

---

## C. Decisions Log (with rationale — push back if reasoning is weak)

These were the major forks in the road, in the order they were resolved.

| # | Decision | Rationale | Push-back surface |
|---|---|---|---|
| 1 | **Build the tool** (rejected: don't build, pivot to paid SaaS for accountants) | Personal-use only; user has real money decision; no monetisation distortion. Pivoting to SaaS for accountants would 50–100× revenue but isn't what user wants. | Is the personal-use framing actually right, or is the user under-pricing their own time? |
| 2 | **Both abstract + specific-property modes** (rejected: abstract only, or specific-only) | Most useful long-term; specific mode lets user model a real listing while abstract mode supports general curiosity. | Does specific-property mode add scope creep? Could v1 ship abstract-only and add specific-mode later? |
| 3 | **Three normalisation modes (Realistic + Fair fight + Asset only)** (rejected: shares-unleveraged-only) | Equal-leverage comparison is the missing piece in every existing AU calculator. All three modes share ~one engine. | Is Mode C (zero-leverage on both) actually useful, or is it academic? Does it add UI complexity for no real-decision value? |
| 4 | **Streamlit + Python, notebook-first development** (rejected: Excel, Jupyter-only, Next.js) | User reads but doesn't write Python; Claude maintains the code; Streamlit gives sliders/charts for free; pure-Python model is testable and easy to update when tax law changes. | Is Streamlit overkill for a single-user tool? Could a Jupyter notebook with `ipywidgets` serve as well at lower complexity? |
| 5 | **Headline = P(property > shares) Monte Carlo; secondary = year-by-year cashflow** (rejected: terminal wealth, IRR) | Probability framing is the differentiator; cashflow chart shows the year-7 squeeze that single-number tools hide. | Is the user equipped to interpret a probability correctly? "47 % chance property wins" can be misread as "property is bad" when it might mean "tossup." |
| 6 | **Tax engine: SA-only, current FY2026 rules, depreciation included, MLS/HECS/SMSF/PPOR excluded** | Material items in; second-order items out; deferral of Budget-2026 changes until law is known is the safest path. | **Most important push-back area.** Is anything material missing? See §D. |
| 7 | **5,000 Monte Carlo trials, μ/σ on 5 variables, correlation 0.3** | Compute is essentially free; 5000 yields ±0.5 % standard error; correlation 0.3 is "not joined at the hip but not independent" — defensible eyeball value. | Is correlation 0.3 actually defensible against AU long-run data? Should we use historical AU residential property index vs ASX 200 returns? |
| 8 | **Symmetric reinvestment of cashflow** | Most important fairness fix; without it, property is silently subsidised by free cash that vanishes from comparison. Banner above headline. | Edge case: what if property generates massive positive cashflow late in horizon — does the "extra" go into more shares without limit? Does that distort? |
| 9 | **Add to v1 (after second-pass review): depreciation, terminal CGT sale event explicit, inflation toggle, brokerage on shares, IO→P&I default loan structure** | Each materially changes the answer; cheap to model. | Did we actually add all five to the spec correctly? Verify spec internal consistency. |
| 10 | **Defer to v1.1: Budget-2026 toggle** | Can't model speculation; wait until May 13 for actual law. | If Budget changes are very material, does v1 mislead user during the 2-week gap? |

---

## D. Specific Review Prompts (please address each)

### D.1 AU tax accuracy spot-check

Cross-check these specific claims against current ATO / RevenueSA publications:

1. **FY2026 resident MTR brackets** — what are they? (Spec says "pre-loaded from `config.py`" but doesn't list them. List the actual brackets so we know the implementation has the right numbers.)
2. **Negative gearing — current rules** — "net rental loss deducted against other income at MTR, full deductibility, no quarantining." Correct as of May 2026?
3. **Franking credits — refund mechanics** — "gross-up dividends, apply MTR, allow refund of excess imputation credits (standard individual treatment)." Specifically: are excess franking credits *refundable* to individuals at all MTRs in FY2026, or only below a threshold? (The 2019 election proposal to remove refundability didn't pass, but verify this hasn't changed.)
4. **CGT 50 % discount** — held > 12 months. Any FY2026 changes proposed or made? Apply to both AU residents and non-residents the same? (User is AU resident.)
5. **SA stamp duty bands FY2026** — list the actual bands. Any concessions for investors vs first-home-buyers that matter here?
6. **SA land tax FY2026** — list the actual thresholds. What's the standard practice for estimating unimproved land value when modelling? Is "60 % of purchase price" defensible, or is there a better proxy?
7. **Selling costs treatment** — "capitalised into cost-base reduction." Correct CGT treatment in AU tax law? (i.e. agent commission and legal fees on sale reduce the capital gain rather than being deducted as expenses?)
8. **Depreciation post-2017 changes** — for second-hand residential properties acquired after May 2017, plant and equipment (Div 40) deductions are restricted to *new* items installed by the current owner. Is the spec's flat-annual-deduction model consistent with this restriction, or would it overstate depreciation for typical established-housing buyers?

### D.2 Defaults sanity check

For each default in §B.4 / §B.8, is it defensible against published long-run AU data? Specifically:

1. **Property capital growth μ = 5.5 %, σ = 8 %** — sources? CoreLogic / ABS / RBA long-run data? Is 5.5 % real or nominal? (Spec says model in nominal — so 5.5 % should be nominal — verify defensibility.)
2. **Share total return μ = 8.5 %, σ = 15 %** — for what index? ASX 200, ASX 300, MSCI World, mixed? Total return (incl. dividends) is the right framing — but verify the magnitude. Vanguard's published long-run AU equity returns are in the 9 %ish range nominal — 8.5 % may be conservative.
3. **Rental yield σ = 0.3 pp** — too tight? Adelaide gross yields have moved more than that in single years.
4. **Vacancy σ = 1 week** — Adelaide vacancy rates have been < 1 % for years; 1-week σ may be plausible. Verify against SQM Research data.
5. **Loan rate σ = 0.5 pp / year** — implies a slow drift. Is this realistic for variable-rate AU mortgages, where the RBA has moved 4+ percentage points in 18 months recently?
6. **Property–shares correlation 0.3** — historical AU data (CoreLogic Home Value Index vs ASX 200 total return)? Is 0.3 defensible or should we look it up?
7. **Franked portion of dividends 70 %** — for an ASX-only portfolio, ~80 % is more common; for a global / mixed portfolio, much lower. Default of 70 % is a hedge — is that the right hedge?

### D.3 Fairness modelling — push hard here

This is the model's signature. If broken, the whole tool is broken.

1. **Symmetric reinvestment edge cases** — the spec says "if property strategy generates $Y of positive cashflow, $Y is invested into shares *within the property strategy*." Does this actually maintain symmetry, or does it secretly add a share-portfolio tail to property strategy that shares strategy doesn't have? Walk through a worked example: 10-year horizon, property positively geared from year 6, what does each strategy actually hold at horizon? Are they comparable?
2. **Mode A (Realistic) reinvestment behaviour** — in Mode A, shares strategy starts with same deposit ($140k) as property. Then if property needs $10k/yr extra, shares contributes another $10k/yr. Over 25 years that's $250k of additional shares contributions. Is the comparison still meaningful, or has it become "invested deposit + DCA $10k/yr into shares vs invested deposit + property"?
3. **Mode B (Fair fight) reinvestment behaviour** — Mode B already has shares leveraged via margin loan to match property. Then *also* applies symmetric reinvestment? Double-leveraging risk?
4. **Mode C (Asset only) reinvestment behaviour** — both strategies have same equity and zero leverage. If property has negative cashflow (likely with no leverage and full purchase price as equity), does symmetric reinvestment still apply? What does it even mean here?

### D.4 Things possibly missed entirely

Open questions for the reviewer to add to:

1. **Tax on share dividends during accumulation phase** — DRP'd dividends are still taxed in the year received. Does the model handle this correctly?
2. **Loan offset account modelling** — Rask's tool includes "offset" as a third strategy. We've excluded it. Is that actually right for a tool whose user might use offset balances against the investment loan?
3. **Stamp duty on the loan vs property** — SA mortgage stamp duty was abolished years ago, but verify no gotcha here.
4. **GST on property purchase** — irrelevant for established residential; flag if user might model new builds.
5. **CGT main residence partial exemption** — we excluded PPOR entirely, so this doesn't apply, but worth confirming the user understands "investment property only" = pure rental, no 6-year rule, no partial exemption.
6. **Land tax aggregation across properties** — single-property assumption sidesteps this, but flag for v1.1 multi-property mode.
7. **Trust / company ownership structures** — assumed individual ownership. Many AU property investors use trusts. Out of scope, but flag.
8. **Inflation on rents and property costs** — rent grows over time; rates / insurance / maintenance grow over time. Spec doesn't explicitly say these are inflated year-over-year. They should be. Verify.
9. **Real returns vs nominal in Monte Carlo** — spec models in nominal and offers a "today's dollars" display toggle. But the σ values — are they nominal-σ or real-σ? Matters for distribution shape over long horizons.
10. **Black swan handling** — Normal distributions ignore that property had > 30 % drawdowns in some markets in 2008. σ = 8 % for property growth implies a 99th-percentile single-year drop of ~−13 %. Realistic for AU?

### D.5 Architecture / build risk

1. **Notebook in production folder** — `scratch.ipynb` lives alongside `app.py`. Risk of it accidentally being run by the user, or being committed with stale outputs?
2. **Tests cross-checked against ATO publications** — who validates the worked examples? If Claude writes both the implementation and the test, both can be wrong. Suggest external cross-check against e.g. RevenueSA online calculator for stamp duty, ATO simple tax calc for income tax.
3. **Streamlit performance** — 5,000 trials × 30 years × 2 strategies × 3 normalisation modes — does this actually run sub-second in pure numpy on a laptop, or have we kidded ourselves?
4. **No git repo** — `Financial Modeling/` isn't under version control. Should we `git init` before any code is written?

---

## E. What we'd love from your review

Format: just markdown back. Headed sections matching D.1–D.5 above so we can act on each. Prioritise:

1. **Anything materially wrong** (tax law incorrect, defaults indefensible, fairness logic broken).
2. **Anything material we forgot** (gaps in scope that change the answer).
3. **Anything minor we should fix** (smaller corrections that are still worth doing).
4. **Things you'd push back on but ultimately we got right** (so we have your reasoning on file).

Don't pull punches. The user wants a tool that gives an honest answer, not one that confirms a prior. If the design is fundamentally misaligned for the question, say so — early reversal is cheaper than late reversal.

---

*End of review packet. Saved at `Financial Modeling/for-codex-review-2026-05-11.md`.*
