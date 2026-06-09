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


CGT_DISCOUNT = 0.50
DISCOUNT_HOLDING_THRESHOLD_YEARS = 1.0


def cgt_payable(gain: float, holding_years: float, mtr: float) -> float:
    """CGT on a capital gain. AU resident, 50% discount if held > 12 months.

    Returns 0 for capital losses (offsetting against other gains is out of v1 scope).
    """
    if gain <= 0:
        return 0.0
    if holding_years > DISCOUNT_HOLDING_THRESHOLD_YEARS:
        gain = gain * (1 - CGT_DISCOUNT)
    return gain * mtr


# Federal Budget 2026-27 — indexed CGT regime for established residential property
# acquired after 7:30pm 12 May 2026. Replaces the 50% discount with cost-base
# CPI indexation (caller is responsible for inflating the base) and a minimum
# effective tax rate floor.
CGT_RESTRICTED_MIN_EFFECTIVE_RATE = 0.30


def cgt_payable_indexed(
    indexed_gain: float,
    mtr: float,
    min_effective_rate: float = CGT_RESTRICTED_MIN_EFFECTIVE_RATE,
) -> float:
    """CGT under the Federal Budget 2026-27 indexed regime.

    Effective rate = max(MTR, min_effective_rate). High-MTR earners pay MTR;
    low-MTR earners are floored at the minimum (default 30%).

    Args:
        indexed_gain: capital gain after the cost base has been CPI-indexed and
            after any quarantined-loss offset is applied. Caller responsibility.
        mtr: investor's marginal tax rate.
        min_effective_rate: floor for the effective rate (default 0.30 per the
            12 May 2026 Budget announcement).

    SIMPLIFICATION (announcement-only as of 2026-05-16): the announced "30%
    minimum tax" is modelled as a simple floor on the effective rate. Real
    legislation may interact with progressive brackets, Medicare levy, offsets
    and exemptions in ways this fixed-MTR simplification does not capture.
    Acceptable for a personal-use modeller; revisit when law passes.
    """
    if indexed_gain <= 0:
        return 0.0
    return indexed_gain * max(mtr, min_effective_rate)


# SA land tax bands: (upper_bound, base_tax_at_lower_bound, marginal_rate_above_lower_bound)
# FY2026 SA general (investor) thresholds — placeholder; verify against RevenueSA in production:
# https://revenuesa.sa.gov.au/landtax/rates-and-thresholds
SA_LAND_TAX_BANDS = [
    (833_000,        0,       0.0000),
    (1_212_000,      0,       0.0050),
    (1_756_000,  1_895,       0.0100),
    (float("inf"), 7_335,     0.0240),
]


def sa_land_tax(unimproved_land_value: float) -> float:
    """Annual SA land tax on an investor-held property's unimproved land value."""
    if unimproved_land_value <= 0:
        return 0.0

    prev_upper = 0
    for upper, base, rate in SA_LAND_TAX_BANDS:
        if unimproved_land_value <= upper:
            return base + (unimproved_land_value - prev_upper) * rate
        prev_upper = upper
    return 0.0


from typing import Optional
from config import DIV_43_RATE


def depreciation_for_year(
    property_age: str,
    building_cost: float,
    override: Optional[float] = None,
) -> float:
    """Annual depreciation deduction for an investment property.

    v1 simplification: returns Div 43 (capital works @ 2.5% of building cost) for all property
    ages. Div 40 (plant & equipment) is not modelled in detail — for new builds this would
    add ~$2-3k/yr in early years declining over effective life; user can override.

    Established post-May-2017 properties have Div 40 BLOCKED by the legislative change; only
    Div 43 applies. v1 conservatively applies the same Div-43-only rule across all ages and
    relies on the override for power values with a quantity surveyor schedule.
    """
    if override is not None:
        return float(override)
    if building_cost <= 0:
        return 0.0
    return building_cost * DIV_43_RATE
