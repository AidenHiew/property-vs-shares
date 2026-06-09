"""Scenario sweep — sanity-check Federal Budget 2026-27 regime impact across the
input space. Run from the project root with the venv active:

    python notebooks/scenario_sweep.py

Reports five tables:
  1. Regime impact across horizons (P(prop wins), worst-year cash, P(solvent))
  2. Regime impact across MTR bands
  3. Regime impact across deposit ratios
  4. Regime impact across gross yield (does a 5% yield property survive restricted?)
  5. Regime impact across property-age (new build keeps higher Div 43 in pre-period)

All sweeps share a common base scenario; only the swept dial moves.
"""
import numpy as np
from model.monte_carlo import run_monte_carlo
from model.duty import stamp_duty


BASE = dict(
    trials=2000,         # cut from 5000 for sweep speed; sampling error ~1pp
    horizon_years=25,
    purchase_price=700_000,
    deposit=140_000,     # 20%
    stamp_duty=stamp_duty("SA", 700_000),
    buying_costs=2_600,
    loan_rate_mu=0.06,
    loan_rate_sigma=0.01,
    gross_yield=0.04,
    vacancy_weeks_mu=2.0,
    vacancy_weeks_sigma=1.0,
    rental_yield_sigma=0.005,  # no-op in v1, kept for signature compat
    property_growth_mu=0.055,
    property_growth_sigma=0.11,
    management_fee_pct=0.07,
    maintenance_pct=0.012,
    property_age="established_post_2017",
    asset_type="house",
    depreciation_override=None,
    share_return_mu=0.085,
    share_return_sigma=0.15,
    portfolio_profile="blended",
    mode="realistic",
    margin_loan_rate=0.075,
    isolate_asset_quality=False,
    correlation=0.3,
    mtr=0.37,
    cpi=0.025,
    drp=True,
    serviceability_ceiling=20_000,
    seed=42,
)


def run(**overrides):
    inputs = {**BASE, **overrides}
    return run_monte_carlo(**inputs)


def fmt_money(x):
    return f"${x:>10,.0f}"


def fmt_pct(x):
    return f"{x*100:>5.1f}%"


def sweep_table(title, dial_label, values, override_key, secondary_keys_per_value=None):
    """Run both regimes for each value, print a side-by-side comparison table."""
    print()
    print("=" * 90)
    print(f"SWEEP: {title}")
    print("=" * 90)
    headers = [
        f"{dial_label:<22}",
        "regime",
        "P(prop wins)",
        "median prop",
        "median shares",
        "worst-yr cash",
        "P(solvent)",
    ]
    print("  ".join(headers))
    print("-" * 90)

    for v in values:
        secondary = (secondary_keys_per_value or {}).get(v, {})
        for regime in ("current", "restricted_2027"):
            r = run(property_regime=regime, **{override_key: v}, **secondary)
            label = str(v) if not secondary else f"{v}"
            print(
                f"{label:<22}  "
                f"{regime:<16}  "
                f"{fmt_pct(r['p_property_wins'])}        "
                f"{fmt_money(r['median_property_wealth'])}  "
                f"{fmt_money(r['median_shares_wealth'])}  "
                f"{fmt_money(r['worst_year_cash'])}     "
                f"{fmt_pct(r['p_solvent'])}"
            )
        print()


def main():
    print()
    print("BASE SCENARIO:")
    print(f"  $700k purchase, 20% deposit, 25y, 37% MTR, 6% loan, 4% yield, 5.5% growth")
    print(f"  established_post_2017 house, blended portfolio, realistic mode, 2000 trials")

    # 1) Horizon
    sweep_table(
        "Regime impact across horizons (other dials fixed)",
        "horizon (years)", [10, 15, 20, 25, 30], "horizon_years",
    )

    # 2) MTR
    sweep_table(
        "Regime impact across MTR (low MTR sees biggest CGT-floor hit)",
        "MTR", [0.19, 0.30, 0.37, 0.45], "mtr",
    )

    # 3) Deposit
    sweep_table(
        "Regime impact across deposit ratio (more leverage = more NG dependency)",
        "deposit ($)", [70_000, 140_000, 210_000, 280_000], "deposit",
    )

    # 4) Gross yield
    sweep_table(
        "Regime impact across gross yield (high yield = less NG, less affected)",
        "gross yield", [0.03, 0.04, 0.05, 0.06], "gross_yield",
    )

    # 5) Property age
    sweep_table(
        "Regime impact across property age (new build = more Div 43 in pre-period)",
        "property age",
        ["new_build", "established_post_2017", "established_pre_2017"],
        "property_age",
    )


if __name__ == "__main__":
    main()
