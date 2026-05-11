"""End-to-end smoke test. Validates the full pipeline produces sane numbers for a default
scenario."""
import pytest
from model.monte_carlo import run_monte_carlo


def test_default_scenario_produces_sane_numbers():
    result = run_monte_carlo(
        trials=1000, horizon_years=25,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=32_330, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04, vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.005,
        property_growth_mu=0.055, property_growth_sigma=0.11,
        share_return_mu=0.085, share_return_sigma=0.15,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age='established_post_2017', asset_type='house',
        depreciation_override=None,
        portfolio_profile='blended',
        mode='realistic',
        margin_loan_rate=0.075, isolate_asset_quality=False,
        correlation=0.3,
        mtr=0.37, cpi=0.025, drp=True,
        seed=42,
    )

    # Sanity checks
    assert 0.20 <= result["p_property_wins"] <= 0.80, "P(property wins) outside plausible range"
    assert result["median_property_wealth"] > 500_000, "Property wealth implausibly low"
    assert result["median_shares_wealth"] > 500_000, "Shares wealth implausibly low"
    assert result["p_solvent"] >= 0.50, "Default scenario shouldn't fail solvency in most trials"
    assert result["worst_year_cash"] < 200_000, "Worst-year cash implausibly high"
