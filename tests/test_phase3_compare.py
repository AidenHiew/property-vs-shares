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


# ---------------------------------------------------------------------------
# Task 3 — guard helpers + render smoke tests
# ---------------------------------------------------------------------------

def test_differing_horizons_detected():
    """_horizons_differ returns True when A and B have different horizon_years."""
    from ui.compare import _horizons_differ
    snap = {"run_kwargs": {"horizon_years": 20}}
    assert _horizons_differ(snap, current_horizon=25) is True
    assert _horizons_differ(snap, current_horizon=20) is False


def test_display_mode_mismatch_detected():
    """_display_mode_mismatch returns True when A and B have different display_mode."""
    from ui.compare import _display_mode_mismatch
    snap = {"display_mode": "today"}
    assert _display_mode_mismatch(snap, current_display_mode="nominal") is True
    assert _display_mode_mismatch(snap, current_display_mode="today") is False


def test_render_ab_mini_cards_does_not_crash():
    """render_ab_mini_cards must not raise with valid MixPoint curves."""
    from ui.compare import render_ab_mini_cards
    from model.mix_curve import MixPoint
    from unittest.mock import patch, MagicMock
    import streamlit as st

    def _pt(mix, wealth, solvent):
        return MixPoint(mix_pct=mix, median_mixed_wealth=wealth, p_solvent=solvent,
                        p_succeeds=0.7, p_mix_beats_pure_shares=0.7,
                        worst_year_cash=5000, total_top_ups=30000, forced_sale_rate=0.05)

    a_curve = [_pt(m / 10, 900_000 + m * 10_000, 0.97 - m * 0.01) for m in range(11)]
    b_curve = [_pt(m / 10, 950_000 + m * 10_000, 0.96 - m * 0.01) for m in range(11)]

    with patch.object(st, "columns", return_value=[MagicMock(), MagicMock()]):
        with patch("ui.compare._render_html"):
            render_ab_mini_cards(
                a_curve=a_curve, b_curve=b_curve,
                a_label="A · current · nominal", b_label="B (current)",
                horizon=25,
            )
    # No exception = pass


def test_render_ab_frontier_no_crash_same_horizon():
    """render_ab_frontier must not raise when horizons match."""
    from ui.compare import render_ab_frontier
    from model.mix_curve import MixPoint
    from unittest.mock import patch, MagicMock
    import streamlit as st

    def _pt(mix, wealth, solvent):
        return MixPoint(mix_pct=mix, median_mixed_wealth=wealth, p_solvent=solvent,
                        p_succeeds=0.7, p_mix_beats_pure_shares=0.7,
                        worst_year_cash=5000, total_top_ups=30000, forced_sale_rate=0.05)

    a_curve = [_pt(m / 20, 900_000 + m * 5_000, 0.97 - m * 0.005) for m in range(21)]
    b_curve = [_pt(m / 20, 950_000 + m * 5_000, 0.96 - m * 0.005) for m in range(21)]

    with patch.object(st, "plotly_chart"):
        with patch("ui.compare._render_html"):
            render_ab_frontier(
                a_curve=a_curve, b_curve=b_curve,
                a_label="A · current · nominal",
                b_label="B (current)",
                horizon=25, dial_safety_pct=95,
            )


# ---------------------------------------------------------------------------
# Task 4 — AppTest wiring: differing-horizon fallback + layout toggle
# ---------------------------------------------------------------------------

def _build_snap_curve(horizon_years: int = 25):
    """Build a real MixPoint curve for AppTest injection."""
    from model.monte_carlo import run_monte_carlo
    from model.mix_curve import build_mix_curve
    r = run_monte_carlo(
        trials=200, horizon_years=horizon_years, property_share_mix=1.0,
        purchase_price=700_000, deposit=140_000, stamp_duty=32_330,
        buying_costs=2_600, loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04, vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.0, property_growth_mu=0.055, property_growth_sigma=0.11,
        share_return_mu=0.085, share_return_sigma=0.15, correlation=0.3,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age="established_post_2017", asset_type="house",
        depreciation_override=None, portfolio_profile="blended",
        mode="realistic", margin_loan_rate=0.075, isolate_asset_quality=False,
        mtr=0.37, cpi=0.025, drp=True, serviceability_ceiling=20_000, seed=42,
        return_distribution="gaussian", t_df=5,
        loan_rate_distribution="gaussian", loan_rate_t_df=5,
        property_regime="restricted_2027", annual_land_tax=0,
    )
    return build_mix_curve(
        p_terminal=r["property_terminal_wealth"],
        s_terminal=r["shares_terminal_wealth"],
        p_outside_cash=r["outside_cash_per_trial_year"],
        ceiling=20_000,
    )


def test_differing_horizon_fallback_shown_in_app():
    """When A has horizon=10 and current inputs have horizon=25, stacked fallback appears."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("app.py", default_timeout=120)
    at.query_params["yrs"] = "25"
    at.run()
    assert not at.exception

    snap_curve = _build_snap_curve(horizon_years=10)
    at.session_state["_scenario_a"] = {
        "run_kwargs": {"horizon_years": 10},
        "max_top_up": 20_000,
        "display_mode": "nominal",
        "comparison_mode": "realistic",
        "horizon": 10,
        "property_regime": "restricted_2027",
        "label": "A · restricted_2027 · nominal",
        "curve": snap_curve,
        "median_wealth": 900_000.0,
        "p_solvent_balanced": 0.95,
    }
    at.run()
    assert not at.exception
    # Different-horizons note must appear in markdown or HTML output
    all_text = " ".join(m.value for m in at.markdown)
    assert "Different hold periods" in all_text or "differ" in all_text.lower(), (
        f"Differing-horizon fallback note not found in markdown. Sample: {all_text[:500]}"
    )


def test_ab_compare_no_url_bleed():
    """After a fresh app run, no A/B data appears in URL query params."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("app.py", default_timeout=120)
    at.run()
    assert not at.exception
    for key in list(at.query_params.keys()):
        assert "scenario" not in key.lower(), (
            f"Scenario data leaked to URL param '{key}'"
        )
        assert "snap" not in key.lower(), (
            f"Snapshot data leaked to URL param '{key}'"
        )


def test_ab_layout_toggle_present_when_snapshot_saved():
    """When _scenario_a is in session_state with matching horizon, 'Side-by-side' checkbox appears."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("app.py", default_timeout=120)
    at.run()
    assert not at.exception

    snap_curve = _build_snap_curve(horizon_years=25)
    at.session_state["_scenario_a"] = {
        "run_kwargs": {"horizon_years": 25},
        "max_top_up": 20_000,
        "display_mode": "nominal",
        "comparison_mode": "realistic",
        "horizon": 25,
        "property_regime": "restricted_2027",
        "label": "A · restricted_2027 · nominal",
        "curve": snap_curve,
        "median_wealth": 900_000.0,
        "p_solvent_balanced": 0.95,
    }
    at.run()
    assert not at.exception
    cb_labels = [c.label for c in at.checkbox]
    assert any(
        "side-by-side" in (lbl or "").lower() or "tablet" in (lbl or "").lower()
        for lbl in cb_labels
    ), (f"Layout toggle checkbox not found. Checkboxes: {cb_labels}")
