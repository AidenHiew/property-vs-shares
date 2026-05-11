"""Monte Carlo runner. Vectorised over trials."""
import numpy as np
from typing import Dict


def generate_correlated_paths(
    trials: int,
    horizon: int,
    property_mu: float,
    property_sigma: float,
    share_mu: float,
    share_sigma: float,
    correlation: float,
    seed: int = 42,
) -> Dict[str, np.ndarray]:
    """Return correlated normal draws for property capital growth and share total return.

    Uses Cholesky decomposition to introduce the target correlation.

    Returns dict with 'property_growth' and 'share_return' as (trials, horizon) arrays.
    """
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((trials, horizon, 2))

    # Cholesky factor for 2x2 corr matrix [[1, rho], [rho, 1]]
    L = np.array([[1.0, 0.0], [correlation, np.sqrt(1 - correlation ** 2)]])

    correlated = z @ L.T

    property_growth = property_mu + property_sigma * correlated[..., 0]
    share_return    = share_mu    + share_sigma    * correlated[..., 1]

    return {
        "property_growth": property_growth,
        "share_return": share_return,
    }


from typing import Optional
from model.property_strategy import PropertyInputs, simulate_property_trial
from model.shares_strategy import simulate_shares_trial
from model.normalisation import (
    build_shares_inputs_for_mode_a,
    build_shares_inputs_for_mode_b,
    PORTFOLIO_PROFILES,
)


def run_monte_carlo(
    trials: int,
    horizon_years: int,
    # property
    purchase_price: float,
    deposit: float,
    stamp_duty: float,
    buying_costs: float,
    loan_rate_mu: float,
    loan_rate_sigma: float,
    gross_yield: float,
    vacancy_weeks_mu: float,
    vacancy_weeks_sigma: float,
    rental_yield_sigma: float,
    property_growth_mu: float,
    property_growth_sigma: float,
    management_fee_pct: float,
    maintenance_pct: float,
    property_age: str,
    asset_type: str,
    depreciation_override: Optional[float],
    # shares
    share_return_mu: float,
    share_return_sigma: float,
    portfolio_profile: str,
    # comparison
    mode: str,
    margin_loan_rate: float,
    isolate_asset_quality: bool,
    correlation: float,
    # macro
    mtr: float,
    cpi: float,
    drp: bool,
    seed: int = 42,
):
    """Run the full Monte Carlo simulation. Returns aggregated outputs."""
    rng = np.random.default_rng(seed)

    paths = generate_correlated_paths(
        trials=trials, horizon=horizon_years,
        property_mu=property_growth_mu, property_sigma=property_growth_sigma,
        share_mu=share_return_mu, share_sigma=share_return_sigma,
        correlation=correlation, seed=seed,
    )

    loan_rate_paths = loan_rate_mu + loan_rate_sigma * rng.standard_normal((trials, horizon_years))
    vacancy_paths = np.maximum(0, vacancy_weeks_mu + vacancy_weeks_sigma * rng.standard_normal((trials, horizon_years)))
    # rental_yield_sigma is plumbed through for future use; v1 PropertyInputs takes a scalar
    # gross_yield, so we don't actually use yield_paths in the loop. Kept here for symmetry
    # with the other stochastic vars; can plumb into PropertyInputs in v2.

    p_terminal = np.zeros(trials)
    s_terminal = np.zeros(trials)
    p_outside_cash = np.zeros((trials, horizon_years))

    for t in range(trials):
        p_inputs = PropertyInputs(
            purchase_price=purchase_price,
            deposit=deposit,
            loan_rate_path=loan_rate_paths[t],
            loan_term_years=30,
            io_period_years=5,
            gross_yield=gross_yield,  # scalar — see comment above re yield_paths
            vacancy_weeks_path=vacancy_paths[t],
            capital_growth_path=paths["property_growth"][t],
            management_fee_pct=management_fee_pct,
            maintenance_pct=maintenance_pct,
            property_age=property_age,
            asset_type=asset_type,
            depreciation_override=depreciation_override,
            mtr=mtr,
            cpi=cpi,
            horizon_years=horizon_years,
            selling_costs_pct=0.025,
        )
        p_result = simulate_property_trial(p_inputs)

        if mode == "realistic":
            s_inputs = build_shares_inputs_for_mode_a(
                purchase_price=purchase_price, deposit=deposit, stamp_duty=stamp_duty,
                buying_costs=buying_costs, mtr=mtr, horizon_years=horizon_years,
                portfolio_profile=portfolio_profile,
                return_path=paths["share_return"][t], drp=drp,
            )
        elif mode == "fair_fight":
            s_inputs = build_shares_inputs_for_mode_b(
                purchase_price=purchase_price, deposit=deposit, stamp_duty=stamp_duty,
                buying_costs=buying_costs, mtr=mtr, horizon_years=horizon_years,
                portfolio_profile=portfolio_profile,
                margin_loan_rate=margin_loan_rate,
                isolate_asset_quality=isolate_asset_quality,
                mortgage_rate=loan_rate_mu,
                return_path=paths["share_return"][t], drp=drp,
            )
        else:
            raise ValueError(f"unknown mode: {mode}")

        s_inputs.external_contributions = p_result.outside_cash_required_per_year
        s_result = simulate_shares_trial(s_inputs)

        p_terminal[t] = p_result.terminal_after_tax_wealth + p_result.overflow_share_terminal_value
        s_terminal[t] = s_result.terminal_after_tax_wealth
        p_outside_cash[t] = p_result.outside_cash_required_per_year

    return {
        "property_terminal_wealth": p_terminal,
        "shares_terminal_wealth": s_terminal,
        "p_property_wins": float((p_terminal > s_terminal).mean()),
        "outside_cash_per_trial_year": p_outside_cash,
        "median_outside_cash_total": float(np.median(p_outside_cash.sum(axis=1))),
        "worst_year_cash": float(np.percentile(p_outside_cash.max(axis=1), 90)),
        "median_property_wealth": float(np.median(p_terminal)),
        "median_shares_wealth": float(np.median(s_terminal)),
    }
