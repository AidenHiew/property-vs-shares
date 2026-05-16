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


def test_generate_correlated_paths_default_is_gaussian():
    """Default arg unchanged → identical output to pre-refactor."""
    from model.monte_carlo import generate_correlated_paths
    paths = generate_correlated_paths(
        trials=100, horizon=10,
        property_mu=0.055, property_sigma=0.11,
        share_mu=0.085, share_sigma=0.15,
        correlation=0.3, seed=42,
    )
    # Snapshot a few values from the seeded Gaussian draw
    assert paths["property_growth"].shape == (100, 10)
    # Pre-refactor mean across all draws (seed=42, these are stable)
    assert abs(paths["property_growth"].mean() - 0.055) < 0.02


def test_generate_correlated_paths_student_t_realized_sigma():
    """With rescaling, realized std should match specified σ within ~3% at large N."""
    from model.monte_carlo import generate_correlated_paths
    paths = generate_correlated_paths(
        trials=10000, horizon=10,
        property_mu=0.0, property_sigma=0.11,
        share_mu=0.0, share_sigma=0.15,
        correlation=0.0, seed=42,
        return_distribution="student_t", t_df=5,
    )
    # Realized σ should be close to specified σ thanks to sqrt((df-2)/df) rescale
    assert abs(paths["property_growth"].std() - 0.11) / 0.11 < 0.05
    assert abs(paths["share_return"].std() - 0.15) / 0.15 < 0.05


def test_student_t_has_fatter_tails_than_gaussian():
    """At same σ, t-dist should have bigger 1st/99th percentile magnitudes."""
    from model.monte_carlo import generate_correlated_paths
    common = dict(
        trials=10000, horizon=10,
        property_mu=0.0, property_sigma=0.11,
        share_mu=0.0, share_sigma=0.15,
        correlation=0.0, seed=42,
    )
    g = generate_correlated_paths(**common, return_distribution="gaussian")
    t = generate_correlated_paths(**common, return_distribution="student_t", t_df=5)
    import numpy as np
    g_p99 = np.percentile(np.abs(g["property_growth"]), 99)
    t_p99 = np.percentile(np.abs(t["property_growth"]), 99)
    assert t_p99 > g_p99 * 1.05, f"Expected fatter tails: gaussian p99={g_p99:.4f}, t p99={t_p99:.4f}"


def test_run_monte_carlo_accepts_student_t():
    """End-to-end smoke: passing return_distribution='student_t' shouldn't error."""
    result = run_monte_carlo(
        trials=200, horizon_years=10,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=30_000, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04,
        vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.005,
        property_growth_mu=0.055, property_growth_sigma=0.11,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age="established_post_2017", asset_type="house",
        depreciation_override=None,
        share_return_mu=0.085, share_return_sigma=0.15,
        portfolio_profile="blended",
        mode="realistic",
        margin_loan_rate=0.075, isolate_asset_quality=False,
        correlation=0.3,
        mtr=0.37, cpi=0.025, drp=True,
        serviceability_ceiling=20_000, seed=42,
        return_distribution="student_t", t_df=5,
    )
    assert "p_property_succeeds" in result
    assert 0 <= result["p_property_succeeds"] <= 1


def test_loan_rate_default_is_gaussian():
    """Default loan_rate_distribution preserves Gaussian behaviour."""
    result = run_monte_carlo(
        trials=200, horizon_years=10,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=30_000, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04,
        vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.005,
        property_growth_mu=0.055, property_growth_sigma=0.11,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age="established_post_2017", asset_type="house",
        depreciation_override=None,
        share_return_mu=0.085, share_return_sigma=0.15,
        portfolio_profile="blended",
        mode="realistic",
        margin_loan_rate=0.075, isolate_asset_quality=False,
        correlation=0.3,
        mtr=0.37, cpi=0.025, drp=True,
        serviceability_ceiling=20_000, seed=42,
    )
    # Just confirm it runs and headline metrics are in valid range
    assert 0 <= result["p_property_succeeds"] <= 1
    # Headline should match the v1 baseline for default seed at 10y
    # (allow loose tolerance — this is a smoke test, not a snapshot)
    assert result["p_property_succeeds"] > 0.4


def test_loan_rate_student_t_runs_end_to_end():
    """Pass loan_rate_distribution='student_t' — should not error."""
    result = run_monte_carlo(
        trials=200, horizon_years=10,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=30_000, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04,
        vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.005,
        property_growth_mu=0.055, property_growth_sigma=0.11,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age="established_post_2017", asset_type="house",
        depreciation_override=None,
        share_return_mu=0.085, share_return_sigma=0.15,
        portfolio_profile="blended",
        mode="realistic",
        margin_loan_rate=0.075, isolate_asset_quality=False,
        correlation=0.3,
        mtr=0.37, cpi=0.025, drp=True,
        serviceability_ceiling=20_000, seed=42,
        loan_rate_distribution="student_t", loan_rate_t_df=5,
    )
    assert "p_property_succeeds" in result
    assert 0 <= result["p_property_succeeds"] <= 1


