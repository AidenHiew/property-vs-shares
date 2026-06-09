import numpy as np
import streamlit as st

from model.monte_carlo import run_monte_carlo
from ui.common import AMBER_DK, GLOBAL_CSS, _render_html, _fmt_money, _fmt_pct

# ============================================================================
# Persona sweep (recommendation engine)
# ============================================================================
PERSONA_DEFS = [
    ("Safe Player",      0.99, "I want near-certainty of staying within my cash ceiling — even if it costs some wealth."),
    ("Balanced",         0.95, "I want very high safety, but I'll accept a small chance of cashflow stress for more wealth."),
    ("Wealth Maximizer", 0.85, "I'll accept real risk of a forced sale (~1 in 7 futures) in exchange for the highest wealth."),
]


@st.cache_data(show_spinner="Computing allocation recommendations…")
def compute_persona_sweep(**kwargs):
    """Mix sweep at 11 points × 2000 trials. Returns one dict per mix point."""
    rows = []
    for mix_pct in range(0, 101, 10):
        r = run_monte_carlo(**{**kwargs, "property_share_mix": mix_pct / 100, "trials": 2000})
        rows.append({
            "mix_pct": mix_pct,
            "median_wealth": r["median_mixed_wealth"],
            "p_solvent": r["p_mix_solvent"],
            "worst_year_cash": float(np.percentile(r["mixed_outside_cash_per_trial_year"].max(axis=1), 90)),
            "p_beats_shares": r["p_mix_beats_pure_shares"],
        })
    return rows


def find_optimal_mix(rows, min_p_solvent):
    safe = [r for r in rows if r["p_solvent"] >= min_p_solvent]
    if not safe:
        return None
    return max(safe, key=lambda r: r["median_wealth"])


def _persona_card_html(name, threshold, blurb, row, is_rec, failed):
    badge = '<div class="badge">★ RECOMMENDED</div>' if is_rec else ''
    klass = "card rec" if is_rec else "card"
    if failed:
        return f"""
        <div class="{klass}">{badge}
          <div class="pname">{name}</div>
          <div class="pthr">Safety appetite: ≥{int(threshold*100)}% chance of staying within your cash ceiling</div>
          <div class="alloc" style="font-size:19px;color:{AMBER_DK};">Not reachable</div>
          <div class="hr"></div>
          <p class="blurb">No allocation reaches ≥{int(threshold*100)}% safety under your inputs. Try raising your
          "max annual top-up", lowering the loan amount, or shifting toward shares.</p>
        </div>"""
    mix = row["mix_pct"]
    return f"""
    <div class="{klass}">{badge}
      <div class="pname">{name}</div>
      <div class="pthr">Safety appetite: ≥{int(threshold*100)}% chance of staying within your cash ceiling</div>
      <div class="alloc">{mix}% property</div>
      <div class="alloc-sub">{100-mix}% shares</div>
      <div class="hr"></div>
      <div class="mrow"><div class="mlabel">Typical wealth in {{H}} years</div><div class="mval">{_fmt_money(row['median_wealth'])}</div></div>
      <div class="mrow"><div class="mlabel">Chance you never run out of cash</div><div class="mval">{_fmt_pct(row['p_solvent'])}</div></div>
      <div class="mrow"><div class="mlabel">Worst-year cash you'd need to find</div><div class="mval">{_fmt_money(row['worst_year_cash'])}</div></div>
      <div class="hr"></div>
      <p class="blurb">"{blurb}"</p>
    </div>"""


def render_persona_cards(rows, horizon):
    resolved = [(n, t, b, find_optimal_mix(rows, t)) for n, t, b in PERSONA_DEFS]
    safe_failed = resolved[0][3] is None

    # All three resolve to the same mix → single merged card.
    if not safe_failed:
        mixes = {r[3]["mix_pct"] for r in resolved}
        if len(mixes) == 1:
            row = resolved[1][3]
            html = f"""
            <div class="cards" style="grid-template-columns:1fr;max-width:560px;margin:0 auto;">
              <div class="card rec"><div class="badge">★ RECOMMENDED</div>
                <div class="pname">Optimal allocation</div>
                <div class="alloc">{row['mix_pct']}% property</div>
                <div class="alloc-sub">{100-row['mix_pct']}% shares</div>
                <div class="hr"></div>
                <div class="mrow"><div class="mlabel">Typical wealth in {horizon} years</div><div class="mval">{_fmt_money(row['median_wealth'])}</div></div>
                <div class="mrow"><div class="mlabel">Chance you never run out of cash</div><div class="mval">{_fmt_pct(row['p_solvent'])}</div></div>
                <div class="hr"></div>
                <p class="blurb">"All three safety levels (≥99%, ≥95%, ≥85%) point to the same allocation under your
                current inputs — pick this with confidence."</p>
              </div></div>"""
            _render_html(GLOBAL_CSS + html)
            return

    cards = ""
    for name, thr, blurb, row in resolved:
        failed = (name == "Safe Player" and safe_failed) or (row is None)
        cards += _persona_card_html(name, thr, blurb, row, name == "Balanced", failed)
    _render_html(GLOBAL_CSS + f'<div class="cards">{cards}</div>'.replace("{H}", str(horizon)))


def render_comparison_table(rows, recommended_mix):
    body = ""
    for row in rows:
        is_rec = row["mix_pct"] == recommended_mix
        star = ' <span style="color:#16a34a;">★</span>' if is_rec else ""
        body += f"""<tr class="{'rec' if is_rec else ''}">
          <td>{row['mix_pct']}%{star}</td>
          <td>{_fmt_money(row['median_wealth'])}</td>
          <td>{_fmt_pct(row['p_solvent'])}</td>
          <td>{_fmt_money(row['worst_year_cash'])}</td>
          <td>{_fmt_pct(row['p_beats_shares'])}</td></tr>"""
    html = f"""
    <div class="tbl-wrap"><table class="tbl">
      <thead><tr><th>Property mix</th><th>Typical wealth</th>
        <th>Never run out of cash</th><th>Worst-year cash</th><th>Beats pure shares</th></tr></thead>
      <tbody>{body}</tbody></table></div>"""
    _render_html(GLOBAL_CSS + html)
