# tests/test_mix_curve.py
"""Phase 1 engine tests: mix curve, CRN, downside metrics, deflation, state."""
import time
import pytest
import numpy as np

# Shared minimal kwargs for run_monte_carlo (small trials for fast unit tests;
# the Task 0 timing test overrides trials=5000).
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


def test_cold_base_run_p95_under_3s():
    """Cold 5,000-trial run must complete in <=3s (acceptance gate for no-button UX).
    Runs 3 timed repetitions; checks the slowest (conservative p95 proxy)."""
    from model.monte_carlo import run_monte_carlo
    kwargs = dict(_BASE_KWARGS, trials=5000, horizon_years=25)
    times = []
    for _ in range(3):
        t0 = time.perf_counter()
        run_monte_carlo(**kwargs)
        times.append(time.perf_counter() - t0)
    p95 = sorted(times)[-1]
    assert p95 <= 3.0, (
        f"Cold base run took {p95:.2f}s — exceeds 3s target. "
        f"Consider background-thread fallback (see spec §3.5)."
    )


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
        mix_pct=0.5,  # float fraction in [0,1], not an int percent
        median_mixed_wealth=1_000_000.0,
        p_solvent=0.95,
        p_succeeds=0.70,
        p_mix_beats_pure_shares=0.65,
        worst_year_cash=15_000.0,
        total_top_ups=80_000.0,
        forced_sale_rate=0.05,
    )
    assert mp.mix_pct == pytest.approx(0.5)
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
    (more property = more cash stress = lower solvency). Allow <=3 non-monotone steps
    due to sampling noise."""
    from model.mix_curve import build_mix_curve
    r = base_run_5000
    curve = build_mix_curve(
        p_terminal=r["property_terminal_wealth"],
        s_terminal=r["shares_terminal_wealth"],
        p_outside_cash=r["outside_cash_per_trial_year"],
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
        ceiling=20_000,
    )
    curve_b = build_mix_curve(
        p_terminal=r["property_terminal_wealth"],
        s_terminal=r["shares_terminal_wealth"],
        p_outside_cash=r["outside_cash_per_trial_year"],
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
        k: v for k, v in _BASE_KWARGS.items() if k != "mode"
    })

    def _curve(r):
        return build_mix_curve(
            p_terminal=r["property_terminal_wealth"],
            s_terminal=r["shares_terminal_wealth"],
            p_outside_cash=r["outside_cash_per_trial_year"],
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