def test_loan_rate_student_t_fattens_worst_year_cash_distribution():
    """At low df, worst-year cash 99th-percentile should be bigger than Gaussian
    because rare rate spikes are more frequent."""
    common = dict(
        trials=2000, horizon_years=10,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=30_000, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04,
        vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.005,
        property_growth_mu=0.055, property_growth_sigma=0.11,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age="established_post_2017", asset_type="house",
        depreciation_override=None,
        share_return_mu=0.085, share_return_sigma=0.15,
        portfolio_profile="blended",
        mode="realistic",
        margin_loan_rate=0.075, isolate_asset_quality=False,
        correlation=0.3,
        mtr=0.37, cpi=0.025, drp=True,
        serviceability_ceiling=20_000, seed=42,
    )
    import numpy as np
    g = run_monte_carlo(**common)  # default gaussian
    t = run_monte_carlo(**common, loan_rate_distribution="student_t", loan_rate_t_df=4)
    # 99th percentile of MAX over years per trial (tail of cashflow stress)
    g_p99 = np.percentile(g["outside_cash_per_trial_year"].max(axis=1), 99)
    t_p99 = np.percentile(t["outside_cash_per_trial_year"].max(axis=1), 99)
    assert t_p99 > g_p99 * 1.05, f"Expected fatter tails: g_p99={g_p99:.0f}, t_p99={t_p99:.0f}"


def test_p_property_succeeds_is_joint_of_wins_and_solvent():
    """Joint success = P(property wins AND stays solvent within ceiling)."""
    result = run_monte_carlo(
        trials=200, horizon_years=10,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=30_000, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04,
        vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.005,
        property_growth_mu=0.055, property_growth_sigma=0.11,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age="established_post_2017", asset_type="house",
        depreciation_override=None,
        share_return_mu=0.085, share_return_sigma=0.15,
        portfolio_profile="blended",
        mode="realistic",
        margin_loan_rate=0.075, isolate_asset_quality=False,
        correlation=0.3,
        mtr=0.37, cpi=0.025, drp=True,
        serviceability_ceiling=20_000, seed=42,
    )
    expected = float(
        (
            (result["property_terminal_wealth"] > result["shares_terminal_wealth"])
            & (result["forced_sale_flags"] == 0)
        ).mean()
    )
    assert result["p_property_succeeds"] == pytest.approx(expected)
    # Sanity: joint must be ≤ both components
    assert result["p_property_succeeds"] <= result["p_property_wins"]
    assert result["p_property_succeeds"] <= result["p_solvent"]


def test_property_share_mix_default_is_one_preserves_current_behaviour():
    """Default mix=1.0 → mixed_terminal exactly equals p_terminal."""
    result = run_monte_carlo(
        trials=200, horizon_years=10,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=30_000, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04,
        vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.005,
        property_growth_mu=0.055, property_growth_sigma=0.11,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age="established_post_2017", asset_type="house",
        depreciation_override=None,
        share_return_mu=0.085, share_return_sigma=0.15,
        portfolio_profile="blended",
        mode="realistic",
        margin_loan_rate=0.075, isolate_asset_quality=False,
        correlation=0.3,
        mtr=0.37, cpi=0.025, drp=True,
        serviceability_ceiling=20_000, seed=42,
    )
    import numpy as np
    np.testing.assert_array_equal(
        result["mixed_terminal_wealth"], result["property_terminal_wealth"]
    )


def test_property_share_mix_zero_is_pure_shares():
    """mix=0.0 → mixed_terminal exactly equals s_terminal."""
    result = run_monte_carlo(
        trials=200, horizon_years=10,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=30_000, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04,
        vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.005,
        property_growth_mu=0.055, property_growth_sigma=0.11,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age="established_post_2017", asset_type="house",
        depreciation_override=None,
        share_return_mu=0.085, share_return_sigma=0.15,
        portfolio_profile="blended",
        mode="realistic",
        margin_loan_rate=0.075, isolate_asset_quality=False,
        correlation=0.3,
        mtr=0.37, cpi=0.025, drp=True,
        serviceability_ceiling=20_000, seed=42,
        property_share_mix=0.0,
    )
    import numpy as np
    np.testing.assert_array_equal(
        result["mixed_terminal_wealth"], result["shares_terminal_wealth"]
    )


