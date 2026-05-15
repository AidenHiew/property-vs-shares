"""Property strategy tests."""
import pytest
import numpy as np
from model.property_strategy import simulate_property_trial, PropertyInputs


def make_default_inputs() -> PropertyInputs:
    return PropertyInputs(
        purchase_price=700_000,
        deposit=140_000,
        loan_rate_path=np.full(25, 0.06),  # flat 6% for simplicity
        loan_term_years=30,
        io_period_years=5,
        gross_yield=0.04,
        vacancy_weeks_path=np.full(25, 2.0),
        capital_growth_path=np.full(25, 0.055),
        management_fee_pct=0.07,
        maintenance_pct=0.012,
        property_age="established_post_2017",
        asset_type="house",
        depreciation_override=None,
        mtr=0.37,
        cpi=0.025,
        horizon_years=25,
        selling_costs_pct=0.025,
    )


def test_property_year_one_cashflow_components():
    """Hand-calc year 1 with NO CPI inflation effects (year 1 baseline):
    - Rent: $700k * 4% = $28,000 gross; less 2 weeks vacancy = 28,000 * 50/52 = $26,923
    - Management: $26,923 * 7% = $1,885
    - Maintenance: $700k * 1.2% = $8,400
    - Interest (IO): $560k * 6% = $33,600
    - Land tax (SA, land=$420k below $833k threshold): $0
    - Depreciation (non-cash): $7,000
    - Pre-tax cashflow (rent - cash costs only): 26,923 - (1885 + 8400 + 33600 + 0) = -$16,962
    - Taxable income from property: 26,923 - 43,885 - 7,000 = -$23,962 (rental loss)
    - Tax saving on the loss at 37% MTR: 23,962 * 0.37 = $8,866
    - After-tax cashflow yr 1: -16,962 + 8,866 = -$8,096
    """
    inputs = make_default_inputs()
    result = simulate_property_trial(inputs)

    assert result.cashflow_per_year[0] == pytest.approx(-8_096, abs=50)


def test_property_terminal_wealth_includes_capital_growth():
    """End-of-horizon house value = $700k * (1.055)^25 ≈ $2.65m"""
    inputs = make_default_inputs()
    result = simulate_property_trial(inputs)

    expected_sale_price = 700_000 * (1.055) ** 25
    assert result.gross_sale_price == pytest.approx(expected_sale_price, rel=0.01)


def test_property_depreciation_override_flows_to_cashflow():
    """User-overridden depreciation must change the after-tax cashflow."""
    inputs = make_default_inputs()
    inputs.depreciation_override = 12_000  # well above the $7k Div 43 default
    result = simulate_property_trial(inputs)

    # With higher depreciation, taxable loss is bigger, tax saving is bigger,
    # cashflow is LESS negative (closer to zero) than the default.
    default_inputs = make_default_inputs()
    default_result = simulate_property_trial(default_inputs)

    assert result.cashflow_per_year[0] > default_result.cashflow_per_year[0]
    # The difference should be approximately (12000 - 7000) * 0.37 = $1,850 less out of pocket
    expected_diff = (12_000 - 7_000) * 0.37
    actual_diff = result.cashflow_per_year[0] - default_result.cashflow_per_year[0]
    assert actual_diff == pytest.approx(expected_diff, abs=10)


def test_property_io_to_pi_transition_at_year_5():
    """At end of IO period (year 5, index 5), loan starts amortising.
    Year 5's interest = balance * rate; balance starts to decline year-on-year after that.
    """
    inputs = make_default_inputs()
    result = simulate_property_trial(inputs)

    # The simulator returns cashflow per year. We can't directly inspect interest path,
    # but we can verify that cashflow CHANGES between IO and P&I phases due to higher
    # cash outflow (P&I payment > IO interest-only payment).
    # IO years should have flatter cashflow; P&I years should have larger cash burden initially.
    # Simpler check: terminal loan balance should be substantially less than initial $560k
    # (since IO+P&I over 25 years on a 30-year term reduces but doesn't fully retire the loan).
    assert result.terminal_loan_balance < 560_000  # some amortisation happened
    assert result.terminal_loan_balance > 0        # not fully paid off (25 < 30 yr term)


def test_property_positive_cashflow_invests_in_shares():
    """If property generates surplus in some years, that surplus is invested in
    shares within the property strategy (the 'overflow wealth' bucket).

    At 8% gross yield against a 6% loan rate, the property is positively geared
    in every year, so the overflow bucket must end up strictly positive.
    """
    inputs = make_default_inputs()
    inputs.gross_yield = 0.08  # high yield → positively geared every year
    result = simulate_property_trial(inputs)

    # Sanity check: every year really is positive cashflow under these inputs.
    assert (result.cashflow_per_year > 0).all()
    assert result.overflow_share_terminal_value > 0


def test_property_exposes_outside_cash_required_per_year():
    """Property must expose per-year outside cash needed (= max(0, -cashflow))
    so the shares strategy can mirror it as external_contributions for equal
    outside-cash symmetry (see design spec §7).
    """
    inputs = make_default_inputs()
    result = simulate_property_trial(inputs)

    expected = np.where(result.cashflow_per_year < 0, -result.cashflow_per_year, 0)
    np.testing.assert_array_almost_equal(result.outside_cash_required_per_year, expected)


def test_property_negatively_geared_overflow_is_zero():
    """When every year produces negative cashflow, the overflow share bucket
    must remain at zero — nothing was ever contributed.

    Uses a 5-year IO-only horizon with a 3% gross yield against 6% loan rate.
    Over 5 IO years, rent growth (tracking ~5.5% capital appreciation) never
    outpaces the interest burden, so cashflow stays negative throughout.
    """
    inputs = make_default_inputs()
    inputs.gross_yield = 0.03       # low yield → deep negative gearing
    inputs.horizon_years = 5        # stay within IO period so no amortisation drag change
    inputs.loan_rate_path = np.full(5, 0.06)
    inputs.vacancy_weeks_path = np.full(5, 2.0)
    inputs.capital_growth_path = np.full(5, 0.055)
    result = simulate_property_trial(inputs)

    assert (result.cashflow_per_year < 0).all()
    assert result.overflow_share_terminal_value == 0.0


# =============================================================================
# Federal Budget 2026-27 — restricted_2027 regime tests
# =============================================================================

def test_property_restricted_regime_no_refund_on_loss_year():
    """Under restricted_2027 with start_year_index=0, a year-1 rental loss yields
    tax_on_property = 0 (NOT a refund). The loss goes to the residential property
    loss pool for later use against rental surplus or post-commencement capital gain.

    Same year-1 inputs as test_property_year_one_cashflow_components but with
    restriction active immediately:
      pre_tax_cash:    -$16,962  (unchanged)
      tax_on_property: $0        (was -$8,866 refund under current regime)
      cashflow:        -$16,962  (vs -$8,096 under current)
    """
    inputs = make_default_inputs()
    inputs.property_regime = "restricted_2027"
    inputs.restricted_ng_start_year_index = 0  # restriction kicks in immediately
    result = simulate_property_trial(inputs)

    assert result.cashflow_per_year[0] == pytest.approx(-16_962, abs=50)
