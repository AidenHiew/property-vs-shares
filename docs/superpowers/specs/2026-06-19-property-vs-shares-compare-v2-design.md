# Property vs Shares — Compare v2 ("same money" verdict) — Design

**Date:** 2026-06-19
**Status:** Approved design, ready for implementation plan
**Author:** brainstormed with owner

---

## 1. Purpose

Answer one question for a personal investor who has the cash to buy an
**investment property**:

> "If I have the money to buy this investment property, am I better off over
> 5–20 years buying the property (with its mortgage), or putting the same cash
> into shares and reinvesting every dollar the property would have demanded
> into more shares instead?"

The comparison is deliberately **realistic, not academic**:

- **Property** is leveraged — the bank lends ~80% at the mortgage rate, the
  owner pays interest + holding costs net of rent.
- **Shares** are **unleveraged** by default — they start with the property's
  full upfront cash and receive, each year, the exact out-of-pocket cash the
  property demanded (and the property's surplus in cash-positive years).

Property keeping its cheap leverage is **not unfair** — it is a real advantage
the investor actually receives. So the realistic comparison is the headline.

**Funding model — the investor always covers the shortfall, and the engine
already assumes this.** This tool does not model a forced sale. Each year the
investor feeds in whatever cash the property demands; the same dollar goes into
the shares side. The wealth verdict is therefore "if you fund every shortfall
and hold to term, who ends richer?" — which is exactly what the engine already
computes (`outside_cash_required_per_year` is injected uncapped, terminal wealth
held to term; verified `property_strategy.py:363`, `monte_carlo.py:234,237`).

The "forced sale" concept is **dropped from this screen**. The honest cost it
used to flag is carried instead by a dedicated **affordability panel** (§5.6):
the verdict answers *who's richer if you can fund it*, the affordability panel
answers *can you fund it, and how much would you cough up*. The two are
explicitly linked so the verdict is never read in isolation.

## 2. Relationship to the existing app

This is a **new, standalone version**, not a rebuild. It does **not** compete
with or modify the existing mix/persona app.

- Existing `app.py`, `model/`, `ui/persona.py`, and all current tests remain
  **untouched**.
- New Streamlit entry point: `app_compare.py`, launched with
  `streamlit run app_compare.py`.
- New display helper module: `ui/verdict.py`.
- The Monte Carlo engine (`model/`) is **reused as-is, with zero changes**.
  Verified 2026-06-19 against `model/monte_carlo.py`,
  `model/normalisation.py`, `model/property_strategy.py`,
  `model/shares_strategy.py`.

## 3. Engine reuse — confirmed behaviour

`run_monte_carlo(...)` already implements the exact comparison:

- **Realistic mode** (`mode="realistic"`): shares start with
  `deposit + stamp_duty + buying_costs`, `margin_loan_initial=0`
  (`build_shares_inputs_for_mode_a`, `model/normalisation.py:13`).
- Each year the property's net out-of-pocket cash
  (`outside_cash_required_per_year` = `max(0, -cashflow)`, where
  `cashflow = (rent − cash costs) − tax`) is injected into the share portfolio
  as `external_contributions` (`model/monte_carlo.py:234`). Cash-positive years
  invest the surplus into "overflow shares" so both sides deploy the identical
  dollar every year.
- **Fair-fight mode** (`mode="fair_fight"`): shares borrow the same
  `purchase_price − equity` via a margin loan. With
  `isolate_asset_quality=True` the margin rate is pinned to the mortgage rate
  (`build_shares_inputs_for_mode_b`, `model/normalisation.py:45`).

Return keys consumed by this screen (all already produced,
`model/monte_carlo.py:268`+):

| Key | Use |
|---|---|
| `property_terminal_wealth` (array) | property median + P10/P90 over **all trials** (§7) |
| `shares_terminal_wealth` (array) | shares median + P10/P90 over all trials |
| `p_property_wins` | **headline win-line** — property wealthier, holding to term (`(p>s).mean()`, `monte_carlo.py:271`). Honest under the fund-every-shortfall model (§1) |
| `outside_cash_per_trial_year` (array, trials × years) | affordability panel — per-year shortfall; source for typical/per-year/crossover/tail |
| `median_outside_cash_total` | **$T** — typical total fed in over the horizon (`monte_carlo.py:273`); used in both the trust line and the affordability panel |
| `worst_year_cash` | **$Z** — worst single year in a rough future (P90 of per-trial max, `monte_carlo.py:274`) |
| `property_cashflow_path` (array) | self-funding **crossover year $K** — first year the median cashflow turns ≥ 0 |

Cash-figure glossary (kept distinct in the UI): **$X** = upfront = `deposit +
upfront costs`; **$T** = `median_outside_cash_total` (typical total top-up); **$Z**
= `worst_year_cash` (engine P90 worst year); **$Wmax** = true max worst year
(`outside_cash_per_trial_year.max()`, shown in detail only); **$C** = user's input
ceiling (`serviceability_ceiling`, a *reference plan*, not a hard gate); **$K** =
median self-funding crossover year; **$L** = `purchase_price − $X` (bank leverage);
**$Y** = fair-fight shares median.

## 4. Two-run model

On **every input change**, run the engine **twice** at 5,000 trials, same seed:

1. `mode="realistic"` — drives the headline. Always computed and shown.
2. `mode="fair_fight"`, `isolate_asset_quality=True` — computed at the same
   time. Its one-line *result* is shown inline (§5.5); the full side-by-side
   detail expands on click. No recompute on click; reveal cached numbers.

**Verified 2026-06-19** (5,000 trials, 20-year horizon, default-ish inputs):
realistic 324ms + fair-fight 269ms = **592ms total** — comfortably sub-second,
so recompute-on-every-change with no debounce is fine (Streamlit caches anyway).
Property median **identical across modes** ($1,797,207 both) — the honesty guard
holds and is regression-tested (§9). The same run characterised the scenario the
affordability panel must surface: realistic `p_property_wins`=0.68; in ~0.47 of
futures the property demanded more than the default $C plan in some year; the
fair-fight shares median ($3.09m) far exceeds realistic shares ($1.20m).

**No solvent-conditioning, no forced-sale gate.** Under the fund-every-shortfall
model (§1) all trials are funded and held to term, so the headline cards, range,
and win-line are computed over **all trials** — no masking. This matches what the
engine actually computes and keeps the verdict simple. The honest cost of that
assumption (how much cash, how often beyond plan) is carried entirely by the
affordability panel (§5.6), which is explicitly linked from the verdict. Proper
forced-sale *repricing* would be a separate engine model; it is **not** part of
this screen and not deferred work for it (§10).

## 5. Screen layout (top to bottom)

Base layout approved via mockup `property_vs_shares_verdict_v2`. The mockup
shows the static happy-path; the conditional behaviour added below (win-rate-
gated badge with a "too close to call" neutral state, always-visible fair-fight
spoiler, affordability panel) supersedes the mockup's single-state rendering and
should be reflected when the UI is built. The owner has accepted that the live
screen will often not match the calm mockup — with realistic inputs it can open
on a neutral verdict or a loud affordability panel.

1. **Horizon toggle** — segmented control: `5 / 10 / 15 / 20` years. Drives
   `horizon_years`. Default 10.
2. **Lead line** — "You put in $X upfront, plus whatever the property needs
   each year (and shares get that exact same cash). Most likely you end up
   with:" — $X = `deposit + upfront costs`, rounded.
   - **Same-money trust line** (small, below): "You'd put in about **$X
     upfront**, plus about **$T total** over the N years as the property needs
     it — and the shares side received that same $X upfront and the same $T.
     Both plans feed in the identical cash; the difference is what each gives
     back." $X = `deposit + upfront costs`; $T = `median_outside_cash_total`
     (the single $T used everywhere — §7). Pre-empts the "but you put more into
     property" objection.
3. **Two verdict cards** side by side. All numbers over **all trials** (§7) —
   no masking, because every future is funded by assumption (§1).
   - **Property** card — leading `ti-home` icon, median (large), "usually
     between $low and $high" (P10–P90), range bar with the **P10 (downside) end
     marked distinctly** — for a leveraged asset the bad tail is what matters.
   - **Shares** card — leading `ti-chart-line` icon, median, P10–P90 range,
     range bar.
   - **Verdict link clause (always under the cards):** "These assume you fund
     every shortfall and never sell — see *what you'd cough up* below." This
     line is mandatory; it is what keeps the cheerful verdict from being read in
     isolation (the affordability panel carries the cost of the assumption).
   - **Winner treatment is threshold-gated and driven by the win-rate, not the
     median** (so the badge and the win-line can never contradict):
     - Win-rate within **45–55/100** *or* P10–P90 ranges substantially overlap
       → **no badge, no border, equal weight.** Neutral line: "Too close to
       call — property and shares land within a whisker of each other."
     - Win-rate **≥ 60/100** for the higher side → that card gets the 2px info
       border + badge **"Ahead in most futures"** (a text label, not colour
       alone — a11y).
     - In between (55–60) → border only, no superlative badge.
     - **Median-vs-win-rate mismatch:** when one side's median is clearly higher
       but the win-rate sits in the 45–55 neutral band, the verbal verdict
       follows the **win-rate** (badge stays neutral); the card medians stand as
       magnitude only, with the line: "Typically richer, but it's close across
       futures." The median cards never drive the badge.
4. **Win-rate line** — uses **`p_property_wins`** (wealthier, holding to term):
   "Assuming you fund it every year, property comes out ahead in about N of
   every 100 futures." N = `round(p_property_wins * 100)`. Flips to a shares-led
   phrasing when shares win. The "assuming you fund it" half is not optional —
   it is the inline echo of the verdict link clause, pointing to §5.6.
   - **Futures anchor** (one-time gloss near first use): "We simulate thousands
     of possible market outcomes; these are how often each side comes out
     ahead."
5. **Leverage explainer** (secondary surface) — "Property is ahead mainly
   because the bank lends you $L you never put in yourself. That leverage works
   both ways: it lifts gains, and it's why the property can demand more cash
   than you have (see *what you'd cough up* below)." L =
   `purchase_price − (deposit + upfront costs)`.
   No "not a trick" phrasing; link explicitly to the affordability panel.
   - **One-line fair-fight spoiler, always visible** (not hidden behind the
     button): "At equal borrowing — shares taking the same $L margin loan at the
     mortgage rate — shares land about $Y. Property's lead here is mostly the
     cheap loan." $Y = fair-fight shares median. If shares *win* the fair-fight,
     that flip is stated plainly here, not gated.
   - Button **"See the side-by-side →"** expands the full fair-fight panel
     (both medians + ranges). Must state the modelled margin loan **never
     margin-calls** — it's a best-case leverage scenario for shares, at the
     mortgage rate it can't actually get; not a realistic apples-to-apples.
6. **Affordability panel — "What you'd cough up"** (its own bordered block, the
   target of every "see below" link). Answers *can you fund the property plan?* —
   distinct from the wealth verdict. Header gloss: **"Both plans feed in this
   same cash — this is just whether you could find it for the property."**
   - **Upfront:** "$X — deposit + stamp duty + buying costs." $X = `deposit +
     upfront costs`.
   - **Typical:** "About **$T** total over N years, on top of the deposit —
     heaviest early, easing by about year **$K** as rent catches up." $T =
     `median_outside_cash_total`; $K = first year the **median**
     `property_cashflow_path` turns ≥ 0.
     - **If the median never turns positive within N years:** drop the "easing
       by year $K" clause and instead show: "still costing you cash in year N —
       it doesn't fully cover its own costs within the horizon."
   - **Rough year:** "Up to about **$Z** in a single worst year (a rough future,
     worst ~1 in 10)." $Z = `worst_year_cash` (P90). A detail line exposes the
     true tail: "Worst we modelled at all: **$Wmax**." $Wmax =
     `outside_cash_per_trial_year.max()`.
   - **Sparkline (inline, not in an expander):** per-year shortfall — median line
     + P10–P90 band — from `outside_cash_per_trial_year`. Shows the front-loaded
     shape at a glance; the front-loading is the decision-relevant part.
   - **Honest cross-tab line:** "In about **J** of property's winning futures,
     you'd have needed more than your **$C** plan in some year." J =
     `round(((p_terminal > s_terminal) & ((outside_cash_per_trial_year >
     serviceability_ceiling).any(axis=1))).mean() * 100)`. Directly answers "is
     the win affordable." (Computed in the UI from the returned arrays.)
   - **Visual loudness scales with $Z vs $C, never gates the verdict:** $Z ≤ $C →
     quiet/neutral; $Z moderately over $C → bolded amber; $Z ≫ $C (e.g. ≥ ~2×) →
     amber `ti-alert-triangle` heading, but the **verdict cards and badge above
     are never suppressed or recoloured**. The panel informs; it does not gate.
   - **$C is a reference plan, not a ceiling:** it is the figure the cross-tab and
     loudness compare against, not a number that triggers a forced sale (there is
     none — §1).

## 6. Inputs

### Slim panel (10 fields, always visible)

| # | Field | Engine param | Default |
|---|---|---|---|
| 1 | Purchase price | `purchase_price` | 950,000 |
| 2 | Deposit | `deposit` | 190,000 |
| 3 | Loan interest rate | `loan_rate_mu` | 0.062 |
| 4 | Gross rent yield | `gross_yield` | 0.035 |
| 5 | Property capital growth %/yr | `property_growth_mu` | 0.055 |
| 6 | Vacancy (weeks/yr) | `vacancy_weeks_mu` | 2 |
| 7 | Upfront costs (stamp duty + fees) | `stamp_duty` + `buying_costs` | auto-derived, editable |
| 8 | Share portfolio profile | `portfolio_profile` (asx_only/global/blended) | blended |
| 9 | Marginal tax rate | `mtr` | 0.37 |
| 10 | Annual top-up you'd plan for | `serviceability_ceiling` | 20,000 |

- **Horizon** is the toggle above the cards (§5.1), not counted in the 10.
- **Rent growth is not a separate input** — the engine derives rent each year
  as `gross_yield × start-of-year property value` (`model/property_strategy.py`),
  so rent automatically grows with capital growth. Exposing a standalone
  "rental growth %" would be a fake control with no engine param.
- **Upfront costs** auto-derives from `model/duty.py` (AU stamp duty) given
  purchase price + state default, shown pre-filled and editable. Editing splits
  into `stamp_duty` (the derived duty) and `buying_costs` (remainder) — or, for
  simplicity, the edited total overrides `stamp_duty` with `buying_costs=0`.
  Implementation plan to pick the cleaner of the two; default behaviour:
  treat the single editable figure as `stamp_duty`, `buying_costs=0`, and show
  the duty-calculator value as the pre-fill.
- **Share profile** sets `share_return_mu`, `share_return_sigma`, dividend
  yield, and franking from `PORTFOLIO_PROFILES` (`model/normalisation.py:6`).
  The slim panel does **not** expose raw mu/sigma — Advanced does.

### Advanced expander (defaults, collapsed)

`vacancy_weeks_sigma`, `rental_yield_sigma`,
`property_growth_sigma`, `loan_rate_sigma`, `management_fee_pct`,
`maintenance_pct`, `property_age`, `asset_type`, `annual_land_tax`,
share MER / dividend yield / franking overrides, `share_return_sigma` override,
`correlation`, `cpi`, `drp`, `property_regime`, `return_distribution` / `t_df`,
`loan_rate_distribution`, `seed`.

All carry the engine's current defaults so the slim panel alone produces a
valid run.

### Fixed for this screen (not surfaced)

- `mode` — driven by the two-run model, not a user input.
- `margin_loan_rate` — irrelevant under `isolate_asset_quality=True` (rate
  pinned to mortgage); leave at engine default.
- `isolate_asset_quality=True` — fixed per the approved fair-fight decision.
- `property_share_mix=1.0` — this screen is pure property vs pure shares; no
  mix curve.

## 7. Number definitions

- **No masking.** Headline medians, ranges, and win-line are computed over **all
  trials** (every future is funded by assumption, §1). The UI may use the engine's
  all-path scalars (`median_property_wealth`, `median_shares_wealth`,
  `p_property_wins`) or recompute from the arrays — they are equivalent.
- **Headline medians** = `np.median(arr)` for each side (all trials).
- **Range** = `np.percentile(arr, [10, 90])`, P10 (downside) end marked.
- **Win line** = `p_property_wins` (`(p_terminal > s_terminal).mean()`), framed
  with the mandatory "assuming you fund it" clause (§5.4). `p_property_succeeds`
  and solvent-conditioning are **not used** on this screen.
- **$T (typical total top-up)** = `median_outside_cash_total` — the *single*
  definition, used identically in the trust line (§5.2) and the affordability
  panel (§5.6). Never compute a second "total" elsewhere.
- **$K (self-funding crossover)** = first year index where the median across
  trials of `property_cashflow_path[:, year]` is ≥ 0; **undefined** if no year
  qualifies → use the "doesn't cover its costs within N years" copy (§5.6).
- **$Z** = `worst_year_cash` (P90); **$Wmax** = `outside_cash_per_trial_year.max()`.
- **Cross-tab J** = `round((win_mask & over_plan_mask).mean() * 100)` where
  `win_mask = property_terminal_wealth > shares_terminal_wealth` and
  `over_plan_mask = (outside_cash_per_trial_year > serviceability_ceiling).any(axis=1)`.
- **Winner badge** is gated on the win-rate per §5.3 (neutral band 45–55, badge
  ≥60), not on the median — so the badge and the win-line cannot contradict.
- **Both medians round consistently**; when the two round to within one display
  unit of each other, treat as the §5.3 "too close to call" case (resolves the
  "badge with no visible numeric gap" confusion). Show one more significant
  figure (e.g. `$1.35m` vs `$1.31m`) when medians are within ~10%.
- All displayed dollars rounded; all "N of 100" figures `round(x * 100)`.
- **Terminal wealth is post-exit-CGT on both sides** (property:
  `terminal_after_tax_wealth + overflow_share_terminal_value`, both CGT-paid;
  shares: `terminal_after_tax_wealth`, CGT-paid). Verified — the verdict is not
  silently flattered by ignoring property's exit tax.
- **Tax-simplification footnote** (small, under the verdict): negative gearing
  assumes losses are absorbed at full MTR every year (no income cap); shares CGT
  uses a single blended cost base with the 50% discount on the whole gain. Both
  minor and roughly offsetting; disclosed for honesty.

## 8. State persistence & clamping

Per the project rule, all slim + advanced inputs persist to the URL query
params, and every persisted value is **clamped on both read and write** in the
same change, with malformed/boundary inputs handled explicitly:

- Numeric inputs clamp to sane min/max (e.g. deposit ≤ purchase price; rates in
  [0, 0.30]; horizon ∈ {5,10,15,20}; top-up ≥ 0).
- Malformed/missing/junk query values fall back to the default, never crash.
- Boundary cases (deposit = price → zero loan; top-up = 0; horizon at each end)
  are explicitly tested.

## 9. Testing

- **Engine** — already covered by existing suite; not re-tested here beyond
  confirming `app_compare.py` calls it with valid args.
- **Headless AppTest smoke** (`streamlit.testing.v1.AppTest`) — app loads with
  no exception; both verdict numbers render; toggling horizon and editing slim
  inputs triggers a recompute without error.
- **Boundary tests** — malformed URL params, deposit = price, top-up = 0,
  each horizon value, profile switch.
- **Two-run check** — property median identical across realistic and
  fair-fight results for the same inputs (regression guard on the honesty
  claim).
- **$T single-source check** — the $T in the trust line and the $T in the
  affordability panel are the same value (`median_outside_cash_total`); assert
  they are read from one computed figure, not two.
- **Crossover both-branches check** — inputs where the median cashflow crosses
  zero within N years → assert a year $K is shown; inputs where it never crosses
  (high rate / low yield) → assert the "doesn't cover its costs within N years"
  copy and **no** $K.
- **Affordability-never-gates check** — synthesise inputs with $Z ≫ $C (loud
  affordability panel) and assert the verdict cards + winner badge above are
  **unchanged** (not suppressed/recoloured) — the panel informs only.
- **Framing checks** — (a) near-tie win-rate → neutral "too close to call", no
  badge; (b) median clearly higher but win-rate in 45–55 band → "typically
  richer but close" copy, badge stays neutral; (c) fair-fight share win → inline
  spoiler states the flip without requiring expansion.

## 10. Out of scope (YAGNI)

- No mix curve / persona cards (that's the existing app).
- No PPOR (owner-occupier) modelling — investment property only.
- No realistic-margin-rate fair-fight variant (pinned-rate only, per decision).
- No PDF/report export in v1.
- No change to the engine or the existing app.
- **No forced-sale modelling at all** — this screen assumes the investor funds
  every shortfall and holds to term (§1). There is no forced sale to reprice and
  no solvent-conditioning; the affordability panel (§5.6) surfaces the cash cost
  of that assumption instead. A genuine forced-sale/repricing model would be a
  separate engine project, not part of or deferred from this screen.

## 11. Assumptions to confirm at spec review

- Investment property with rent offsetting costs — **confirmed** by owner.
- Default input values above are starting points, freely editable; the listed
  defaults are reasonable AU figures, not prescriptions.
- Upfront-costs handling (single editable figure → `stamp_duty`) is the v1
  simplification; revisit only if the duty split matters to a real decision.