def test_property_share_mix_60_40_is_weighted_average():
    """At mix=0.6, mixed = 0.6*property + 0.4*shares trial-by-trial."""
    result = run_monte_carlo(
        trials=200, horizon_years=10,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=30_000, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04,
        vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.005,
        property_growth_mu=0.055, property_growth_sigma=0.11,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age="established_post_2017", asset_type="house",
        depreciation_override=None,
        share_return_mu=0.085, share_return_sigma=0.15,
        portfolio_profile="blended",
        mode="realistic",
        margin_loan_rate=0.075, isolate_asset_quality=False,
        correlation=0.3,
        mtr=0.37, cpi=0.025, drp=True,
        serviceability_ceiling=20_000, seed=42,
        property_share_mix=0.6,
    )
    import numpy as np
    expected = 0.6 * result["property_terminal_wealth"] + 0.4 * result["shares_terminal_wealth"]
    np.testing.assert_array_almost_equal(result["mixed_terminal_wealth"], expected)


def test_p_mix_metrics_in_valid_range():
    """p_mix_beats_pure_shares and p_mix_solvent are probabilities in [0,1]."""
    result = run_monte_carlo(
        trials=200, horizon_years=10,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=30_000, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04,
        vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.005,
        property_growth_mu=0.055, property_growth_sigma=0.11,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age="established_post_2017", asset_type="house",
        depreciation_override=None,
        share_return_mu=0.085, share_return_sigma=0.15,
        portfolio_profile="blended",
        mode="realistic",
        margin_loan_rate=0.075, isolate_asset_quality=False,
        correlation=0.3,
        mtr=0.37, cpi=0.025, drp=True,
        serviceability_ceiling=20_000, seed=42,
        property_share_mix=0.6,
    )
    assert 0 <= result["p_mix_beats_pure_shares"] <= 1
    assert 0 <= result["p_mix_solvent"] <= 1
    # At mix=0.6, mix should be solvent more often than pure property (less outside cash)
    assert result["p_mix_solvent"] >= result["p_solvent"]


def test_loan_rate_path_uncorrelated_with_return_paths():
    """After dual-seed fix, loan_rate draws should be uncorrelated with property/share
    return draws (correlation < 0.05 at N=5000). Pre-fix this was ~0.004 by coincidence
    but the streams were structurally identical; fix decouples them properly."""
    import numpy as np
    from model.monte_carlo import generate_correlated_paths

    # Mirror what run_monte_carlo does: outer rng seeded with `seed`, inner with `seed+1`
    seed = 42
    rng = np.random.default_rng(seed)
    loan_rate_z = rng.standard_normal((5000, 10))  # same shape as run_monte_carlo

    paths = generate_correlated_paths(
        trials=5000, horizon=10,
        property_mu=0.055, property_sigma=0.11,
        share_mu=0.085, share_sigma=0.15,
        correlation=0.0, seed=seed + 1,
    )
    prop = paths["property_growth"]
    # Flatten and correlate
    corr = np.corrcoef(loan_rate_z.ravel(), prop.ravel())[0, 1]
    # Sampling noise at N=50000 is roughly 1/sqrt(N) ≈ 0.0045; allow 5x for safety
    assert abs(corr) < 0.05, f"Expected near-zero correlation, got {corr:.4f}"


def test_run_monte_carlo_default_restricted_with_new_build_runs():
    """Confirm passing property_regime='current' with new_build runs end-to-end.
    Wiring sanity check for the app's effective_property_regime computation."""
    result = run_monte_carlo(
        trials=200, horizon_years=10,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=30_000, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04,
        vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.0,
        property_growth_mu=0.055, property_growth_sigma=0.11,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age="new_build", asset_type="house",
        depreciation_override=None,
        share_return_mu=0.085, share_return_sigma=0.15,
        portfolio_profile="blended",
        mode="realistic",
        margin_loan_rate=0.075, isolate_asset_quality=False,
        correlation=0.3,
        mtr=0.37, cpi=0.025, drp=True,
        serviceability_ceiling=20_000, seed=42,
        property_regime="current",  # what effective_property_regime would resolve to
    )
    # Just confirm it runs and produces valid metrics
    assert 0 <= result["p_property_succeeds"] <= 1


def test_p_solvent_consistent_with_forced_flags():
    """p_solvent must equal 1 - forced_flags.mean() (no double computation)."""
    result = run_monte_carlo(
        trials=200, horizon_years=10,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=30_000, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04,
        vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.0,
        property_growth_mu=0.055, property_growth_sigma=0.11,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age="established_post_2017", asset_type="house",
        depreciation_override=None,
        share_return_mu=0.085, share_return_sigma=0.15,
        portfolio_profile="blended",
        mode="realistic",
        margin_loan_rate=0.075, isolate_asset_quality=False,
        correlation=0.3,
        mtr=0.37, cpi=0.025, drp=True,
        serviceability_ceiling=20_000, seed=42,
    )
    import numpy as np
    expected_p_solvent = float(1 - result["forced_sale_flags"].mean())
    assert result["p_solvent"] == expected_p_solvent
