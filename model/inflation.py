"""CPI-based inflation / deflation helpers. Used to inflate rent and holding costs over
the model horizon, and to deflate output dollar figures for the 'today's dollars' display."""

import numpy as np


def inflate(value: float, years: float, cpi: float = 0.025) -> float:
    """Compound-inflate a value forward by `years` at `cpi` rate."""
    return value * (1 + cpi) ** years


def deflate(value: float, years: float, cpi: float = 0.025) -> float:
    """Compound-deflate a future value back to today's dollars."""
    return value / (1 + cpi) ** years


def inflate_series(value: float, years: int, cpi: float = 0.025) -> np.ndarray:
    """Return an array of the value compounded across years 0..years-1.

    Year 0 = original value, year 1 = value * (1+cpi), etc.
    """
    multipliers = (1 + cpi) ** np.arange(years)
    return value * multipliers
