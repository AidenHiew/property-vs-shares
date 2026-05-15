"""Year-by-year property cashflow simulator + terminal sale.

A single trial = one realisation of the random variables (capital growth, loan rate,
vacancy, etc.). The Monte Carlo runner calls this 5000 times.

Cashflow accounting:
  - Cash costs (management, maintenance, insurance/rates, loan interest, land tax) reduce
    cash AND reduce taxable income.
  - Depreciation reduces taxable income but is NON-CASH.
  - After-tax cashflow = (rent - cash costs) - tax_on_property
    where tax_on_property = (rent - cash costs - depreciation) * MTR
    (a NEGATIVE tax means the user gets a refund / reduction in other tax — this is
    negative gearing.)
"""
from dataclasses import dataclass
from typing import Optional
import numpy as np

from config import BUILDING_COST_PCT, LAND_VALUE_PCT, SHARE_RETURN_FOR_OVERFLOW
from model.tax import sa_land_tax, depreciation_for_year, cgt_payable
from model.inflation import inflate_series


@dataclass
class PropertyInputs:
    """All inputs the property strategy needs for one trial."""
    purchase_price: float
    deposit: float
    loan_rate_path: np.ndarray  # length = horizon_years; per-year loan rate (stochastic)
    loan_term_years: int
    io_period_years: int
    gross_yield: float
    vacancy_weeks_path: np.ndarray  # length = horizon_years
    capital_growth_path: np.ndarray  # length = horizon_years
    management_fee_pct: float
    maintenance_pct: float
    property_age: str
    asset_type: str
    depreciation_override: Optional[float]
    mtr: float
    cpi: float
    horizon_years: int
    selling_costs_pct: float
    # --- Federal Budget 2026-27 regime ---
    # "current": status quo (full NG + 50% CGT discount).
    # "restricted_2027": NG losses quarantined to residential property income/gains from
    # commencement; CGT splits at commencement (current rules pre-, indexed + 30%-min rate
    # post-). See docs/2026-05-16-budget-2026-27-design.md.
    property_regime: str = "current"
    # End of model year (this index) = commencement boundary. Default 1 = year 1 is
    # pre-commencement (FY2027, current rules); year 2+ is post-commencement (FY2028+,
    # restricted rules). Matches a May-2026 today-purchase.
    restricted_ng_start_year_index: int = 1


@dataclass
class PropertyResult:
    """All outputs from one property trial."""
    cashflow_per_year: np.ndarray
    cumulative_div43_claimed: float
    gross_sale_price: float
    terminal_loan_balance: float
    cgt_paid_on_sale: float
    selling_costs: float
    terminal_after_tax_wealth: float
    overflow_share_terminal_value: float
    outside_cash_required_per_year: np.ndarray  # = max(0, -cashflow); used by shares strategy
    # --- Restricted regime traceability (zero under "current" regime) ---
    terminal_loss_pool_offset: float = 0.0           # pool $ used against post-commencement gain
    commencement_value: float = 0.0                  # property value at end of pre-commencement period
    pre_commencement_taxable_gain: float = 0.0       # nominal gain × 50% discount (pre-commencement)
    post_commencement_indexed_gain: float = 0.0      # indexed gain after pool offset


