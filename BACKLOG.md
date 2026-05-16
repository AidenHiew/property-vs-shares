# v1.1 Backlog

Items surfaced by the final holistic code review (2026-05-11) that were not
critical for shipping v1 but should be addressed before the model is used for
a real allocation decision a second time.

## Pickup notes (when resuming)

**Last touched: 2026-05-16, very late night session (continued into the small hours).** Working
tree clean, 95/95 tests passing. **All v1.1 bugs + ALL polish + ALL 4 finance-expert
recommendations + ALL surfaced-during-sensitivity items + UI redesign all shipped.** The app
is now recommendation-first (persona cards lead the main pane, comparison table behind expander,
old histograms demoted into a detail expander). Only larger v1.2 features remain.

### What landed across the 2026-05-16 sessions (~20 commits — see `git log` for full list)

Highlights by phase:

**Evening 1** — joint-metric reframe + sensitivity + fat-tail honesty:
- `8775380` **joint `p_property_succeeds` metric + reframed headline**
- `a6120ac` tornado sensitivity (`notebooks/tornado.py`)
- `fe2836a` opt-in Student-t for returns
- `8bd01f6` extended Student-t to loan_rate (tornado-dominant input)

**Evening 2** — bugs, polish, BACKLOG cleanup:
- `f108b2a` fat-tailed tornado (confirmed loan_rate dominance robust)
- `32a8f01` **stamp duty + buying costs in CGT cost base** (BACKLOG §1)
- `4f061d8` new-build × regime warning + dual-seed RNG decoupling
- `42f8135` hid no-op `rental_yield_sigma` slider + `p_solvent` helper dedup
- `f15e95a` **exact today-$ deflation + mix-array deflation + p_solvent revert**

**Evening 3 (night)** — UI redesign from histogram → recommendation hero:
- `4cf417c` auto-couple new-build → current regime (Budget 2026-27 carve-out)
- `493c27e` **wealth-level allocation mix slider** (the headline finding came from this)
- `a324240` model-layer `wealth_per_year` exposure
- 4 mockup iterations (frontier / fan / static personas / dynamic personas)
- `b9a1e8c` **persona cards + comparison table as recommendation hero in app.py**
- `1fc66d1` **bugfix: HTML rendering + dollar-sign mathjax escapes**

### The five findings worth re-reading before doing anything new

1. **Honest headline = ~32%, not 70%.** Under restricted_2027, joint success
   `p_property_wins ∧ p_solvent` is what matters. Solvency is the binding constraint.
2. **Loan rate dominates under restricted regime** — ~55pp swing in `p_property_succeeds`.
   Confirmed robust under both Gaussian and Student-t distributions (commit `f108b2a`).
   `mtr` effect collapses to <1pp (NG quarantining kills the tax shield).
3. **Symmetric fat tails barely move headlines, but inflate p99 worst-year cash.**
   The t-dist feature's real value is inspecting tail metrics, not headlines.
4. **Acquisition costs were missing from CGT cost base.** Fixed (commit `32a8f01`). Under
   `current` regime, headline lifted +0.4pp; under `restricted_2027`, headline barely moved
   because the loss pool already neutralizes most post-commencement CGT. Implication: the
   bug was hiding under current rules, not under the restricted regime.
5. **The Budget 2026-27 regime restructures the optimal allocation from 100% → ~60%.**
   Cross-regime mix sweep (commit `493c27e`) revealed: under `current` rules, pure property
   is rational (high solvency at any mix). Under `restricted_2027`, the optimal mix per
   the persona logic (highest wealth at ≥95% safety) is **60% property / 40% shares**.
   Beyond 60%, solvency drops off a cliff (60% → 65% takes P(solvent) from 97% → 94%).
   This is the actionable answer the model now gives via the persona cards in the app UI.

### Suggested resume order

1. **Smoke-test the app first** (5 min). `source .venv/bin/activate && streamlit run app.py`.
   The UI is now recommendation-first — the three persona cards lead the main pane. Drag
   the sidebar mix slider to override the recommendation; toggle regime/property-age to
   see the cards adapt.
2. **Pick a v1.2 feature from "Remaining" below** if you want to keep building. Mode B
   margin calls is the most honesty-improving option (current Mode B is misleadingly
   favorable to leveraged-shares). Other states (VIC/NSW) is most practically useful if
   you're considering investing outside SA.

