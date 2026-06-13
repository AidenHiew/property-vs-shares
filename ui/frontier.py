# ui/frontier.py
"""Phase 2 UI components: dot-grid headline, downside callout, failure taxonomy.

No Streamlit state writes from this module — all state (dial_safety_pct,
free_mix_pct, persona_pick) is read/written in app.py; these functions are
pure renderers.
"""
from __future__ import annotations
import numpy as np
import streamlit as st

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
    deflate          : if True, amounts are already deflated — label as today's $.
    """
    if breakdown_mix == 0.0:
        return  # pure shares: no cash demand, callout not applicable

    dollar_label = "today's $" if deflate else "future $"
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
