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
