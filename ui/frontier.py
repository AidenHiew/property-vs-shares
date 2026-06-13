# ui/frontier.py
"""Phase 2 UI components: dot-grid headline, downside callout, failure taxonomy,
frontier expander.

No Streamlit state writes from this module — all state (dial_safety_pct,
free_mix_pct, persona_pick) is read/written in app.py; these functions are
pure renderers.
"""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from model.mix_curve import MixPoint
from model.solvency import flag_forced_sales
from ui.common import (
    GREEN, TEAL, AMBER, RED, AMBER_DK, INK, MUTED, FAINT, LINE,
    GLOBAL_CSS, _render_html, _fmt_money, _fmt_pct,
)


def render_dot_grid(p_succeeds: float, n_trials: int, horizon: int) -> None:
    """Render a 10x10 dot grid + natural-frequency headline + two-sentence explainer.

    p_succeeds: fraction of trials that succeeded (0-1).
    n_trials: total trials (for natural language phrasing).
    horizon: hold period in years (for phrasing).

    Green dots = round(p_succeeds * 100); grey = remainder.
    Two-colour only (green = succeeds, grey = not) per spec §5.1.
    """
    green_dots = round(p_succeeds * 100)
    grey_dots = 100 - green_dots

    # Build 10x10 grid HTML: 100 span elements, first green_dots are green
    dots_html = ""
    for i in range(100):
        colour = GREEN if i < green_dots else "#d1d5db"
        dots_html += f'<span class="dot" style="background:{colour};"></span>'

    # Natural-frequency phrase: "about X in 10" or "about X in 100"
    # Use "in 10" when the numerator rounds cleanly to a multiple of 10
    if green_dots % 10 == 0:
        nf_num = green_dots // 10
        nf_phrasing = f"about {nf_num} in 10"
    else:
        nf_phrasing = f"about {green_dots} in 100"

    html = f"""
<div class="dot-grid-block">
  <div class="dot-grid">{dots_html}</div>
  <div class="dot-headline">
    <span class="dot-big">{nf_phrasing}</span>
    <span class="dot-ctx">of {n_trials:,} what-if stories built from your numbers,
    property both beats shares <i>and</i> keeps you solvent over {horizon} years.</span>
  </div>
  <p class="dot-explainer">
    This counts the fictional {horizon}-year paths — drawn from the ranges you set —
    where property came out ahead with the cash ceiling intact.
    It is <b>not a forecast</b>: future returns depend on markets, rates, and choices
    that no model can predict.
  </p>
</div>"""
    _render_html(GLOBAL_CSS + html)


def render_downside_callout(
    worst_year_cash: float,
    total_top_ups: float,
    forced_sale_rate: float,
    max_top_up: float,
    breakdown_mix: float,
    mixed_outside_cash: np.ndarray,
    mixed_terminal: np.ndarray,
    s_terminal: np.ndarray,
    ceiling: float,
    deflate: bool = False,
) -> None:
    """Render the amber downside callout for the selected mix.

    At mix=0 (pure shares) there is no cash demand; callout is suppressed.

    Parameters
    ----------
    worst_year_cash  : 90th-pct of per-trial worst single year's outside cash ($).
    total_top_ups    : median of per-trial cumulative outside cash ($).
    forced_sale_rate : fraction of trials with any year exceeding ceiling.
    max_top_up       : user's cash ceiling ($).
    breakdown_mix    : selected mix fraction (0-1).
    mixed_outside_cash : (trials, years) array of mix-scaled outside cash demand.
    mixed_terminal   : (trials,) array of mixed terminal wealth.
    s_terminal       : (trials,) array of pure-shares terminal wealth.
    ceiling          : serviceability ceiling in $ (same as max_top_up, pre-deflation).
    deflate          : retained for API compatibility; figures are always nominal (future $).
    """
    if breakdown_mix == 0.0:
        return  # pure shares: no cash demand, callout not applicable

    # Both worst_year_cash and total_top_ups are always nominal (future $) regardless
    # of display_mode — they come from pre-deflation arrays and are compared against
    # the nominal max_top_up ceiling.  Label them consistently as "future $".
    dollar_label = "future $"
    z_pct = int(round(forced_sale_rate * 100))

    html = f"""
<div class="callout-amber">
  <b>If it goes wrong:</b> in the worst 1-in-10 stretches you could need about
  <b>{_fmt_money(worst_year_cash)}</b> extra in a single year ({dollar_label}),
  and about <b>{_fmt_money(total_top_ups)}</b> total top-ups at median over the hold.
  In <b>{z_pct}%</b> of stories you could have been forced to sell in at least one year.
  <span class="caveat">This comes from the cash-flow model and excludes major repairs,
  your income stopping, and other personal shocks.
  Worth checking it fits your safety net.</span>
</div>"""
    _render_html(GLOBAL_CSS + html)


