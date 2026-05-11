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


COMPANY_TAX_RATE = 0.30


def franking_credit_refund(cash_dividend: float, mtr: float, franked_portion: float) -> float:
    """Net tax payable on a dividend after franking credits.

    Returns positive for tax owed, negative for cash refund (excess credits).

    Args:
        cash_dividend: gross cash dividend received (before franking gross-up)
        mtr: investor's marginal tax rate (0.0 to 0.45)
        franked_portion: fraction of the dividend that's franked (0.0 to 1.0)
    """
    if cash_dividend <= 0:
        return 0.0

    franked_cash = cash_dividend * franked_portion
    unfranked_cash = cash_dividend * (1 - franked_portion)

    # Franking credit attached to the franked portion
    franking_credit = franked_cash * COMPANY_TAX_RATE / (1 - COMPANY_TAX_RATE)
    grossed_up = franked_cash + franking_credit + unfranked_cash

    tax_before_credit = grossed_up * mtr
    return tax_before_credit - franking_credit
