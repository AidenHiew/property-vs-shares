"""Inflation helper tests."""
import pytest
import numpy as np
from model.inflation import inflate, deflate, inflate_series


def test_inflate_zero_years_identity():
    assert inflate(1000, years=0, cpi=0.025) == 1000


def test_inflate_one_year():
    assert inflate(1000, years=1, cpi=0.025) == pytest.approx(1025)


def test_inflate_compound():
    # $1000 inflated 10 yrs at 2.5% = 1000 * 1.025^10 ≈ 1280.08
    assert inflate(1000, years=10, cpi=0.025) == pytest.approx(1280.08, rel=1e-3)


def test_deflate_round_trip():
    # inflate then deflate = identity
    inflated = inflate(1000, years=10, cpi=0.025)
    assert deflate(inflated, years=10, cpi=0.025) == pytest.approx(1000)


def test_inflate_series_vectorised():
    # $1000 across years 0..3 at 2.5%
    result = inflate_series(1000, years=4, cpi=0.025)
    assert isinstance(result, np.ndarray)
    assert result[0] == pytest.approx(1000)
    assert result[1] == pytest.approx(1025)
    assert result[2] == pytest.approx(1050.625)
    assert result[3] == pytest.approx(1076.890625)
