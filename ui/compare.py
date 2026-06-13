# ui/compare.py
"""Phase 3: A/B scenario compare rendering.

Pure renderers — no Streamlit state writes. All state is managed in app.py.

Public API:
  render_ab_mini_cards(a_curve, b_curve, a_label, b_label, horizon) -> None
  render_ab_frontier(a_curve, b_curve, a_label, b_label, horizon, dial_safety_pct) -> None
  render_ab_stacked_fallback(a_curve, b_curve, a_label, b_label, a_horizon, b_horizon) -> None
  render_ab_tabs_fallback(a_curve, b_curve, a_label, b_label, horizon, dial_safety_pct) -> None
  _horizons_differ(snap, current_horizon) -> bool      (internal; exposed for tests)
  _display_mode_mismatch(snap, current_display_mode) -> bool  (internal; exposed for tests)
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from model.mix_curve import MixPoint
from ui.common import (
    TEAL, AMBER, INK, MUTED,
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
    A has a solid TEAL border; B has a dashed TEAL border (mirrors chart line style).
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
    - Sampling-noise band omitted on the overlay to reduce visual noise.
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
            text=f"Scenario A vs B — Safety vs wealth tradeoff ({horizon}-year horizon)",
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
    st.plotly_chart(fig, width="stretch")


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
    An amber note explains why they can't be overlaid.
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
        st.plotly_chart(fig, width="stretch")

    _mini_chart(a_curve, a_label, a_horizon, "solid")
    _mini_chart(b_curve, b_label, b_horizon, "dash")


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
        st.plotly_chart(fig, width="stretch")

    with tab_a:
        _tab_content(a_curve, a_label, "solid")
    with tab_b:
        _tab_content(b_curve, b_label, "dash")
    with tab_cmp:
        render_ab_frontier(a_curve, b_curve, a_label, b_label, horizon, dial_safety_pct)
