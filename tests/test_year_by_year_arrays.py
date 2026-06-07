"""Tests for per-year breakdown arrays surfaced by the Monte Carlo runner and
individual strategy simulators.

New result-dict keys asserted here (all shape (trials, horizon_years)):
  property_value_path, property_loan_balance_path, property_rent_path,
  property_interest_path, property_other_costs_path, property_depreciation_path,
  property_tax_path, property_cashflow_path, property_overflow_path,
  shares_dividend_path, shares_dividend_tax_path, shares_margin_interest_path,
  shares_cashflow_path
"""
import pytest
import numpy as np
from model.monte_carlo import run_monte_carlo
from model.property_strategy import simulate_property_trial, PropertyInputs


# ---------------------------------------------------------------------------
# Shared fixture: default scenario (mirrors test_e2e_smoke.py)
# ---------------------------------------------------------------------------

TRIALS = 100
HORIZON = 25

MC_KWARGS = dict(
    trials=TRIALS,
    horizon_years=HORIZON,
    purchase_price=700_000,
    deposit=140_000,
    stamp_duty=32_330,
    buying_costs=2_600,
    loan_rate_mu=0.06,
    loan_rate_sigma=0.01,
    gross_yield=0.04,
    vacancy_weeks_mu=2.0,
    vacancy_weeks_sigma=1.0,
    rental_yield_sigma=0.005,
    property_growth_mu=0.055,
    property_growth_sigma=0.11,
    share_return_mu=0.085,
    share_return_sigma=0.15,
    management_fee_pct=0.07,
    maintenance_pct=0.012,
    property_age="established_post_2017",
    asset_type="house",
    depreciation_override=None,
    portfolio_profile="blended",
    mode="realistic",
    margin_loan_rate=0.075,
    isolate_asset_quality=False,
    correlation=0.3,
    mtr=0.37,
    cpi=0.025,
    drp=True,
    seed=42,
)

NEW_RESULT_KEYS = [
    "property_value_path",
    "property_loan_balance_path",
    "property_rent_path",
    "property_interest_path",
    "property_other_costs_path",
    "property_depreciation_path",
    "property_tax_path",
    "property_cashflow_path",
    "property_overflow_path",
    "shares_dividend_path",
    "shares_dividend_tax_path",
    "shares_margin_interest_path",
    "shares_cashflow_path",
]


@pytest.fixture(scope="module")
def result():
    return run_monte_carlo(**MC_KWARGS)


# ---------------------------------------------------------------------------
# Shape assertions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", NEW_RESULT_KEYS)
def test_new_array_shape(result, key):
    """Every new result-dict array must have shape (trials, horizon_years)."""
    assert key in result, f"key '{key}' missing from result dict"
    arr = result[key]
    assert arr.shape == (TRIALS, HORIZON), (
        f"result['{key}'].shape = {arr.shape}, expected ({TRIALS}, {HORIZON})"
    )


# ---------------------------------------------------------------------------
# property_loan_balance_path sanity checks
# ---------------------------------------------------------------------------

def test_loan_balance_non_negative(result):
    """Loan balance must never go below zero."""
    assert (result["property_loan_balance_path"] >= 0).all()


def test_loan_balance_less_than_initial(result):
    """By end of horizon (25y on a 30y/5y-IO loan) balances must be below the
    initial loan ($700k - $140k = $560k) and strictly positive (25 < 30y term)."""
    initial_loan = 700_000 - 140_000
    final_balances = result["property_loan_balance_path"][:, -1]
    assert (final_balances < initial_loan).all(), "Some trial's final balance >= initial loan"
    assert (final_balances >= 0).all(), "Some trial's final balance is negative"


def test_loan_balance_non_increasing_post_io(result):
    """After the IO period (year index 5) balances must be non-increasing year-on-year
    (P&I repayments only reduce the principal, never add to it)."""
    balances = result["property_loan_balance_path"]
    io_end = 5  # io_period_years in the default scenario
    post_io = balances[:, io_end:]
    diffs = np.diff(post_io, axis=1)  # shape (trials, horizon-io_end-1)
    assert (diffs <= 1e-6).all(), (
        f"Some balance increased post-IO; max increase = {diffs.max():.2f}"
    )


# ---------------------------------------------------------------------------
# property_rent_path sanity check
# ---------------------------------------------------------------------------

def test_year1_rent_near_expected(result):
    """Year-1 rent mean across trials should be within 10% of
    purchase_price * gross_yield (vacancy randomness is the only source of spread)."""
    purchase_price = 700_000
    gross_yield = 0.04
    expected_full_rent = purchase_price * gross_yield  # no vacancy
    year1_mean = result["property_rent_path"][:, 0].mean()
    # vacancy_weeks_mu=2 => expected occupied fraction = 50/52
    expected_with_vacancy = expected_full_rent * (50 / 52)
    assert abs(year1_mean - expected_with_vacancy) / expected_with_vacancy < 0.10, (
        f"Year-1 mean rent {year1_mean:.0f} is more than 10% from "
        f"expected {expected_with_vacancy:.0f}"
    )


# ---------------------------------------------------------------------------
# property_value_path sanity checks
# ---------------------------------------------------------------------------

def test_property_value_positive(result):
    """Property values must always be positive."""
    assert (result["property_value_path"] > 0).all()


def test_property_value_increasing_on_average(result):
    """On average, property should appreciate over the horizon (mu=5.5%/yr)."""
    mean_values = result["property_value_path"].mean(axis=0)  # shape (horizon,)
    # Mean at year 25 should exceed mean at year 1
    assert mean_values[-1] > mean_values[0], (
        "Mean property value did not increase over horizon"
    )


