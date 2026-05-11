"""Normalisation tests."""
import pytest
import numpy as np
from model.normalisation import build_shares_inputs_for_mode_a


def test_mode_a_shares_starts_with_property_total_upfront():
    """Mode A: shares starts with deposit + stamp duty + buying costs (not just deposit)."""
    s_inputs = build_shares_inputs_for_mode_a(
        purchase_price=700_000,
        deposit=140_000,
        stamp_duty=32_330,
        buying_costs=2_600,  # conveyancing + inspection + loan app
        mtr=0.37,
        horizon_years=25,
        portfolio_profile="blended",
    )
    assert s_inputs.initial_capital == pytest.approx(140_000 + 32_330 + 2_600)


from model.normalisation import build_shares_inputs_for_mode_b


def test_mode_b_shares_takes_margin_loan_to_match_exposure():
    """Mode B: shares matches property's total exposure ($700k)."""
    s_inputs = build_shares_inputs_for_mode_b(
        purchase_price=700_000,
        deposit=140_000,
        stamp_duty=32_330,
        buying_costs=2_600,
        mtr=0.37,
        horizon_years=25,
        portfolio_profile="blended",
        margin_loan_rate=0.075,
        isolate_asset_quality=False,
        mortgage_rate=0.06,
    )
    # Initial capital (equity) = property's upfront cash
    assert s_inputs.initial_capital == pytest.approx(140_000 + 32_330 + 2_600)
    # Margin loan brings total exposure to property's purchase price ($700k)
    assert s_inputs.margin_loan_initial == pytest.approx(700_000 - (140_000 + 32_330 + 2_600))


def test_mode_b_isolate_asset_quality_uses_mortgage_rate():
    s_inputs = build_shares_inputs_for_mode_b(
        purchase_price=700_000,
        deposit=140_000,
        stamp_duty=32_330,
        buying_costs=2_600,
        mtr=0.37,
        horizon_years=25,
        portfolio_profile="blended",
        margin_loan_rate=0.075,
        isolate_asset_quality=True,
        mortgage_rate=0.06,
    )
    assert s_inputs.margin_loan_rate_path[0] == pytest.approx(0.06)