### Remaining items (larger v1.2 features only)

- **Mode B margin-call modelling (BIG feature).** Currently the model warns that
  margin calls aren't modelled but the Mode B comparison is still misleadingly
  favorable to leveraged-shares. Real margin calls force-sell at the bottom of crashes.
  Needs design: when does a call trigger? what's the forced sale loss model?
- **Single-property idiosyncratic risk shocks (BIG feature).** v1 uses index-level
  property returns; a single property has materially more variance (rebuild/repair
  events, neighbourhood shocks, tenancy gaps). Needs design: shock frequency, magnitude
  distribution, correlation with macro factors.
- **Major capex events (BIG feature).** Roof, hot water, HVAC, structural — rare but
  large negative cashflows. Needs design: probability per year, magnitude distribution,
  whether capitalised vs immediately deducted.
- **Offset account as a third strategy (BIG feature).** Conceptually different
  comparison: NG property + offset bucket vs straight shares. Needs design: how the
  offset interacts with the existing mode A/B framing.
- **Other states beyond SA (BIG feature).** Currently uses SA stamp duty and land tax
  tables. Other states have different brackets and exemptions. Needs scoping: which
  state matters most for the user (VIC, NSW most likely).

### Small follow-ups (nice-to-have, not blocking)

- **Persona-card thresholds (≥99/95/85%) are hardcoded.** Could be exposed as Advanced
  settings if you want to tune your safety appetite levels per scenario.
- **Cards are informational, not clickable.** Could become "click to set the slider" via
  `st.session_state` for one-click selection.
- **Sweep runs at 2000 trials × 11 mix points.** First load of new inputs takes ~5–10 s.
  Cached, so subsequent re-renders are instant. Could shrink to 7 mix points or 1000 trials
  if the cold-load delay bothers you.
- **Year-by-year wealth fan chart mockup exists** at `notebooks/wealth_fan_mockup.py` but
  was not integrated — user said it didn't land. The model-layer `wealth_per_year` exposure
  shipped anyway (commit `a324240`); ready if you change your mind.

### Setup commands

```bash
cd "/Users/aidenmacmini/AI Project/Financial Modeling/property-vs-shares"
source .venv/bin/activate
PYTHONPATH=. pytest -q              # expect 95 passed
PYTHONPATH=. python notebooks/scenario_sweep.py   # full regime × dial sweep
PYTHONPATH=. python notebooks/tornado.py          # sensitivity ranking (4 tables)
streamlit run app.py                # launch UI
```

Last meaningful commit on `main`: `1fc66d1 fix(app): persona cards render as HTML + dollar signs escape mathjax`

### Mockup files (informational — chart redesign already shipped to app)

- `notebooks/frontier_mockup.html` — interactive efficient-frontier chart with
  plain-language axes. Standalone view; the app ships persona cards instead.
- `notebooks/wealth_fan_mockup.html` — year-by-year wealth path with bands.
  User dismissed as "not landing" — not integrated. Model layer (`wealth_per_year`)
  is still exposed in case the framing comes back.
- `notebooks/recommendation_mockup.html` — the side-by-side cards + table
  comparison that informed the final design. Now redundant since both are in the app.

Regenerate any of these with:
```bash
PYTHONPATH=. python notebooks/<name>_mockup.py
```

## Bugs / correctness

*All three v1.1 bugs shipped 2026-05-16. See "Done since v1" below.*

## Polish / minor

*All shipped 2026-05-16. See "Done since v1" below.*

## Larger v1.1 features (already noted in design spec §16)

- Mode B margin-call modelling
- Single-property idiosyncratic risk shock events
- Major capex events (roof, hot water, etc.)
- Offset account as a third strategy
- Other states beyond SA

## Surfaced by 2026-05-16 sensitivity work (post-Budget regime build)

- **Loan-rate fat tails matter MORE than return fat tails** under the restricted regime.
  The tornado (commit `a6120ac`) showed `loan_rate_mu` drives a ~55pp swing in
  `p_property_succeeds`. **Shipped** as commit `8bd01f6`: opt-in Student-t now also
  covers `loan_rate_paths`, controlled by the same UI toggle. Fat-tailed tornado
  (commit `f108b2a`) confirmed `loan_rate_mu` is still the dominant driver under
  Student-t (54pp swing) — finding robust to distribution choice.