def _annual_loan_balance_and_interest(
    initial_loan: float,
    rate_path: np.ndarray,
    term_years: int,
    io_period: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (interest_per_year, balance_per_year) over the horizon.

    During IO period: principal stays at initial_loan; interest = balance * rate.
    Post IO: P&I amortisation across remaining term using each year's rate.
    """
    horizon = len(rate_path)
    balance = np.zeros(horizon)
    interest = np.zeros(horizon)
    current_balance = initial_loan

    for year in range(horizon):
        r = rate_path[year]
        if year < io_period:
            interest[year] = current_balance * r
            balance[year] = current_balance
        else:
            years_remaining = term_years - year
            if years_remaining <= 0:
                interest[year] = 0
                balance[year] = 0
                continue
            if r > 0:
                payment = current_balance * (r * (1 + r) ** years_remaining) / ((1 + r) ** years_remaining - 1)
            else:
                payment = current_balance / years_remaining
            interest[year] = current_balance * r
            principal = max(0, payment - interest[year])
            current_balance = max(0, current_balance - principal)
            balance[year] = current_balance

    return interest, balance


def simulate_property_trial(inputs: PropertyInputs) -> PropertyResult:
    """Simulate one trial of the property strategy."""
    h = inputs.horizon_years
    initial_loan = inputs.purchase_price - inputs.deposit
    assert h <= inputs.loan_term_years, (
        f"horizon_years ({h}) must be <= loan_term_years ({inputs.loan_term_years}); "
        "v1 doesn't model holding past full loan amortisation"
    )

    # Property value path: end-of-year values after applying capital growth each year.
    # value_path[0] = purchase_price * (1 + g[0])  (end of year 1)
    # value_path[k] = purchase_price * prod(1 + g[0..k])
    value_path = inputs.purchase_price * np.cumprod(1 + inputs.capital_growth_path)

    # Rent path: gross_yield applied to the START-of-year value (before that year's growth).
    # Year 1 rent is on the purchase price; year 2 rent is on value at end of year 1, etc.
    # start_of_year_values[0] = purchase_price
    # start_of_year_values[k] = value_path[k-1]  for k >= 1
    start_of_year_values = np.empty(h)
    start_of_year_values[0] = inputs.purchase_price
    start_of_year_values[1:] = value_path[:-1]

    occupied_weeks = 52 - inputs.vacancy_weeks_path
    rent_path = inputs.gross_yield * start_of_year_values * occupied_weeks / 52

    # Maintenance: % of purchase price, inflated by CPI annually.
    base_maintenance = inputs.purchase_price * inputs.maintenance_pct
    maintenance_path = inflate_series(base_maintenance, h, inputs.cpi)

    # Management: % of rent (auto-tracks rent inflation via value growth).
    management_path = rent_path * inputs.management_fee_pct

    # Loan interest + balance per year.
    interest_path, balance_path = _annual_loan_balance_and_interest(
        initial_loan, inputs.loan_rate_path, inputs.loan_term_years, inputs.io_period_years
    )

    # Land tax (annual, on unimproved land value at start of year).
    # Year 1 land value = purchase_price * LAND_VALUE_PCT (e.g. $420k for a house at $700k).
    land_value_path = start_of_year_values * LAND_VALUE_PCT[inputs.asset_type]
    land_tax_path = np.array([sa_land_tax(v) for v in land_value_path])

    # Depreciation (constant per year in v1, from building cost).
    building_cost = inputs.purchase_price * BUILDING_COST_PCT[inputs.asset_type]
    annual_depreciation = depreciation_for_year(
        property_age=inputs.property_age,
        building_cost=building_cost,
        override=inputs.depreciation_override,
    )
    depreciation_path = np.full(h, annual_depreciation)

    # After-tax cashflow per year.
    # Cash costs: those that actually leave the bank account.
    cash_costs_path = management_path + maintenance_path + interest_path + land_tax_path
    pre_tax_cash = rent_path - cash_costs_path
    # Taxable income from property: includes depreciation as a (non-cash) deduction.
    taxable_income = rent_path - cash_costs_path - depreciation_path

    # Tax on property income — branches on regime.
    # Under "current": rental losses generate a refund against other income at MTR
    # (negative gearing). Under "restricted_2027" from the start year onwards, losses
    # are quarantined to a residential property loss pool — no refund. The pool is
    # consumed by future rental surpluses (offsetting taxable income before MTR is
    # applied) and any remainder offsets the post-commencement capital gain at sale.
    residential_property_loss_pool = 0.0
    tax_on_property = np.zeros(h)
    for year in range(h):
        ti = taxable_income[year]
        is_restricted = (
            inputs.property_regime == "restricted_2027"
            and year >= inputs.restricted_ng_start_year_index
        )
        if not is_restricted:
            tax_on_property[year] = ti * inputs.mtr  # negative = refund
        else:
            if ti >= 0:
                # Rental surplus — pool absorbs first, MTR on remainder
                offset = min(ti, residential_property_loss_pool)
                residential_property_loss_pool -= offset
                tax_on_property[year] = (ti - offset) * inputs.mtr
            else:
                # Rental loss — no refund; quarantine
                tax_on_property[year] = 0.0
                residential_property_loss_pool += -ti

    cashflow_per_year = pre_tax_cash - tax_on_property

    # Overflow share portfolio: any positive year's cashflow is invested in shares.
    # Use a constant share return for v1 (overflow is small; full Monte Carlo treatment
    # lives on the shares strategy module). 8.5% pre-tax, no dividend tax drag (v1 simplification).
    overflow_balance = 0.0
    for year in range(h):
        overflow_balance *= (1 + SHARE_RETURN_FOR_OVERFLOW)
        if cashflow_per_year[year] > 0:
            overflow_balance += cashflow_per_year[year]
            # Note: future years' cashflow array is not affected — we just track the parallel bucket.

    overflow_share_terminal_value = overflow_balance

    # Terminal sale event (end of horizon, year h-1).
    gross_sale_price = value_path[-1]
    selling_costs = gross_sale_price * inputs.selling_costs_pct
    terminal_loan_balance = balance_path[-1]

    # Cost base: purchase price + selling costs (capitalised) - cumulative Div 43 claimed.
    # (Stamp duty + buying costs added by comparison engine; not included here.)
    cumulative_div43 = annual_depreciation * h  # all v1 depreciation treated as Div 43
    cost_base = inputs.purchase_price + selling_costs - cumulative_div43
    capital_gain = gross_sale_price - cost_base
    cgt_paid = cgt_payable(capital_gain, holding_years=h, mtr=inputs.mtr)

    terminal_after_tax_wealth = (
        gross_sale_price - selling_costs - terminal_loan_balance - cgt_paid
    )

    outside_cash_required_per_year = np.where(
        cashflow_per_year < 0, -cashflow_per_year, 0
    )

    return PropertyResult(
        cashflow_per_year=cashflow_per_year,
        cumulative_div43_claimed=cumulative_div43,
        gross_sale_price=gross_sale_price,
        terminal_loan_balance=terminal_loan_balance,
        cgt_paid_on_sale=cgt_paid,
        selling_costs=selling_costs,
        terminal_after_tax_wealth=terminal_after_tax_wealth,
        overflow_share_terminal_value=overflow_share_terminal_value,
        outside_cash_required_per_year=outside_cash_required_per_year,
    )
