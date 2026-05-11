"""Solvency tests."""
import pytest
import numpy as np
from model.solvency import flag_forced_sales


def test_no_forced_sale_when_all_under_ceiling():
    outside_cash = np.array([
        [5_000, 5_000, 5_000],
        [3_000, 4_000, 6_000],
    ])
    flags = flag_forced_sales(outside_cash, ceiling=20_000)
    assert flags.sum() == 0


def test_forced_sale_when_year_exceeds_ceiling():
    outside_cash = np.array([
        [5_000, 25_000, 5_000],   # year 1 breach
        [3_000, 4_000, 30_000],   # year 2 breach
        [5_000, 5_000, 5_000],    # never breaches
    ])
    flags = flag_forced_sales(outside_cash, ceiling=20_000)
    assert flags.tolist() == [True, True, False]


def test_p_solvent_metric():
    from model.solvency import p_solvent
    outside_cash = np.array([
        [5_000, 25_000, 5_000],
        [5_000, 5_000, 5_000],
        [3_000, 4_000, 5_000],
        [5_000, 5_000, 30_000],
    ])
    # 2 of 4 trials never breach
    assert p_solvent(outside_cash, ceiling=20_000) == 0.5
