import numpy as np
import pytest

from ui.verdict import (
    VerdictNumbers, compute_verdict, _badge_state, _crossover_year,
    _loudness, _cross_tab_j,
)


# ---------------------------------------------------------------------------
# _badge_state
# ---------------------------------------------------------------------------
def test_badge_state_neutral_band():
    for wr in (45, 50, 55):
        leader, state, label = _badge_state(wr)
        assert leader == "tie"
        assert state == "neutral"
        assert label == ""


def test_badge_state_property_badge_at_60():
    leader, state, label = _badge_state(68)
    assert leader == "property"
    assert state == "badge"
    assert label == "Ahead in most futures"


def test_badge_state_property_border_between_55_and_60():
    leader, state, label = _badge_state(57)
    assert leader == "property"
    assert state == "border"
    assert label == ""


def test_badge_state_shares_lead_uses_complement():
    leader, state, label = _badge_state(30)  # property wins 30 → shares lead 70
    assert leader == "shares"
    assert state == "badge"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def test_crossover_year_returns_first_self_funding_year():
    cashflow = np.array([
        [-100, -50, 10, 20],
        [-120, -40, 30, 25],
        [-110, -45, 20, 22],
    ], dtype=float)  # median per col: -110, -45, 20, 22 → first ≥0 at col 2 (year 3)
    assert _crossover_year(cashflow) == 3


def test_crossover_year_none_when_never_positive():
    cashflow = np.array([
        [-100, -90, -80, -70],
        [-110, -95, -85, -75],
    ], dtype=float)
    assert _crossover_year(cashflow) is None


def test_loudness_tiers():
    assert _loudness(15_000, 20_000) == "quiet"
    assert _loudness(30_000, 20_000) == "amber"
    assert _loudness(45_000, 20_000) == "loud"


def test_cross_tab_j_counts_winning_unaffordable_futures():
    p_term = np.array([100., 100., 100., 50.])
    s_term = np.array([90., 90., 90., 90.])
    outside = np.array([
        [25_000, 0.],   # trial 0: wins AND over → counts
        [0., 0.],       # trial 1: wins, affordable
        [0., 0.],       # trial 2: wins, affordable
        [30_000, 0.],   # trial 3: loses (over but doesn't count)
    ])
    assert _cross_tab_j(p_term, s_term, outside, 20_000) == 25


# ---------------------------------------------------------------------------
# compute_verdict
# ---------------------------------------------------------------------------
def _fake_result(p_term, s_term, outside_cash, cashflow):
    p_term = np.asarray(p_term, float)
    s_term = np.asarray(s_term, float)
    outside_cash = np.asarray(outside_cash, float)
    cashflow = np.asarray(cashflow, float)
    return {
        "property_terminal_wealth": p_term,
        "shares_terminal_wealth": s_term,
        "p_property_wins": float((p_term > s_term).mean()),
        "outside_cash_per_trial_year": outside_cash,
        "median_outside_cash_total": float(np.median(outside_cash.sum(axis=1))),
        "worst_year_cash": float(np.percentile(outside_cash.max(axis=1), 90)),
        "median_property_wealth": float(np.median(p_term)),
        "median_shares_wealth": float(np.median(s_term)),
        "property_cashflow_path": cashflow,
    }


def test_compute_verdict_basic_property_lead():
    n = 100
    p_term = np.full(n, 200_000.0)
    s_term = np.full(n, 150_000.0)
    p_term[:32] = 100_000.0       # property wins 68/100
    outside = np.zeros((n, 4))
    outside[:, 0] = 5_000.0
    cashflow = np.tile(np.array([-5_000., -1_000., 500., 800.]), (n, 1))
    real = _fake_result(p_term, s_term, outside, cashflow)
    fair = _fake_result(s_term, p_term * 2, outside, cashflow)  # shares win fair-fight

    v = compute_verdict(real, fair, serviceability_ceiling=20_000,
                        deposit=190_000, upfront_costs=40_000)

    assert v.win_rate == 68
    assert v.leader == "property"
    assert v.badge_state == "badge"
    assert v.upfront_x == 230_000
    assert v.typical_t == 5_000.0
    assert v.crossover_k == 3
    assert v.fairfight_shares_win is True
    assert v.loudness == "quiet"