- **Property age toggle is a no-op under v1's depreciation simplification.**
  The 5-row sweep (`new_build` / `established_post_2017` / `established_pre_2017`)
  produces bit-identical numbers because `model/tax.py:depreciation_for_year` returns
  Div 43 only, ignoring `property_age`. Partially mitigated by warning banner (commit
  `4f061d8`) which fires when `new_build` + `restricted_2027` is selected. **Still
  pending:** auto-couple `property_age == "new_build"` → force `regime = "current"`
  with override, OR plumb Div 40 / building-cost differentiation properly.

- **Allocation-mix framing.** **Shipped** as commit `493c27e` using Option A
  (wealth-level mix; per-trial weighted blend preserving correlation structure).
  Default `property_share_mix=1.0` preserves current behaviour bit-for-bit.
  See "Done since v1" for the cross-regime allocation finding.

## Done since v1

- ✅ Federal Budget 2026-27 NG + CGT regime toggle (2026-05-16). See
  `docs/2026-05-16-budget-2026-27-design.md` for design + GPT review notes.
- ✅ Joint success metric `p_property_succeeds = P(wins ∧ solvent)` and reframed
  app headline (2026-05-16, commit `8775380`). The naive `p_property_wins` was
  misleading — it included trials where the strategy "won" on paper but was forced
  insolvent along the way. Joint metric drops the BASE headline from 70% → 31.6%
  under restricted_2027, which is the honest decision-relevant number.
- ✅ Tornado sensitivity analysis (2026-05-16, commit `a6120ac`). Ranks 10 inputs
  by their swing in `p_property_succeeds`. **Headline finding:** under restricted
  regime, `loan_rate_mu` dominates (55pp swing); MTR effect collapses to <1pp.
- ✅ Student-t innovations opt-in (2026-05-16, commit `fe2836a`). Default Gaussian
  preserved. Toggle in Advanced UI. Realized σ rescaled to match user-specified σ.
- ✅ Student-t extended to loan_rate (2026-05-16, commit `8bd01f6`). Same UI toggle
  controls both. AU rates empirically fat-tailed (1989, 2022).
- ✅ Fat-tailed tornado sanity check (2026-05-16, commit `f108b2a`). Confirmed
  `loan_rate_mu` dominant under both Gaussian and Student-t distributions.
- ✅ Stamp duty + buying costs in CGT cost base (2026-05-16, commit `32a8f01`).
  BACKLOG §Bugs §1 fix. `current` regime headline lifted +0.4pp; `restricted_2027`
  unchanged (loss pool already neutralizes most post-commencement CGT).
- ✅ New-build × restricted_2027 warning banner (2026-05-16, commit `4f061d8`).
  Surfaces the regime-misapplication footgun for new builds. Full auto-couple
  remains in "Surfaced…" section as v1.2.
- ✅ Dual same-seed RNG decoupled (2026-05-16, commit `4f061d8`). BACKLOG §Bugs §2.
  `seed + 1` passed to `generate_correlated_paths`. Regression test guards.
- ✅ `rental_yield_sigma` slider hidden (2026-05-16, commit `42f8135`). BACKLOG §Bugs §3.
  Was a no-op; re-expose when yield-path stochasticity ships.
- ✅ `p_solvent` helper dedup (2026-05-16, commit `42f8135`). BACKLOG §Polish §1.
  Minor double-call to `flag_forced_sales` introduced — captured in §Polish §2 above.
- ✅ **Allocation-mix slider** (2026-05-16, commit `493c27e`). Wealth-level Option A
  per Opus design conversation. **Headline finding from cross-regime sweep:**

  | mix | current beats_shr / solvent | restricted beats_shr / solvent |
  |---:|---:|---:|
  | 0% (pure shares) | 0% / 100% | 0% / 100% |
  | 25% | 77.8% / 100% | 70.7% / 100% |
  | 50% | 77.8% / 100% | 70.7% / 99.9% |
  | 75% | 77.8% / 100% | 60.5% / 79.6% |
  | 100% (pure property) | 77.6% / 99.0% | **31.4% / 37.1%** |

  Under current rules, pure property is rational (high solvency, no allocation penalty).
  **Under restricted_2027, the optimal allocation shifts to ~50% property** — beyond that,
  solvency degrades faster than wealth grows. The Budget 2026-27 changes don't just
  penalize property; they restructure the optimal portfolio composition.

