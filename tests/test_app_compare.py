import numpy as np
import pytest
from streamlit.testing.v1 import AppTest

from app_compare import clamp_horizon, clamp_rate, clamp_deposit, clamp_topup
from ui.verdict import compute_verdict


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


# ---------------------------------------------------------------------------
# AppTest smoke + URL boundary
# ---------------------------------------------------------------------------
def test_app_loads_without_exception():
    at = AppTest.from_file("app_compare.py", default_timeout=90).run()
    assert not at.exception


def test_malformed_url_params_do_not_crash():
    at = AppTest.from_file("app_compare.py", default_timeout=90)
    for key in ("yrs", "price", "dep", "rate", "yield", "grow", "vac",
                "upfront", "mtr", "topup", "port"):
        at.query_params[key] = "None"
    at.run()
    assert not at.exception


def test_out_of_range_url_params_do_not_crash():
    at = AppTest.from_file("app_compare.py", default_timeout=90)
    at.query_params["rate"] = "999"
    at.query_params["yield"] = "999"
    at.query_params["grow"] = "-999"
    at.query_params["mtr"] = "999"
    at.run()
    assert not at.exception


def test_zero_topup_boundary_runs():
    at = AppTest.from_file("app_compare.py", default_timeout=90)
    at.query_params["topup"] = "0"
    at.run()
    assert not at.exception


# ---------------------------------------------------------------------------
# framing behaviour (direct compute_verdict)
# ---------------------------------------------------------------------------
def _result(p_term, s_term, outside, cashflow):
    p_term, s_term = np.asarray(p_term, float), np.asarray(s_term, float)
    outside, cashflow = np.asarray(outside, float), np.asarray(cashflow, float)
    return {
        "property_terminal_wealth": p_term, "shares_terminal_wealth": s_term,
        "p_property_wins": float((p_term > s_term).mean()),
        "outside_cash_per_trial_year": outside,
        "median_outside_cash_total": float(np.median(outside.sum(axis=1))),
        "worst_year_cash": float(np.percentile(outside.max(axis=1), 90)),
        "median_property_wealth": float(np.median(p_term)),
        "median_shares_wealth": float(np.median(s_term)),
        "property_cashflow_path": cashflow,
    }


def test_near_tie_is_neutral_no_badge():
    n = 100
    p = np.full(n, 100_000.0); s = np.full(n, 100_000.0)
    p[:50] = 110_000.0; s[50:] = 110_000.0   # ~50/50
    r = _result(p, s, np.zeros((n, 3)), np.zeros((n, 3)))
    v = compute_verdict(r, r, serviceability_ceiling=20_000, deposit=190_000, upfront_costs=40_000)
    assert v.badge_state == "neutral"
    assert v.badge_label == ""


def test_affordability_loud_does_not_change_badge():
    n = 100
    p = np.full(n, 300_000.0); s = np.full(n, 100_000.0)   # property wins 100/100
    outside = np.zeros((n, 3)); outside[:, 0] = 80_000.0     # Z >> C
    r = _result(p, s, outside, np.full((n, 3), -1_000.0))
    v = compute_verdict(r, r, serviceability_ceiling=20_000, deposit=190_000, upfront_costs=40_000)
    assert v.loudness == "loud"
    assert v.badge_state == "badge"      # verdict NOT suppressed by loud panel
    assert v.leader == "property"


def test_t_single_source_matches_engine_key():
    n = 50
    outside = np.zeros((n, 4)); outside[:, 0] = 6_000.0; outside[:, 1] = 4_000.0
    r = _result(np.full(n, 2.0), np.full(n, 1.0), outside, np.zeros((n, 4)))
    v = compute_verdict(r, r, serviceability_ceiling=20_000, deposit=190_000, upfront_costs=40_000)
    assert v.typical_t == r["median_outside_cash_total"]   # one source, not recomputed
