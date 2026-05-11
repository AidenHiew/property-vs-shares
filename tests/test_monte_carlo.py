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
