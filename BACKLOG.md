# v1.1 Backlog

Items surfaced by the final holistic code review (2026-05-11) that were not
critical for shipping v1 but should be addressed before the model is used for
a real allocation decision a second time.

## Pickup notes (when resuming)

**Last touched: 2026-05-16, evening session.** Working tree clean, 82/82 tests passing,
all six session commits on `main` (no remote — local only).

### What landed in the 2026-05-16 evening session

Six commits, ordered:
1. `7ef3baf` test — scenario sweep script (`notebooks/scenario_sweep.py`)
2. `8775380` **feat — joint `p_property_succeeds` metric + reframed app headline**
3. `a6120ac` test — tornado sensitivity (`notebooks/tornado.py`)
4. `fe2836a` feat — opt-in Student-t for property + share returns
5. `ca4dd41` docs — this file: ticked off shipped, captured findings
6. `8bd01f6` feat — extended Student-t to loan_rate (the tornado-dominant input)

### The three findings worth re-reading before doing anything new

1. **Honest headline = 31.6%, not 70%.** Under restricted_2027, joint success
   `p_property_wins ∧ p_solvent` is what matters. Solvency is the binding constraint.
2. **Loan rate dominates under restricted regime** — 55pp swing in `p_property_succeeds`
   per the tornado. `mtr` effect collapses to <1pp (NG quarantining kills the tax shield).
3. **Symmetric fat tails barely move headlines, but inflate p99 worst-year cash.**
   At df=3, `p_succeeds` actually goes UP (low-rate draws rescue marginal trials) but
   `worst_year p99` goes from $34.7k → $51.5k. The t-dist feature's real value is
   inspecting tail metrics, not headlines.

### Suggested resume order

1. **Smoke-test the new headline in Streamlit first** (5 min).
   `source .venv/bin/activate && streamlit run app.py`
   Toggle the regime, toggle Student-t in Advanced. Does the 31.6% feel right
   against your intuition? If it doesn't, that discrepancy is the next signal.

2. **Re-run the tornado with `loan_rate_distribution=student_t`** (15 min, mostly
   re-typing the script). Confirms loan_rate is *still* the dominant driver under
   fat tails — should be, but worth verifying. Edit `notebooks/tornado.py` to thread
   `loan_rate_distribution=dist` into the `run(...)` calls.

3. **Pick from the BACKLOG below.** Highest decision-relevance items are now flagged
   in the "Surfaced by 2026-05-16 sensitivity work" section — start there, not the
   original 2026-05-11 cleanup list. The pre-2026-05-11 bugs are still real but
   smaller-leverage.

### Decision point you parked

