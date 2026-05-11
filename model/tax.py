"""Pure tax functions. No I/O, no globals (other than reading config)."""
from typing import Iterable
from config import STAGE_3_BRACKETS


def marginal_tax(taxable_income: float, brackets: Iterable[tuple] = None) -> float:
    """Return total income tax on a positive taxable income.

    Negative income returns 0 — losses do not refund prior tax in isolation.
    Excludes Medicare Levy and any offsets (out of v1 scope).
    """
    if taxable_income <= 0:
        return 0.0
    if brackets is None:
        brackets = STAGE_3_BRACKETS

    tax = 0.0
    prev_upper = 0.0
    for upper, rate in brackets:
        if taxable_income <= upper:
            tax += (taxable_income - prev_upper) * rate
            return tax
        tax += (upper - prev_upper) * rate
        prev_upper = upper
    return tax
