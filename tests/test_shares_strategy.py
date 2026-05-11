"""Shares strategy tests."""
import pytest
import numpy as np
from model.shares_strategy import simulate_shares_trial, SharesInputs


def make_default_shares_inputs() -> SharesInputs:
    return SharesInputs(
        initial_capital=172_000,  # property's deposit + stamp duty + buying costs
        share_return_path=np.full(25, 0.085),
        dividend_yield_pct=0.035,
        franked_portion=0.50,
        mer=0.0020,
        brokerage_per_trade=10.0,
        drp=True,
        mtr=0.37,
        external_contributions=np.zeros(25),  # set by comparison engine
        horizon_years=25,
        margin_loan_initial=0.0,
        margin_loan_rate_path=None,
    )


def test_shares_year_one_cashflow_with_drp():
    """Year 1 cashflow (out-of-pocket) is dividend tax only — approximately -$1,415.

    Hand-calc:
      Dividends:       $172k × 3.5% = $6,020
      Franked cash:    $6,020 × 50% = $3,010
      Unfranked cash:  $6,020 × 50% = $3,010
      Franking credit: $3,010 × 0.30/0.70 = $1,290
      Grossed-up div:  $3,010 + $1,290 + $3,010 = $7,310
      Tax @ 37%:       $7,310 × 37% = $2,704.70
      Net of credit:   $2,704.70 − $1,290 = $1,414.70 ≈ $1,415

    MER (0.20% of portfolio) reduces NAV internally — the fund manager deducts it
    from the fund's assets. It is NOT a cash payment from the investor's bank account,
    so it does NOT appear in cashflow_per_year. Only the dividend tax hits the bank.

    With DRP enabled the cash dividends are reinvested; the only actual cash outflow
    is the tax bill on those dividends. Cashflow = -$1,415.
    """
    inputs = make_default_shares_inputs()
    result = simulate_shares_trial(inputs)

    assert result.cashflow_per_year[0] == pytest.approx(-1_415, abs=20)


def test_shares_terminal_wealth_compounds():
    """No dividends, just price growth at 8.5%/yr for 25 yrs with MER drag.

    The simulator subtracts MER × start-of-year NAV each year (additive on the
    start balance), so the effective per-year compound factor is approximately
    1 + 0.085 - 0.002 = 1.083. We approximate this here with the close-enough
    multiplicative form 1.085 * (1 - 0.002) ≈ 1.08283 — the two forms differ by
    ~0.4% over 25 years, comfortably inside the rel=0.02 tolerance.
    gross_terminal_value = value before CGT but after MER drag.

    Expected: ~$172k × 1.083^25 ≈ $1.28m
    (vs. $1.32m without MER — a ~$40-65k drag over 25 years)
    """
    inputs = make_default_shares_inputs()
    inputs.dividend_yield_pct = 0.0
    inputs.franked_portion = 0.0
    result = simulate_shares_trial(inputs)

    # Net-of-MER compound factor (approximate; see docstring for exact behaviour).
    expected_pre_cgt = 172_000 * (1.085 * (1 - inputs.mer)) ** 25
    assert result.gross_terminal_value == pytest.approx(expected_pre_cgt, rel=0.02)
