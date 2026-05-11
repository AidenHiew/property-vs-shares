"""Monte Carlo tests."""
import pytest
import numpy as np
from model.monte_carlo import generate_correlated_paths


def test_generate_paths_shape():
    paths = generate_correlated_paths(
        trials=5000, horizon=25,
        property_mu=0.055, property_sigma=0.11,
        share_mu=0.085, share_sigma=0.15,
        correlation=0.3, seed=42,
    )
    assert paths["property_growth"].shape == (5000, 25)
    assert paths["share_return"].shape == (5000, 25)


def test_generate_paths_means_are_close_to_mu():
    paths = generate_correlated_paths(
        trials=5000, horizon=25,
        property_mu=0.055, property_sigma=0.11,
        share_mu=0.085, share_sigma=0.15,
        correlation=0.3, seed=42,
    )
    assert paths["property_growth"].mean() == pytest.approx(0.055, abs=0.005)
    assert paths["share_return"].mean() == pytest.approx(0.085, abs=0.005)


def test_correlation_close_to_target():
    paths = generate_correlated_paths(
        trials=5000, horizon=25,
        property_mu=0.055, property_sigma=0.11,
        share_mu=0.085, share_sigma=0.15,
        correlation=0.3, seed=42,
    )
    p_flat = paths["property_growth"].flatten()
    s_flat = paths["share_return"].flatten()
    empirical_corr = np.corrcoef(p_flat, s_flat)[0, 1]
    assert empirical_corr == pytest.approx(0.3, abs=0.05)


def test_seeded_reproducibility():
    paths_a = generate_correlated_paths(
        trials=100, horizon=10,
        property_mu=0.05, property_sigma=0.1,
        share_mu=0.08, share_sigma=0.15,
        correlation=0.3, seed=42,
    )
    paths_b = generate_correlated_paths(
        trials=100, horizon=10,
        property_mu=0.05, property_sigma=0.1,
        share_mu=0.08, share_sigma=0.15,
        correlation=0.3, seed=42,
    )
    np.testing.assert_array_equal(paths_a["property_growth"], paths_b["property_growth"])


from model.monte_carlo import run_monte_carlo


def test_run_monte_carlo_returns_distributions():
    """Smoke test: run 100 trials with default inputs and check output shape."""
    result = run_monte_carlo(
        trials=100, horizon_years=25,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=32_330, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04, vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.005,
        property_growth_mu=0.055, property_growth_sigma=0.11,
        share_return_mu=0.085, share_return_sigma=0.15,
        correlation=0.3,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age="established_post_2017", asset_type="house",
        depreciation_override=None,
        portfolio_profile="blended",
        mode="realistic",
        margin_loan_rate=0.075, isolate_asset_quality=False,
        mtr=0.37, cpi=0.025, drp=True, seed=42,
    )

    assert "property_terminal_wealth" in result
    assert "shares_terminal_wealth" in result
    assert result["property_terminal_wealth"].shape == (100,)
    assert result["shares_terminal_wealth"].shape == (100,)
    assert "p_property_wins" in result
    assert 0 <= result["p_property_wins"] <= 1


def test_run_monte_carlo_exposes_solvency_metrics():
    """Solvency metrics must flow through the runner output."""
    result = run_monte_carlo(
        trials=100, horizon_years=25,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=32_330, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04, vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.005,
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
    )
    assert "p_solvent" in result
    assert "forced_sale_flags" in result
    assert 0 <= result["p_solvent"] <= 1
    assert result["forced_sale_flags"].shape == (100,)
    assert result["forced_sale_flags"].dtype == bool
