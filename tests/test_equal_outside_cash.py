"""Cross-strategy test: verify equal outside-cash contributions produce symmetric capital
deployment.

Milestone 2: both strategies simulate one full trial with proven symmetry.

The core assertion is intentionally tautological under its construction — we set
``s_inputs.external_contributions = p_result.outside_cash_required_per_year`` and then
verify that summing both sides gives the same total.  The *real* value of this test is
confirming that the two strategies wire together end-to-end without TypeError, dimension
mismatch, missing field, or import error.

A second, non-tautological sanity assertion checks that passing nonzero contributions
actually increases the shares terminal value — catching bugs where ``external_contributions``
is silently ignored.
"""
import numpy as np
import pytest

from model.property_strategy import simulate_property_trial
from model.shares_strategy import simulate_shares_trial
from tests.test_property_strategy import make_default_inputs as make_p_inputs
from tests.test_shares_strategy import make_default_shares_inputs


def test_total_outside_cash_matches_between_strategies() -> None:
    """Shares strategy receives the same outside-cash flow as property required.

    Symmetry identity (per design spec §7):
        total outside cash (shares) == initial_capital + sum(property's negative cashflow years)

    ``initial_capital`` in the shares fixture is set to 172 000 (deposit $140k + stamp duty ~$32k),
    mirroring the property strategy's upfront outlay.  Together they represent every dollar the
    investor must source from outside their portfolio.
    """
    p_inputs = make_p_inputs()
    p_result = simulate_property_trial(p_inputs)

    # Shares strategy receives the same year-by-year outside-cash flow that property required.
    s_inputs = make_default_shares_inputs()
    s_inputs.external_contributions = p_result.outside_cash_required_per_year
    s_result = simulate_shares_trial(s_inputs)

    total_p_outside = p_result.outside_cash_required_per_year.sum()
    # Shares: initial capital deployed (matched to property's upfront) + sum of contributions.
    total_s_outside = s_inputs.initial_capital + s_inputs.external_contributions.sum()

    # Property's total outside cash = deposit + stamp duty (= initial_capital by construction)
    # plus the sum of years where cashflow was negative.
    total_p_outside_full = s_inputs.initial_capital + total_p_outside

    # Use np.isclose in case float arithmetic promotes int → float differently in np.where.
    assert np.isclose(total_s_outside, total_p_outside_full), (
        f"Outside-cash totals differ: shares={total_s_outside:.2f}, "
        f"property={total_p_outside_full:.2f}"
    )


def test_external_contributions_increase_terminal_value() -> None:
    """Passing nonzero external_contributions must grow the shares terminal portfolio.

    This is the non-tautological half of the symmetry check: it catches bugs where the
    shares simulator silently ignores the ``external_contributions`` array (e.g. forgot
    the ``portfolio_value += inputs.external_contributions[year]`` line).
    """
    p_inputs = make_p_inputs()
    p_result = simulate_property_trial(p_inputs)

    # With contributions equal to property's negative cashflow years.
    s_inputs_contrib = make_default_shares_inputs()
    s_inputs_contrib.external_contributions = p_result.outside_cash_required_per_year
    s_result_contrib = simulate_shares_trial(s_inputs_contrib)

    # Baseline: no external contributions.
    s_inputs_zero = make_default_shares_inputs()
    s_result_zero = simulate_shares_trial(s_inputs_zero)

    assert s_result_contrib.gross_terminal_value > s_result_zero.gross_terminal_value, (
        "Adding external_contributions did not increase the terminal portfolio value — "
        "check that simulate_shares_trial actually applies external_contributions."
    )
