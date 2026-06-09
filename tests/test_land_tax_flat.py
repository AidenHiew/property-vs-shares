import numpy as np
from model.property_strategy import PropertyInputs, simulate_property_trial


def _base_inputs(annual_land_tax):
    h = 10
    return PropertyInputs(
        purchase_price=700_000, deposit=140_000,
        loan_rate_path=np.full(h, 0.06), loan_term_years=30, io_period_years=5,
        gross_yield=0.04, vacancy_weeks_path=np.zeros(h), capital_growth_path=np.full(h, 0.05),
        management_fee_pct=0.07, maintenance_pct=0.01, property_age="established_post_2017",
        asset_type="house", depreciation_override=None, mtr=0.37, cpi=0.025, horizon_years=h,
        selling_costs_pct=0.025, acquisition_costs=30_000, property_regime="current",
        overflow_dividend_yield=0.04, overflow_franked_portion=0.8,
        annual_land_tax=annual_land_tax,
    )


def test_land_tax_zero_is_baseline():
    r = simulate_property_trial(_base_inputs(0.0))
    assert r.other_costs_path is not None


def test_land_tax_increases_cost_and_deducts():
    r0 = simulate_property_trial(_base_inputs(0.0))
    r1 = simulate_property_trial(_base_inputs(3_000.0))
    assert r1.other_costs_path[0] - r0.other_costs_path[0] == 3_000.0
    drag = (r0.terminal_after_tax_wealth + r0.overflow_share_terminal_value) \
         - (r1.terminal_after_tax_wealth + r1.overflow_share_terminal_value)
    assert drag > 0
