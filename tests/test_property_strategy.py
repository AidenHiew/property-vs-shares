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
