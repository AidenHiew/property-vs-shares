"""National conveyance/stamp duty for an investment property purchase.

Each state's schedule is a list of typed segments evaluated against the
purchase price. Segment kinds:
  - "marginal": duty = base + rate * (price - lower_bound), for price in (lower, upper].
  - "flat_pct": duty = rate * price  (the WHOLE price), for price in (lower, upper].
NT uses a quadratic for price <= 525k; see model.duty._nt_duty.

Registration/transfer fees levied by separate agencies (Land Services SA,
NSW LRS, etc.) are NOT included — the app's buying_costs approximates them.
Foreign-purchaser surcharges are out of scope. Schedules are FY2025-26,
sourced from official state revenue offices 2026-06-09 (see spec).
"""

INF = float("inf")

# Each segment: (lower_bound, upper_bound, kind, a, b)
#   marginal: a = base_duty_at_lower_bound, b = marginal_rate
#     duty = a + (price - lower_bound) * b
#   flat_pct: a is ignored (use None), b = flat rate on full price
#     duty = b * price
DUTY_SCHEDULES = {
    "NSW": [
        (0,         17_000,    "marginal", 0,       0.0125),
        (17_000,    37_000,    "marginal", 212,     0.0150),
        (37_000,    99_000,    "marginal", 512,     0.0175),
        (99_000,    372_000,   "marginal", 1_597,   0.0350),
        (372_000,   1_240_000, "marginal", 11_152,  0.0450),
        (1_240_000, 3_721_000, "marginal", 50_212,  0.0550),
        (3_721_000, INF,       "marginal", 186_667, 0.0700),
    ],
    "VIC": [
        (0,          25_000,    "marginal", 0,       0.014),
        (25_000,     130_000,   "marginal", 350,     0.024),
        (130_000,    960_000,   "marginal", 2_870,   0.060),
        (960_000,    2_000_000, "flat_pct", None,    0.055),
        (2_000_000,  INF,       "marginal", 110_000, 0.065),
    ],
    "QLD": [
        (0,          5_000,     "marginal", 0,      0.000),
        (5_000,      75_000,    "marginal", 0,      0.015),
        (75_000,     540_000,   "marginal", 1_050,  0.035),
        (540_000,    1_000_000, "marginal", 17_325, 0.045),
        (1_000_000,  INF,       "marginal", 38_025, 0.0575),
    ],
    "WA": [
        (0,        120_000, "marginal", 0,      0.0190),
        (120_000,  150_000, "marginal", 2_280,  0.0285),
        (150_000,  360_000, "marginal", 3_135,  0.0380),
        (360_000,  725_000, "marginal", 11_115, 0.0475),
        (725_000,  INF,     "marginal", 28_453, 0.0515),
    ],
    "SA": [
        (0,        12_000,  "marginal", 0,      0.0100),
        (12_000,   30_000,  "marginal", 120,    0.0200),
        (30_000,   50_000,  "marginal", 480,    0.0300),
        (50_000,   100_000, "marginal", 1_080,  0.0350),
        (100_000,  200_000, "marginal", 2_830,  0.0400),
        (200_000,  250_000, "marginal", 6_830,  0.0425),
        (250_000,  300_000, "marginal", 8_955,  0.0475),
        (300_000,  500_000, "marginal", 11_330, 0.0500),
        (500_000,  INF,     "marginal", 21_330, 0.0550),
    ],
    "TAS": [
        (0,        3_000,   "marginal", 50,     0.000),
        (3_000,    25_000,  "marginal", 50,     0.0175),
        (25_000,   75_000,  "marginal", 435,    0.0225),
        (75_000,   200_000, "marginal", 1_560,  0.035),
        (200_000,  375_000, "marginal", 5_935,  0.040),
        (375_000,  725_000, "marginal", 12_935, 0.0425),
        (725_000,  INF,     "marginal", 27_810, 0.045),
    ],
    "ACT": [
        (0,          200_000,   "marginal", 0,      0.0120),
        (200_000,    300_000,   "marginal", 2_400,  0.0220),
        (300_000,    500_000,   "marginal", 4_600,  0.0340),
        (500_000,    750_000,   "marginal", 11_400, 0.0432),
        (750_000,    1_000_000, "marginal", 22_200, 0.0590),
        (1_000_000,  1_455_000, "marginal", 36_950, 0.0640),
        (1_455_000,  INF,       "flat_pct", None,   0.0454),
    ],
    # NT uses a quadratic formula; see _nt_duty. Sentinel entry keeps
    # DUTY_SCHEDULES as the complete state registry.
    "NT": [],
}


def _eval_segments(segments, price):
    for lower, upper, kind, a, b in segments:
        if price <= upper:
            if kind == "flat_pct":
                return b * price
            return a + (price - lower) * b
    return 0.0


def _nt_duty(price):
    """NT: quadratic for price <= 525k, then flat % of full value."""
    if price <= 525_000:
        v = price / 1000.0
        return 0.06571441 * v * v + 15 * v
    if price < 3_000_000:
        return 0.0495 * price
    if price < 5_000_000:
        return 0.0575 * price
    return 0.0595 * price


def stamp_duty(state, price):
    """Conveyance/stamp duty for an investment purchase in `state` at `price`."""
    if price <= 0:
        return 0.0
    if state == "NT":
        return _nt_duty(price)
    return _eval_segments(DUTY_SCHEDULES[state], price)
