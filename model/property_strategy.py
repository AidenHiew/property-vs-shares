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
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from config import BUILDING_COST_PCT, SHARE_RETURN_FOR_OVERFLOW
from model.tax import (
    depreciation_for_year, cgt_payable, cgt_payable_indexed,
    franking_credit_refund,
)
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
    # Acquisition costs incurred at purchase: stamp duty + conveyancing/inspection/
    # loan-application fees. ATO allows these as cost-base inclusions (s110-25 ITAA97).
    # Loan-app fees are technically borrowing costs deductible separately but bundled
    # here for simplicity per BACKLOG §1 note. Default 0.0 preserves backward
    # compatibility for tests that construct PropertyInputs directly without this field.
    acquisition_costs: float = 0.0
    # Overflow share bucket tax assumptions. Positive property cashflow is reinvested
    # in shares (same portfolio profile as the shares strategy); those shares bear
    # franking-adjusted dividend tax annually and CGT at terminal sale. Defaults of 0.0
    # mean "no dividend yield" (CGT still applies) for direct-construction callers; the
    # Monte Carlo runner passes the portfolio profile's div_yield + franked portion.
    overflow_dividend_yield: float = 0.0
    overflow_franked_portion: float = 0.0
    # Flat annual land tax ($). User-supplied, constant across the horizon.
    # Default 0.0 means no land tax (makes property slightly cheaper than reality).
    # Tax-deductible; the cost+deduction wiring yields the correct net land_tax*(1-MTR).
    annual_land_tax: float = 0.0


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
    wealth_per_year: np.ndarray  # mark-to-market PRE-tax: value - balance + overflow_balance, per year
    # --- Per-year breakdown arrays (length = horizon_years) ---
    property_value_path: np.ndarray = field(default=None)        # end-of-year property value
    loan_balance_path: np.ndarray = field(default=None)          # end-of-year loan balance
    rent_path: np.ndarray = field(default=None)                  # gross rent after vacancy
    interest_path: np.ndarray = field(default=None)              # loan interest per year
    other_costs_path: np.ndarray = field(default=None)           # management + maintenance + land tax
    depreciation_path: np.ndarray = field(default=None)          # depreciation (non-cash) per year
    tax_path: np.ndarray = field(default=None)                   # tax on property income (negative = refund)
    overflow_balance_path: np.ndarray = field(default=None)      # overflow share portfolio balance
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

    # Land tax: flat user-supplied annual amount, constant across the horizon.
    # (Per-state land-tax tables are out of scope; editable in the UI, default 0.)
    land_tax_path = np.full(h, inputs.annual_land_tax)

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

    # Overflow share portfolio: any positive year's cashflow is invested in shares
    # (same portfolio profile as the shares strategy). Modelled as a DRP holding so it
    # bears the same tax drag as a real share investment:
    #   - SHARE_RETURN_FOR_OVERFLOW (8.5%) total return splits into a dividend yield
    #     (reinvested, DRP) and the residual capital growth.
    #   - dividends bear franking-adjusted tax each year (paid out of the bucket).
    #   - the terminal gain bears CGT (50% discount, held > 12 months) at sale.
    # This removes the prior +0.5-1.2% bias from compounding the bucket untaxed.
    overflow_div_yield = inputs.overflow_dividend_yield
    overflow_capital_return = SHARE_RETURN_FOR_OVERFLOW - overflow_div_yield
    overflow_balance = 0.0
    overflow_cost_base = 0.0
    overflow_balance_path = np.zeros(h)
    for year in range(h):
        # Dividends on the opening balance, taxed (franking-adjusted) and reinvested (DRP).
        dividends = overflow_balance * overflow_div_yield
        div_tax = franking_credit_refund(dividends, inputs.mtr, inputs.overflow_franked_portion)
        overflow_balance *= (1 + overflow_capital_return)
        overflow_balance += dividends - div_tax
        overflow_cost_base += dividends  # reinvested dividends lift the cost base
        # This year's property surplus is contributed at year-end (no growth this year).
        if cashflow_per_year[year] > 0:
            overflow_balance += cashflow_per_year[year]
            overflow_cost_base += cashflow_per_year[year]
        overflow_balance_path[year] = overflow_balance

    # Terminal CGT on the overflow gain (whole bucket held > 12 months → 50% discount,
    # mirroring the shares strategy's terminal-CGT simplification).
    overflow_gain = overflow_balance - overflow_cost_base
    overflow_cgt = cgt_payable(overflow_gain, holding_years=h, mtr=inputs.mtr)
    overflow_share_terminal_value = overflow_balance - overflow_cgt

    # Mark-to-market wealth per year (PRE-tax of hypothetical sale CGT).
    # Used for path visualisation. Differs from terminal_after_tax_wealth at year h-1
    # because the latter nets selling_costs and CGT.
    wealth_per_year = value_path - balance_path + overflow_balance_path

    # Terminal sale event (end of horizon, year h-1).
    gross_sale_price = value_path[-1]
    selling_costs = gross_sale_price * inputs.selling_costs_pct
    terminal_loan_balance = balance_path[-1]

    # Default traceability outputs (zero unless restricted_2027 path executes).
    commencement_value = 0.0
    pre_commencement_taxable_gain = 0.0
    post_commencement_indexed_gain = 0.0
    terminal_loss_pool_offset = 0.0

    if inputs.property_regime == "restricted_2027":
        # --- Transitional CGT split at end of pre-commencement period ---
        #
        # Acquisition cost is allocated by years held in each period:
        #   pre_years  = restricted_ng_start_year_index  (e.g. 1 for default May-2026 buy)
        #   post_years = h - pre_years
        # Div 43 (constant per year in v1) is split proportionally by years claimed.
        # Selling costs are incurred at the sale event (year h-1, post-commencement)
        # and allocated entirely to the post-commencement cost base.
        # Stamp duty + buying costs aren't in v1 cost base on either side (BACKLOG §1).
        pre_years = inputs.restricted_ng_start_year_index
        post_years = h - pre_years
        assert post_years > 0, (
            f"restricted_ng_start_year_index ({pre_years}) must be < horizon ({h}); "
            "transitional split needs at least 1 post-commencement year"
        )

        div43_pre = annual_depreciation * pre_years
        div43_post = annual_depreciation * post_years
        cumulative_div43 = div43_pre + div43_post

        # Commencement value = modelled property value at end of pre-commencement period.
        # If pre_years = 0 (restriction immediate), commencement = original purchase.
        commencement_value = (
            float(value_path[pre_years - 1]) if pre_years > 0 else float(inputs.purchase_price)
        )

        # Pre-commencement: nominal gain, current 50% discount rules.
        # Cost base = purchase price + acquisition costs (stamp duty + conveyancing/
        # inspections; incurred at purchase, i.e. pre-commencement) - Div 43 claimed
        # in pre-commencement years. No selling costs here (they belong to the sale event).
        pre_cost_base = inputs.purchase_price + inputs.acquisition_costs - div43_pre
        pre_nominal_gain = max(0.0, commencement_value - pre_cost_base)
        # Holding period for the pre-commencement portion. For the default
        # 1-year pre period (May 2026 buy → 1 Jul 2027 commencement = ~13 months),
        # the 50% discount applies. We pass 1.01 to ensure cgt_payable's strict
        # >12-month gate triggers; tweak if pre_years is somehow 0.
        holding_years_pre = max(pre_years, 1.01) if pre_years > 0 else 0.0
        pre_cgt = cgt_payable(pre_nominal_gain, holding_years=holding_years_pre, mtr=inputs.mtr)
        # Trace: post-50%-discount taxable amount (mirrors cgt_payable's internal calc
        # so the user can sanity-check the dollar number that gets taxed at MTR).
        pre_commencement_taxable_gain = (
            pre_nominal_gain * (1 - 0.50) if holding_years_pre > 1.0 else pre_nominal_gain
        )

        # Post-commencement: indexed cost base from commencement value over post_years.
        indexed_post_base = commencement_value * (1 + inputs.cpi) ** post_years
        post_cost_base = indexed_post_base + selling_costs - div43_post
        post_indexed_gain_raw = max(0.0, gross_sale_price - post_cost_base)

        # Loss pool offsets POST-commencement gain only (conservative: pool only grew
        # post-commencement under the restricted regime, so applying it pre would
        # over-credit the carry-forward).
        if residential_property_loss_pool > 0:
            terminal_loss_pool_offset = min(
                residential_property_loss_pool, post_indexed_gain_raw
            )
            post_indexed_gain = post_indexed_gain_raw - terminal_loss_pool_offset
        else:
            post_indexed_gain = post_indexed_gain_raw

        post_commencement_indexed_gain = post_indexed_gain
        post_cgt = cgt_payable_indexed(post_indexed_gain, mtr=inputs.mtr)
        cgt_paid = pre_cgt + post_cgt

    else:
        # Current regime: nominal cost base + 50% discount via cgt_payable.
        # Includes acquisition costs (stamp duty + conveyancing/inspection/loan-app fees;
        # loan-app fees are technically borrowing costs deductible separately but bundled
        # here for simplicity per BACKLOG §1 note).
        cumulative_div43 = annual_depreciation * h  # all v1 depreciation treated as Div 43
        cost_base = inputs.purchase_price + inputs.acquisition_costs + selling_costs - cumulative_div43
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
        wealth_per_year=wealth_per_year,
        # Per-year breakdown arrays
        property_value_path=value_path,
        loan_balance_path=balance_path,
        rent_path=rent_path,
        interest_path=interest_path,
        other_costs_path=management_path + maintenance_path + land_tax_path,
        depreciation_path=depreciation_path,
        tax_path=tax_on_property,
        overflow_balance_path=overflow_balance_path,
        # Restricted regime traceability
        terminal_loss_pool_offset=terminal_loss_pool_offset,
        commencement_value=commencement_value,
        pre_commencement_taxable_gain=pre_commencement_taxable_gain,
        post_commencement_indexed_gain=post_commencement_indexed_gain,
    )
