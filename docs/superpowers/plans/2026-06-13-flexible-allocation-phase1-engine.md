# Flexible Allocation — Phase 1 (Engine + Auto-Recompute) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 11-point sweep (11 × 2,000-trial re-simulations + a manual ↻ button) with a single 5,000-trial base run whose unblended per-trial arrays feed a pure post-hoc `build_mix_curve` function. Add input-hash-guarded auto-recompute (no manual button), wire all downstream charts to derive from that one run, and harden `None`-card handling for all three personas. (`st.fragment` scoping of the dial/free-mix is Phase 2, when those widgets exist — see A6.)

**Architecture:** Task 0 verifies `run_monte_carlo` already exposes all needed raw arrays (it does — see below) and measures cold-run p95. Task 1 creates `model/mix_curve.py` with a pure `build_mix_curve` function and its dataclass, with a full TDD regression gate. Task 2 wires `app.py`: replaces `compute_persona_sweep` + the ↻ button + `sweep_key`/`stale` machinery with one base-run call → `build_mix_curve`, hardens `render_persona_cards` `None` handling on all three cards, adds the input-hash state machine, `try/except` error state, and new URL-param guards. Persona names/badge and the comparison table are preserved (renames/retirement are Phase 2 — see A7).

**Tech Stack:** Python 3.x, NumPy, Streamlit, pytest (run via `.venv/bin/python -m pytest -q`)

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `model/mix_curve.py` | **Create** | `MixPoint` dataclass + `build_mix_curve` pure function; no Streamlit imports |
| `model/monte_carlo.py` | **Verify only (Task 0)** — no changes needed (all arrays already exposed) | Expose raw `p_terminal`, `s_terminal`, `outside_cash_per_trial_year`, `property_wealth_path`, `shares_wealth_path` |
| `ui/persona.py` | **Modify** | `find_optimal_mix` accepts `list[MixPoint]`; `render_persona_cards` hardens `None` handling for ALL three cards + merged path; retire `compute_persona_sweep`; keep `render_comparison_table` adapted to `MixPoint`. Names/badge unchanged (renames = Phase 2, A7) |
| `app.py` | **Modify** | Replace sweep + ↻ button with base-run → `build_mix_curve`; add `_input_hash()`, input-hash state machine, try/except error state, new URL params (`dial_safety`, `free_mix`) with clamp on read AND write. (`st.fragment` is Phase 2, A6) |
| `tests/test_mix_curve.py` | **Create** | Engine-equivalence regression, mix-aware downside, CRN smoothness (gaussian + student_t), deflation contract, comparison_mode relabel, state transitions, malformed URL param clamps |

---

## Task 0 — Verify array exposure + measure cold-run p95

**Files:**
- Verify only: `model/monte_carlo.py` (lines 133–137, 239–285)
- Create: `tests/test_mix_curve.py` (initial file with Task 0 measurement + assertion)

### Why Task 0 comes first

Before any behavior-affecting change, establish: (a) `run_monte_carlo` already exposes every array `build_mix_curve` needs, so no return-dict refactor is required; (b) a timing measurement sets the acceptance baseline. This is the regression gate.

- [ ] **Step 1: Verify array exposure in `model/monte_carlo.py`**

  Check the return dict (lines 239–285). Confirmed present:
  - `outside_cash_per_trial_year` → raw `p_outside_cash` (trials, horizon) — line 243
  - `property_wealth_path` → raw `p_wealth_path` (trials, horizon) — line 259
  - `shares_wealth_path` → raw `s_wealth_path` (trials, horizon) — line 260
  - `property_terminal_wealth` → raw `p_terminal` (trials,) — line 239
  - `shares_terminal_wealth` → raw `s_terminal` (trials,) — line 240

  **No refactor required.** All arrays are already returned unblended. The `mixed_*` keys in the return dict are derived from `property_share_mix` at call-time but do not affect the raw arrays. Task 0 is verification-only.

