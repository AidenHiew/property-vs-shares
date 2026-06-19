import pytest

from app_compare import clamp_horizon, clamp_rate, clamp_deposit, clamp_topup


def test_clamp_horizon_valid_and_invalid():
    assert clamp_horizon(10) == 10
    assert clamp_horizon(7) == 10        # not in {5,10,15,20} → default 10
    assert clamp_horizon("None") == 10   # malformed
    assert clamp_horizon(20) == 20


def test_clamp_rate_bounds():
    assert clamp_rate(0.062) == 0.062
    assert clamp_rate(-1) == 0.0
    assert clamp_rate(0.9) == 0.30       # cap at 30%
    assert clamp_rate("junk") == 0.062   # default


def test_clamp_deposit_not_above_price():
    assert clamp_deposit(190_000, price=950_000) == 190_000
    assert clamp_deposit(2_000_000, price=950_000) == 950_000
    assert clamp_deposit(-5, price=950_000) == 0


def test_clamp_topup_floor_zero():
    assert clamp_topup(20_000) == 20_000
    assert clamp_topup(-100) == 0
    assert clamp_topup("None") == 20_000
