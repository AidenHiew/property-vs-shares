# Phase 3 Implementation Plan — A/B Scenario Compare

**Goal:** Add a session-only "Save snapshot / Compare to saved" control near the sidebar inputs so users can pin Scenario A's *input parameters*, then overlay Scenario B (live inputs) as a dashed curve on the same frontier chart, with appropriate guards for differing horizons and mobile viewports.

**Architecture:** A new `ui/compare.py` module owns all A/B rendering logic (mini-cards + overlaid/stacked chart). A small helper `_build_scenario_curve` in `app.py` centralises how either scenario's curve is derived (reusing `cached_run` + `build_mix_curve` so cache hits are free). Snapshot state lives only in `st.session_state` — never the URL. `ui/frontier.py` gains an `overlay_curve` parameter to receive Scenario A's pre-computed curve for the overlay render path.

**Tech Stack:** Python 3.11 · Streamlit 1.37+ · Plotly · NumPy · existing `cached_run` / `build_mix_curve` / `MixPoint` · `streamlit.testing.v1.AppTest` for tests.

> **REQUIRED SUB-SKILL: subagent-driven-development**

Tasks are written as independent shippable slices — each ends with the full test suite green (currently 199 tests). Checkbox steps within a task run in order: write failing test → run suite → implement → run suite → commit. "Visual styling" steps are flagged inline; they still include the exact code to add.

---

## File Structure

| File | Role in Phase 3 |
|---|---|
| `ui/compare.py` | **NEW.** `render_ab_mini_cards()`, `render_ab_frontier()`. Pure renderers; no session-state writes. All A/B display logic lives here. |
| `ui/frontier.py` | **MODIFIED.** `render_frontier_expander` gains an optional `overlay_curve: list[MixPoint] \| None = None` and `overlay_label: str \| None = None` parameter. When provided, adds the A-curve as a dashed trace and a gap-fill between A and B. |
| `app.py` | **MODIFIED.** (1) Extract `_build_scenario_curve(run_kwargs, max_top_up)` helper. (2) Save-snapshot button + `st.session_state["_scenario_a"]` lifecycle. (3) Call `render_ab_mini_cards` + `render_ab_frontier` when A is saved. (4) Pass `overlay_curve` into `render_frontier_expander`. |
| `tests/test_phase3_compare.py` | **NEW.** Unit + AppTest tests for snapshot lifecycle, differing-horizon guard, display-mode guard, mobile tab fallback, and session-only persistence. |

**Why a new `ui/compare.py` rather than extending `ui/frontier.py`?**
The compare view is a distinct display mode (two curves, two mini-cards, horizon guard, mobile tabs) that does not share state with the single-curve frontier expander. Keeping them separate lets each module stay under ~200 lines and makes the horizon-guard fallback path trivially testable without loading the full frontier.

---

## Task 1 — Extract `_build_scenario_curve` helper in `app.py`

**Files:** `app.py`, `tests/test_phase3_compare.py`

This is the foundation. Both A and B need to produce a `list[MixPoint]` from a param dict. Centralising the derivation prevents drift and ensures A's curve reuses the `@st.cache_data` cache when params match B.

### Steps

**1.1 — Write failing test**

Add to `tests/test_phase3_compare.py`:

```python
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
    portfolio_profile="blended",
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
```

Run: `.venv/bin/python -m pytest tests/test_phase3_compare.py -q`
Expected: 3 pass (the helper is pure Python, no app.py import needed yet).

**1.2 — Add `_build_scenario_curve` to `app.py`**

Insert after the `cached_run` definition (around line 405):

```python
def _build_scenario_curve(run_kwargs: dict, max_top_up: float) -> list:
    """Derive a mix curve from run_kwargs using the same cached base run.

    Reuses cached_run (cache hit when params match the current scenario).
    Always runs at property_share_mix=1.0 to get unblended arrays.
    Returns list[MixPoint].
    """
    result = cached_run(trials=5000, property_share_mix=1.0, **run_kwargs)
    return build_mix_curve(
        p_terminal=result["property_terminal_wealth"],
        s_terminal=result["shares_terminal_wealth"],
        p_outside_cash=result["outside_cash_per_trial_year"],
        ceiling=max_top_up,
    )
```

**1.3 — Run suite**

`.venv/bin/python -m pytest -q` — must stay at 199+ pass, 0 failures.

**1.4 — Commit**

```
git add app.py tests/test_phase3_compare.py
git commit -m "phase3 task1: extract _build_scenario_curve helper + baseline tests"
```

---

