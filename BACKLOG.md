# v1.1 Backlog

Items surfaced by the final holistic code review (2026-05-11) that were not
critical for shipping v1 but should be addressed before the model is used for
a real allocation decision a second time.

## Pickup notes (when resuming)

**Last touched: 2026-05-16, very late evening session.** Working tree clean, 90/90 tests passing.
All v1.1 bugs + ALL 4 finance-expert recommendations + 2 of 3 surfaced-during-sensitivity items
shipped (the third is the property-age auto-couple, partially mitigated by warning banner).
Only `worst_year_cash` deflation precision (small) and larger v1.2 features remain.

### What landed across the 2026-05-16 sessions (10 commits)

Earlier (evening 1):
1. `7ef3baf` test — scenario sweep script (`notebooks/scenario_sweep.py`)
2. `8775380` **feat — joint `p_property_succeeds` metric + reframed app headline**
3. `a6120ac` test — tornado sensitivity (`notebooks/tornado.py`)
4. `fe2836a` feat — opt-in Student-t for property + share returns
5. `ca4dd41` docs — BACKLOG ticked off shipped, captured findings
6. `8bd01f6` feat — extended Student-t to loan_rate (tornado-dominant input)
7. `31cd5ab` docs — pickup notes refresh

Later (evening 2):
8. `f108b2a` test — tornado pass under fat-tailed distributions (validated finding)
9. `32a8f01` **fix — stamp duty + buying costs in CGT cost base (BACKLOG §1)**
10. `4f061d8` fix — new-build × regime warning banner + dual-seed RNG decoupling
11. `42f8135` chore — hid no-op `rental_yield_sigma` slider + `p_solvent` helper dedup

### The four findings worth re-reading before doing anything new

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

### Suggested resume order

1. **Smoke-test the app first** (5 min). `source .venv/bin/activate && streamlit run app.py`.
   New things to look at: the joint success headline, the new-build × restricted warning
   banner (toggle property_age → new_build + regime → restricted_2027), and the Student-t
   dropdown in Advanced.
2. **Pick from "Remaining" below.** The allocation-mix slider is the highest-leverage piece
   left (PM-grade reframing). The `worst_year_cash` deflation refinement is small and only
   matters if the rough number feels wrong.

### Remaining items (in decision-relevance order)

- **Property-age × regime auto-coupling** (currently just a warning banner). Auto-set regime
  to `current` when `property_age == "new_build"` with override option. v1.2 candidate.
- **`worst_year_cash` deflation** (BACKLOG §Polish §2). Approximate; only fix if the
  number ever feels off.
- **Larger v1.2 features**: Mode B margin-call modelling, single-property idiosyncratic
  risk shocks, capex events, offset account, other states. All bigger commitments —
  brainstorm scope before plunging in.

### Setup commands

```bash
cd "/Users/aidenmacmini/AI Project/Financial Modeling/property-vs-shares"
source .venv/bin/activate
PYTHONPATH=. pytest -q              # expect 90 passed
PYTHONPATH=. python notebooks/scenario_sweep.py   # full regime × dial sweep
PYTHONPATH=. python notebooks/tornado.py          # sensitivity ranking (4 tables)
streamlit run app.py                # launch UI
```

Last meaningful commit on `main`: `493c27e feat(monte-carlo): wealth-level allocation mix slider`

## Bugs / correctness

*All three v1.1 bugs shipped 2026-05-16. See "Done since v1" below.*

## Polish / minor

- **`worst_year_cash` deflation is approximate** — `app.py` uses `(1 + cpi) ** horizon` for the
  90th-percentile worst-year cash figure, but those worst years don't all land at year `horizon`.
  Error up to ~80% of the full deflator (a few thousand dollars on a $15k figure). Acceptable
  for a personal tool but worth either a UI tooltip or an exact per-trial-year deflation.

- **`flag_forced_sales` is called twice in `run_monte_carlo`** as a side effect of the
  `p_solvent` helper dedup (commit `42f8135`). Once explicitly to compute `forced_flags`
  (still needed for `p_property_succeeds` and the `forced_sale_flags` return key), once
  inside `p_solvent(p_outside_cash, ceiling)`. Performance is irrelevant (vectorised numpy,
  sub-ms) but it's not clean dedup. Future cleanup: either restructure `p_solvent` to accept
  pre-computed flags, or revert to inline `float(1 - forced_flags.mean())` (the original was
  actually fine).

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

---

*Generated from final holistic code review on 2026-05-11. Issues #1 (max_top_up
serviceability wiring) and #6 (unused `deflate` import) were fixed inline in commit
that landed alongside this file.*
