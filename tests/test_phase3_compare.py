# tests/test_phase3_compare.py
"""Phase 3 A/B scenario compare tests."""
import pytest
import numpy as np

# Shared minimal run_kwargs for tests (same pattern as test_mix_curve.py)
_BASE_KWARGS = dict(
    purchase_price=700_000, deposit=140_000,
    stamp_duty=32_330, buying_costs=2_600,
    loan_rate_mu=0.06, loan_rate_sigma=0.01,
    gross_yield=0.04, vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
    rental_yield_sigma=0.0,
    property_growth_mu=0.055, property_growth_sigma=0.11,
    share_return_mu=0.085, share_return_sigma=0.15,
    correlation=0.3,
    management_fee_pct=0.07, maintenance_pct=0.012,
    property_age="established_post_2017", asset_type="house",
    depreciation_override=None,
    portfolio_profile="blended",
    mode="realistic",
    margin_loan_rate=0.075, isolate_asset_quality=False,
    mtr=0.37, cpi=0.025, drp=True,
    serviceability_ceiling=20_000,
    seed=42,
    return_distribution="gaussian", t_df=5,
    horizon_years=10,
    loan_rate_distribution="gaussian", loan_rate_t_df=5,
    property_regime="restricted_2027",
    annual_land_tax=0,
)


def _make_curve(kwargs=None):
    """Build a mix curve using the same path as _build_scenario_curve in app.py."""
    from model.monte_carlo import run_monte_carlo
    from model.mix_curve import build_mix_curve
    kw = dict(_BASE_KWARGS, **(kwargs or {}))
    result = run_monte_carlo(trials=200, property_share_mix=1.0, **{
        k: v for k, v in kw.items()
        if k not in ("trials", "property_share_mix")
    })
    return build_mix_curve(
        p_terminal=result["property_terminal_wealth"],
        s_terminal=result["shares_terminal_wealth"],
        p_outside_cash=result["outside_cash_per_trial_year"],
        ceiling=kw["serviceability_ceiling"],
    )


def test_build_scenario_curve_returns_21_mixpoints():
    """_make_curve returns 21 MixPoints (same contract as build_mix_curve default)."""
    curve = _make_curve()
    assert len(curve) == 21


def test_build_scenario_curve_same_params_identical_result():
    """Same params → same curve (CRN; cache hit in app.py)."""
    from model.mix_curve import MixPoint
    c1 = _make_curve()
    c2 = _make_curve()
    for a, b in zip(c1, c2):
        assert a.median_mixed_wealth == pytest.approx(b.median_mixed_wealth)
        assert a.p_solvent == pytest.approx(b.p_solvent)


def test_build_scenario_curve_different_params_differ():
    """Different purchase_price → different mix curve."""
    c1 = _make_curve()
    c2 = _make_curve({"purchase_price": 900_000, "deposit": 180_000, "stamp_duty": 48_000})
    mid1 = c1[10].median_mixed_wealth
    mid2 = c2[10].median_mixed_wealth
    assert mid1 != pytest.approx(mid2, rel=0.001)


# ---------------------------------------------------------------------------
# Task 2 — AppTest tests for save/clear snapshot lifecycle
# ---------------------------------------------------------------------------

def _run_app(**query_params) -> "AppTest":
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("app.py", default_timeout=120)
    for k, v in query_params.items():
        at.query_params[k] = str(v)
    at.run()
    return at


def test_save_snapshot_button_present_in_sidebar():
    """A 'Save snapshot' button must exist in the sidebar after Task 2."""
    at = _run_app()
    assert not at.exception, f"App crashed: {at.exception}"
    button_labels = [b.label for b in at.button]
    assert any("Save snapshot" in (lbl or "") for lbl in button_labels), (
        f"'Save snapshot' button not found. Buttons: {button_labels}"
    )


def test_snapshot_not_written_to_url():
    """No URL param named 'scenario_a' or 'snap' must be written."""
    at = _run_app()
    assert not at.exception
    for key in at.query_params:
        assert "scenario_a" not in key and "snap" not in key, (
            f"A/B snapshot written to URL param '{key}' — must be session-only"
        )


def test_snapshot_session_only_absent_before_save():
    """Before save, _scenario_a must not exist in session_state."""
    at = _run_app()
    assert not at.exception
    assert "_scenario_a" not in at.session_state, (
        "'_scenario_a' exists in session_state before any save"
    )


def test_clear_button_absent_before_save():
    """'Clear' / 'Compare to saved' button must not appear before a snapshot is saved."""
    at = _run_app()
    button_labels = [b.label for b in at.button]
    assert not any("Clear" in (lbl or "") and "scenario" in (lbl or "").lower() for lbl in button_labels), (
        f"Premature Clear button: {button_labels}"
    )
