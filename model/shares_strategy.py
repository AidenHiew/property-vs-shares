"""Year-by-year shares cashflow simulator + terminal sale.

A single trial = one realisation of the random variables (share returns, etc.).
The Monte Carlo runner calls this many times.

Cashflow accounting:
  - MER is deducted from the fund's NAV by the fund manager — the investor never
    writes a cheque for it. It reduces portfolio_value but NOT cashflow_per_year.
  - With DRP enabled, dividends are reinvested; the only cash outflow is the net
    dividend tax (tax on grossed-up dividend less franking credits).
  - cashflow_per_year = -(dividend_tax + margin_interest + external_contributions)
    This mirrors the property strategy convention: what actually hits the bank account.
"""
from dataclasses import dataclass
from typing import Optional
import numpy as np

from model.tax import franking_credit_refund, cgt_payable


@dataclass
class SharesInputs:
    initial_capital: float
    share_return_path: np.ndarray
    dividend_yield_pct: float
    franked_portion: float
    mer: float
    brokerage_per_trade: float
    drp: bool
    mtr: float
    external_contributions: np.ndarray
    horizon_years: int
    margin_loan_initial: float
    margin_loan_rate_path: Optional[np.ndarray]


@dataclass
class SharesResult:
    cashflow_per_year: np.ndarray
    gross_terminal_value: float
    margin_loan_balance: float
    total_dividends_received: float
    total_dividend_tax: float
    cgt_paid_on_sale: float
    terminal_after_tax_wealth: float
    wealth_per_year: np.ndarray  # mark-to-market PRE-tax: portfolio_value at end of each year


def simulate_shares_trial(inputs: SharesInputs) -> SharesResult:
    """Simulate one trial of the shares strategy.

    v1 supports DRP=True only; DRP=False cashflow is not fully modelled.
    """
    h = inputs.horizon_years
    portfolio_value = inputs.initial_capital
    cumulative_cost_base = inputs.initial_capital

    cashflow_per_year = np.zeros(h)
    wealth_per_year = np.zeros(h)
    total_dividends = 0.0
    total_dividend_tax = 0.0

    margin_balance = inputs.margin_loan_initial
    portfolio_value += margin_balance

    for year in range(h):
        total_return = inputs.share_return_path[year]
        dividend_return = inputs.dividend_yield_pct
        capital_return = total_return - dividend_return

        dividends = portfolio_value * dividend_return
        total_dividends += dividends

        # Bug 2 fix: compute margin-interest tax saving BEFORE accumulating total_dividend_tax.
        div_tax = franking_credit_refund(dividends, inputs.mtr, inputs.franked_portion)

        margin_interest = 0.0
        if inputs.margin_loan_rate_path is not None and margin_balance > 0:
            margin_interest = margin_balance * inputs.margin_loan_rate_path[year]
            # Margin interest is deductible; reduce div_tax by the tax saving.
            div_tax -= margin_interest * inputs.mtr

        # Accumulate AFTER adjusting div_tax for margin-interest saving.
        total_dividend_tax += div_tax

        # MER reduces portfolio NAV internally — not a cash cost to the investor.
        mer_cost = portfolio_value * inputs.mer

        # Apply capital return (price appreciation component only).
        portfolio_value = portfolio_value * (1 + capital_return)

        if inputs.drp:
            # Dividends are reinvested; portfolio grows by dividends minus MER drag.
            portfolio_value += dividends - mer_cost
            cumulative_cost_base += dividends
        else:
            # v1 supports DRP=True only; DRP=False cashflow is not fully modelled.
            portfolio_value -= mer_cost

        portfolio_value += inputs.external_contributions[year]
        cumulative_cost_base += inputs.external_contributions[year]

        # Cashflow = actual cash leaving the investor's bank account.
        # MER is excluded (fund-internal, not out-of-pocket).
        cashflow_per_year[year] = -(div_tax + margin_interest + inputs.external_contributions[year])

        # Mark-to-market portfolio value at end of this year (PRE-tax of hypothetical liquidation).
        wealth_per_year[year] = portfolio_value

    gross_terminal_value = portfolio_value
    capital_gain = gross_terminal_value - cumulative_cost_base
    cgt_paid = cgt_payable(capital_gain, holding_years=h, mtr=inputs.mtr)

    terminal_after_tax_wealth = (
        gross_terminal_value - cgt_paid - margin_balance - inputs.brokerage_per_trade
    )

    return SharesResult(
        cashflow_per_year=cashflow_per_year,
        gross_terminal_value=gross_terminal_value,
        margin_loan_balance=margin_balance,
        total_dividends_received=total_dividends,
        total_dividend_tax=total_dividend_tax,
        cgt_paid_on_sale=cgt_paid,
        terminal_after_tax_wealth=terminal_after_tax_wealth,
        wealth_per_year=wealth_per_year,
    )
