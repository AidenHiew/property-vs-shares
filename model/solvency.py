"""Solvency / serviceability tracking.

If property strategy needs more outside-cash in any year than the user can fund, that trial
is marked as a 'forced sale' — meaning the user would have had to sell early at whatever
price the property had reached at that year. v1 simplification: terminal wealth for forced-
sale trials is *not* recalculated; instead they are just flagged so the user can see how often
the strategy actually fails.
"""
import numpy as np


def flag_forced_sales(outside_cash_per_trial_year: np.ndarray, ceiling: float) -> np.ndarray:
    """Return a boolean array (length = trials) flagging trials with any year exceeding ceiling."""
    return (outside_cash_per_trial_year > ceiling).any(axis=1)


def p_solvent(outside_cash_per_trial_year: np.ndarray, ceiling: float) -> float:
    """Fraction of trials where property strategy never breaches the serviceability ceiling."""
    return float(1 - flag_forced_sales(outside_cash_per_trial_year, ceiling).mean())