def render_failure_taxonomy(
    mixed_outside_cash: np.ndarray,
    mixed_terminal: np.ndarray,
    s_terminal: np.ndarray,
    ceiling: float,
) -> None:
    """Render the 2x2 failure taxonomy inside a detail expander.

    Axes:
      - rows: beats shares (mixed_terminal > s_terminal) / loses to shares
      - cols: within ceiling (no forced sale) / over ceiling (forced sale)

    Each cell shows: frequency as "X in 100" + cell-median mixed wealth.
    """
    n = len(mixed_terminal)
    forced = flag_forced_sales(mixed_outside_cash, ceiling)  # (trials,) bool
    beats = mixed_terminal > s_terminal

    # Four cells
    cells = {
        ("beats", "within"): (~forced) & beats,
        ("beats", "over"):   forced & beats,
        ("loses", "within"): (~forced) & ~beats,
        ("loses", "over"):   forced & ~beats,
    }
    cell_data = {}
    for k, mask in cells.items():
        count = int(mask.sum())
        freq = f"{round(count / n * 100)} in 100"
        med_wealth = float(np.median(mixed_terminal[mask])) if count > 0 else 0.0
        cell_data[k] = (freq, med_wealth)

    def _cell(row, col, bg):
        freq, med = cell_data[(row, col)]
        return (f'<td style="background:{bg};padding:14px 18px;border:1px solid {LINE};">'
                f'<b>{freq}</b><br><span style="font-size:13px;color:{MUTED};">'
                f'median wealth {_fmt_money(med)}</span></td>')

    html = f"""
<div style="overflow-x:auto;margin-top:10px;">
<table style="border-collapse:collapse;font-size:14px;min-width:400px;">
  <thead><tr>
    <th style="padding:10px 18px;background:#f9fafb;border:1px solid {LINE};"></th>
    <th style="padding:10px 18px;background:#f9fafb;border:1px solid {LINE};">
      Within your ceiling</th>
    <th style="padding:10px 18px;background:#f9fafb;border:1px solid {LINE};">
      Over ceiling (forced-sale risk)</th>
  </tr></thead>
  <tbody>
    <tr>
      <td style="padding:10px 18px;font-weight:700;background:#f9fafb;border:1px solid {LINE};">
        Beats shares</td>
      {_cell("beats", "within", "rgba(22,163,74,.06)")}
      {_cell("beats", "over",   "rgba(245,158,11,.08)")}
    </tr>
    <tr>
      <td style="padding:10px 18px;font-weight:700;background:#f9fafb;border:1px solid {LINE};">
        Loses to shares</td>
      {_cell("loses", "within", "rgba(14,165,233,.06)")}
      {_cell("loses", "over",   "rgba(239,68,68,.08)")}
    </tr>
  </tbody>
</table>
<p style="font-size:13px;color:{MUTED};margin-top:8px;">
  Each cell: fraction of the {n:,} stories + median mixed wealth in that cell.
  "Over ceiling" = at least one year needed more than your
  {_fmt_money(ceiling)} maximum annual top-up.
</p>
</div>"""
    _render_html(GLOBAL_CSS + html)


