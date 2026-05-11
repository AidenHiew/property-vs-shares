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
