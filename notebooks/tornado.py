"""Tornado (one-at-a-time) sensitivity analysis on p_property_succeeds.

Perturbs 10 key inputs ±1 economically-meaningful delta from BASE under both
regimes; ranks by swing in joint success probability.

Run from the project root with the venv active:

    PYTHONPATH=. python notebooks/tornado.py
"""
from notebooks.scenario_sweep import BASE, run  # noqa: F401 — re-exported by name

TRIALS = 2000

PERTURBATIONS = [
    # (input_name,          low,       base,   high)
    ("property_growth_mu",  0.045,     0.055,  0.065),
    ("property_growth_sigma", 0.09,    0.11,   0.13),
    ("share_return_mu",     0.075,     0.085,  0.095),
    ("share_return_sigma",  0.12,      0.15,   0.18),
    ("loan_rate_mu",        0.05,      0.06,   0.07),
    ("gross_yield",         0.035,     0.04,   0.045),
    ("correlation",         -0.1,      0.3,    0.6),
    ("mtr",                 0.30,      0.37,   0.45),
    ("deposit",             100_000,   140_000, 200_000),
    ("cpi",                 0.02,      0.025,  0.03),
]

REGIMES = ("current", "restricted_2027")

FAT_TAILED_KWARGS = dict(
    return_distribution="student_t",
    t_df=5,
    loan_rate_distribution="student_t",
    loan_rate_t_df=5,
)


def run_regime(regime, dist_kwargs=None, **overrides):
    """Run Monte Carlo with a given regime and optional overrides."""
    kwargs = dict(dist_kwargs) if dist_kwargs else {}
    kwargs.update(overrides)
    return run(property_regime=regime, trials=TRIALS, **kwargs)


def tornado_for_regime(regime, dist_kwargs=None):
    """Compute tornado rows for a single regime. Returns (base_p, rows)."""
    base_result = run_regime(regime, dist_kwargs=dist_kwargs)
    base_p = base_result["p_property_succeeds"]

    rows = []
    for (name, low_val, base_val, high_val) in PERTURBATIONS:
        r_low = run_regime(regime, dist_kwargs=dist_kwargs, **{name: low_val})
        r_high = run_regime(regime, dist_kwargs=dist_kwargs, **{name: high_val})

        p_low = r_low["p_property_succeeds"]
        p_high = r_high["p_property_succeeds"]

        delta_low = p_low - base_p
        delta_high = p_high - base_p
        swing = abs(delta_high - delta_low)

        rows.append(dict(
            name=name,
            low_val=low_val,
            base_val=base_val,
            high_val=high_val,
            delta_low=delta_low,
            delta_high=delta_high,
            swing=swing,
        ))

    rows.sort(key=lambda r: r["swing"], reverse=True)
    return base_p, rows


def fmt_delta(d):
    sign = "+" if d >= 0 else ""
    return f"{sign}{d*100:.1f}pp"


def print_table(regime, base_p, rows, dist_label="Gaussian"):
    print()
    print("=" * 88)
    print(f"TORNADO ({dist_label}): regime={regime}")
    print(f"BASE p_property_succeeds = {base_p*100:.1f}%")
    print("=" * 88)
    header = (
        f"{'input':<26}  {'low value':>10}  {'base':>8}  {'high value':>10}"
        f"  {'Δ low':>8}  {'Δ high':>8}  {'swing':>8}"
    )
    print(header)
    print("-" * 88)
    for r in rows:
        print(
            f"{r['name']:<26}  {r['low_val']:>10.4g}  {r['base_val']:>8.4g}  {r['high_val']:>10.4g}"
            f"  {fmt_delta(r['delta_low']):>8}  {fmt_delta(r['delta_high']):>8}  {r['swing']*100:>7.1f}pp"
        )


def main():
    # --- Gaussian pass ---
    gaussian_results = {}
    for regime in REGIMES:
        base_p, rows = tornado_for_regime(regime, dist_kwargs=None)
        gaussian_results[regime] = (base_p, rows)
        print_table(regime, base_p, rows, dist_label="Gaussian")

    # --- Fat-tailed pass ---
    print()
    print("#" * 88)
    print("# NOW WITH FAT-TAILED DISTRIBUTIONS (Student-t df=5 on returns AND rates)        #")
    print("#" * 88)

    fat_results = {}
    for regime in REGIMES:
        base_p, rows = tornado_for_regime(regime, dist_kwargs=FAT_TAILED_KWARGS)
        fat_results[regime] = (base_p, rows)
        print_table(regime, base_p, rows, dist_label="Student-t df=5")

    # Interpretation footer
    print()
    print("INTERPRETATION:")

    # Gaussian summary
    print("  [Gaussian]")
    for regime in REGIMES:
        _, rows = gaussian_results[regime]
        top = rows[0]
        print(
            f"  - Top input under {regime}: {top['name']} drives ~{top['swing']*100:.0f}pp swing"
            f" in p_property_succeeds."
        )

    top_current_g = gaussian_results["current"][1][0]["name"]
    top_restricted_g = gaussian_results["restricted_2027"][1][0]["name"]
    dominant_g = top_current_g if top_current_g == top_restricted_g else f"{top_current_g} (current) / {top_restricted_g} (restricted)"
    swing_restricted_g = gaussian_results["restricted_2027"][1][0]["swing"] * 100

    print(f"  - Gaussian headline driver: {dominant_g} (~{swing_restricted_g:.0f}pp range under restricted_2027).")

    # Fat-tailed summary
    print("  [Student-t df=5]")
    for regime in REGIMES:
        _, rows = fat_results[regime]
        top = rows[0]
        print(
            f"  - Top input under {regime}: {top['name']} drives ~{top['swing']*100:.0f}pp swing"
            f" in p_property_succeeds."
        )

    top_current_f = fat_results["current"][1][0]["name"]
    top_restricted_f = fat_results["restricted_2027"][1][0]["name"]
    dominant_f = top_current_f if top_current_f == top_restricted_f else f"{top_current_f} (current) / {top_restricted_f} (restricted)"

    # loan_rate_mu robustness check
    fat_restricted_rows = fat_results["restricted_2027"][1]
    loan_rate_row_fat = next((r for r in fat_restricted_rows if r["name"] == "loan_rate_mu"), None)
    loan_rate_rank_fat = next(
        (i + 1 for i, r in enumerate(fat_restricted_rows) if r["name"] == "loan_rate_mu"), None
    )
    loan_rate_swing_fat = loan_rate_row_fat["swing"] * 100 if loan_rate_row_fat else None

    still_dominant = (top_restricted_f == "loan_rate_mu")
    if still_dominant:
        robustness_msg = (
            f"  - ROBUST: loan_rate_mu is STILL the top driver under restricted_2027 + Student-t df=5"
            f" ({loan_rate_swing_fat:.0f}pp swing). The leveraged-bet-on-rates thesis holds across"
            f" both distribution choices."
        )
    else:
        robustness_msg = (
            f"  - REVISED: loan_rate_mu is NO LONGER top driver under restricted_2027 + Student-t df=5"
            f" (rank #{loan_rate_rank_fat}, swing {loan_rate_swing_fat:.0f}pp)."
            f" Top driver is now {top_restricted_f}. Reconsider the leveraged-bet-on-rates headline."
        )

    print(robustness_msg)
    print(
        f"  - Fat-tailed headline driver: {dominant_f}."
    )


if __name__ == "__main__":
    main()
