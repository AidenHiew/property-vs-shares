# tests/test_rental_yield_variance.py
"""Phase 1b — rent-level variance tests.

Invariants verified here:
  1. Byte-identical at sigma=0 (two runs, same seed).
  2. sigma>0 changes property_terminal_wealth (it is wired).
  3. Variance of per-year rent rises by >0% and <=35% with sigma=0.005.
  4. Yield deviation is negatively correlated with vacancy (design intent).
  5. Determinism: same seed, sigma>0 → identical results.
"""
import numpy as np
import pytest

# Base kwargs mirroring test_mix_curve.py pattern — small trials for speed.
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

# Slightly larger trial count for statistical tests so variance estimates are stable.
_STAT_TRIALS = 2000
_STAT_HORIZON = 10


# ---------------------------------------------------------------------------
# Test 1 — Byte-identical at sigma=0
# Two runs with rental_yield_sigma=0, same seed → array-equal.
# ---------------------------------------------------------------------------
def test_byte_identical_at_sigma_zero():
    """Two sigma=0 runs with same seed must produce identical property_terminal_wealth."""
    from model.monte_carlo import run_monte_carlo

    run_a = run_monte_carlo(trials=500, horizon_years=10, **_BASE_KWARGS)
    run_b = run_monte_carlo(trials=500, horizon_years=10, **_BASE_KWARGS)

    np.testing.assert_array_equal(
        run_a["property_terminal_wealth"],
        run_b["property_terminal_wealth"],
        err_msg="sigma=0 runs with same seed must be byte-identical",
    )
    np.testing.assert_array_equal(
        run_a["property_rent_path"],
        run_b["property_rent_path"],
        err_msg="p_rent_path must be byte-identical at sigma=0",
    )


# ---------------------------------------------------------------------------
# Test 2 — sigma>0 changes results
# ---------------------------------------------------------------------------
def test_sigma_nonzero_changes_terminal_wealth():
    """rental_yield_sigma=0.005 must produce different property_terminal_wealth from sigma=0."""
    from model.monte_carlo import run_monte_carlo

    run_sigma0 = run_monte_carlo(trials=500, horizon_years=10, **_BASE_KWARGS)
    run_sigma1 = run_monte_carlo(
        trials=500, horizon_years=10,
        **{**_BASE_KWARGS, "rental_yield_sigma": 0.005},
    )

    # Arrays must NOT be equal — sigma>0 must change the numbers.
    with pytest.raises(AssertionError):
        np.testing.assert_array_equal(
            run_sigma0["property_terminal_wealth"],
            run_sigma1["property_terminal_wealth"],
        )


# ---------------------------------------------------------------------------
# Test 3 — Variance bound (acceptance gate)
# With sigma=0.005, per-year rent variance increases by >0% and <=35%.
# ---------------------------------------------------------------------------
def test_variance_bound_sigma_0005():
    """sigma=0.005: rent variance rises >0% and <=35% vs sigma=0 across all trial-years."""
    from model.monte_carlo import run_monte_carlo

    run_sigma0 = run_monte_carlo(
        trials=_STAT_TRIALS, horizon_years=_STAT_HORIZON,
        **{**_BASE_KWARGS, "rental_yield_sigma": 0.0},
    )
    run_sigma1 = run_monte_carlo(
        trials=_STAT_TRIALS, horizon_years=_STAT_HORIZON,
        **{**_BASE_KWARGS, "rental_yield_sigma": 0.005},
    )

    # rent_path shape: (trials, horizon_years)
    rent0 = run_sigma0["property_rent_path"]
    rent1 = run_sigma1["property_rent_path"]

    # Variance per year, averaged across the horizon.
    var0 = np.mean(np.var(rent0, axis=0))
    var1 = np.mean(np.var(rent1, axis=0))

    var_ratio = var1 / var0
    assert var_ratio > 1.0, (
        f"Expected variance to increase with sigma=0.005, got ratio={var_ratio:.4f}"
    )
    assert var_ratio <= 1.35, (
        f"Variance ratio {var_ratio:.4f} exceeds 1.35 — yield drift too large"
    )


# ---------------------------------------------------------------------------
# Test 4 — Vacancy correlation sign (the design intent: RHO_YIELD_VACANCY = -0.5)
# The rent-level yield deviation shares the vacancy standard-normal draw with a
# negative loading, so higher vacancy ↔ lower yield. We isolate the yield signal by
# dividing the sigma>0 rent path by the sigma=0 rent path: with the same seed the
# property value path AND occupied weeks are identical across the two runs, so they
# cancel in the ratio, leaving yield_path / gross_yield. That ratio must be NEGATIVELY
# correlated with the per-trial-year vacancy_paths output.
# ---------------------------------------------------------------------------
def test_yield_negatively_correlated_with_vacancy():
    """Rent-level yield ratio (rent_sigma>0 / rent_sigma=0) must be negatively correlated
    with vacancy — the RHO_YIELD_VACANCY = -0.5 design intent, asserted not inspected."""
    from model.monte_carlo import run_monte_carlo

    run_sigma1 = run_monte_carlo(
        trials=_STAT_TRIALS, horizon_years=_STAT_HORIZON,
        **{**_BASE_KWARGS, "rental_yield_sigma": 0.005},
    )
    run_sigma0 = run_monte_carlo(
        trials=_STAT_TRIALS, horizon_years=_STAT_HORIZON,
        **{**_BASE_KWARGS, "rental_yield_sigma": 0.0},
    )

    rent1 = run_sigma1["property_rent_path"]   # (trials, horizon) — yield_path drives rent
    rent0 = run_sigma0["property_rent_path"]   # (trials, horizon) — scalar gross_yield
    vacancy = run_sigma1["vacancy_paths"]      # (trials, horizon) — same draw in both runs

    # Same seed → identical value path & occupied weeks; both cancel in the ratio, leaving
    # rent1 / rent0 == yield_path / gross_yield. Mask any zero-rent trial-year defensively.
    mask = rent0 > 0
    yield_ratio = rent1[mask] / rent0[mask]
    vac = vacancy[mask]

    corr = np.corrcoef(yield_ratio.ravel(), vac.ravel())[0, 1]
    assert corr < 0, (
        f"yield ratio (rent_sigma>0 / rent_sigma=0) must be negatively correlated with "
        f"vacancy (RHO_YIELD_VACANCY=-0.5), got corrcoef={corr:.4f}"
    )


# ---------------------------------------------------------------------------
# Test 5 — Determinism with sigma>0
# Same seed, sigma=0.005 → identical results on two runs.
# ---------------------------------------------------------------------------
def test_determinism_with_sigma_nonzero():
    """Same seed with rental_yield_sigma=0.005 must produce identical results."""
    from model.monte_carlo import run_monte_carlo

    kwargs = {**_BASE_KWARGS, "rental_yield_sigma": 0.005}

    run_a = run_monte_carlo(trials=200, horizon_years=10, **kwargs)
    run_b = run_monte_carlo(trials=200, horizon_years=10, **kwargs)

    np.testing.assert_array_equal(
        run_a["property_terminal_wealth"],
        run_b["property_terminal_wealth"],
        err_msg="sigma>0 runs with same seed must be deterministic",
    )
    np.testing.assert_array_equal(
        run_a["property_rent_path"],
        run_b["property_rent_path"],
        err_msg="p_rent_path must be deterministic at sigma>0",
    )