**Allocation-mix slider** (#4 from the finance-expert recommendation list). PM-grade
framing — "what mix of property/shares?", not binary. Needs an Opus-tier design
conversation (how does equal-cash rule split across two strategies? how does
serviceability work for a 60/40 mix?) before any code. Captured under "Surfaced by
2026-05-16…" → "Allocation-mix framing."

### Setup commands

```bash
cd "/Users/aidenmacmini/AI Project/Financial Modeling/property-vs-shares"
source .venv/bin/activate
PYTHONPATH=. pytest -q              # expect 82 passed
PYTHONPATH=. python notebooks/scenario_sweep.py   # full regime × dial sweep
PYTHONPATH=. python notebooks/tornado.py          # sensitivity ranking
streamlit run app.py                # launch UI
```

Last meaningful commit on `main`: `8bd01f6 feat(monte-carlo): extend opt-in Student-t to loan_rate_paths`

## Bugs / correctness

- **Stamp duty + buying costs missing from property CGT cost base.** `model/property_strategy.py`
  computes `cost_base = purchase_price + selling_costs - cumulative_div43`. Under ATO rules,
  acquisition costs (stamp duty, conveyancing, inspections, loan establishment fees) are
  legitimate cost-base inclusions. Property CGT is currently overstated by ~MTR × 0.5 ×
  ($32k stamp duty + $2.6k buying costs) ≈ $6.4k per trial at 37% MTR. Direction
  *disadvantages* property — fixing it will slightly raise `p_property_wins`. Add
  `acquisition_costs` to `PropertyInputs` and include in cost-base calc.

- **Dual same-seed RNG in `run_monte_carlo`.** The function instantiates its own
  `rng = np.random.default_rng(seed)` and then calls `generate_correlated_paths(..., seed=seed)`,
  which creates its own RNG from the same seed. Empirically the spurious correlation between
  loan-rate draws and return draws is negligible (-0.004 vs 0.001 for independent seeds), but
  it is a latent defect. Fix: pass the outer `rng` into `generate_correlated_paths`, or use
  `seed + 1` for one of the two streams.

- **`rental_yield_sigma` slider is a no-op.** The Advanced sidebar exposes a "Rental yield σ"
  slider that is plumbed into `run_monte_carlo` but never consumed (the property strategy takes
  a scalar `gross_yield`). A user who cranks this slider expecting wider rent distributions
  sees no change. Either: (a) plumb it into `PropertyInputs` as a per-year `rental_yield_path`,
  or (b) hide/disable the slider with a "v1.1" label.

## Polish / minor

- **`p_solvent` reimplemented inline** in `model/monte_carlo.py` instead of using the helper
  in `model/solvency.py`. Trivial dedup.

- **`worst_year_cash` deflation is approximate** — `app.py` uses `(1 + cpi) ** horizon` for the
  90th-percentile worst-year cash figure, but those worst years don't all land at year `horizon`.
  Error up to ~80% of the full deflator (a few thousand dollars on a $15k figure). Acceptable
  for a personal tool but worth either a UI tooltip or an exact per-trial-year deflation.

## Larger v1.1 features (already noted in design spec §16)

- Mode B margin-call modelling
- Single-property idiosyncratic risk shock events
- Major capex events (roof, hot water, etc.)
- Offset account as a third strategy
- Other states beyond SA

## Surfaced by 2026-05-16 sensitivity work (post-Budget regime build)

- **Loan-rate fat tails matter MORE than return fat tails** under the restricted regime.
  The tornado (commit `a6120ac`) shows `loan_rate_mu` drives a 55pp swing in
  `p_property_succeeds` — the dominant input by a wide margin. The Student-t feature
  (commit `fe2836a`) deliberately leaves `loan_rate_paths` Gaussian per design lock; the
  2x2 confirmed t-dist on returns barely moves the headline because returns aren't the
  binding constraint, rates are. **v1.1 candidate:** allow `return_distribution` to also
  cover `loan_rate_paths` (or add a separate `loan_rate_distribution` toggle). Without
  it, the t-dist feature is honest about return tails but blind to rate-shock tails —
  which is the actual risk under restricted_2027.

- **Property age toggle is a no-op under v1's depreciation simplification.**
  The 5-row sweep (`new_build` / `established_post_2017` / `established_pre_2017`)
  produces bit-identical numbers because `model/tax.py:depreciation_for_year` returns
  Div 43 only, ignoring `property_age`. This interacts with the Budget 2026-27 regime
  toggle: in real life, a new build *retains full NG* and can elect either CGT method,
  whereas the model treats them identically. Either: (a) UI clarification — banner
  warns the regime toggle should be `current` for new builds, or (b) auto-couple
  `property_age == "new_build"` → force `regime = "current"` (with override).

- **Allocation-mix framing.** Real PMs don't ask "100% property OR 100% shares" — they
  ask "what mix?". A `property_share_mix` slider running both strategies in parallel
  and reporting blended outcomes is conceptually simple but architecturally non-trivial
  (how does the equal-cash rule split across two strategies? how does serviceability
  work for a 60/40 mix?). Defer until base model is stable.

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
  See "loan-rate fat tails" item above for follow-on work.

---

*Generated from final holistic code review on 2026-05-11. Issues #1 (max_top_up
serviceability wiring) and #6 (unused `deflate` import) were fixed inline in commit
that landed alongside this file.*