def render_frontier_expander(
    mix_curve: list[MixPoint],
    horizon: int,
    breakdown_mix_pct: int,
    dial_safety_pct: int,
    free_mix_pct: int,
    max_top_up: float,
) -> tuple[int, int]:
    """Render the 'How much safety does each mix buy?' expander.

    Contains:
    - Plotly frontier chart (x=median wealth, y=solvency chance)
    - Safety-target dial (st.slider, key='dial_safety_slider')
    - Free % property slider (key='free_mix_slider')
    - Optional 'Show as table' toggle (accessibility fallback)
    - Linear-blend model-assumption caveat

    Returns (new_dial_safety_pct, new_free_mix_pct) so app.py can write them
    to URL params and session state.

    Snap rule: the dial readout finds the highest-wealth qualifying mix point
    at or above the safety threshold (snap-to-qualifying-point, not linear
    interpolation); dollar/rate fields snap to that same qualifying point.
    """
    from ui.persona import find_optimal_mix, PERSONA_DEFS, render_comparison_table

    with st.expander("How much safety does each mix buy?"):
        # --- Frontier chart ---
        mixes_pct = [int(round(pt.mix_pct * 100)) for pt in mix_curve]
        wealth = [pt.median_mixed_wealth for pt in mix_curve]
        solvency = [pt.p_solvent * 100 for pt in mix_curve]

        # Sampling-noise band: binomial CI ~±1ppt at n=5000
        n_trials = 5000
        lower = [
            max(0.0, s - 1.96 * (s / 100 * (1 - s / 100) / n_trials) ** 0.5 * 100)
            for s in solvency
        ]
        upper = [
            min(100.0, s + 1.96 * (s / 100 * (1 - s / 100) / n_trials) ** 0.5 * 100)
            for s in solvency
        ]

        PERSONA_LABEL_MAP = {
            "Safe · 99%+": "Safe",
            "Balanced · 95%+": "Balanced",
            "Growth-focused · 85%+": "Growth",
        }
        persona_colours = {
            "Safe · 99%+": GREEN,
            "Balanced · 95%+": AMBER,
            "Growth-focused · 85%+": RED,
        }
        persona_symbols = {
            "Safe · 99%+": "square",
            "Balanced · 95%+": "diamond",
            "Growth-focused · 85%+": "triangle-up",
        }

        fig = go.Figure()

        # Noise band (faint)
        fig.add_trace(go.Scatter(
            x=wealth + wealth[::-1],
            y=upper + lower[::-1],
            fill="toself",
            fillcolor="rgba(14,165,233,.08)",
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
            name="Sampling noise",
        ))

        # Main curve — lines + markers so it's legible without colour alone
        fig.add_trace(go.Scatter(
            x=wealth, y=solvency,
            mode="lines+markers",
            name="Mix curve",
            line=dict(color=TEAL, width=2.5),
            marker=dict(size=5, color=TEAL, symbol="circle"),
            hovertemplate=(
                "Property: %{customdata}%<br>"
                "Wealth: %{x:$,.0f}<br>"
                "Safety: %{y:.1f}%<extra></extra>"
            ),
            customdata=mixes_pct,
        ))

        # Persona rings (distinct symbol per persona)
        for name, thr, _ in PERSONA_DEFS:
            pt = find_optimal_mix(mix_curve, thr)
            if pt is None:
                continue
            short = PERSONA_LABEL_MAP.get(name, name)
            fig.add_trace(go.Scatter(
                x=[pt.median_mixed_wealth], y=[pt.p_solvent * 100],
                mode="markers+text",
                name=short,
                marker=dict(
                    size=14, color="white",
                    symbol=persona_symbols[name],
                    line=dict(color=persona_colours[name], width=3),
                ),
                text=[short], textposition="top center",
                textfont=dict(size=12, color=persona_colours[name]),
                hovertemplate=(
                    f"{short}: {int(round(pt.mix_pct * 100))}% property, "
                    f"wealth {_fmt_money(pt.median_mixed_wealth)}, "
                    f"safety {pt.p_solvent:.1%}<extra></extra>"
                ),
            ))

        # Currently selected mix — heavier ring, circle symbol
        selected_pt = next(
            (p for p in mix_curve if int(round(p.mix_pct * 100)) == breakdown_mix_pct),
            None,
        )
        if selected_pt:
            fig.add_trace(go.Scatter(
                x=[selected_pt.median_mixed_wealth], y=[selected_pt.p_solvent * 100],
                mode="markers",
                name="Selected mix",
                marker=dict(
                    size=18, color="white",
                    symbol="circle",
                    line=dict(color=INK, width=3),
                ),
                hovertemplate=(
                    f"Selected: {breakdown_mix_pct}% property, "
                    f"wealth {_fmt_money(selected_pt.median_mixed_wealth)}, "
                    f"safety {selected_pt.p_solvent:.1%}<extra></extra>"
                ),
            ))

        # Dial safety threshold line
        fig.add_hline(
            y=dial_safety_pct,
            line_dash="dash",
            line_color=MUTED,
            annotation_text=f"Safety target: {dial_safety_pct}%",
            annotation_font_size=11,
        )

        fig.update_layout(
            title=dict(
                text=f"Safety vs wealth tradeoff — {horizon}-year horizon",
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

        # --- Safety-target dial ---
        st.markdown(
            "**Set a safety target** — the model highlights the highest-wealth mix "
            "at or above this level."
        )
        new_dial = st.slider(
            "Safety target (%)",
            min_value=50, max_value=99, value=dial_safety_pct, step=1,
            key="dial_safety_slider",
            help="Drag to change the target. The dashed line on the chart moves with it.",
        )

        # Snap readout: highest-wealth mix at or above the dial threshold
        qualifying = [pt for pt in mix_curve if pt.p_solvent * 100 >= new_dial]
        if qualifying:
            dial_point = max(qualifying, key=lambda pt: pt.median_mixed_wealth)
            st.markdown(
                f"At {new_dial}%+ safety: **{int(round(dial_point.mix_pct * 100))}% property** — "
                f"typical wealth {_fmt_money(dial_point.median_mixed_wealth)}, "
                f"actual safety {dial_point.p_solvent:.1%}"
            )
        else:
            max_achievable = max(pt.p_solvent * 100 for pt in mix_curve)
            st.markdown(
                f"Not achievable above {max_achievable:.0f}% — try raising your "
                f"max annual top-up or reducing the property portion."
            )

        st.markdown("---")

        # --- Free % property slider ---
        st.markdown("**Or set a specific property allocation directly:**")
        new_free_mix = st.slider(
            "% property",
            min_value=0, max_value=100, value=free_mix_pct, step=5,
            key="free_mix_slider",
            help=(
                "Pick your exact property/shares split. "
                "Selects 'Custom' in the breakdown view."
            ),
        )

        # Model-assumption caveat (spec §5.3)
        _render_html("""
<p class="frontier-caveat">
  <b>How this curve works:</b> it blends two full strategies (100% property and 100% shares)
  as an allocation rule — it doesn't model buying a part-property; a real investor can't sell
  40% of a house in a bad year. Mid-range mixes may understate a bad year's cash crunch.
  Sampling noise (shown as a faint band) is ~&#177;1ppt at 5,000 stories.
</p>""")

        # --- Show as table toggle (accessibility fallback) ---
        st.markdown("---")
        show_table = st.checkbox("Show as table", value=False, key="frontier_show_table")
        if show_table:
            render_comparison_table(mix_curve, breakdown_mix_pct)

    return int(new_dial), int(new_free_mix)
