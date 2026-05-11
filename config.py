"""Constants and defaults. When tax law changes, this is the file you mostly edit."""

# FY2026 (2025-26) Stage 3 resident brackets.
# Format: (upper bound, marginal rate on the bracket).
# Source: https://www.ato.gov.au/tax-rates-and-codes/tax-rates-australian-residents
STAGE_3_BRACKETS = [
    (18_200, 0.00),
    (45_000, 0.16),
    (135_000, 0.30),
    (190_000, 0.37),
    (float("inf"), 0.45),
]

# Monte Carlo
TRIALS = 5000
SEED = 42

# CPI default
DEFAULT_CPI = 0.025

from typing import Literal

PropertyAge = Literal["new_build", "established_post_2017", "established_pre_2017"]
AssetType = Literal["house", "apartment", "townhouse"]

# Building cost as % of purchase price, by asset type.
BUILDING_COST_PCT = {
    "house": 0.40,
    "apartment": 0.85,
    "townhouse": 0.65,
}

# Land value as % of purchase price (inverse of building cost).
LAND_VALUE_PCT = {k: 1 - v for k, v in BUILDING_COST_PCT.items()}

# Div 43 rate (capital works deduction)
DIV_43_RATE = 0.025  # 2.5% per year of original construction cost

# Constant share return assumption for v1 "overflow" buckets.
# Used by the property strategy to compound positive cashflow into a parallel
# share portfolio (see model/property_strategy.py). Kept simple and constant
# (not stochastic) because the overflow position is small relative to the main
# property; the actual shares strategy module uses full Monte Carlo.
SHARE_RETURN_FOR_OVERFLOW = 0.085