def test_property_value_last_col_matches_wealth_denominator(result):
    """property_value_path[:, -1] should equal the gross_sale_price used in the
    terminal wealth calc — cross-check via property_wealth_path (which equals
    value - balance + overflow at each year, so at year -1:
    property_wealth_path[:, -1] == property_value_path[:, -1]
                                    - property_loan_balance_path[:, -1]
                                    + property_overflow_path[:, -1])."""
    pv = result["property_value_path"][:, -1]
    lb = result["property_loan_balance_path"][:, -1]
    ov = result["property_overflow_path"][:, -1]
    pw = result["property_wealth_path"][:, -1]
    reconstructed = pv - lb + ov
    np.testing.assert_allclose(reconstructed, pw, rtol=1e-10,
                               err_msg="property_value_path - loan_balance + overflow != property_wealth_path")


# ---------------------------------------------------------------------------
# property_cashflow_path consistency
# ---------------------------------------------------------------------------

def test_property_cashflow_path_matches_wealth_path_key(result):
    """property_cashflow_path must equal the cashflow arrays used to build the
    overflow bucket — verify by checking it matches the existing
    outside_cash_per_trial_year where cashflow < 0."""
    cf = result["property_cashflow_path"]
    outside_cash = result["outside_cash_per_trial_year"]
    # outside_cash = max(0, -cashflow), so where cashflow < 0:
    #   outside_cash == -cashflow  ⟹  cashflow == -outside_cash
    mask = cf < 0
    np.testing.assert_allclose(
        -cf[mask], outside_cash[mask], rtol=1e-10,
        err_msg="property_cashflow_path inconsistent with outside_cash_per_trial_year"
    )


# ---------------------------------------------------------------------------
# shares_cashflow_path consistency
# ---------------------------------------------------------------------------

def test_shares_cashflow_path_consistent(result):
    """shares_cashflow_path should be <= 0 (or near 0) in most years — it's
    a cash outflow (div tax + margin interest + external contributions, all
    negated). assert the mean is negative."""
    mean_cf = result["shares_cashflow_path"].mean()
    assert mean_cf <= 0, (
        f"Mean shares cashflow {mean_cf:.2f} should be <= 0 "
        "(investors pay taxes/interest, not receive them)"
    )


# ---------------------------------------------------------------------------
# Unit test at strategy level: PropertyResult new fields
# ---------------------------------------------------------------------------

def make_property_inputs(h=25) -> PropertyInputs:
    return PropertyInputs(
        purchase_price=700_000,
        deposit=140_000,
        loan_rate_path=np.full(h, 0.06),
        loan_term_years=30,
        io_period_years=5,
        gross_yield=0.04,
        vacancy_weeks_path=np.full(h, 2.0),
        capital_growth_path=np.full(h, 0.055),
        management_fee_pct=0.07,
        maintenance_pct=0.012,
        property_age="established_post_2017",
        asset_type="house",
        depreciation_override=None,
        mtr=0.37,
        cpi=0.025,
        horizon_years=h,
        selling_costs_pct=0.025,
    )


def test_property_result_new_arrays_have_correct_length():
    """All new PropertyResult arrays must have length == horizon_years."""
    h = 25
    inputs = make_property_inputs(h)
    result = simulate_property_trial(inputs)

    for attr in (
        "property_value_path",
        "loan_balance_path",
        "rent_path",
        "interest_path",
        "other_costs_path",
        "depreciation_path",
        "tax_path",
        "overflow_balance_path",
    ):
        arr = getattr(result, attr)
        assert arr is not None, f"PropertyResult.{attr} is None"
        assert len(arr) == h, f"PropertyResult.{attr} length {len(arr)} != {h}"


def test_property_interest_path_year1_io():
    """During IO period (year 0), interest = (purchase_price - deposit) * loan_rate."""
    inputs = make_property_inputs()
    result = simulate_property_trial(inputs)

    initial_loan = inputs.purchase_price - inputs.deposit  # 560_000
    expected_interest_yr1 = initial_loan * inputs.loan_rate_path[0]  # 560_000 * 0.06 = 33_600
    assert result.interest_path[0] == pytest.approx(expected_interest_yr1, abs=1), (
        f"Year-1 interest {result.interest_path[0]:.2f} != expected {expected_interest_yr1:.2f}"
    )


def test_property_other_costs_excludes_interest():
    """other_costs_path = management + maintenance + land_tax (no interest).
    Year-1 interest is ~$33,600; year-1 other costs should be much less."""
    inputs = make_property_inputs()
    result = simulate_property_trial(inputs)

    # Rough year-1 other costs: mgmt ~$1,885 + maintenance $8,400 + land_tax $0 ≈ $10,285
    assert result.other_costs_path[0] < result.interest_path[0], (
        "other_costs_path should be less than interest in year 1 for default inputs"
    )
    assert result.other_costs_path[0] > 0


def test_property_tax_path_year1_negative():
    """Default inputs are negatively geared → year-1 tax should be negative (a refund)."""
    inputs = make_property_inputs()
    result = simulate_property_trial(inputs)
    assert result.tax_path[0] < 0, "Year-1 tax should be negative (NG refund) for default inputs"


def test_property_overflow_balance_path_zero_when_negatively_geared():
    """When all cashflows are negative the overflow bucket stays at zero."""
    h = 5
    inputs = make_property_inputs(h)
    inputs.gross_yield = 0.03  # deep negative gearing
    inputs.loan_rate_path = np.full(h, 0.06)
    inputs.vacancy_weeks_path = np.full(h, 2.0)
    inputs.capital_growth_path = np.full(h, 0.055)
    result = simulate_property_trial(inputs)

    assert (result.cashflow_per_year < 0).all()
    np.testing.assert_array_equal(result.overflow_balance_path, np.zeros(h))
