# ui/persona.py
"""Persona card rendering and mix-curve helpers.

find_optimal_mix now accepts list[MixPoint] from model/mix_curve.py.
compute_persona_sweep is retired — replaced by build_mix_curve in app.py.
All three persona cards handle None (not just Safe).
"""
import streamlit as st

from model.mix_curve import MixPoint
from ui.common import AMBER_DK, GLOBAL_CSS, _render_html, _fmt_money, _fmt_pct

# ============================================================================
# Persona definitions
# ============================================================================
# NOTE: persona display names, the "★ RECOMMENDED" badge, and the ★-on-Balanced
# are UNCHANGED in Phase 1 (engine-only). Renaming to "Growth-focused · 85%+",
# dropping the ★, and the "SUGGESTED" relabel are Phase 2 (spec §4.1, §8) — doing
# them here would desync app.py's segmented_control / PERSONA_TO_THRESHOLD /
# VALID_PERSONAS, which still use "Safe"/"Balanced"/"Wealth Maximizer".
PERSONA_DEFS = [
    ("Safe Player",      0.99, "I want near-certainty of staying within my cash ceiling — even if it costs some wealth."),
    ("Balanced",         0.95, "I want very high safety, but I'll accept a small chance of cashflow stress for more wealth."),
    ("Wealth Maximizer", 0.85, "I'll accept real risk of a forced sale (~1 in 7 futures) in exchange for the highest wealth."),
]


def find_optimal_mix(curve: list[MixPoint], min_p_solvent: float) -> MixPoint | None:
    """Return the MixPoint with highest median_mixed_wealth at/above min_p_solvent.

    Returns None if no mix meets the threshold.
    """
    qualifying = [pt for pt in curve if pt.p_solvent >= min_p_solvent]
    if not qualifying:
        return None
    return max(qualifying, key=lambda pt: pt.median_mixed_wealth)


def _persona_card_html(name: str, threshold: float, blurb: str,
                       point: MixPoint | None, is_rec: bool) -> str:
    badge = '<div class="badge">★ RECOMMENDED</div>' if is_rec else ""
    klass = "card rec" if is_rec else "card"
    if point is None:
        return f"""
        <div class="{klass}">{badge}
          <div class="pname">{name}</div>
          <div class="pthr">Safety appetite: ≥{int(threshold * 100)}% chance of staying within your cash ceiling</div>
          <div class="alloc" style="font-size:19px;color:{AMBER_DK};">Not reachable</div>
          <div class="hr"></div>
          <p class="blurb">No allocation reaches ≥{int(threshold * 100)}% safety under your inputs.
          Try raising your "max annual top-up", lowering the loan amount, or shifting toward shares.</p>
        </div>"""
    mix_int = int(round(point.mix_pct * 100))
    actual_solvent_pct = int(round(point.p_solvent * 100))
    return f"""
    <div class="{klass}">{badge}
      <div class="pname">{name}</div>
      <div class="pthr">Safety appetite: ≥{int(threshold * 100)}% · actual: {actual_solvent_pct}%</div>
      <div class="alloc">{mix_int}% property</div>
      <div class="alloc-sub">{100 - mix_int}% shares</div>
      <div class="hr"></div>
      <div class="mrow"><div class="mlabel">Typical wealth in {{H}} years</div><div class="mval">{_fmt_money(point.median_mixed_wealth)}</div></div>
      <div class="mrow"><div class="mlabel">Chance you never run out of cash</div><div class="mval">{_fmt_pct(point.p_solvent)}</div></div>
      <div class="mrow"><div class="mlabel">Worst-year cash you'd need to find</div><div class="mval">{_fmt_money(point.worst_year_cash)}</div></div>
      <div class="hr"></div>
      <p class="blurb">"{blurb}"</p>
    </div>"""


def render_persona_cards(curve: list[MixPoint], horizon: int) -> None:
    """Render three persona cards from a mix curve. All None cases are handled."""
    resolved = [
        (name, thr, blurb, find_optimal_mix(curve, thr))
        for name, thr, blurb in PERSONA_DEFS
    ]

    # All three reachable AND resolve to the same mix → single merged card.
    # (If any card is None, do NOT merge — an unreachable safety level is
    # information the user must see, per the no-solvent-mix state.)
    if all(r[3] is not None for r in resolved) and len(
            {int(round(r[3].mix_pct * 100)) for r in resolved}) == 1:
        row = resolved[1][3]
        mix_int = int(round(row.mix_pct * 100))
        html = f"""
        <div class="cards" style="grid-template-columns:1fr;max-width:560px;margin:0 auto;">
          <div class="card rec"><div class="badge">★ RECOMMENDED</div>
            <div class="pname">Optimal allocation</div>
            <div class="alloc">{mix_int}% property</div>
            <div class="alloc-sub">{100 - mix_int}% shares</div>
            <div class="hr"></div>
            <div class="mrow"><div class="mlabel">Typical wealth in {horizon} years</div><div class="mval">{_fmt_money(row.median_mixed_wealth)}</div></div>
            <div class="mrow"><div class="mlabel">Chance you never run out of cash</div><div class="mval">{_fmt_pct(row.p_solvent)}</div></div>
            <div class="hr"></div>
            <p class="blurb">"All three safety levels (≥99%, ≥95%, ≥85%) point to the same allocation under your
            current inputs — pick this with confidence."</p>
          </div></div>"""
        _render_html(GLOBAL_CSS + html)
        return

    cards = ""
    for name, thr, blurb, point in resolved:
        is_rec = (name == "Balanced")
        cards += _persona_card_html(name, thr, blurb, point, is_rec)
    _render_html(
        GLOBAL_CSS
        + f'<div class="cards">{cards}</div>'.replace("{H}", str(horizon))
    )


def render_comparison_table(curve: list[MixPoint], recommended_mix_pct: int) -> None:
    """Per-mix comparison table, adapted to consume list[MixPoint].

    Kept in Phase 1 so the phase ships with no feature regression. Phase 2
    relocates this into the tradeoff-chart expander as a 'show as table' toggle
    and retires the standalone expander (spec §4.3).
    """
    body = ""
    for pt in curve:
        mix_int = int(round(pt.mix_pct * 100))
        is_rec = (mix_int == recommended_mix_pct)
        star = ' <span style="color:#16a34a;">★</span>' if is_rec else ""
        body += f"""<tr class="{'rec' if is_rec else ''}">
          <td>{mix_int}%{star}</td>
          <td>{_fmt_money(pt.median_mixed_wealth)}</td>
          <td>{_fmt_pct(pt.p_solvent)}</td>
          <td>{_fmt_money(pt.worst_year_cash)}</td>
          <td>{_fmt_pct(pt.p_mix_beats_pure_shares)}</td></tr>"""
    html = f"""
    <div class="tbl-wrap"><table class="tbl">
      <thead><tr><th>Property mix</th><th>Typical wealth</th>
        <th>Never run out of cash</th><th>Worst-year cash</th><th>Beats pure shares</th></tr></thead>
      <tbody>{body}</tbody></table></div>"""
    _render_html(GLOBAL_CSS + html)
