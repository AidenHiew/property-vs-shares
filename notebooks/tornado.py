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


def run_regime(regime, **overrides):
    """Run Monte Carlo with a given regime and optional overrides."""
    return run(property_regime=regime, trials=TRIALS, **overrides)


def tornado_for_regime(regime):
    """Compute tornado rows for a single regime. Returns (base_p, rows)."""
    base_result = run_regime(regime)
    base_p = base_result["p_property_succeeds"]

    rows = []
    for (name, low_val, base_val, high_val) in PERTURBATIONS:
        r_low = run_regime(regime, **{name: low_val})
        r_high = run_regime(regime, **{name: high_val})

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


def print_table(regime, base_p, rows):
    print()
    print("=" * 88)
    print(f"TORNADO: regime={regime}")
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
    results = {}
    for regime in REGIMES:
        base_p, rows = tornado_for_regime(regime)
        results[regime] = (base_p, rows)
        print_table(regime, base_p, rows)

    # Interpretation footer
    print()
    print("INTERPRETATION:")
    for regime in REGIMES:
        _, rows = results[regime]
        top = rows[0]
        print(
            f"- Top input under {regime}: {top['name']} drives ~{top['swing']*100:.0f}pp swing"
            f" in p_property_succeeds."
        )

    # Cross-regime insight — find inputs that appear #1 in each regime
    top_current = results["current"][1][0]["name"]
    top_restricted = results["restricted_2027"][1][0]["name"]
    dominant = top_current if top_current == top_restricted else f"{top_current} (current) / {top_restricted} (restricted)"
    swing_current = results["current"][1][0]["swing"] * 100
    swing_restricted = results["restricted_2027"][1][0]["swing"] * 100
    max_swing = max(swing_current, swing_restricted)

    print(
        f"- Implication: the headline is most sensitive to {dominant}. If your conviction"
    )
    print(
        f"  on {dominant} is weak, the model is correspondingly weak (~{max_swing:.0f}pp range)."
    )


if __name__ == "__main__":
    main()