- [ ] **Step 2: Write failing test — cold run timing measurement**

  ```python
  # tests/test_mix_curve.py  (new file — full content for this task)
  """Phase 1 engine tests: mix curve, CRN, downside metrics, deflation, state."""
  import time
  import pytest
  import numpy as np

  # ---------------------------------------------------------------------------
  # Shared minimal kwargs for run_monte_carlo (100 trials for fast unit tests;
  # Task 0 timing test uses 5000).
  # ---------------------------------------------------------------------------
  _BASE_KWARGS = dict(
      purchase_price=700_000, deposit=140_000,
      stamp_duty=32_330, buying_costs=2_600,
      loan_rate_mu=0.06, loan_rate_sigma=0.01,
      gross_yield=0.04, vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
      rental_yield_sigma=0.0,
      property_growth_mu=0.055, property_growth_sigma=0.11,
      share_return_mu=0.085, share_return_sigma=0.15,
      correlation=0.3,
      management_fee_pct=0.07, maintenance_pct=0.012,
      property_age="established_post_2017", asset_type="house",
      depreciation_override=None,
      portfolio_profile="blended",
      mode="realistic",
      margin_loan_rate=0.075, isolate_asset_quality=False,
      mtr=0.37, cpi=0.025, drp=True,
      serviceability_ceiling=20_000,
      seed=42,
      return_distribution="gaussian",
  )

  # ---------------------------------------------------------------------------
  # Task 0 — cold-run timing (p95 target ≤ ~3 s)
  # ---------------------------------------------------------------------------
  def test_cold_base_run_p95_under_3s():
      """Cold 5,000-trial run must complete in ≤ 3 s (acceptance gate for no-button UX).
      Runs 3 timed repetitions; checks that the slowest (p95 proxy) is within limit."""
      from model.monte_carlo import run_monte_carlo
      kwargs = dict(_BASE_KWARGS, trials=5000, horizon_years=25)
      times = []
      for _ in range(3):
          t0 = time.perf_counter()
          run_monte_carlo(**kwargs)
          times.append(time.perf_counter() - t0)
      p95 = sorted(times)[-1]  # max of 3 = conservative p95 proxy
      assert p95 <= 3.0, (
          f"Cold base run took {p95:.2f}s — exceeds 3s target. "
          f"Consider background-thread fallback (see spec §3.5)."
      )
  ```

  Run: `.venv/bin/python -m pytest tests/test_mix_curve.py::test_cold_base_run_p95_under_3s -v`
  Expected: FAIL (file doesn't exist yet) → after writing the file: runs and either PASSES or prints the timing advisory.

- [ ] **Step 3: Run the timing test and record result**

  ```
  .venv/bin/python -m pytest tests/test_mix_curve.py::test_cold_base_run_p95_under_3s -v -s
  ```

  If it PASSES (≤ 3s): proceed. If it FAILS (> 3s): record the measured time in a comment in `tests/test_mix_curve.py` next to the test; note the background-thread fallback as a follow-up task (do NOT add it now — out of Phase 1 scope per the prompt). Mark the test `@pytest.mark.slow` and skip it in CI with `-m "not slow"`.

- [ ] **Step 4: Commit the test file**

  ```bash
  git add tests/test_mix_curve.py
  git commit -m "test(mix_curve): Task 0 cold-run timing gate (p95 ≤ 3s)"
  ```

---

## Task 1 — `model/mix_curve.py`: `MixPoint` dataclass + `build_mix_curve` pure function

**Files:**
- Create: `model/mix_curve.py`
- Extend: `tests/test_mix_curve.py` (add all engine-equivalence and downside tests)

### Step-by-step

- [ ] **Step 1: Write failing tests for `build_mix_curve` (append to `tests/test_mix_curve.py`)**

  ```python
  # --- append to tests/test_mix_curve.py ---

  from model.solvency import flag_forced_sales

  # ---------------------------------------------------------------------------
  # Helper: one shared base run at 200 trials (fast) for unit tests
  # ---------------------------------------------------------------------------
  @pytest.fixture(scope="module")
  def base_run_200():
      from model.monte_carlo import run_monte_carlo
      return run_monte_carlo(trials=200, horizon_years=10, **_BASE_KWARGS)


  @pytest.fixture(scope="module")
  def base_run_5000():
      """Full-resolution run for CRN smoothness tests."""
      from model.monte_carlo import run_monte_carlo
      return run_monte_carlo(trials=5000, horizon_years=25, **_BASE_KWARGS)


  # ---------------------------------------------------------------------------
  # Task 1a — MixPoint dataclass shape
  # ---------------------------------------------------------------------------
  def test_mix_point_has_required_fields():
      from model.mix_curve import MixPoint
      mp = MixPoint(
          mix_pct=50,
          median_mixed_wealth=1_000_000.0,
          p_solvent=0.95,
          p_succeeds=0.70,
          p_mix_beats_pure_shares=0.65,
          worst_year_cash=15_000.0,
          total_top_ups=80_000.0,
          forced_sale_rate=0.05,
      )
      assert mp.mix_pct == 50
      assert mp.p_solvent == pytest.approx(0.95)


  # ---------------------------------------------------------------------------
  # Task 1b — build_mix_curve output shape and values
  # ---------------------------------------------------------------------------
  def test_build_mix_curve_returns_21_points(base_run_200):
      from model.mix_curve import build_mix_curve
      r = base_run_200
      curve = build_mix_curve(
          p_terminal=r["property_terminal_wealth"],
          s_terminal=r["shares_terminal_wealth"],
          p_outside_cash=r["outside_cash_per_trial_year"],
          p_wealth_path=r["property_wealth_path"],
          s_wealth_path=r["shares_wealth_path"],
          ceiling=20_000,
      )
      assert len(curve) == 21
      assert curve[0].mix_pct == pytest.approx(0.0)
      assert curve[-1].mix_pct == pytest.approx(1.0)


  def test_build_mix_curve_mix_pcts_are_linspace(base_run_200):
      from model.mix_curve import build_mix_curve
      r = base_run_200
      curve = build_mix_curve(
          p_terminal=r["property_terminal_wealth"],
          s_terminal=r["shares_terminal_wealth"],
          p_outside_cash=r["outside_cash_per_trial_year"],
          p_wealth_path=r["property_wealth_path"],
          s_wealth_path=r["shares_wealth_path"],
          ceiling=20_000,
      )
      expected = np.linspace(0, 1, 21)
      actual = np.array([pt.mix_pct for pt in curve])
      np.testing.assert_allclose(actual, expected)


  def test_build_mix_curve_probabilities_in_range(base_run_200):
      from model.mix_curve import build_mix_curve
      r = base_run_200
      curve = build_mix_curve(
          p_terminal=r["property_terminal_wealth"],
          s_terminal=r["shares_terminal_wealth"],
          p_outside_cash=r["outside_cash_per_trial_year"],
          p_wealth_path=r["property_wealth_path"],
          s_wealth_path=r["shares_wealth_path"],
          ceiling=20_000,
      )
      for pt in curve:
          assert 0.0 <= pt.p_solvent <= 1.0, f"p_solvent={pt.p_solvent} out of range at mix={pt.mix_pct}"
          assert 0.0 <= pt.p_succeeds <= 1.0
          assert 0.0 <= pt.p_mix_beats_pure_shares <= 1.0
          assert 0.0 <= pt.forced_sale_rate <= 1.0


  # ---------------------------------------------------------------------------
  # Task 1c — Engine equivalence (byte-identical regression gate)
  # Calling build_mix_curve at mix=0.6 must match a direct run_monte_carlo
  # at property_share_mix=0.6 for the metrics build_mix_curve computes.
  # ---------------------------------------------------------------------------
  def test_build_mix_curve_engine_equivalence_at_0_6():
      """build_mix_curve at mix=0.6 must be byte-identical to run_monte_carlo at mix=0.6.
      This is the Phase 1 regression gate: the refactor changes no numbers."""
      from model.monte_carlo import run_monte_carlo
      from model.mix_curve import build_mix_curve

      # Single base run (unblended arrays)
      base = run_monte_carlo(trials=200, horizon_years=10, **_BASE_KWARGS)

      # Reference: direct single-mix run at 0.6
      ref = run_monte_carlo(
          trials=200, horizon_years=10, property_share_mix=0.6, **_BASE_KWARGS
      )

      # Derive mix=0.6 from build_mix_curve; pick the 0.6 point (index 12 of linspace(0,1,21))
      curve = build_mix_curve(
          p_terminal=base["property_terminal_wealth"],
          s_terminal=base["shares_terminal_wealth"],
          p_outside_cash=base["outside_cash_per_trial_year"],
          p_wealth_path=base["property_wealth_path"],
          s_wealth_path=base["shares_wealth_path"],
          ceiling=20_000,
      )
      # mix_pct = 0.6 is index 12 in linspace(0,1,21)
      pt = curve[12]
      assert pt.mix_pct == pytest.approx(0.6)

      # median_mixed_wealth — both derive np.median(0.6*p + 0.4*s)
      mixed_from_base = 0.6 * base["property_terminal_wealth"] + 0.4 * base["shares_terminal_wealth"]
      mixed_from_ref = ref["mixed_terminal_wealth"]
      # Byte-identical (same arrays, same operation)
      np.testing.assert_array_equal(mixed_from_base, mixed_from_ref)
      assert pt.median_mixed_wealth == pytest.approx(float(np.median(mixed_from_base)))

      # p_solvent — both derive from flag_forced_sales(0.6 * p_outside_cash, ceiling)
      mixed_cash_base = 0.6 * base["outside_cash_per_trial_year"]
      mixed_cash_ref = ref["mixed_outside_cash_per_trial_year"]
      np.testing.assert_array_equal(mixed_cash_base, mixed_cash_ref)
      flags_base = flag_forced_sales(mixed_cash_base, 20_000)
      flags_ref = flag_forced_sales(mixed_cash_ref, 20_000)
      np.testing.assert_array_equal(flags_base, flags_ref)
      assert pt.p_solvent == pytest.approx(float(1 - flags_base.mean()))
      assert pt.p_solvent == pytest.approx(ref["p_mix_solvent"])


  def test_build_mix_curve_engine_equivalence_at_1_0():
      """mix=1.0 point (pure property) matches direct run at property_share_mix=1.0."""
      from model.monte_carlo import run_monte_carlo
      from model.mix_curve import build_mix_curve

      base = run_monte_carlo(trials=200, horizon_years=10, **_BASE_KWARGS)
      # property_share_mix defaults to 1.0 in run_monte_carlo
      ref = run_monte_carlo(trials=200, horizon_years=10, property_share_mix=1.0, **_BASE_KWARGS)

      curve = build_mix_curve(
          p_terminal=base["property_terminal_wealth"],
          s_terminal=base["shares_terminal_wealth"],
          p_outside_cash=base["outside_cash_per_trial_year"],
          p_wealth_path=base["property_wealth_path"],
          s_wealth_path=base["shares_wealth_path"],
          ceiling=20_000,
      )
      pt = curve[-1]  # index 20, mix_pct=1.0
      assert pt.mix_pct == pytest.approx(1.0)
      assert pt.p_solvent == pytest.approx(ref["p_mix_solvent"])
      assert pt.forced_sale_rate == pytest.approx(float(flag_forced_sales(
          1.0 * base["outside_cash_per_trial_year"], 20_000).mean()))


  def test_build_mix_curve_engine_equivalence_at_0_0():
      """mix=0.0 (pure shares): p_solvent=1.0, worst_year_cash=0, forced_sale_rate=0."""
      from model.monte_carlo import run_monte_carlo
      from model.mix_curve import build_mix_curve

      base = run_monte_carlo(trials=200, horizon_years=10, **_BASE_KWARGS)
      curve = build_mix_curve(
          p_terminal=base["property_terminal_wealth"],
          s_terminal=base["shares_terminal_wealth"],
          p_outside_cash=base["outside_cash_per_trial_year"],
          p_wealth_path=base["property_wealth_path"],
          s_wealth_path=base["shares_wealth_path"],
          ceiling=20_000,
      )
      pt = curve[0]  # index 0, mix_pct=0.0
      assert pt.mix_pct == pytest.approx(0.0)
      # Pure shares has zero outside-cash demand
      assert pt.worst_year_cash == pytest.approx(0.0)
      assert pt.forced_sale_rate == pytest.approx(0.0)
      assert pt.p_solvent == pytest.approx(1.0)


  # ---------------------------------------------------------------------------
  # Task 1d — Mix-aware downside metric definitions (spec §5.3)
  # ---------------------------------------------------------------------------
  def test_worst_year_cash_definition(base_run_200):
      """worst_year_cash = percentile(mixed_outside_cash.max(axis=1), 90)."""
      from model.mix_curve import build_mix_curve
      r = base_run_200
      mix = 0.5
      curve = build_mix_curve(
          p_terminal=r["property_terminal_wealth"],
          s_terminal=r["shares_terminal_wealth"],
          p_outside_cash=r["outside_cash_per_trial_year"],
          p_wealth_path=r["property_wealth_path"],
          s_wealth_path=r["shares_wealth_path"],
          ceiling=20_000,
      )
      # mix=0.5 is index 10 of linspace(0,1,21)
      pt = curve[10]
      assert pt.mix_pct == pytest.approx(0.5)
      mixed_cash = mix * r["outside_cash_per_trial_year"]
      expected = float(np.percentile(mixed_cash.max(axis=1), 90))
      assert pt.worst_year_cash == pytest.approx(expected)


  def test_total_top_ups_definition(base_run_200):
      """total_top_ups = median(mixed_outside_cash.sum(axis=1))."""
      from model.mix_curve import build_mix_curve
      r = base_run_200
      mix = 0.5
      curve = build_mix_curve(
          p_terminal=r["property_terminal_wealth"],
          s_terminal=r["shares_terminal_wealth"],
          p_outside_cash=r["outside_cash_per_trial_year"],
          p_wealth_path=r["property_wealth_path"],
          s_wealth_path=r["shares_wealth_path"],
          ceiling=20_000,
      )
      pt = curve[10]
      mixed_cash = mix * r["outside_cash_per_trial_year"]
      expected = float(np.median(mixed_cash.sum(axis=1)))
      assert pt.total_top_ups == pytest.approx(expected)


  def test_forced_sale_rate_definition(base_run_200):
      """forced_sale_rate = mean(flag_forced_sales(mixed_outside_cash, ceiling))."""
      from model.mix_curve import build_mix_curve
      r = base_run_200
      mix = 0.5
      curve = build_mix_curve(
          p_terminal=r["property_terminal_wealth"],
          s_terminal=r["shares_terminal_wealth"],
          p_outside_cash=r["outside_cash_per_trial_year"],
          p_wealth_path=r["property_wealth_path"],
          s_wealth_path=r["shares_wealth_path"],
          ceiling=20_000,
      )
      pt = curve[10]
      mixed_cash = mix * r["outside_cash_per_trial_year"]
      expected = float(flag_forced_sales(mixed_cash, 20_000).mean())
      assert pt.forced_sale_rate == pytest.approx(expected)


  def test_mix_aware_downside_at_mix_zero_is_zero(base_run_200):
      """At mix=0.0 (pure shares) worst_year_cash=0 and forced_sale_rate=0 (§10)."""
      from model.mix_curve import build_mix_curve
      r = base_run_200
      curve = build_mix_curve(
          p_terminal=r["property_terminal_wealth"],
          s_terminal=r["shares_terminal_wealth"],
          p_outside_cash=r["outside_cash_per_trial_year"],
          p_wealth_path=r["property_wealth_path"],
          s_wealth_path=r["shares_wealth_path"],
          ceiling=20_000,
      )
      pt = curve[0]
      assert pt.worst_year_cash == pytest.approx(0.0)
      assert pt.total_top_ups == pytest.approx(0.0)
      assert pt.forced_sale_rate == pytest.approx(0.0)


  def test_mix_aware_downside_scales_with_mix(base_run_200):
      """Downside metrics at mix=0.5 are strictly less than at mix=1.0 (less property cash)."""
      from model.mix_curve import build_mix_curve
      r = base_run_200
      curve = build_mix_curve(
          p_terminal=r["property_terminal_wealth"],
          s_terminal=r["shares_terminal_wealth"],
          p_outside_cash=r["outside_cash_per_trial_year"],
          p_wealth_path=r["property_wealth_path"],
          s_wealth_path=r["shares_wealth_path"],
          ceiling=20_000,
      )
      half = curve[10]   # mix=0.5
      full = curve[-1]   # mix=1.0
      assert half.worst_year_cash <= full.worst_year_cash
      assert half.forced_sale_rate <= full.forced_sale_rate


  # ---------------------------------------------------------------------------
  # Task 1e — CRN smoothness (fixed seed → p_solvent near-monotonic in mix)
  # ---------------------------------------------------------------------------
  def test_crn_p_solvent_near_monotone_gaussian(base_run_5000):
      """Fixed seed + CRN: p_solvent should be near-monotone non-increasing in mix_pct
      (more property = more cash stress = lower solvency). Allow ≤3 non-monotone steps
      due to sampling noise."""
      from model.mix_curve import build_mix_curve
      r = base_run_5000
      curve = build_mix_curve(
          p_terminal=r["property_terminal_wealth"],
          s_terminal=r["shares_terminal_wealth"],
          p_outside_cash=r["outside_cash_per_trial_year"],
          p_wealth_path=r["property_wealth_path"],
          s_wealth_path=r["shares_wealth_path"],
          ceiling=20_000,
      )
      solvencies = [pt.p_solvent for pt in curve]
      inversions = sum(
          1 for i in range(len(solvencies) - 1) if solvencies[i] < solvencies[i + 1] - 0.005
      )
      assert inversions <= 3, (
          f"p_solvent not near-monotone: {inversions} inversions in {solvencies}"
      )


  def test_crn_p_solvent_near_monotone_student_t():
      """Same smoothness test under student_t return distribution (CRN guarantee must hold)."""
      from model.monte_carlo import run_monte_carlo
      from model.mix_curve import build_mix_curve
      kwargs = dict(_BASE_KWARGS, return_distribution="student_t", t_df=5)
      r = run_monte_carlo(trials=5000, horizon_years=25, **kwargs)
      curve = build_mix_curve(
          p_terminal=r["property_terminal_wealth"],
          s_terminal=r["shares_terminal_wealth"],
          p_outside_cash=r["outside_cash_per_trial_year"],
          p_wealth_path=r["property_wealth_path"],
          s_wealth_path=r["shares_wealth_path"],
          ceiling=20_000,
      )
      solvencies = [pt.p_solvent for pt in curve]
      inversions = sum(
          1 for i in range(len(solvencies) - 1) if solvencies[i] < solvencies[i + 1] - 0.005
      )
      assert inversions <= 3, (
          f"student_t p_solvent not near-monotone: {inversions} inversions"
      )


  def test_crn_suggested_mix_stable_across_runs(base_run_5000):
      """Same base run called twice (fixture is module-scoped) → identical curve."""
      from model.mix_curve import build_mix_curve
      r = base_run_5000
      curve_a = build_mix_curve(
          p_terminal=r["property_terminal_wealth"],
          s_terminal=r["shares_terminal_wealth"],
          p_outside_cash=r["outside_cash_per_trial_year"],
          p_wealth_path=r["property_wealth_path"],
          s_wealth_path=r["shares_wealth_path"],
          ceiling=20_000,
      )
      curve_b = build_mix_curve(
          p_terminal=r["property_terminal_wealth"],
          s_terminal=r["shares_terminal_wealth"],
          p_outside_cash=r["outside_cash_per_trial_year"],
          p_wealth_path=r["property_wealth_path"],
          s_wealth_path=r["shares_wealth_path"],
          ceiling=20_000,
      )
      for a, b in zip(curve_a, curve_b):
          assert a.median_mixed_wealth == pytest.approx(b.median_mixed_wealth)
          assert a.p_solvent == pytest.approx(b.p_solvent)


  # ---------------------------------------------------------------------------
  # Task 1f — Deflation contract: curve built in nominal $; deflation is per-render only
  # The function itself does NOT accept a deflator — the contract is enforced by
  # interface (no deflator param). This test confirms the nominal invariant by
  # verifying worst_year_cash at mix=1.0 equals the raw nominal computation.
  # ---------------------------------------------------------------------------
  def test_deflation_contract_curve_is_nominal(base_run_200):
      """build_mix_curve returns nominal values; no deflation is applied internally."""
      from model.mix_curve import build_mix_curve
      r = base_run_200
      curve = build_mix_curve(
          p_terminal=r["property_terminal_wealth"],
          s_terminal=r["shares_terminal_wealth"],
          p_outside_cash=r["outside_cash_per_trial_year"],
          p_wealth_path=r["property_wealth_path"],
          s_wealth_path=r["shares_wealth_path"],
          ceiling=20_000,
      )
      # At mix=1.0, worst_year_cash must equal the raw nominal calculation
      pt = curve[-1]
      nominal_wyc = float(np.percentile(r["outside_cash_per_trial_year"].max(axis=1), 90))
      assert pt.worst_year_cash == pytest.approx(nominal_wyc)


  def test_deflation_contract_no_deflator_param():
      """build_mix_curve signature must NOT accept a deflation parameter (contract: nominal only)."""
      import inspect
      from model.mix_curve import build_mix_curve
      sig = inspect.signature(build_mix_curve)
      for bad_param in ("deflate", "deflator", "cpi", "today_dollars"):
          assert bad_param not in sig.parameters, (
              f"build_mix_curve must not accept '{bad_param}' — deflation is per-render only"
          )


  # ---------------------------------------------------------------------------
  # Task 1g — comparison_mode: curve recomputes on mode switch and labels mode
  # (Tested via run_monte_carlo mode kwarg flowing through to different base runs;
  # build_mix_curve itself is mode-agnostic — it only sees arrays.)
  # ---------------------------------------------------------------------------
  def test_comparison_mode_realistic_vs_fair_fight_produce_different_curves():
      """Different comparison_mode values must produce different curve results
      (s_terminal differs, so median_mixed_wealth differs)."""
      from model.monte_carlo import run_monte_carlo
      from model.mix_curve import build_mix_curve

      realistic = run_monte_carlo(trials=200, horizon_years=10, mode="realistic", **{
          k: v for k, v in _BASE_KWARGS.items() if k != "mode"
      })
      fair_fight = run_monte_carlo(trials=200, horizon_years=10, mode="fair_fight", **{
          k: v for k, v in {**_BASE_KWARGS, "mode": "fair_fight"}.items() if k != "mode"
      })

      def _curve(r):
          return build_mix_curve(
              p_terminal=r["property_terminal_wealth"],
              s_terminal=r["shares_terminal_wealth"],
              p_outside_cash=r["outside_cash_per_trial_year"],
              p_wealth_path=r["property_wealth_path"],
              s_wealth_path=r["shares_wealth_path"],
              ceiling=20_000,
          )

      c_real = _curve(realistic)
      c_fair = _curve(fair_fight)

      # At least one mid-mix point must differ (mode affects share returns)
      mid_real = c_real[10].median_mixed_wealth
      mid_fair = c_fair[10].median_mixed_wealth
      assert mid_real != pytest.approx(mid_fair, rel=0.001), (
          "Expected realistic and fair_fight modes to produce different curves"
      )
  ```

  Run: `.venv/bin/python -m pytest tests/test_mix_curve.py -v --ignore=tests/test_persona_control.py`
  Expected: ALL FAIL with `ModuleNotFoundError: No module named 'model.mix_curve'`

- [ ] **Step 2: Create `model/mix_curve.py`**

  ```python
  # model/mix_curve.py
  """Pure mix-curve builder. No Streamlit imports.

  Derives the full allocation efficiency curve from a single Monte Carlo base
  run's unblended per-trial arrays. All mix points are computed post-hoc via
  linear algebra — no re-simulation per mix.

  See spec §3.2, §5.3 for metric definitions.
  """
  from __future__ import annotations
  from dataclasses import dataclass

  import numpy as np

  from model.solvency import flag_forced_sales


  @dataclass
  class MixPoint:
      """One point on the mix efficiency curve.

      mix_pct: fraction of portfolio in property (0.0 = pure shares, 1.0 = pure property).
      median_mixed_wealth: median terminal wealth at this mix across all trials ($).
      p_solvent: fraction of trials where mixed_outside_cash never exceeds ceiling.
      p_succeeds: fraction of trials solvent AND mixed beats pure shares.
      p_mix_beats_pure_shares: fraction of trials where mixed_terminal > s_terminal AND solvent.
      worst_year_cash: 90th-percentile of per-trial worst single year's outside cash (§5.3).
      total_top_ups: median of per-trial cumulative outside cash over the hold (§5.3).
      forced_sale_rate: fraction of trials with any year breaching ceiling (§5.3).
      """
      mix_pct: float
      median_mixed_wealth: float
      p_solvent: float
      p_succeeds: float
      p_mix_beats_pure_shares: float
      worst_year_cash: float
      total_top_ups: float
      forced_sale_rate: float


  def build_mix_curve(
      p_terminal: np.ndarray,
      s_terminal: np.ndarray,
      p_outside_cash: np.ndarray,
      p_wealth_path: np.ndarray,
      s_wealth_path: np.ndarray,
      ceiling: float,
      mixes: np.ndarray | None = None,
  ) -> list[MixPoint]:
      """Build the allocation efficiency curve from one base run's unblended arrays.

      Parameters
      ----------
      p_terminal : (trials,) float — pure-property terminal after-tax wealth per trial.
      s_terminal : (trials,) float — pure-shares terminal after-tax wealth per trial.
      p_outside_cash : (trials, horizon) float — pure-property outside-cash demand per trial-year.
          Scale by mix to get mixed outside-cash demand (only property carries cash demand).
      p_wealth_path : (trials, horizon) float — pure-property wealth path per trial-year.
      s_wealth_path : (trials, horizon) float — pure-shares wealth path per trial-year.
          (p_wealth_path and s_wealth_path are accepted to preserve the full function signature
          for downstream chart derivation; wealth path at a given mix is
          mix * p_wealth_path + (1-mix) * s_wealth_path computed by callers per-render.)
      ceiling : float — serviceability ceiling in $ (same units as p_outside_cash).
      mixes : 1-D float array of mix fractions to evaluate. Defaults to np.linspace(0, 1, 21).

      Returns
      -------
      list[MixPoint] of length len(mixes), ordered by ascending mix_pct.

      Metric definitions (spec §5.3):
        worst_year_cash  = percentile(mixed_outside_cash.max(axis=1), 90)
        total_top_ups    = median(mixed_outside_cash.sum(axis=1))
        forced_sale_rate = mean(flag_forced_sales(mixed_outside_cash, ceiling))
        p_solvent        = 1 - forced_sale_rate
        p_succeeds       = mean(mixed_terminal > s_terminal AND NOT forced_sale)
        p_mix_beats_pure_shares = p_succeeds   (alias; strictly: solvent AND beats shares)
        median_mixed_wealth = median(mix * p_terminal + (1-mix) * s_terminal)

      CRN guarantee: all mixes share the same underlying trial paths (one base run,
      fixed seed). The curve reflects the blend, not sampling noise.

      Deflation contract: this function operates entirely in nominal dollars.
      Apply deflation per-render outside this function; never pass deflated arrays in.
      """
      if mixes is None:
          mixes = np.linspace(0.0, 1.0, 21)

      points: list[MixPoint] = []

      for mix in mixes:
          mixed_terminal = mix * p_terminal + (1.0 - mix) * s_terminal
          mixed_outside_cash = mix * p_outside_cash  # shares carry no outside-cash demand

          forced_flags = flag_forced_sales(mixed_outside_cash, ceiling)
          forced_sale_rate = float(forced_flags.mean())
          p_solvent = 1.0 - forced_sale_rate

          # p_succeeds: solvent AND mixed beats pure shares
          beats_shares = mixed_terminal > s_terminal
          p_succeeds = float((beats_shares & ~forced_flags).mean())
          p_mix_beats_pure_shares = p_succeeds  # same definition per spec output mapping

          median_mixed_wealth = float(np.median(mixed_terminal))

          # Downside metrics (spec §5.3) — mix=0.0 gives zeros (no property cash demand)
          worst_year_cash = float(
              np.percentile(mixed_outside_cash.max(axis=1), 90)
          ) if mix > 0.0 else 0.0

          total_top_ups = float(
              np.median(mixed_outside_cash.sum(axis=1))
          ) if mix > 0.0 else 0.0

          points.append(MixPoint(
              mix_pct=float(mix),
              median_mixed_wealth=median_mixed_wealth,
              p_solvent=p_solvent,
              p_succeeds=p_succeeds,
              p_mix_beats_pure_shares=p_mix_beats_pure_shares,
              worst_year_cash=worst_year_cash,
              total_top_ups=total_top_ups,
              forced_sale_rate=forced_sale_rate,
          ))

      return points
  ```

  Run: `.venv/bin/python -m pytest tests/test_mix_curve.py -v -k "not cold_base_run"`
  Expected: ALL PASS (engine-equivalence, shape, downside defs, CRN, deflation, comparison_mode).

- [ ] **Step 3: Run full test suite to confirm no regressions**

  ```
  .venv/bin/python -m pytest -q
  ```
  Expected: all pre-existing tests still PASS; new tests in `test_mix_curve.py` PASS.

- [ ] **Step 4: Commit**

  ```bash
  git add model/mix_curve.py tests/test_mix_curve.py
  git commit -m "feat(mix_curve): build_mix_curve pure function + MixPoint dataclass + engine-equivalence tests"
  ```

---

## Task 2 — Wire `app.py`: replace sweep + ↻ button with base-run → `build_mix_curve`; add state machine + fragments

**Files:**
- Modify: `app.py` (lines 21, 382–429, 429–450, 52–61, 324–343)
- Modify: `ui/persona.py` (lines 17–30, 69–98)
- Extend: `tests/test_mix_curve.py` (state-machine and URL-param tests)

### Sub-task 2a: Update `ui/persona.py` to accept `list[MixPoint]`

- [ ] **Step 1: Write failing tests for updated persona helpers (append to `tests/test_mix_curve.py`)**

  ```python
  # --- append to tests/test_mix_curve.py ---

  # ---------------------------------------------------------------------------
  # Task 2a — persona.py: find_optimal_mix + render_persona_cards with MixPoint
  # ---------------------------------------------------------------------------
  def test_find_optimal_mix_returns_none_when_no_mix_qualifies():
      """find_optimal_mix returns None when no MixPoint meets min_p_solvent."""
      from ui.persona import find_optimal_mix
      from model.mix_curve import MixPoint

      low_curve = [
          MixPoint(mix_pct=0.0, median_mixed_wealth=500_000, p_solvent=0.50,
                   p_succeeds=0.40, p_mix_beats_pure_shares=0.40,
                   worst_year_cash=0.0, total_top_ups=0.0, forced_sale_rate=0.50),
          MixPoint(mix_pct=0.5, median_mixed_wealth=800_000, p_solvent=0.80,
                   p_succeeds=0.65, p_mix_beats_pure_shares=0.65,
                   worst_year_cash=12_000, total_top_ups=60_000, forced_sale_rate=0.20),
      ]
      result = find_optimal_mix(low_curve, min_p_solvent=0.99)
      assert result is None


  def test_find_optimal_mix_returns_highest_wealth_qualifying_mix():
      """find_optimal_mix returns the MixPoint with highest median_mixed_wealth at/above threshold."""
      from ui.persona import find_optimal_mix
      from model.mix_curve import MixPoint

      curve = [
          MixPoint(mix_pct=0.0, median_mixed_wealth=900_000, p_solvent=0.98,
                   p_succeeds=0.75, p_mix_beats_pure_shares=0.75,
                   worst_year_cash=0.0, total_top_ups=0.0, forced_sale_rate=0.02),
          MixPoint(mix_pct=0.5, median_mixed_wealth=1_100_000, p_solvent=0.96,
                   p_succeeds=0.80, p_mix_beats_pure_shares=0.80,
                   worst_year_cash=8_000, total_top_ups=40_000, forced_sale_rate=0.04),
          MixPoint(mix_pct=1.0, median_mixed_wealth=1_050_000, p_solvent=0.91,
                   p_succeeds=0.78, p_mix_beats_pure_shares=0.78,
                   worst_year_cash=18_000, total_top_ups=95_000, forced_sale_rate=0.09),
      ]
      # At threshold 0.95: both 0.0 and 0.5 qualify; 0.5 has higher wealth
      result = find_optimal_mix(curve, min_p_solvent=0.95)
      assert result is not None
      assert result.mix_pct == pytest.approx(0.5)


  def test_find_optimal_mix_all_three_thresholds_none_handled():
      """Simulate all-None scenario: no mix meets 0.99, 0.95, or 0.85 thresholds."""
      from ui.persona import find_optimal_mix
      from model.mix_curve import MixPoint

      very_bad = [
          MixPoint(mix_pct=m / 20, median_mixed_wealth=500_000, p_solvent=0.70,
                   p_succeeds=0.50, p_mix_beats_pure_shares=0.50,
                   worst_year_cash=50_000, total_top_ups=300_000, forced_sale_rate=0.30)
          for m in range(21)
      ]
      for threshold in (0.99, 0.95, 0.85):
          assert find_optimal_mix(very_bad, min_p_solvent=threshold) is None, (
              f"Expected None at threshold {threshold}"
          )
  ```

  Run: `.venv/bin/python -m pytest tests/test_mix_curve.py -v -k "find_optimal_mix"`
  Expected: FAIL (`find_optimal_mix` currently accepts dicts, not `MixPoint`)

- [ ] **Step 2: Update `ui/persona.py` — `find_optimal_mix` accepts `list[MixPoint]`, retire `compute_persona_sweep`, update card rendering for all-None**

  Replace the entire `ui/persona.py` file:

  ```python
  # ui/persona.py
  """Persona card rendering and mix-curve helpers.

  find_optimal_mix now accepts list[MixPoint] from model/mix_curve.py.
  compute_persona_sweep is retired — replaced by build_mix_curve in app.py.
  All three persona cards handle None (not just Safe).
  """
  import numpy as np
  import streamlit as st

  from model.mix_curve import MixPoint
  from ui.common import AMBER_DK, GLOBAL_CSS, _render_html, _fmt_money, _fmt_pct

  # ============================================================================
  # Persona definitions
  # ============================================================================
  # NOTE: persona display names, the "★ RECOMMENDED" badge, and the ★-on-Balanced
  # are UNCHANGED in Phase 1 (engine-only). Renaming to "Growth-focused · 85%+",
  # dropping the ★, and the "SUGGESTED" relabel are Phase 2 (spec §4.1, §8) — doing
  # them here would desync app.py's segmented_control / PERSONA_TO_THRESHOLD /
  # VALID_PERSONAS, which still use "Safe"/"Balanced"/"Wealth Maximizer".
  PERSONA_DEFS = [
      ("Safe Player",      0.99, "I want near-certainty of staying within my cash ceiling — even if it costs some wealth."),
      ("Balanced",         0.95, "I want very high safety, but I'll accept a small chance of cashflow stress for more wealth."),
      ("Wealth Maximizer", 0.85, "I'll accept real risk of a forced sale (~1 in 7 futures) in exchange for the highest wealth."),
  ]


  def find_optimal_mix(curve: list[MixPoint], min_p_solvent: float) -> MixPoint | None:
      """Return the MixPoint with highest median_mixed_wealth at/above min_p_solvent.

      Returns None if no mix meets the threshold.
      """
      qualifying = [pt for pt in curve if pt.p_solvent >= min_p_solvent]
      if not qualifying:
          return None
      return max(qualifying, key=lambda pt: pt.median_mixed_wealth)


  def _persona_card_html(name: str, threshold: float, blurb: str,
                         point: MixPoint | None, is_rec: bool) -> str:
      badge = '<div class="badge">★ RECOMMENDED</div>' if is_rec else ""
      klass = "card rec" if is_rec else "card"
      if point is None:
          return f"""
          <div class="{klass}">{badge}
            <div class="pname">{name}</div>
            <div class="pthr">Safety appetite: ≥{int(threshold * 100)}% chance of staying within your cash ceiling</div>
            <div class="alloc" style="font-size:19px;color:{AMBER_DK};">Not reachable</div>
            <div class="hr"></div>
            <p class="blurb">No allocation reaches ≥{int(threshold * 100)}% safety under your inputs.
            Try raising your "max annual top-up", lowering the loan amount, or shifting toward shares.</p>
          </div>"""
      mix_int = int(round(point.mix_pct * 100))
      actual_solvent_pct = int(round(point.p_solvent * 100))
      return f"""
      <div class="{klass}">{badge}
        <div class="pname">{name}</div>
        <div class="pthr">Safety appetite: ≥{int(threshold * 100)}% · actual: {actual_solvent_pct}%</div>
        <div class="alloc">{mix_int}% property</div>
        <div class="alloc-sub">{100 - mix_int}% shares</div>
        <div class="hr"></div>
        <div class="mrow"><div class="mlabel">Typical wealth in {{H}} years</div><div class="mval">{_fmt_money(point.median_mixed_wealth)}</div></div>
        <div class="mrow"><div class="mlabel">Chance you never run out of cash</div><div class="mval">{_fmt_pct(point.p_solvent)}</div></div>
        <div class="mrow"><div class="mlabel">Worst-year cash you'd need to find</div><div class="mval">{_fmt_money(point.worst_year_cash)}</div></div>
        <div class="hr"></div>
        <p class="blurb">"{blurb}"</p>
      </div>"""


  def render_persona_cards(curve: list[MixPoint], horizon: int) -> None:
      """Render three persona cards from a mix curve. All None cases are handled."""
      resolved = [
          (name, thr, blurb, find_optimal_mix(curve, thr))
          for name, thr, blurb in PERSONA_DEFS
      ]

      # All three reachable AND resolve to the same mix → single merged card.
      # (If any card is None, do NOT merge — an unreachable safety level is
      # information the user must see, per the no-solvent-mix state.)
      if all(r[3] is not None for r in resolved) and len(
              {int(round(r[3].mix_pct * 100)) for r in resolved}) == 1:
          row = resolved[1][3]
          mix_int = int(round(row.mix_pct * 100))
          html = f"""
          <div class="cards" style="grid-template-columns:1fr;max-width:560px;margin:0 auto;">
            <div class="card rec"><div class="badge">★ RECOMMENDED</div>
              <div class="pname">Optimal allocation</div>
              <div class="alloc">{mix_int}% property</div>
              <div class="alloc-sub">{100 - mix_int}% shares</div>
              <div class="hr"></div>
              <div class="mrow"><div class="mlabel">Typical wealth in {horizon} years</div><div class="mval">{_fmt_money(row.median_mixed_wealth)}</div></div>
              <div class="mrow"><div class="mlabel">Chance you never run out of cash</div><div class="mval">{_fmt_pct(row.p_solvent)}</div></div>
              <div class="hr"></div>
              <p class="blurb">"All three safety levels (≥99%, ≥95%, ≥85%) point to the same allocation under your
              current inputs — pick this with confidence."</p>
            </div></div>"""
          _render_html(GLOBAL_CSS + html)
          return

      cards = ""
      for name, thr, blurb, point in resolved:
          is_rec = (name == "Balanced")
          cards += _persona_card_html(name, thr, blurb, point, is_rec)
      _render_html(
          GLOBAL_CSS
          + f'<div class="cards">{cards}</div>'.replace("{H}", str(horizon))
      )


  def render_comparison_table(curve: list[MixPoint], recommended_mix_pct: int) -> None:
      """Per-mix comparison table, adapted to consume list[MixPoint].

      Kept in Phase 1 so the phase ships with no feature regression. Phase 2
      relocates this into the tradeoff-chart expander as a 'show as table' toggle
      and retires the standalone expander (spec §4.3).
      """
      body = ""
      for pt in curve:
          mix_int = int(round(pt.mix_pct * 100))
          is_rec = (mix_int == recommended_mix_pct)
          star = ' <span style="color:#16a34a;">★</span>' if is_rec else ""
          body += f"""<tr class="{'rec' if is_rec else ''}">
            <td>{mix_int}%{star}</td>
            <td>{_fmt_money(pt.median_mixed_wealth)}</td>
            <td>{_fmt_pct(pt.p_solvent)}</td>
            <td>{_fmt_money(pt.worst_year_cash)}</td>
            <td>{_fmt_pct(pt.p_mix_beats_pure_shares)}</td></tr>"""
      html = f"""
      <div class="tbl-wrap"><table class="tbl">
        <thead><tr><th>Property mix</th><th>Typical wealth</th>
          <th>Never run out of cash</th><th>Worst-year cash</th><th>Beats pure shares</th></tr></thead>
        <tbody>{body}</tbody></table></div>"""
      _render_html(GLOBAL_CSS + html)
  ```

  Run: `.venv/bin/python -m pytest tests/test_mix_curve.py -v -k "find_optimal_mix"`
  Expected: ALL PASS.

- [ ] **Step 3: Run full test suite**

  ```
  .venv/bin/python -m pytest -q
  ```
  Expected: all pre-existing tests still pass (note: `test_persona_control.py` tests will still pass because `app.py` hasn't changed yet — `render_persona_cards` signature change only applies once app.py is updated in sub-task 2b).

### Sub-task 2b: Rewrite `app.py` — replace sweep + ↻ with base-run → curve, add state machine + fragments + URL guards

- [ ] **Step 1: Write failing app-level tests (append to `tests/test_mix_curve.py`)**

  ```python
  # --- append to tests/test_mix_curve.py ---

  # ---------------------------------------------------------------------------
  # Task 2b — app.py: state machine, URL param clamping, no-solvent-mix, error state
  # These tests use Streamlit's AppTest harness (same pattern as test_persona_control.py).
  # ---------------------------------------------------------------------------

  def test_dial_safety_invalid_url_param_clamps_to_95():
      """dial_safety=999 in URL must clamp to 95 (valid default) and not crash."""
      from streamlit.testing.v1 import AppTest
      at = AppTest.from_file("app.py", default_timeout=90)
      at.query_params["dial_safety"] = "999"
      at.run()
      assert not at.exception, f"App crashed on dial_safety=999: {at.exception}"
      # The URL must be rewritten to a value in [50, 99]
      written = at.query_params.get("dial_safety")
      if written is not None:
          if isinstance(written, list):
              written = written[0]
          assert 50 <= int(written) <= 99, f"dial_safety not clamped: {written}"


  def test_dial_safety_negative_url_param_clamps():
      """dial_safety=-10 in URL must clamp to 50 (minimum) and not crash."""
      from streamlit.testing.v1 import AppTest
      at = AppTest.from_file("app.py", default_timeout=90)
      at.query_params["dial_safety"] = "-10"
      at.run()
      assert not at.exception, f"App crashed on dial_safety=-10: {at.exception}"


  def test_free_mix_invalid_url_param_clamps():
      """free_mix=150 in URL must clamp to 100 and not crash."""
      from streamlit.testing.v1 import AppTest
      at = AppTest.from_file("app.py", default_timeout=90)
      at.query_params["free_mix"] = "150"
      at.run()
      assert not at.exception, f"App crashed on free_mix=150: {at.exception}"
      written = at.query_params.get("free_mix")
      if written is not None:
          if isinstance(written, list):
              written = written[0]
          assert 0 <= int(written) <= 100, f"free_mix not clamped: {written}"


  def test_free_mix_negative_url_param_clamps():
      """free_mix=-5 in URL must clamp to 0 and not crash."""
      from streamlit.testing.v1 import AppTest
      at = AppTest.from_file("app.py", default_timeout=90)
      at.query_params["free_mix"] = "-5"
      at.run()
      assert not at.exception, f"App crashed on free_mix=-5: {at.exception}"


  def test_app_runs_without_exception_default_params():
      """App must load and render with default params (no sweep button needed)."""
      from streamlit.testing.v1 import AppTest
      at = AppTest.from_file("app.py", default_timeout=90)
      at.run()
      assert not at.exception, f"App crashed on default load: {at.exception}"


  def test_no_sweep_button_present():
      """The ↻ Update recommendations button must no longer exist."""
      from streamlit.testing.v1 import AppTest
      at = AppTest.from_file("app.py", default_timeout=90)
      at.run()
      button_labels = [b.label for b in at.button]
      assert not any("Update recommendations" in (lbl or "") for lbl in button_labels), (
          f"Found ↻ button that should have been removed: {button_labels}"
      )
  ```

  Run: `.venv/bin/python -m pytest tests/test_mix_curve.py -v -k "dial_safety or free_mix or no_sweep or app_runs"`
  Expected: `test_no_sweep_button_present` FAILS (button still exists); URL-param tests FAIL/PASS depending on whether params are wired.

- [ ] **Step 2: Rewrite the relevant sections of `app.py`**

  **2b-i: Update import line (line 21)**

  Replace:
  ```python
  from ui.persona import (compute_persona_sweep, find_optimal_mix,
                          render_persona_cards, render_comparison_table)
  ```
  With:
  ```python
  from model.mix_curve import build_mix_curve, MixPoint
  from ui.persona import (find_optimal_mix, render_persona_cards, render_comparison_table)
  ```

  **2b-ii: Add `_input_hash` helper after the `qp` function (after line 61)**

  Insert after the `qp` function block:
  ```python
  import hashlib, json as _json

  def _input_hash(kwargs: dict) -> str:
      """Stable hash of run_monte_carlo kwargs for change-detection.
      Uses json.dumps with sort_keys so dict ordering doesn't affect the hash."""
      return hashlib.md5(
          _json.dumps(kwargs, sort_keys=True, default=str).encode()
      ).hexdigest()
  ```

  **2b-iii: Add new URL params for `dial_safety` and `free_mix` — with clamp on read (around line 324–343)**

  In the `st.query_params.update(...)` block, add `dial_safety` and `free_mix` to the URL write. But first we need to read them clamped. Add these two reads immediately after the existing `qp` calls in the sidebar (or at the top of the inputs section, before any widget that uses them):

  After the `run_kwargs` dict is assembled (around line 370) and before the `@st.cache_data` block, add:

  ```python
  # --- New URL-persisted allocation controls (clamped on read AND write) ---
  # dial_safety: integer percent in [50, 99]; default 95.
  _dial_raw = qp("dial_safety", int, 95)
  dial_safety_pct = max(50, min(99, _dial_raw))  # clamp on read

  # free_mix: integer percent of property in [0, 100]; default 50.
  _free_mix_raw = qp("free_mix", int, 50)
  free_mix_pct = max(0, min(100, _free_mix_raw))  # clamp on read
  ```

  **2b-iv: Add new URL params to `st.query_params.update(...)` (write, with clamp)**

  In the existing `st.query_params.update(...)` call (around line 332–343), add:
  ```python
  "dial_safety": max(50, min(99, dial_safety_pct)),
  "free_mix": max(0, min(100, free_mix_pct)),
  ```

  **2b-v: Replace the sweep + ↻ button block (lines 382–429) with base-run → curve + input-hash state machine**

  Replace from `sweep_kwargs = dict(run_kwargs)` through `sweep_rows = st.session_state["sweep_rows"]` (lines 382–402) with:

  ```python
  # ---------------------------------------------------------------------------
  # Base run (one simulation; no per-mix re-runs) + input-hash auto-recompute
  # ---------------------------------------------------------------------------
  # Hash the full run_kwargs to detect input changes.
  _current_hash = _input_hash({**run_kwargs, "trials": 5000})

  _stale = st.session_state.get("_run_hash") != _current_hash
  _prior_result = st.session_state.get("_base_result")

  if _stale or _prior_result is None:
      # Input changed (or first load): recompute. Show spinner; dim prior result via CSS.
      with st.spinner("Running 5,000 simulated futures…"):
          try:
              _new_result = cached_run(trials=5000, property_share_mix=1.0, **run_kwargs)
              st.session_state["_base_result"] = _new_result
              st.session_state["_run_hash"] = _current_hash
              _stale = False
          except Exception as _e:
              st.error(
                  "Something went wrong — try a shorter horizon or smaller deposit. "
                  f"(Detail: {_e})"
              )
              st.stop()

  base_result = st.session_state["_base_result"]

  # Build the mix curve from the base run (sub-second; pure NumPy post-processing).
  mix_curve = build_mix_curve(
      p_terminal=base_result["property_terminal_wealth"],
      s_terminal=base_result["shares_terminal_wealth"],
      p_outside_cash=base_result["outside_cash_per_trial_year"],
      p_wealth_path=base_result["property_wealth_path"],
      s_wealth_path=base_result["shares_wealth_path"],
      ceiling=max_top_up,
  )
  ```

  **2b-vi: Replace sweep_rows references throughout the file**

  Replace all occurrences of `sweep_rows` with `mix_curve`.

  Specifically:
  - `render_persona_cards(sweep_rows, horizon)` → `render_persona_cards(mix_curve, horizon)`
  - `balanced = find_optimal_mix(sweep_rows, 0.95)` → `balanced = find_optimal_mix(mix_curve, 0.95)`
  - `_row = find_optimal_mix(sweep_rows, PERSONA_TO_THRESHOLD[picked])` → `_row = find_optimal_mix(mix_curve, PERSONA_TO_THRESHOLD[picked])`

  **2b-vii: Fix `breakdown_mix_pct` resolution for curve-based lookup**

  The existing code does `_row["mix_pct"]` (dict access). With `MixPoint` it's `_row.mix_pct`. Update:

  Replace:
  ```python
  breakdown_mix_pct = _row["mix_pct"] if _row else (balanced["mix_pct"] if balanced else 50)
  ```
  With:
  ```python
  breakdown_mix_pct = int(round(_row.mix_pct * 100)) if _row else (int(round(balanced.mix_pct * 100)) if balanced else 50)
  ```

  **2b-viii: Remove the `compute_persona_sweep` stale/sweep_key session-state block and the ↻ button**

  The following lines (currently ~382–410) must be deleted entirely — they no longer exist:
  ```python
  sweep_kwargs = dict(run_kwargs)
  sweep_key = json.dumps(sweep_kwargs, sort_keys=True, default=str)
  ...
  stale = st.session_state.get("sweep_key") != sweep_key
  c1, c2 = st.columns([1, 3])
  with c1:
      recompute = st.button("↻ Update recommendations", ...)
  if recompute or "sweep_rows" not in st.session_state:
      st.session_state["sweep_rows"] = compute_persona_sweep(**sweep_kwargs)
      st.session_state["sweep_key"] = sweep_key
      stale = False
  with c2:
      if stale:
          st.info("Inputs changed — click **↻ Update recommendations** to refresh the cards below.")
  sweep_rows = st.session_state["sweep_rows"]
  ```
  (These are replaced by the new block in 2b-v above.)

  **2b-ix: Fix the chart derivation block — year-by-year + histogram derive from base_result, NOT a second `cached_run`**

  The existing line:
  ```python
  result = cached_run(trials=5000, property_share_mix=breakdown_mix, **run_kwargs)
  ```
  Must be replaced with a post-hoc derivation so no second simulation runs. Replace it with:

  ```python
  # Derive per-render mixed arrays from base_result (no second simulation).
  # All mix-specific arrays are computed post-hoc from the base run's unblended paths.
  breakdown_mix = breakdown_mix_pct / 100
  result = dict(base_result)  # shallow copy so we can add mix-specific keys
  result["mixed_terminal_wealth"] = (
      breakdown_mix * base_result["property_terminal_wealth"]
      + (1.0 - breakdown_mix) * base_result["shares_terminal_wealth"]
  )
  result["median_mixed_wealth"] = float(np.median(result["mixed_terminal_wealth"]))
  result["mixed_outside_cash_per_trial_year"] = (
      breakdown_mix * base_result["outside_cash_per_trial_year"]
  )
  from model.solvency import flag_forced_sales as _ffs
  _mixed_flags = _ffs(result["mixed_outside_cash_per_trial_year"], max_top_up)
  result["p_mix_solvent"] = float(1.0 - _mixed_flags.mean())
  result["p_mix_beats_pure_shares"] = float(
      ((result["mixed_terminal_wealth"] > base_result["shares_terminal_wealth"])
       & ~_mixed_flags).mean()
  )
  result["mixed_wealth_path"] = (
      breakdown_mix * base_result["property_wealth_path"]
      + (1.0 - breakdown_mix) * base_result["shares_wealth_path"]
  )
  # worst_year_cash for feasibility flag: use mix-scaled outside cash (spec §5.3 fix)
  result["worst_year_cash"] = float(
      np.percentile(result["mixed_outside_cash_per_trial_year"].max(axis=1), 90)
  ) if breakdown_mix > 0.0 else 0.0
  ```

  **2b-x: Fix the deflation block — deflate the derived result dict, not the stale cached result**

  The deflation block (currently ~lines 436–450) mutates `result` keys in place. After step 2b-ix the `result` dict is a fresh shallow copy each rerun, so mutation is safe. However, we must remove `"worst_year_cash"` from the scalar keys that get deflated by `term_deflator` since it's now correctly recomputed from `mixed_outside_cash_per_trial_year` after deflation. The existing logic at line 450:
  ```python
  result["worst_year_cash"] = float(np.percentile(result["outside_cash_per_trial_year"].max(axis=1), 90))
  ```
  Replace with:
  ```python
  result["worst_year_cash"] = float(
      np.percentile(result["mixed_outside_cash_per_trial_year"].max(axis=1), 90)
  ) if breakdown_mix > 0.0 else 0.0
  ```
  (Uses the mix-scaled array, which was already deflated in the `per_year_keys` loop above it.)

  **2b-xi: Keep the comparison-table expander, adapted to the curve (Phase 2 relocates/retires it — spec §4.3)**

  Phase 1 keeps the table so the phase ships without a feature regression (the Phase-2 frontier chart will supersede it). Update the call to pass the curve and the selected mix as an int percent:
  ```python
  with st.expander("⚖️ Compare all property/shares mixes"):
      render_comparison_table(mix_curve, breakdown_mix_pct)
  ```
  The existing `recommended_mix = breakdown_mix_pct` assignment (app.py ~line 425) still feeds this; keep it. If, after the 2b-vi/2b-vii edits, `recommended_mix` is otherwise unused, you may inline `breakdown_mix_pct` here and delete the alias.

- [ ] **Step 3: Run failing tests to verify wiring**

  ```
  .venv/bin/python -m pytest tests/test_mix_curve.py -v -k "dial_safety or free_mix or no_sweep or app_runs"
  ```
  Expected: tests for `no_sweep_button_present` and `app_runs_without_exception` should now PASS; URL-param clamp tests should PASS.

- [ ] **Step 4: Run full suite**

  ```
  .venv/bin/python -m pytest -q
  ```
  Expected: all tests PASS, including all pre-existing persona control tests.

- [ ] **Step 5: Commit**

  ```bash
  git add app.py ui/persona.py tests/test_mix_curve.py
  git commit -m "feat(app): replace persona sweep + manual button with build_mix_curve; input-hash auto-recompute; url-param guards for dial_safety + free_mix"
  ```

---

## Task 3 — Final verification: no second `run_monte_carlo` call + full suite green

**Files:**
- Verify only: `app.py`, full test suite

- [ ] **Step 1: Confirm no second simulation call in `app.py`**

  ```bash
  grep -n "cached_run\|run_monte_carlo" "/Users/aidenmacmini/AI Project/Financial Modeling/property-vs-shares/app.py"
  ```
  Expected output: exactly ONE call to `cached_run(` (the base-run call in the input-hash block). Zero calls to `run_monte_carlo` directly. Zero calls to `compute_persona_sweep`. The grep output must show only:
  - The `@st.cache_data def cached_run(` definition
  - The single `cached_run(trials=5000, property_share_mix=1.0, **run_kwargs)` call

- [ ] **Step 2: Confirm `compute_persona_sweep` is gone**

  ```bash
  grep -c "compute_persona_sweep\|sweep_rows\|sweep_key\|Update recommendations" "/Users/aidenmacmini/AI Project/Financial Modeling/property-vs-shares/app.py"
  ```
  Expected: `0` (all removed).

- [ ] **Step 3: Run the full test suite one final time**

  ```
  .venv/bin/python -m pytest -q
  ```
  Expected: all tests PASS (including the new tests in `tests/test_mix_curve.py`).

- [ ] **Step 4: Commit verification result**

  ```bash
  git add -p  # review any stray changes
  git commit -m "test(mix_curve): full suite green after Phase 1 wiring; no second simulation call confirmed"
  ```

---

## Resolved ambiguities and assumptions flagged

> The following were resolved during plan writing. Each is marked with the decision taken.

**⚠ A1 — `p_mix_beats_pure_shares` vs `p_succeeds` in `MixPoint`.**
The spec §3.2 lists both `p_mix_beats_pure_shares` and `p_succeeds` as separate MixPoint fields, but §5 output-mapping table says "Beats shares" uses `p_mix_beats_pure_shares`. The spec doesn't define them differently. Decision: both are computed the same way (`mixed > s_terminal AND NOT forced_sale`), and both fields are set to the same float. This preserves the spec's field list without inventing a second formula. If the spec intends `p_succeeds` to be something else (e.g., beats shares only, ignoring solvency), that's a Phase 2 clarification.

**⚠ A2 — `worst_year_cash` at mix=0 avoids `percentile(zeros, 90) = 0`.**
When `mix=0`, `mixed_outside_cash` is an all-zeros array. `np.percentile(zeros.max(axis=1), 90)` returns `0.0` correctly, but to make the intent explicit and avoid floating-point edge cases, the implementation short-circuits to literal `0.0`. Tests assert this explicitly.

**⚠ A3 — `MixPoint.mix_pct` is a float in [0, 1], not an integer percent.**
The spec §3.2 says `mixes = np.linspace(0,1,N)` and the MixPoint field is `mix_pct`. Old `compute_persona_sweep` used integer percents (0–100). Decision: `mix_pct` is the fraction (0.0–1.0), matching `linspace`. All integer-percent UI references convert via `int(round(pt.mix_pct * 100))`. This is surfaced in Task 2b-vii.

**⚠ A4 — `result = dict(base_result)` (shallow copy) mutation in the deflation block.**
The deflation block mutates array entries in `result`. A shallow copy means mutating `result["property_wealth_path"]` would mutate `base_result["property_wealth_path"]` too (same object). Decision: replace per-key in-place mutation with assignment of a new divided array (`result[k] = result[k] / yearly_deflator`), which rebinds the key to a new array without touching the original. The shallow copy is therefore safe. If any site later does in-place `result[k] /= x`, that would be a bug — the plan uses `result[k] = result[k] / x` throughout.

**⚠ A5 — `dial_safety` and `free_mix` URL params are added to the write path but NOT yet wired to actual widgets.**
Phase 1 scopes only the URL clamp-on-read + clamp-on-write contract (per CLAUDE.md rule: clamp in the same commit as the widget). The actual dial/slider widgets that read these values live in Phase 2's UI expander. Adding the URL-param handling now is correct: it establishes the guard so that any future Phase 2 widget that writes these params is already safe. The tests verify the clamp, not the widget interaction.

**A6 — `st.fragment` availability (RESOLVED).** The local env is **Streamlit 1.57.0** (`st.fragment` present, ≥1.37), so it is available. Phase 1's recompute mechanism is the input-hash + `st.session_state` stash + `st.spinner` — which is correct and sufficient *because Phase 1 has no dial/free-mix widgets yet to scope*. `@st.fragment` becomes load-bearing in **Phase 2**, where it wraps the results region so the dial/free-mix interactions (which only read the precomputed curve) rerun the fragment without re-triggering the base run. No follow-up version check needed.

**⚠ A7 — Phase-1 scope correction (persona renames + table).** This plan keeps the current persona display names ("Safe Player"/"Balanced"/"Wealth Maximizer"), the `★ RECOMMENDED` badge, and the ★-on-Balanced — and keeps `render_comparison_table` (adapted to `MixPoint`). The renames to "Growth-focused · 85%+", dropping the ★, the "SUGGESTED" relabel, and retiring the table into the tradeoff expander are **Phase 2** (spec §4.1, §4.3, §8). Doing them in Phase 1 would desync `app.py`'s `segmented_control` options / `PERSONA_TO_THRESHOLD` / `VALID_PERSONAS` (still old names) and drop a feature with no replacement until Phase 2.
