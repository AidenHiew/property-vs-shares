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
    return_distribution: str = "gaussian",
    t_df: int = 5,
) -> Dict[str, np.ndarray]:
    """Return correlated draws for property capital growth and share total return.

    Uses Cholesky decomposition to introduce the target correlation.

    Returns dict with 'property_growth' and 'share_return' as (trials, horizon) arrays.
    """
    rng = np.random.default_rng(seed)
    if return_distribution == "gaussian":
        z = rng.standard_normal((trials, horizon, 2))
    elif return_distribution == "student_t":
        raw = rng.standard_t(t_df, size=(trials, horizon, 2))
        z = raw * np.sqrt((t_df - 2) / t_df)  # rescale so realized σ = 1
    else:
        raise ValueError(f"unknown return_distribution: {return_distribution}")

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
from model.solvency import flag_forced_sales


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
    serviceability_ceiling: float = 20_000,
    seed: int = 42,
    # Federal Budget 2026-27 regime — kwarg with default for backward compat
    property_regime: str = "current",
    return_distribution: str = "gaussian",
    t_df: int = 5,
    loan_rate_distribution: str = "gaussian",
    loan_rate_t_df: int = 5,
    # Allocation mix: 1.0 = 100% property (default, preserves current behaviour),
    # 0.0 = 100% shares, anything in between is a per-trial weighted blend.
    property_share_mix: float = 1.0,
):
    """Run the full Monte Carlo simulation. Returns aggregated outputs."""
    rng = np.random.default_rng(seed)

    # Pass seed+1 to decorrelate the return-paths RNG from the outer loan_rate/vacancy RNG.
    # Both were previously seeded identically; empirically the spurious correlation was
    # negligible (~0.004) but it's a latent defect. See BACKLOG §Bugs §2.
    paths = generate_correlated_paths(
        trials=trials, horizon=horizon_years,
        property_mu=property_growth_mu, property_sigma=property_growth_sigma,
        share_mu=share_return_mu, share_sigma=share_return_sigma,
        correlation=correlation, seed=seed + 1,
        return_distribution=return_distribution, t_df=t_df,
    )

    if loan_rate_distribution == "gaussian":
        loan_rate_z = rng.standard_normal((trials, horizon_years))
    elif loan_rate_distribution == "student_t":
        raw = rng.standard_t(loan_rate_t_df, size=(trials, horizon_years))
        loan_rate_z = raw * np.sqrt((loan_rate_t_df - 2) / loan_rate_t_df)
    else:
        raise ValueError(f"unknown loan_rate_distribution: {loan_rate_distribution}")
    loan_rate_paths = loan_rate_mu + loan_rate_sigma * loan_rate_z
    vacancy_paths = np.maximum(0, vacancy_weeks_mu + vacancy_weeks_sigma * rng.standard_normal((trials, horizon_years)))
    # rental_yield_sigma is plumbed through for future use; v1 PropertyInputs takes a scalar
    # gross_yield, so we don't actually use yield_paths in the loop. Kept here for symmetry
    # with the other stochastic vars; can plumb into PropertyInputs in v2.

    p_terminal = np.zeros(trials)
    s_terminal = np.zeros(trials)
    p_outside_cash = np.zeros((trials, horizon_years))
    p_wealth_path = np.zeros((trials, horizon_years))
    s_wealth_path = np.zeros((trials, horizon_years))

    # Per-year breakdown arrays — shape (trials, horizon_years)
    p_value_path = np.zeros((trials, horizon_years))
    p_loan_balance_path = np.zeros((trials, horizon_years))
    p_rent_path = np.zeros((trials, horizon_years))
    p_interest_path = np.zeros((trials, horizon_years))
    p_other_costs_path = np.zeros((trials, horizon_years))
    p_depreciation_path = np.zeros((trials, horizon_years))
    p_tax_path = np.zeros((trials, horizon_years))
    p_cashflow_path = np.zeros((trials, horizon_years))
    p_overflow_path = np.zeros((trials, horizon_years))
    s_dividend_path = np.zeros((trials, horizon_years))
    s_dividend_tax_path = np.zeros((trials, horizon_years))
    s_margin_interest_path = np.zeros((trials, horizon_years))
    s_cashflow_path = np.zeros((trials, horizon_years))

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
            acquisition_costs=stamp_duty + buying_costs,
            property_regime=property_regime,
            # Overflow shares use the same portfolio profile as the shares strategy,
            # so the reinvested-surplus bucket bears the same dividend tax + CGT drag.
            overflow_dividend_yield=PORTFOLIO_PROFILES[portfolio_profile]["div_yield"],
            overflow_franked_portion=PORTFOLIO_PROFILES[portfolio_profile]["franked"],
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
        p_wealth_path[t] = p_result.wealth_per_year
        s_wealth_path[t] = s_result.wealth_per_year

        # Per-year breakdown
        p_value_path[t] = p_result.property_value_path
        p_loan_balance_path[t] = p_result.loan_balance_path
        p_rent_path[t] = p_result.rent_path
        p_interest_path[t] = p_result.interest_path
        p_other_costs_path[t] = p_result.other_costs_path
        p_depreciation_path[t] = p_result.depreciation_path
        p_tax_path[t] = p_result.tax_path
        p_cashflow_path[t] = p_result.cashflow_per_year
        p_overflow_path[t] = p_result.overflow_balance_path
        s_dividend_path[t] = s_result.dividend_path
        s_dividend_tax_path[t] = s_result.dividend_tax_path
        s_margin_interest_path[t] = s_result.margin_interest_path
        s_cashflow_path[t] = s_result.cashflow_per_year

    forced_flags = flag_forced_sales(p_outside_cash, serviceability_ceiling)

    # Allocation mix computation
    mix = property_share_mix
    mixed_terminal = mix * p_terminal + (1 - mix) * s_terminal
    mixed_outside_cash = mix * p_outside_cash  # only property has outside cash demand; mix scales it
    mixed_forced_flags = flag_forced_sales(mixed_outside_cash, serviceability_ceiling)

    return {
        "property_terminal_wealth": p_terminal,
        "shares_terminal_wealth": s_terminal,
        "p_property_wins": float((p_terminal > s_terminal).mean()),
        "outside_cash_per_trial_year": p_outside_cash,
        "median_outside_cash_total": float(np.median(p_outside_cash.sum(axis=1))),
        "worst_year_cash": float(np.percentile(p_outside_cash.max(axis=1), 90)),
        "median_property_wealth": float(np.median(p_terminal)),
        "median_shares_wealth": float(np.median(s_terminal)),
        # Note: model/solvency.py:p_solvent exists but takes (cash_array, ceiling) and re-runs
        # flag_forced_sales internally. Since we already computed forced_flags above, deriving
        # p_solvent inline avoids a redundant vectorised pass. The helper is still available
        # for callers that don't already have flags computed.
        "p_solvent": float(1 - forced_flags.mean()),
        "p_property_succeeds": float(
            ((p_terminal > s_terminal) & (forced_flags == 0)).mean()
        ),
        "forced_sale_flags": forced_flags,
        "mixed_terminal_wealth": mixed_terminal,
        "median_mixed_wealth": float(np.median(mixed_terminal)),
        "property_wealth_path": p_wealth_path,          # shape (trials, horizon_years)
        "shares_wealth_path": s_wealth_path,            # shape (trials, horizon_years)
        "mixed_wealth_path": (
            mix * p_wealth_path + (1 - mix) * s_wealth_path
        ),                                              # shape (trials, horizon_years)
        "p_mix_beats_pure_shares": float(
            ((mixed_terminal > s_terminal) & (mixed_forced_flags == 0)).mean()
        ),
        "p_mix_solvent": float(1 - mixed_forced_flags.mean()),
        "mixed_outside_cash_per_trial_year": mixed_outside_cash,
        # Per-year breakdown arrays — shape (trials, horizon_years)
        "property_value_path": p_value_path,
        "property_loan_balance_path": p_loan_balance_path,
        "property_rent_path": p_rent_path,
        "property_interest_path": p_interest_path,
        "property_other_costs_path": p_other_costs_path,
        "property_depreciation_path": p_depreciation_path,
        "property_tax_path": p_tax_path,
        "property_cashflow_path": p_cashflow_path,
        "property_overflow_path": p_overflow_path,
        "shares_dividend_path": s_dividend_path,
        "shares_dividend_tax_path": s_dividend_tax_path,
        "shares_margin_interest_path": s_margin_interest_path,
        "shares_cashflow_path": s_cashflow_path,
    }
