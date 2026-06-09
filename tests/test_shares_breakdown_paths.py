import numpy as np
from model.shares_strategy import SharesInputs, simulate_shares_trial


def _inputs(h=5):
    return SharesInputs(
        initial_capital=200_000, share_return_path=np.full(h, 0.08),
        dividend_yield_pct=0.03, franked_portion=0.8, mer=0.002,
        brokerage_per_trade=20, drp=True, mtr=0.37,
        external_contributions=np.full(h, 10_000.0), horizon_years=h,
        margin_loan_initial=0.0, margin_loan_rate_path=None,
    )


def test_new_paths_present_and_length():
    r = simulate_shares_trial(_inputs())
    assert r.contribution_path.shape == (5,)
    assert r.capital_growth_path.shape == (5,)


def test_contribution_path_matches_inputs():
    r = simulate_shares_trial(_inputs())
    assert np.allclose(r.contribution_path, 10_000.0)


def test_capital_growth_is_price_slice():
    # capital_return = 0.08 - 0.03 = 0.05; year-1 growth = initial_capital * 0.05
    r = simulate_shares_trial(_inputs())
    assert r.capital_growth_path[0] == 200_000 * (0.08 - 0.03)
