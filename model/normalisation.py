"""Comparison-mode normalisation. Decides what shares strategy starts with given the property
scenario, ensuring the comparison is fair within the chosen mode."""
import numpy as np
from model.shares_strategy import SharesInputs

PORTFOLIO_PROFILES = {
    "asx_only":   {"return_mu": 0.090, "return_sigma": 0.16, "div_yield": 0.040, "franked": 0.85},
    "global":     {"return_mu": 0.085, "return_sigma": 0.14, "div_yield": 0.020, "franked": 0.10},
    "blended":    {"return_mu": 0.085, "return_sigma": 0.15, "div_yield": 0.035, "franked": 0.50},
}


def build_shares_inputs_for_mode_a(
    purchase_price: float,
    deposit: float,
    stamp_duty: float,
    buying_costs: float,
    mtr: float,
    horizon_years: int,
    portfolio_profile: str,
    return_path: np.ndarray = None,
    drp: bool = True,
) -> SharesInputs:
    """Mode A (Realistic): shares starts with property's full upfront cash, no leverage."""
    profile = PORTFOLIO_PROFILES[portfolio_profile]
    if return_path is None:
        return_path = np.full(horizon_years, profile["return_mu"])

    return SharesInputs(
        initial_capital=deposit + stamp_duty + buying_costs,
        share_return_path=return_path,
        dividend_yield_pct=profile["div_yield"],
        franked_portion=profile["franked"],
        mer=0.0020,
        brokerage_per_trade=10.0,
        drp=drp,
        mtr=mtr,
        external_contributions=np.zeros(horizon_years),  # filled in by Monte Carlo runner
        horizon_years=horizon_years,
        margin_loan_initial=0.0,
        margin_loan_rate_path=None,
    )


def build_shares_inputs_for_mode_b(
    purchase_price: float,
    deposit: float,
    stamp_duty: float,
    buying_costs: float,
    mtr: float,
    horizon_years: int,
    portfolio_profile: str,
    margin_loan_rate: float,
    isolate_asset_quality: bool,
    mortgage_rate: float,
    return_path: np.ndarray = None,
    drp: bool = True,
) -> SharesInputs:
    """Mode B (Fair fight): shares matches property's total exposure via margin loan.

    If isolate_asset_quality=True, margin loan rate is pinned to mortgage_rate (counterfactual).
    """
    profile = PORTFOLIO_PROFILES[portfolio_profile]
    if return_path is None:
        return_path = np.full(horizon_years, profile["return_mu"])

    equity = deposit + stamp_duty + buying_costs
    margin_loan = purchase_price - equity
    rate = mortgage_rate if isolate_asset_quality else margin_loan_rate

    return SharesInputs(
        initial_capital=equity,
        share_return_path=return_path,
        dividend_yield_pct=profile["div_yield"],
        franked_portion=profile["franked"],
        mer=0.0020,
        brokerage_per_trade=10.0,
        drp=drp,
        mtr=mtr,
        external_contributions=np.zeros(horizon_years),
        horizon_years=horizon_years,
        margin_loan_initial=margin_loan,
        margin_loan_rate_path=np.full(horizon_years, rate),
    )