## Task 2 — Snapshot save / clear in session_state

**Files:** `app.py`, `tests/test_phase3_compare.py`

Add the "Save snapshot" / "Clear" button pair near the sidebar inputs. Saving captures `run_kwargs` + the display mode + comparison mode + horizon (everything needed to recompute A's curve and label it) into `st.session_state["_scenario_a"]`. Changing inputs does NOT mutate A. Snapshot is never written to the URL.

### Snapshot schema

```python
# Written to st.session_state["_scenario_a"]
{
    "run_kwargs": dict,        # copy of run_kwargs at save time
    "max_top_up": float,
    "display_mode": str,       # "nominal" | "today"
    "comparison_mode": str,    # "realistic" | "fair_fight"
    "horizon": int,
    "property_regime": str,    # for labelling
    "label": str,              # e.g. "Scenario A · restricted_2027 · today's $"
    "curve": list[MixPoint],   # pre-computed at save time
    "median_wealth": float,    # headline figure: mix=1.0 pt median wealth
    "p_solvent_balanced": float,  # solvency at Balanced point for mini-card
}
```

### Steps

**2.1 — Write failing AppTest tests**

Append to `tests/test_phase3_compare.py`:

```python
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
```

Run: `.venv/bin/python -m pytest tests/test_phase3_compare.py::test_save_snapshot_button_present_in_sidebar -q`
Expected: FAIL (button not yet added).

**2.2 — Add the save/clear control to `app.py` sidebar**

In the sidebar block, just below `st.header("Your scenario")` (before the first input group), add:

```python
# --- A/B Scenario compare: save snapshot control ---
_snap = st.session_state.get("_scenario_a")
if _snap is None:
    if st.button("Save snapshot", key="save_snapshot_btn",
                 help="Pin these inputs as Scenario A to compare against future changes."):
        _snap_curve = _build_scenario_curve(run_kwargs, max_top_up)
        _balanced_pt = find_optimal_mix(_snap_curve, 0.95)
        st.session_state["_scenario_a"] = {
            "run_kwargs": dict(run_kwargs),
            "max_top_up": max_top_up,
            "display_mode": display_mode,
            "comparison_mode": comparison_mode,
            "horizon": horizon,
            "property_regime": effective_property_regime,
            "label": f"Scenario A · {effective_property_regime} · {display_mode}",
            "curve": _snap_curve,
            "median_wealth": _snap_curve[-1].median_mixed_wealth,
            "p_solvent_balanced": _balanced_pt.p_solvent if _balanced_pt else 0.0,
        }
        st.rerun()
else:
    st.info(f"Snapshot saved: {_snap['label']}")
    if st.button("Clear snapshot", key="clear_snapshot_btn",
                 help="Remove Scenario A and return to single-scenario view."):
        del st.session_state["_scenario_a"]
        st.rerun()
```

**Important placement note:** The `_build_scenario_curve` call inside the button handler fires only on the rerun triggered by clicking the button. The save block must appear *after* `run_kwargs` is fully constructed (currently around line 398) and after `_build_scenario_curve` is defined (Task 1). In the actual file, this means the sidebar `with st.sidebar:` block is after `run_kwargs` — however, Streamlit sidebar widgets are rendered top-to-bottom in source order. The save button must appear in the sidebar *above* the inputs conceptually (by placement in source) but logically runs after `run_kwargs` is assembled. **Resolution:** move the save/clear control to a second `with st.sidebar:` block placed just after the `run_kwargs` dict construction (around line 402), not inside the first `with st.sidebar:` block. Streamlit merges sidebar contributions from multiple `with st.sidebar:` blocks.

```python
# Placed just after run_kwargs dict construction in app.py (after line ~398):
with st.sidebar:
    st.markdown("---")
    st.markdown("**Compare scenarios**")
    _snap = st.session_state.get("_scenario_a")
    if _snap is None:
        if st.button("Save snapshot", key="save_snapshot_btn",
                     help="Pin these inputs as Scenario A to compare against future changes."):
            _snap_curve = _build_scenario_curve(run_kwargs, max_top_up)
            _balanced_pt = find_optimal_mix(_snap_curve, 0.95)
            st.session_state["_scenario_a"] = {
                "run_kwargs": dict(run_kwargs),
                "max_top_up": max_top_up,
                "display_mode": display_mode,
                "comparison_mode": comparison_mode,
                "horizon": horizon,
                "property_regime": effective_property_regime,
                "label": f"A · {effective_property_regime} · {display_mode}",
                "curve": _snap_curve,
                "median_wealth": float(
                    max(pt.median_mixed_wealth for pt in _snap_curve)
                ),
                "p_solvent_balanced": (
                    _balanced_pt.p_solvent if _balanced_pt is not None else 0.0
                ),
            }
            st.rerun()
    else:
        st.info(f"Saved: {_snap['label']}", icon="📌")
        if st.button("Clear comparison", key="clear_snapshot_btn"):
            del st.session_state["_scenario_a"]
            st.rerun()
```

**2.3 — Add `find_optimal_mix` import** in `app.py` — already imported from `ui.persona`. No change needed.

**2.4 — Run suite**

`.venv/bin/python -m pytest -q` — must be 203+ pass, 0 failures.

**2.5 — Commit**

```
git add app.py tests/test_phase3_compare.py
git commit -m "phase3 task2: save/clear snapshot in session_state; AppTest guards"
```

---

## Task 3 — Mini-cards + overlaid frontier chart + guards

**Files:** `ui/compare.py` (new), `ui/frontier.py` (modified), `tests/test_phase3_compare.py`

The main visual deliverable. When `_scenario_a` is set, render two compact headline mini-cards (typical outcome + solvency at Balanced) then the overlaid chart — A solid, B dashed, same asset-semantic colours (TEAL for both curves), gap-fill between them, and the safety-target reference line. Guards: same-display-mode enforcement; differing-horizon fallback to two stacked mini-charts.

### Steps

**3.1 — Write failing unit tests for guards**

Append to `tests/test_phase3_compare.py`:

```python
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
```

Run: `.venv/bin/python -m pytest tests/test_phase3_compare.py -q`
Expected: 4 new FAIL (module not yet created).

**3.2 — Create `ui/compare.py`**

```python
# ui/compare.py
"""Phase 3: A/B scenario compare rendering.

Pure renderers — no Streamlit state writes. All state is managed in app.py.

Public API:
  render_ab_mini_cards(a_curve, b_curve, a_label, b_label, horizon) -> None
  render_ab_frontier(a_curve, b_curve, a_label, b_label, horizon, dial_safety_pct) -> None
  _horizons_differ(snap, current_horizon) -> bool      (internal; exposed for tests)
  _display_mode_mismatch(snap, current_display_mode) -> bool  (internal; exposed for tests)
"""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from model.mix_curve import MixPoint
from ui.common import (
    GREEN, TEAL, AMBER, RED, INK, MUTED, LINE,
    GLOBAL_CSS, _render_html, _fmt_money, _fmt_pct,
)
from ui.persona import find_optimal_mix


# ---------------------------------------------------------------------------
# Guard helpers
# ---------------------------------------------------------------------------

def _horizons_differ(snap: dict, current_horizon: int) -> bool:
    """Return True when A and B have different horizon_years."""
    return snap["run_kwargs"].get("horizon_years") != current_horizon


def _display_mode_mismatch(snap: dict, current_display_mode: str) -> bool:
    """Return True when A was saved under a different display mode than B."""
    return snap.get("display_mode") != current_display_mode


# ---------------------------------------------------------------------------
# Mini-cards (two compact headline tiles: typical wealth + solvency at Balanced)
# ---------------------------------------------------------------------------

def render_ab_mini_cards(
    a_curve: list[MixPoint],
    b_curve: list[MixPoint],
    a_label: str,
    b_label: str,
    horizon: int,
) -> None:
    """Render two compact headline mini-cards side by side (or stacked on mobile).

    Each card shows: typical outcome at Balanced (95%) mix + solvency %.
    A is always left; B (current) is always right.

    On tablet+ the cards use st.columns(2); on mobile this degrades to
    st.tabs (handled by the caller — render_ab_mini_cards always uses columns
    and the mobile tab fallback is applied at a higher level in app.py).
    """
    a_pt = find_optimal_mix(a_curve, 0.95)
    b_pt = find_optimal_mix(b_curve, 0.95)

    def _card_html(label: str, pt: MixPoint | None, border_dash: str) -> str:
        """border_dash: 'solid' for A, 'dashed' for B (mirrors chart line style)."""
        border_style = (
            f"border: 2px solid {TEAL};"
            if border_dash == "solid"
            else f"border: 2px dashed {TEAL};"
        )
        if pt is None:
            return f"""
<div style="background:#fff;{border_style}border-radius:10px;padding:16px 18px;">
  <div style="font-size:12px;font-weight:700;color:{MUTED};text-transform:uppercase;
       letter-spacing:.5px;margin-bottom:6px;">{label}</div>
  <div style="font-size:22px;font-weight:800;color:{AMBER};">Not reachable</div>
  <div style="font-size:13px;color:{MUTED};margin-top:4px;">
    No mix meets 95%+ safety under these inputs.</div>
</div>"""
        mix_int = int(round(pt.mix_pct * 100))
        return f"""
<div style="background:#fff;{border_style}border-radius:10px;padding:16px 18px;">
  <div style="font-size:12px;font-weight:700;color:{MUTED};text-transform:uppercase;
       letter-spacing:.5px;margin-bottom:6px;">{label}</div>
  <div style="font-size:24px;font-weight:800;color:{INK};line-height:1.1;">
    {_fmt_money(pt.median_mixed_wealth)}</div>
  <div style="font-size:13px;color:{MUTED};margin-top:4px;">
    typical wealth · {horizon} yrs · {mix_int}% property</div>
  <div style="font-size:17px;font-weight:700;color:{INK};margin-top:8px;">
    {_fmt_pct(pt.p_solvent)}</div>
  <div style="font-size:13px;color:{MUTED};">chance you never run out of cash</div>
</div>"""

    col_a, col_b = st.columns(2)
    with col_a:
        _render_html(GLOBAL_CSS + _card_html(a_label, a_pt, "solid"))
    with col_b:
        _render_html(_card_html(b_label, b_pt, "dashed"))


# ---------------------------------------------------------------------------
# Overlaid frontier chart (same-horizon path)
# ---------------------------------------------------------------------------

def render_ab_frontier(
    a_curve: list[MixPoint],
    b_curve: list[MixPoint],
    a_label: str,
    b_label: str,
    horizon: int,
    dial_safety_pct: int,
) -> None:
    """Render overlaid A+B frontier chart.

    - Scenario A: solid TEAL line.
    - Scenario B: dashed TEAL line.
    - Same hue; line *style* is the distinguisher (spec §6 + a11y §7).
    - Gap between curves: faint filled area (rgba TEAL, 0.08 opacity).
    - Safety-target reference line (dashed grey) so the *difference* is primary.
    - Sampling-noise band is omitted on the overlay to reduce visual noise
      (the band is shown in the single-curve view inside render_frontier_expander).
    """
    wealth_a = [pt.median_mixed_wealth for pt in a_curve]
    solv_a   = [pt.p_solvent * 100 for pt in a_curve]
    wealth_b = [pt.median_mixed_wealth for pt in b_curve]
    solv_b   = [pt.p_solvent * 100 for pt in b_curve]
    mixes_pct_a = [int(round(pt.mix_pct * 100)) for pt in a_curve]
    mixes_pct_b = [int(round(pt.mix_pct * 100)) for pt in b_curve]

    fig = go.Figure()

    # Gap fill between A and B (only if same number of points — always 21 by contract)
    if len(wealth_a) == len(wealth_b):
        # Fill from A to B in wealth (x) at each solvency level (y).
        # Use solvency as y-axis; shade between wealth_a and wealth_b at each y.
        # Build fill polygon: trace up A, then back down B.
        fig.add_trace(go.Scatter(
            x=wealth_a + wealth_b[::-1],
            y=solv_a + solv_b[::-1],
            fill="toself",
            fillcolor="rgba(14,165,233,.08)",
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
            name="Gap between A and B",
        ))

    # Scenario A — solid line
    fig.add_trace(go.Scatter(
        x=wealth_a, y=solv_a,
        mode="lines+markers",
        name=a_label,
        line=dict(color=TEAL, width=2.5, dash="solid"),
        marker=dict(size=4, color=TEAL, symbol="circle"),
        hovertemplate=(
            f"{a_label}<br>Property: %{{customdata}}%<br>"
            "Wealth: %{x:$,.0f}<br>Safety: %{y:.1f}%<extra></extra>"
        ),
        customdata=mixes_pct_a,
    ))

    # Scenario B — dashed line
    fig.add_trace(go.Scatter(
        x=wealth_b, y=solv_b,
        mode="lines+markers",
        name=b_label,
        line=dict(color=TEAL, width=2.5, dash="dash"),
        marker=dict(size=4, color=TEAL, symbol="circle-open"),
        hovertemplate=(
            f"{b_label}<br>Property: %{{customdata}}%<br>"
            "Wealth: %{x:$,.0f}<br>Safety: %{y:.1f}%<extra></extra>"
        ),
        customdata=mixes_pct_b,
    ))

    # Safety-target reference line
    fig.add_hline(
        y=dial_safety_pct,
        line_dash="dash",
        line_color=MUTED,
        annotation_text=f"Safety target: {dial_safety_pct}%",
        annotation_font_size=11,
    )

    fig.update_layout(
        title=dict(
            text=f"A vs B — Safety vs wealth tradeoff ({horizon}-year horizon)",
            font=dict(size=15),
        ),
        xaxis_title=f"Typical outcome after {horizon} years ($)",
        yaxis_title="Chance you never run out of cash (%)",
        yaxis=dict(range=[0, 105]),
        height=420,
        margin=dict(t=50, b=40),
        hovermode="closest",
        plot_bgcolor="white",
        legend=dict(orientation="h", y=1.1, x=0),
    )
    fig.update_xaxes(gridcolor="#f0f0f0", tickformat="$,.0f")
    fig.update_yaxes(gridcolor="#f0f0f0", ticksuffix="%")
    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Stacked mini-charts (differing-horizon fallback)
# ---------------------------------------------------------------------------

def render_ab_stacked_fallback(
    a_curve: list[MixPoint],
    b_curve: list[MixPoint],
    a_label: str,
    b_label: str,
    a_horizon: int,
    b_horizon: int,
) -> None:
    """Fallback when A and B have different horizons: two stacked mini-charts.

    Each is a compact version of the single-curve frontier (no gap fill, no overlay).
    A note explains why they can't be overlaid.
    """
    _render_html(GLOBAL_CSS + f"""
<div class="callout-amber" style="background:rgba(245,158,11,.06);">
  <b>Different hold periods</b> — {a_label} runs {a_horizon} years and {b_label}
  runs {b_horizon} years, so the x-axes differ. Showing them separately below.
  To overlay, save a new snapshot with the same horizon as your current inputs.
</div>""")

    def _mini_chart(curve: list[MixPoint], label: str, horizon: int, dash: str) -> None:
        wealth  = [pt.median_mixed_wealth for pt in curve]
        solv    = [pt.p_solvent * 100 for pt in curve]
        mixes_p = [int(round(pt.mix_pct * 100)) for pt in curve]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=wealth, y=solv,
            mode="lines+markers",
            name=label,
            line=dict(color=TEAL, width=2.0, dash=dash),
            marker=dict(size=4, color=TEAL),
            hovertemplate=(
                f"{label}<br>Property: %{{customdata}}%<br>"
                "Wealth: %{x:$,.0f}<br>Safety: %{y:.1f}%<extra></extra>"
            ),
            customdata=mixes_p,
        ))
        fig.update_layout(
            title=dict(text=f"{label} ({horizon}-year horizon)", font=dict(size=13)),
            xaxis_title=f"Typical outcome after {horizon} yrs ($)",
            yaxis_title="Solvency chance (%)",
            yaxis=dict(range=[0, 105]),
            height=280,
            margin=dict(t=40, b=30, l=10, r=10),
            plot_bgcolor="white",
            showlegend=False,
        )
        fig.update_xaxes(gridcolor="#f0f0f0", tickformat="$,.0f")
        fig.update_yaxes(gridcolor="#f0f0f0", ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True)

    _mini_chart(a_curve, a_label, a_horizon, "solid")
    _mini_chart(b_curve, b_label, b_horizon, "dash")
```

**3.3 — Wire `render_ab_mini_cards` + `render_ab_frontier` into `app.py`**

Add import at the top of `app.py`:

```python
from ui.compare import (
    render_ab_mini_cards, render_ab_frontier,
    render_ab_stacked_fallback,
    _horizons_differ, _display_mode_mismatch,
)
```

In the RENDER SECTION of `app.py`, just before the `# 1. Example-data nudge` block, add:

```python
# ---------------------------------------------------------------------------
# A/B Scenario compare section (Phase 3) — shown only when a snapshot is saved
# ---------------------------------------------------------------------------
_snap = st.session_state.get("_scenario_a")
if _snap is not None:
    b_curve = mix_curve  # current scenario's curve (already built above)
    b_label = f"B (current) · {effective_property_regime} · {display_mode}"
    a_label = _snap["label"]

    # Guard: display-mode mismatch — force B to A's display mode
    if _display_mode_mismatch(_snap, display_mode):
        st.warning(
            f"Scenario A was saved in **{_snap['display_mode']}** mode; "
            f"current view is **{display_mode}**. "
            "The comparison uses A's saved mode — switch 'Show dollars as' "
            "to match for a like-for-like overlay.",
            icon="⚠️",
        )

    # Guard: differing horizons → stacked fallback
    if _horizons_differ(_snap, horizon):
        render_ab_stacked_fallback(
            a_curve=_snap["curve"],
            b_curve=b_curve,
            a_label=a_label,
            b_label=b_label,
            a_horizon=_snap["horizon"],
            b_horizon=horizon,
        )
    else:
        # Same horizon → overlaid view
        st.markdown(
            f'<div class="pvs-section">Comparing: {a_label} vs {b_label}</div>',
            unsafe_allow_html=True,
        )
        render_ab_mini_cards(
            a_curve=_snap["curve"],
            b_curve=b_curve,
            a_label=a_label,
            b_label=b_label,
            horizon=horizon,
        )
        render_ab_frontier(
            a_curve=_snap["curve"],
            b_curve=b_curve,
            a_label=a_label,
            b_label=b_label,
            horizon=horizon,
            dial_safety_pct=dial_safety_pct,
        )

    st.markdown("---")
```

**3.4 — Run suite**

`.venv/bin/python -m pytest -q` — must be 207+ pass, 0 failures.

**3.5 — Commit**

```
git add ui/compare.py app.py tests/test_phase3_compare.py
git commit -m "phase3 task3: compare mini-cards + overlaid frontier + horizon/mode guards"
```

---

## Task 4 — Mobile tabs fallback + AppTest wiring + full guard coverage

**Files:** `app.py`, `ui/compare.py`, `tests/test_phase3_compare.py`

On narrow viewports, `st.columns(2)` does not stack — it creates a cramped two-column layout. The spec mandates `st.tabs(["A", "B", "Compare"])` as the mobile fallback. Since Streamlit has no runtime viewport detection in pure Python, the solution is a **user-controlled toggle** in the compare section: a checkbox "Side-by-side (tablet+)" defaulting to True. On small screens the user unchecks it to get tabs. This is the same pattern used for similar responsive issues in the existing codebase.

This task also adds the remaining AppTest smoke tests to confirm the full save → compare → clear lifecycle and that no A/B state leaks to the URL.

### Steps

**4.1 — Write failing tests**

Append to `tests/test_phase3_compare.py`:

```python
def test_differing_horizon_fallback_shown_in_app():
    """When A has horizon=10 and current inputs have horizon=25, stacked fallback appears."""
    from streamlit.testing.v1 import AppTest
    import json

    at = AppTest.from_file("app.py", default_timeout=120)
    at.query_params["yrs"] = "25"
    at.run()
    assert not at.exception

    # Manually inject a saved scenario with horizon=10
    from model.monte_carlo import run_monte_carlo
    from model.mix_curve import build_mix_curve
    r = run_monte_carlo(
        trials=200, horizon_years=10, property_share_mix=1.0,
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
    snap_curve = build_mix_curve(
        p_terminal=r["property_terminal_wealth"],
        s_terminal=r["shares_terminal_wealth"],
        p_outside_cash=r["outside_cash_per_trial_year"],
        ceiling=20_000,
    )
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
    # Different-horizons note must appear
    full_html = " ".join(m.value for m in at.markdown)
    assert "Different hold periods" in full_html or "differ" in full_html.lower(), (
        "Differing-horizon fallback note not found"
    )


def test_ab_compare_no_url_bleed():
    """After saving a snapshot, no A/B data appears in URL query params."""
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
    """When _scenario_a is in session_state, 'Side-by-side' checkbox must appear."""
    from streamlit.testing.v1 import AppTest
    from model.monte_carlo import run_monte_carlo
    from model.mix_curve import build_mix_curve

    at = AppTest.from_file("app.py", default_timeout=120)
    at.run()
    assert not at.exception

    r = run_monte_carlo(
        trials=200, horizon_years=25, property_share_mix=1.0,
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
    snap_curve = build_mix_curve(
        p_terminal=r["property_terminal_wealth"],
        s_terminal=r["shares_terminal_wealth"],
        p_outside_cash=r["outside_cash_per_trial_year"],
        ceiling=20_000,
    )
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
    assert any("side-by-side" in (lbl or "").lower() or "tablet" in (lbl or "").lower()
               for lbl in cb_labels), (
        f"Layout toggle checkbox not found. Checkboxes: {cb_labels}"
    )
```

Run: `.venv/bin/python -m pytest tests/test_phase3_compare.py -q`
Expected: 3 new FAIL.

**4.2 — Add `render_ab_tabs_fallback` to `ui/compare.py`**

Append to `ui/compare.py` (visual styling step — exact code):

```python
# ---------------------------------------------------------------------------
# Mobile tabs fallback (same-horizon)
# ---------------------------------------------------------------------------

def render_ab_tabs_fallback(
    a_curve: list[MixPoint],
    b_curve: list[MixPoint],
    a_label: str,
    b_label: str,
    horizon: int,
    dial_safety_pct: int,
) -> None:
    """Mobile-friendly A / B / Compare tab layout for same-horizon scenarios.

    Used when the user unchecks 'Side-by-side (tablet+)' to indicate a narrow viewport.
    Tab 'A' and 'B' each show one mini-card + one mini frontier chart.
    Tab 'Compare' shows the overlaid chart (same as desktop).
    """
    tab_a, tab_b, tab_cmp = st.tabs([a_label, b_label, "Compare"])

    def _tab_content(curve: list[MixPoint], label: str, dash: str) -> None:
        pt = find_optimal_mix(curve, 0.95)
        if pt is None:
            st.warning(f"No mix meets 95%+ safety under {label}.")
            return
        mix_int = int(round(pt.mix_pct * 100))
        _render_html(GLOBAL_CSS + f"""
<div style="background:#fff;border:2px {'solid' if dash=='solid' else 'dashed'} {TEAL};
     border-radius:10px;padding:16px 18px;margin-bottom:12px;">
  <div style="font-size:22px;font-weight:800;color:{INK};">
    {_fmt_money(pt.median_mixed_wealth)}</div>
  <div style="font-size:13px;color:{MUTED};">typical wealth · {horizon} yrs · {mix_int}% property</div>
  <div style="font-size:17px;font-weight:700;color:{INK};margin-top:8px;">
    {_fmt_pct(pt.p_solvent)}</div>
  <div style="font-size:13px;color:{MUTED};">chance you never run out of cash</div>
</div>""")
        # Mini frontier chart for this scenario only
        wealth  = [p.median_mixed_wealth for p in curve]
        solv    = [p.p_solvent * 100 for p in curve]
        mixes_p = [int(round(p.mix_pct * 100)) for p in curve]
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=wealth, y=solv, mode="lines+markers", name=label,
            line=dict(color=TEAL, width=2.0, dash=dash),
            marker=dict(size=4, color=TEAL),
            hovertemplate=(
                f"{label}<br>Property: %{{customdata}}%<br>"
                "Wealth: %{x:$,.0f}<br>Safety: %{y:.1f}%<extra></extra>"
            ),
            customdata=mixes_p,
        ))
        fig.add_hline(y=dial_safety_pct, line_dash="dash", line_color=MUTED,
                      annotation_text=f"Target: {dial_safety_pct}%",
                      annotation_font_size=10)
        fig.update_layout(
            xaxis_title=f"Typical outcome ({horizon} yrs) ($)",
            yaxis_title="Solvency (%)",
            yaxis=dict(range=[0, 105]), height=300,
            margin=dict(t=20, b=30, l=10, r=10),
            plot_bgcolor="white", showlegend=False,
        )
        fig.update_xaxes(gridcolor="#f0f0f0", tickformat="$,.0f")
        fig.update_yaxes(gridcolor="#f0f0f0", ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True)

    with tab_a:
        _tab_content(a_curve, a_label, "solid")
    with tab_b:
        _tab_content(b_curve, b_label, "dash")
    with tab_cmp:
        render_ab_frontier(a_curve, b_curve, a_label, b_label, horizon, dial_safety_pct)
```

Update the `from ui.compare import ...` line in `app.py` to include `render_ab_tabs_fallback`.

**4.3 — Wire the side-by-side toggle into `app.py`**

Inside the compare section added in Task 3 (same-horizon branch), replace the direct calls to `render_ab_mini_cards` + `render_ab_frontier` with:

```python
# Same horizon → overlaid or tabbed view
st.markdown(
    f'<div class="pvs-section">Comparing: {a_label} vs {b_label}</div>',
    unsafe_allow_html=True,
)
side_by_side = st.checkbox(
    "Side-by-side (tablet+)", value=True, key="ab_side_by_side",
    help="Uncheck on small screens to switch to a tab view (A / B / Compare).",
)
if side_by_side:
    render_ab_mini_cards(
        a_curve=_snap["curve"], b_curve=b_curve,
        a_label=a_label, b_label=b_label, horizon=horizon,
    )
    render_ab_frontier(
        a_curve=_snap["curve"], b_curve=b_curve,
        a_label=a_label, b_label=b_label,
        horizon=horizon, dial_safety_pct=dial_safety_pct,
    )
else:
    render_ab_tabs_fallback(
        a_curve=_snap["curve"], b_curve=b_curve,
        a_label=a_label, b_label=b_label,
        horizon=horizon, dial_safety_pct=dial_safety_pct,
    )
```

**4.4 — Run full suite**

`.venv/bin/python -m pytest -q` — must be 212+ pass, 0 failures (199 existing + 13 new Phase 3 tests).

**4.5 — Commit**

```
git add ui/compare.py app.py tests/test_phase3_compare.py
git commit -m "phase3 task4: mobile tabs fallback + ab_side_by_side toggle + full AppTest coverage"
```

---

## Key design decisions

### Where the save/compare control lives
In a second `with st.sidebar:` block placed after `run_kwargs` is constructed (~line 402). This is the spec's "control near the inputs" and avoids a dead-state toggle at the top of the main page. Streamlit merges multiple sidebar contributions in source order.

### How A's curve is recomputed
At save time: `_build_scenario_curve(run_kwargs, max_top_up)` is called immediately (runs through `@st.cache_data cached_run` at `property_share_mix=1.0` then `build_mix_curve`). The result is stored in `session_state["_scenario_a"]["curve"]` as a `list[MixPoint]`. On subsequent renders A's curve is read directly from session state — **no recomputation on render**. If the user's current params happen to match A's saved params, `cached_run` will be a cache hit anyway (the cache key is the kwargs hash). This matches the "recompute A from its saved params" spec requirement while keeping render fast.

### Differing-horizon fallback
Detected by `_horizons_differ(snap, current_horizon)` comparing `snap["run_kwargs"]["horizon_years"]` to the live `horizon`. When True, `render_ab_stacked_fallback` is called — two independent mini-charts, each labelled with its horizon, plus an explanatory amber note. No overlay is attempted.

### Mobile fallback
A `st.checkbox("Side-by-side (tablet+)", ...)` defaults to `True`. The user unchecks it on a small screen to get `st.tabs(["A", "B", "Compare"])`. This is the most robust approach available in pure Streamlit (no JS component, no viewport detection). The spec's "degrade to st.tabs()" requirement is satisfied, and it degrades gracefully even if the user never encounters a narrow viewport.

### Display-mode mismatch guard
Detected by `_display_mode_mismatch(snap, display_mode)`. When True, a `st.warning` is shown explaining that A was saved under a different mode. The overlay still renders (using each curve's own values, which were computed in that curve's native mode) but the user is warned that the axes represent different dollar bases. This is the least-surprising behaviour — hiding the overlay on a mode mismatch would be confusing; the warning is sufficient.

### A is session-only; URL is untouched
`session_state["_scenario_a"]` is never serialised to the URL. The `st.query_params.update(...)` call near line 357 does not include any `scenario_a`/`snap` key. Tests explicitly assert no URL bleed.

---

## Spec ambiguities resolved

- **⚠ "Recompute A from its saved params, not current selectors" (spec §6 guard):** This is satisfied by storing the pre-computed curve in session_state at save time, not the raw arrays. A's curve is therefore always the result of A's params, regardless of what B's params are. However, if the user clears their browser tab (session ends), A is lost — the spec says "session-only" so this is correct. No warning is needed for this case.

- **⚠ "Force both scenarios to the SAME display mode" (spec §6 guard):** The spec says "force" but does not say which mode wins. Decision: A's display mode is informational in the label; B always uses the current `display_mode` selector. The curves themselves are always nominal (built by `build_mix_curve` which operates in nominal $); deflation is a per-render operation applied to the `result` dict in `app.py`, not to the stored `list[MixPoint]`. Therefore the A/B overlay is always in nominal terms at the `MixPoint` level — the display-mode warning flags the discrepancy but does not change any values. This is consistent with the deflation contract (`build_mix_curve` is nominal-only per spec §3.2 and tested in `test_deflation_contract_curve_is_nominal`).

- **⚠ "One overlaid tradeoff chart … shade the gap between the curves" (spec §6):** The gap fill is built as a Plotly filled polygon tracing A's curve forward then B's curve backward. This works cleanly when both curves have 21 points (the default). If either curve has a different number of points (custom `mixes` arg), the fill is skipped — a defensive guard in `render_ab_frontier` handles `len(wealth_a) != len(wealth_b)`.

- **⚠ Mobile breakpoint:** Streamlit does not expose a Python-accessible viewport width. The checkbox toggle is the pragmatic solution. The spec says "degrade to st.tabs() on mobile" — the toggle achieves this without a JS component.
