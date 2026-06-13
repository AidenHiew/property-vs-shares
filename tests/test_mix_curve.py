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