- ✅ Property-age × regime auto-couple (2026-05-16, commit `4cf417c`). Per Budget 2026-27,
  new builds retain full NG and can elect either CGT method. The model now auto-applies
  `current` rules when `property_age == "new_build"` regardless of the regime selector,
  with an Advanced-section override checkbox for power users modelling the counterfactual.
  Replaces the warning banner from `4f061d8` with a positive carve-out notice. Sanity
  confirmed: new builds give identical `p_property_succeeds = 77.6%` regardless of regime
  selector position; established properties still differentiate (77.6% vs 31.4%).
- ✅ Exact today-$ deflation for `worst_year_cash` + mix-array deflation +
  `p_solvent` revert (2026-05-16, commit `f15e95a`). Three polish items in one:
  - Old today-$ deflation used `(1+cpi)^horizon` regardless of which year was worst.
    Under default scenario this understated the displayed worst-year cash by **$10,522**
    (~67% of the nominal-to-fully-deflated gap). Now correctly recomputes after per-year
    deflation: $26,305 vs the old $15,782.
  - Mix arrays (`mixed_terminal_wealth`, `mixed_outside_cash_per_trial_year`) were
    missing from the deflation block — inconsistent display when mix < 1 + Today's $ mode.
  - Reverted the `p_solvent` "dedup" from commit `42f8135` that introduced redundant
    `flag_forced_sales` computation. Helper still available for fresh callers.
- ✅ Model-layer `wealth_per_year` exposure (2026-05-16, commit `a324240`).
  Read-only addition: PropertyResult, ShareResult, and the monte_carlo return dict
  now expose year-by-year mark-to-market pre-tax wealth. No simulation behavior
  change. Foundation for any future path-dependent visualization.
- ✅ **Recommendation-first UI redesign** (2026-05-16, commits `b9a1e8c` + `1fc66d1`).
  After 4 mockup iterations (frontier with relabels, year-by-year fan chart,
  static personas, dynamic personas), the chosen design landed in `app.py`:
  - **Persona cards lead the main pane**: Safe Player (≥99% safe), Balanced ⭐
    (≥95% safe — the optimization target), Wealth Maximizer (≥85% safe). Each
    allocation is **computed dynamically** from the safety threshold — they shift
    with sidebar inputs.
  - **Comparison table** behind `▾ Compare all allocations` expander (collapsed by
    default). Full 11-row mix sweep with recommended row highlighted green.
  - **Old terminal-wealth histogram + cashflow stress chart** demoted into
    `▾ Show distributions and cashflow detail` expander (collapsed). They still
    exist for users who want the underlying distributions, but no longer compete
    for attention with the recommendation.
  - **Existing slider + headline + KPI tiles unchanged** — they describe the
    user's CURRENT mix selection, which they can override against the recommendation.
  - **Edge cases handled**: merged single-card when all 3 thresholds resolve to same
    allocation (e.g. under `current` regime); "Unreachable" Safe Player card when
    no allocation meets ≥99% safety (e.g. very tight serviceability ceiling).
  - **Sweep runs at 2000 trials × 11 mix points**, cached via `st.cache_data`.
    Cold load adds ~5–10s; subsequent renders instant.
  - **Bugfix bundled in `1fc66d1`**: f-string HTML was indented 4+ spaces, which
    Streamlit's markdown parser interpreted as a code block. Cards initially rendered
    as raw `<div>` text. Fixed via `_render_html` helper that strips per-line
    indent. Also escaped `\$` in pre-existing markdown calls where dollar signs
    were being eaten by Streamlit's mathjax.

  **Mockup files** that informed the design persist in `notebooks/`:
  - `frontier_mockup.py/html` — efficient frontier with plain-language labels
  - `wealth_fan_mockup.py/html` — year-by-year wealth path (rejected as too busy)
  - `recommendation_mockup.py/html` — persona cards + comparison table

---

*Generated from final holistic code review on 2026-05-11. Issues #1 (max_top_up
serviceability wiring) and #6 (unused `deflate` import) were fixed inline in commit
that landed alongside this file.*
