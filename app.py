"""Property vs Shares — Streamlit UI.

Recommendation-first layout for non-expert ("mum & dad") users: a plain-English
intro, three persona cards as the hero, a feasibility flag, then progressively
deeper detail (year-by-year breakdown, allocation table, distributions,
assumptions) behind expanders. Inputs live in the sidebar, grouped and
plain-English, and persist in the URL so a tuned scenario is a shareable link.
"""
import json
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from model.monte_carlo import run_monte_carlo
from model.duty import stamp_duty
from model.normalisation import PORTFOLIO_PROFILES
from config import STAGE_3_BRACKETS

# ============================================================================
# Design system
# ============================================================================
# Semantic palette: green = safe/recommended, teal = shares, amber = property,
# red = risk. System font stack (fast, native-feeling). One type scale.
GREEN, TEAL, AMBER, RED = "#16a34a", "#0ea5e9", "#f59e0b", "#ef4444"
AMBER_DK, INK, MUTED, FAINT, LINE = "#d97706", "#1a1a1a", "#6b7280", "#9ca3af", "#e5e7eb"

GLOBAL_CSS = f"""
<style>
  .block-container {{ padding-top: 2.2rem; max-width: 1180px; }}
  /* type scale */
  .pvs-h1 {{ font-size: 30px; font-weight: 700; color: {INK}; line-height: 1.15; margin: 0 0 4px; }}
  .pvs-sub {{ font-size: 15px; color: {MUTED}; margin: 0 0 14px; line-height: 1.5; }}
  .pvs-section {{ font-size: 20px; font-weight: 700; color: {INK}; margin: 8px 0 2px; }}
  .pvs-section-sub {{ font-size: 13px; color: {MUTED}; margin: 0 0 12px; }}

  /* persona cards */
  .cards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin: 6px 0 8px; }}
  .card {{ background: #fff; border: 1px solid {LINE}; border-radius: 12px; padding: 22px 22px 18px;
           position: relative; transition: box-shadow .18s ease, transform .18s ease; }}
  .card:hover {{ box-shadow: 0 6px 18px rgba(0,0,0,.07); transform: translateY(-1px); }}
  .card.rec {{ border: 1px solid {GREEN}; border-left: 5px solid {GREEN};
               box-shadow: 0 8px 24px rgba(22,163,74,.12); }}
  .badge {{ background: {GREEN}; color: #fff; font-size: 11px; font-weight: 700; letter-spacing: .3px;
            padding: 4px 10px; border-radius: 999px; display: inline-block; margin-bottom: 12px; }}
  .pname {{ font-size: 12px; font-weight: 700; color: {MUTED}; text-transform: uppercase; letter-spacing: .6px; }}
  .pthr {{ font-size: 11px; color: {FAINT}; margin: 2px 0 14px; font-weight: 600; }}
  .alloc {{ font-size: 30px; font-weight: 800; color: {INK}; line-height: 1.05; }}
  .card.rec .alloc {{ color: {GREEN}; }}
  .alloc-sub {{ font-size: 13px; color: {MUTED}; margin-top: 2px; }}
  .hr {{ height: 1px; background: {LINE}; margin: 15px 0; }}
  .mrow {{ margin-bottom: 9px; }}
  .mlabel {{ font-size: 12px; color: {FAINT}; margin-bottom: 1px; }}
  .mval {{ font-size: 17px; font-weight: 700; color: {INK}; }}
  .blurb {{ font-size: 12px; color: #4b5563; font-style: italic; background: #f9fafb;
            border-radius: 8px; padding: 11px 12px; margin: 10px 0 0; }}

  /* metric tiles */
  .tiles {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 6px 0 4px; }}
  .tile {{ background: #fff; border: 1px solid {LINE}; border-radius: 10px; padding: 16px 18px; }}
  .tile.good {{ background: rgba(22,163,74,.05); border-color: rgba(22,163,74,.35); }}
  .tile .tlabel {{ font-size: 12px; color: {MUTED}; margin-bottom: 4px; }}
  .tile .tval {{ font-size: 22px; font-weight: 800; color: {INK}; line-height: 1; }}

  /* headline number */
  .headline {{ display: flex; align-items: baseline; gap: 12px; margin: 4px 0 2px; flex-wrap: wrap; }}
  .headline .big {{ font-size: 40px; font-weight: 800; color: {GREEN}; line-height: 1; }}
  .headline .ctx {{ font-size: 16px; color: {INK}; font-weight: 600; }}

  /* feasibility flag */
  .flag {{ border-radius: 10px; padding: 13px 16px; font-size: 14px; margin: 10px 0 4px; font-weight: 500; }}
  .flag.ok  {{ background: rgba(22,163,74,.08);  border: 1px solid rgba(22,163,74,.4);  color: #166534; }}
  .flag.warn{{ background: rgba(245,158,11,.10); border: 1px solid rgba(245,158,11,.5); color: #92400e; }}
  .flag.bad {{ background: rgba(239,68,68,.08);  border: 1px solid rgba(239,68,68,.45); color: #991b1b; }}

  /* tables */
  .tbl-wrap {{ overflow-x: auto; }}
  .tbl {{ width: 100%; border-collapse: collapse; font-size: 13.5px; background: #fff;
          border: 1px solid {LINE}; border-radius: 8px; overflow: hidden; }}
  .tbl thead {{ background: #f9fafb; }}
  .tbl th {{ text-align: right; padding: 10px 14px; font-weight: 700; color: #374151; font-size: 11px;
             text-transform: uppercase; letter-spacing: .4px; border-bottom: 2px solid {LINE}; white-space: nowrap; }}
  .tbl th:first-child, .tbl td:first-child {{ text-align: left; }}
  .tbl td {{ padding: 9px 14px; border-bottom: 1px solid #f3f4f6; color: {INK}; text-align: right; white-space: nowrap; }}
  .tbl tr:last-child td {{ border-bottom: none; }}
  .tbl .rec {{ background: rgba(22,163,74,.07); font-weight: 700; }}
  .tbl .rec td {{ color: #15803d; }}

  .disclaimer {{ font-size: 12px; color: {MUTED}; border-top: 1px solid {LINE};
                 margin-top: 28px; padding-top: 14px; line-height: 1.6; }}

  @media (max-width: 820px) {{
    .cards {{ grid-template-columns: 1fr; }}
    .tiles {{ grid-template-columns: repeat(2, 1fr); }}
    .pvs-h1 {{ font-size: 24px; }}
    .headline .big {{ font-size: 32px; }}
  }}
</style>
"""


# ============================================================================
# Small helpers
# ============================================================================
def _fmt_money(x):
    if abs(x) >= 1_000_000:
        return f"${x/1_000_000:.2f}M"
    if abs(x) >= 1_000:
        return f"${x/1_000:.0f}k"
    return f"${x:.0f}"


def _fmt_dollars(x):
    return f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"


def _fmt_pct(x):
    return f"{x*100:.1f}%"


def mtr_from_income(income: float) -> float:
    """Marginal tax rate for a taxable income under FY2026 Stage-3 brackets."""
    prev = 0.0
    for upper, rate in STAGE_3_BRACKETS:
        if income <= upper:
            return rate
        prev = upper
    return STAGE_3_BRACKETS[-1][1]


def _corr_words(c: float) -> str:
    """Plain-English reading of a property↔shares correlation value."""
    if c <= -0.5:
        return "tend to move in opposite directions"
    if c < -0.1:
        return "lean toward moving in opposite directions"
    if c <= 0.1:
        return "move mostly on their own (barely related)"
    if c < 0.5:
        return "mostly move on their own, with a slight tendency to move together"
    return "tend to move up and down together"


def _render_html(html: str) -> None:
    """Render raw HTML via st.markdown, stripping per-line indentation so the
    markdown parser doesn't treat indented lines as code blocks."""
    flat = "\n".join(line.lstrip() for line in html.strip().split("\n"))
    st.markdown(flat, unsafe_allow_html=True)


# ----- URL persistence -------------------------------------------------------
def qp(key, cast, default):
    """Read an input default from the URL query params (so a scenario survives
    refresh and is shareable). Falls back to `default` if absent/unparseable."""
    raw = st.query_params.get(key)
    if raw is None:
        return default
    try:
        return cast(raw)
    except (ValueError, TypeError):
        return default


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


# ============================================================================
# Year-by-year breakdown
# ============================================================================
def _median_path(result, key, deflate, yearly_deflator):
    arr = result[key]
    if deflate:
        arr = arr / yearly_deflator
    return np.median(arr, axis=0)


def render_year_by_year_chart(result, horizon, mix_pct, deflate, yearly_deflator):
    """Wealth fan: median + p10/p90 + p25/p75 bands for property, shares, mix."""
    years = np.arange(1, horizon + 1)
    series = [
        ("Property", "property_wealth_path", AMBER),
        ("Shares", "shares_wealth_path", TEAL),
    ]
    if mix_pct < 100:
        series.append((f"Mix ({mix_pct}/{100-mix_pct})", "mixed_wealth_path", GREEN))

    fig = go.Figure()
    for label, key, colour in series:
        arr = result[key] / yearly_deflator if deflate else result[key]
        p10, p25, p50, p75, p90 = (np.percentile(arr, q, axis=0) for q in (10, 25, 50, 75, 90))
        rgba = {AMBER: "245,158,11", TEAL: "14,165,233", GREEN: "22,163,74"}[colour]
        fig.add_trace(go.Scatter(x=np.r_[years, years[::-1]], y=np.r_[p90, p10[::-1]],
                      fill="toself", fillcolor=f"rgba({rgba},.08)", line=dict(width=0),
                      hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=np.r_[years, years[::-1]], y=np.r_[p75, p25[::-1]],
                      fill="toself", fillcolor=f"rgba({rgba},.16)", line=dict(width=0),
                      hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=years, y=p50, mode="lines", name=label,
                      line=dict(color=colour, width=2.5),
                      hovertemplate=f"{label}: %{{y:$,.0f}} (yr %{{x}})<extra></extra>"))
    fig.add_vline(x=5, line_dash="dot", line_color=MUTED,
                  annotation_text="loan starts repaying principal", annotation_font_size=10)
    unit = "today's $" if deflate else "future $"
    fig.update_layout(
        title=dict(text=f"Wealth over {horizon} years — median with likely range (shaded)", font=dict(size=15)),
        xaxis_title="Year", yaxis_title=f"Wealth ({unit})",
        height=420, margin=dict(t=50, b=40), hovermode="x unified",
        plot_bgcolor="white", legend=dict(orientation="h", y=1.08, x=0))
    fig.update_xaxes(gridcolor="#f0f0f0"); fig.update_yaxes(gridcolor="#f0f0f0")
    st.plotly_chart(fig, width="stretch")


def render_year_by_year_table(result, horizon, mix_pct, deflate, yearly_deflator):
    """Median-per-year financial breakdown table."""
    def med(key):
        return _median_path(result, key, deflate, yearly_deflator)

    value = med("property_value_path")
    balance = med("property_loan_balance_path")
    rent = med("property_rent_path")
    interest = med("property_interest_path")
    tax = med("property_tax_path")            # negative = refund (negative gearing benefit)
    pcash = med("property_cashflow_path")     # after-tax property cashflow
    svalue = med("shares_wealth_path")
    mixw = med("mixed_wealth_path")

    cols = ["Year", "Property value", "Loan balance", "Your equity", "Net rent",
            "Loan interest", "Tax benefit", "Property cashflow", "Shares value"]
    if mix_pct < 100:
        cols.append("Mix wealth")
    head = "".join(f"<th>{c}</th>" for c in cols)

    body = ""
    for i in range(horizon):
        equity = value[i] - balance[i]
        tax_benefit = -tax[i]  # show refund as positive benefit
        cells = [
            f"{i+1}", _fmt_dollars(value[i]), _fmt_dollars(balance[i]), _fmt_dollars(equity),
            _fmt_dollars(rent[i]), _fmt_dollars(interest[i]), _fmt_dollars(tax_benefit),
            _fmt_dollars(pcash[i]), _fmt_dollars(svalue[i]),
        ]
        if mix_pct < 100:
            cells.append(_fmt_dollars(mixw[i]))
        body += "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
    _render_html(GLOBAL_CSS + f'<div class="tbl-wrap"><table class="tbl"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')
    st.caption("Each figure is the median across all simulated futures. 'Tax benefit' is the negative-gearing "
               "refund (positive = money back). 'Property cashflow' is after-tax — negative means out-of-pocket that year.")


# ============================================================================
# Page
# ============================================================================
st.set_page_config(page_title="Property vs Shares", layout="wide", page_icon="🏠")
_render_html(GLOBAL_CSS)

_render_html("""
<div class="pvs-h1">🏠 Property vs Shares — should you buy a rental, buy shares, or mix both?</div>
<div class="pvs-sub">This tool simulates <b>5,000 possible 25-year futures</b> for your situation and shows the
likely wealth, the risk of running short on cash, and the property/shares mix that best fits your comfort with risk.
It's a <b>what-if explorer, not a prediction or financial advice.</b> Set your numbers in the sidebar →</div>
""")

# ---------------------------------------------------------------------------
# Sidebar inputs (plain-English, grouped, URL-persisted)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Your scenario")

    st.markdown("**The property**")
    purchase_price = st.number_input("Purchase price", value=qp("price", int, 700_000), step=10_000,
                                     min_value=100_000, help="The rental property you're considering buying.")
    state = st.selectbox(
        "State",
        ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"],
        index=["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"].index(qp("state", str, "SA")),
        help="Sets stamp duty for your purchase. Income tax, CGT and negative gearing are federal (same Australia-wide).",
    )
    deposit_pct = st.slider("Deposit %", 5, 60, qp("dep", int, 20),
                            help="Your cash up front. The rest is borrowed.")
    deposit = purchase_price * deposit_pct / 100
    gross_yield = st.slider("Rental yield %", 2.0, 8.0, qp("yield", float, 4.0), step=0.1,
                            help="Yearly rent ÷ price. $28k rent on a $700k place = 4%. "
                                 "Check Domain / realestate.com.au for your suburb.") / 100
    property_age = st.selectbox(
        "Property age", ["new_build", "established_post_2017", "established_pre_2017"],
        index=qp("age", int, 1),
        format_func=lambda x: {"new_build": "New build",
                               "established_post_2017": "Established (bought after May 2017)",
                               "established_pre_2017": "Established (bought before May 2017)"}[x])
    asset_type = st.selectbox("Type", ["house", "apartment", "townhouse"],
                              index=qp("atype", int, 0), format_func=str.title)

    st.markdown("**Your money**")
    income = st.number_input("Your taxable income", value=qp("income", int, 150_000), step=5_000, min_value=0,
                             help="Used to work out your tax rate automatically.")
    mtr = mtr_from_income(income)
    st.caption(f"→ Your marginal tax rate: **{mtr:.0%}** (drives negative gearing & CGT)")
    loan_rate = st.slider("Mortgage rate %", 3.0, 10.0, qp("rate", float, 6.0), step=0.1,
                          help="Your interest rate. Check your lender / recent rates.") / 100
    horizon = st.slider("How many years?", 5, 40, qp("yrs", int, 25),
                        help="How long you'd hold before selling.")
    max_top_up = st.number_input("Max annual top-up you can afford", value=qp("topup", int, 20_000), step=1_000,
                                 min_value=0, help="The most out-of-pocket cash you could feed the property in a "
                                                   "bad year without financial stress. Your safety ceiling.")

    st.markdown("**The choice**")
    property_share_mix_pct = st.slider("Property share of your money %", 0, 100, qp("mix", int, 100), step=5,
                                       help="100% = all-in on property. 0% = all shares. In between = a blend.")
    property_share_mix = property_share_mix_pct / 100
    portfolio_profile = st.selectbox(
        "If you bought shares, which?", ["asx_only", "global", "blended"], index=qp("port", int, 2),
        format_func=lambda x: {"asx_only": "Australian (ASX)", "global": "Global",
                               "blended": "Blend of both"}[x])
    property_regime = st.selectbox(
        "Tax rules", ["current", "restricted_2027"], index=qp("regime", int, 1),
        format_func=lambda x: {"current": "Current rules (full negative gearing)",
                               "restricted_2027": "Budget 2026-27 (limited negative gearing, from Jul 2027)"}[x],
        help="The 2026-27 Budget limits negative gearing on established property bought after 12 May 2026. "
             "New builds keep the current rules.")

    with st.expander("Advanced (optional)"):
        st.caption("Sensible defaults — change only if you know these.")
        comparison_mode = st.radio("Comparison fairness", ["realistic", "fair_fight"], index=0, horizontal=True,
            format_func=lambda x: {"realistic": "Realistic", "fair_fight": "Equal leverage"}[x],
            help="Realistic = shares unleveraged (what most people do). Equal leverage = shares also borrow, "
                 "via a margin loan, to match the property's borrowing (hypothetical).")
        display_mode = st.radio("Show dollars as", ["nominal", "today"], index=0, horizontal=True,
            format_func=lambda x: {"nominal": "Future $", "today": "Today's $"}[x],
            help="Today's $ adjusts future amounts for inflation so they're easier to relate to now.")
        st.markdown("**Market assumptions**")
        property_growth_mu = st.slider("Property growth (average per year)", 0.0, 10.0, 5.5, step=0.5,
                                       format="%.1f%%", help="Long-run average capital growth.") / 100
        property_growth_sigma = st.slider("Property ups & downs (a typical year's swing)", 5.0, 20.0, 11.0,
                                          step=1.0, format="±%.0f%%") / 100
        st.caption(f"A typical year lands within about ±{property_growth_sigma*100:.0f}% of the average.")
        share_return_mu = st.slider("Share return (average per year)", 0.0, 15.0, 8.5, step=0.5,
                                    format="%.1f%%") / 100
        share_return_sigma = st.slider("Share ups & downs (a typical year's swing)", 5.0, 30.0, 15.0,
                                       step=1.0, format="±%.0f%%") / 100
        st.caption(f"A typical year lands within about ±{share_return_sigma*100:.0f}% of the average.")
        loan_rate_sigma = st.slider("Mortgage-rate ups & downs (a typical year's swing)", 0.5, 2.0, 1.0,
                                    step=0.1, format="±%.1f%%") / 100
        correlation = st.slider("How together property & shares move", -1.0, 1.0, 0.3, step=0.05,
                                help="−1 = move opposite · 0 = unrelated · +1 = move identically. Most use ~0.3.")
        st.caption(f"At {correlation:.2f}: they {_corr_words(correlation)}.")
        return_distribution = st.selectbox(
            "Crash modelling", ["gaussian", "student_t"], index=0,
            format_func=lambda x: {"gaussian": "Normal (standard)",
                                   "student_t": "Fat-tailed (more big-shock risk)"}[x],
            help="Fat-tailed (Student-t) gives heavier crash and rate-shock tails than a normal distribution — "
                 "useful for stress-testing worst-year cash. It does NOT predict any specific crash.")
        t_df = st.slider("Fat-tail strength", 3, 30, 5,
                         help="Lower = fatter tails. 5 ≈ historical equities; 30 ≈ normal.") \
            if return_distribution == "student_t" else 5
        vacancy_weeks = st.slider("Vacancy (weeks/yr)", 0, 8, 2)
        vacancy_weeks_sigma = st.slider("Vacancy ups & downs (weeks)", 0.5, 4.0, 1.0, step=0.5)
        cpi = st.slider("Inflation (per year)", 0.0, 5.0, 2.5, step=0.5, format="%.1f%%") / 100
        management_fee_pct = st.slider("Property manager fee", 0.0, 12.0, 7.0, step=0.5, format="%.1f%%") / 100
        maintenance_pct = st.slider("Upkeep — maintenance, insurance, rates (per year)", 0.5, 3.0, 1.2,
                                    step=0.1, format="%.1f%%") / 100
        depreciation_override = st.number_input("Depreciation override ($/yr, 0 = auto)", value=0, step=500, min_value=0)
        depreciation_override = depreciation_override if depreciation_override > 0 else None
        margin_loan_rate = st.slider("Margin loan rate (equal-leverage mode)", 5.0, 12.0, 7.5, step=0.5,
                                     format="%.1f%%") / 100
        isolate_asset_quality = st.checkbox("Pin shares loan rate to mortgage rate", value=False)
        if property_age == "new_build":
            override_new_build_carveout = st.checkbox(
                "Apply restricted rules to this new build anyway", value=False,
                help="New builds keep current rules per the Budget announcement. Tick to model the counterfactual.")
        else:
            override_new_build_carveout = False
        rental_yield_sigma = 0.0

# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
errors = []
if deposit_pct >= 100:
    errors.append("Deposit % must be under 100%.")
if purchase_price <= 0:
    errors.append("Purchase price must be positive.")
if horizon <= 0:
    errors.append("Investment horizon must be at least 1 year.")
if loan_rate <= 0:
    errors.append("Mortgage rate must be positive.")
if errors:
    for e in errors:
        st.error(e)
    st.stop()

# Persist inputs in the URL (shareable + survives refresh). Advanced σ knobs stay session-local.
st.query_params.update({k: str(v) for k, v in {
    "price": purchase_price, "dep": deposit_pct, "yield": round(gross_yield * 100, 1),
    "age": ["new_build", "established_post_2017", "established_pre_2017"].index(property_age),
    "atype": ["house", "apartment", "townhouse"].index(asset_type),
    "income": income, "rate": round(loan_rate * 100, 1), "yrs": horizon, "topup": max_top_up,
    "mix": property_share_mix_pct,
    "port": ["asx_only", "global", "blended"].index(portfolio_profile),
    "regime": ["current", "restricted_2027"].index(property_regime),
    "state": state,
}.items()})

# Stamp duty + buying costs
stamp_duty_amount = stamp_duty(state, purchase_price)
buying_costs = 2_600
upfront = deposit + stamp_duty_amount + buying_costs

# New-build carve-out
effective_property_regime = "current" if (property_age == "new_build" and not override_new_build_carveout) else property_regime

# ---------------------------------------------------------------------------
# Run the model (cached)
# ---------------------------------------------------------------------------
run_kwargs = dict(
    horizon_years=horizon, purchase_price=purchase_price, deposit=deposit,
    stamp_duty=stamp_duty_amount, buying_costs=buying_costs,
    loan_rate_mu=loan_rate, loan_rate_sigma=loan_rate_sigma, gross_yield=gross_yield,
    vacancy_weeks_mu=vacancy_weeks, vacancy_weeks_sigma=vacancy_weeks_sigma, rental_yield_sigma=rental_yield_sigma,
    property_growth_mu=property_growth_mu, property_growth_sigma=property_growth_sigma,
    share_return_mu=share_return_mu, share_return_sigma=share_return_sigma,
    management_fee_pct=management_fee_pct, maintenance_pct=maintenance_pct,
    property_age=property_age, asset_type=asset_type, depreciation_override=depreciation_override,
    property_regime=effective_property_regime, portfolio_profile=portfolio_profile,
    mode=comparison_mode, margin_loan_rate=margin_loan_rate, isolate_asset_quality=isolate_asset_quality,
    correlation=correlation, mtr=mtr, cpi=cpi, drp=True, serviceability_ceiling=max_top_up, seed=42,
    return_distribution=return_distribution, t_df=t_df,
    loan_rate_distribution=return_distribution, loan_rate_t_df=t_df,
)


@st.cache_data(show_spinner="Running 5,000 simulated futures…")
def cached_run(**kwargs):
    return run_monte_carlo(**kwargs)


result = cached_run(trials=5000, property_share_mix=property_share_mix, **run_kwargs)

# Deflation to today's dollars
deflate = display_mode == "today"
yearly_deflator = (1 + cpi) ** np.arange(1, horizon + 1)
if deflate:
    term_deflator = (1 + cpi) ** horizon
    for k in ["property_terminal_wealth", "shares_terminal_wealth", "median_property_wealth",
              "median_shares_wealth", "mixed_terminal_wealth", "median_mixed_wealth"]:
        result[k] = result[k] / term_deflator
    per_year_keys = [
        "outside_cash_per_trial_year", "mixed_outside_cash_per_trial_year",
        "property_wealth_path", "shares_wealth_path", "mixed_wealth_path",
        "property_value_path", "property_loan_balance_path", "property_rent_path",
        "property_interest_path", "property_other_costs_path", "property_depreciation_path",
        "property_tax_path", "property_cashflow_path", "property_overflow_path",
        "shares_dividend_path", "shares_dividend_tax_path", "shares_cashflow_path",
    ]
    for k in per_year_keys:
        result[k] = result[k] / yearly_deflator
    result["worst_year_cash"] = float(np.percentile(result["outside_cash_per_trial_year"].max(axis=1), 90))

# ---------------------------------------------------------------------------
# Recommendation (perf: sweep runs only on demand, not every slider drag)
# ---------------------------------------------------------------------------
sweep_kwargs = dict(run_kwargs)  # already carries serviceability_ceiling
sweep_key = json.dumps(sweep_kwargs, sort_keys=True, default=str)

st.markdown('<div class="pvs-section">Recommended allocation for you</div>', unsafe_allow_html=True)
st.markdown('<div class="pvs-section-sub">Pick the safety level that matches your comfort with risk — '
            'the optimiser finds the property/shares mix that delivers it with the most wealth.</div>',
            unsafe_allow_html=True)

stale = st.session_state.get("sweep_key") != sweep_key
c1, c2 = st.columns([1, 3])
with c1:
    recompute = st.button("↻ Update recommendations", type="primary" if stale else "secondary",
                          width="stretch")
if recompute or "sweep_rows" not in st.session_state:
    st.session_state["sweep_rows"] = compute_persona_sweep(**sweep_kwargs)
    st.session_state["sweep_key"] = sweep_key
    stale = False
with c2:
    if stale:
        st.info("Inputs changed — click **↻ Update recommendations** to refresh the cards below.")
sweep_rows = st.session_state["sweep_rows"]

render_persona_cards(sweep_rows, horizon)
balanced = find_optimal_mix(sweep_rows, 0.95)
recommended_mix = balanced["mix_pct"] if balanced else None

# "What now?" guidance
_render_html(f"""
<div class="blurb" style="max-width:none;margin-top:6px;">
<b>What this means:</b> if you want both, the recommended split is the most wealth at that safety level — e.g. put the
property-share of your savings toward the property and the rest into shares. It is <i>not</i> a push to own both.
Next step: talk to a licensed financial adviser about your loan approval, tax, and goals.
</div>""")

st.markdown("---")

# ---------------------------------------------------------------------------
# Headline + feasibility + tiles
# ---------------------------------------------------------------------------
n = result["property_terminal_wealth"].size
_render_html(f"""
<div class="headline"><span class="big">{result['p_property_succeeds']:.0%}</span>
<span class="ctx">of {n:,} simulated {horizon}-year futures, property both beats shares <i>and</i> keeps you solvent.</span></div>
<div class="pvs-section-sub">Property beats shares in {result['p_property_wins']:.0%} of futures, but only
{result['p_solvent']:.0%} stay within your {_fmt_money(max_top_up)} cash ceiling. "Succeeds" needs both.</div>
""")

# Feasibility flag
wyc = result["worst_year_cash"]
if wyc <= max_top_up:
    flag = ("ok", f"✅ Comfortable — the worst simulated year needs about {_fmt_money(wyc)}, within your "
                  f"{_fmt_money(max_top_up)} ceiling.")
elif wyc <= max_top_up * 1.25:
    flag = ("warn", f"⚠️ Tight — a bad year could need about {_fmt_money(wyc)} vs your {_fmt_money(max_top_up)} "
                    f"ceiling. A rate or rent shock could tip you over.")
else:
    flag = ("bad", f"❌ Stretched — a bad year could need about {_fmt_money(wyc)}, well above your "
                   f"{_fmt_money(max_top_up)} ceiling. Consider more shares or a bigger deposit.")
_render_html(f'<div class="flag {flag[0]}">{flag[1]}</div>')

if property_share_mix < 1.0:
    pp = int(property_share_mix * 100)
    _render_html(f"""<div class="pvs-section-sub" style="margin-top:8px;">Your chosen mix
    ({pp}% property / {100-pp}% shares) beats pure shares in <b>{result['p_mix_beats_pure_shares']:.0%}</b>
    of futures · median wealth {_fmt_money(result['median_mixed_wealth'])} · stays solvent {result['p_mix_solvent']:.0%}.</div>""")

good = "good" if result["p_solvent"] >= 0.95 else ""
_render_html(f"""
<div class="tiles">
  <div class="tile"><div class="tlabel">Typical property wealth</div><div class="tval">{_fmt_money(result['median_property_wealth'])}</div></div>
  <div class="tile"><div class="tlabel">Typical shares wealth</div><div class="tval">{_fmt_money(result['median_shares_wealth'])}</div></div>
  <div class="tile"><div class="tlabel">Worst-year cash needed</div><div class="tval">{_fmt_money(wyc)}</div></div>
  <div class="tile {good}"><div class="tlabel">Chance you never run out of cash</div><div class="tval">{result['p_solvent']:.0%}</div></div>
</div>
""")

# ---------------------------------------------------------------------------
# Detail expanders
# ---------------------------------------------------------------------------
with st.expander("📈 Year-by-year breakdown (chart + table)"):
    render_year_by_year_chart(result, horizon, property_share_mix_pct, deflate, yearly_deflator)
    render_year_by_year_table(result, horizon, property_share_mix_pct, deflate, yearly_deflator)

with st.expander("⚖️ Compare all property/shares mixes"):
    render_comparison_table(sweep_rows, recommended_mix)

with st.expander("🎲 Range of outcomes & cashflow stress"):
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=result["property_terminal_wealth"], name="Property",
                  opacity=0.65, nbinsx=40, marker_color=AMBER))
    fig.add_trace(go.Histogram(x=result["shares_terminal_wealth"], name="Shares",
                  opacity=0.65, nbinsx=40, marker_color=TEAL))
    if property_share_mix < 1.0:
        fig.add_trace(go.Histogram(x=result["mixed_terminal_wealth"],
                      name=f"Mix ({property_share_mix_pct}/{100-property_share_mix_pct})",
                      opacity=0.65, nbinsx=40, marker_color=GREEN))
    fig.update_layout(barmode="overlay", title=dict(text=f"Where you might land after {horizon} years", font=dict(size=15)),
                      xaxis_title="Final wealth ($)", yaxis_title="Number of futures",
                      plot_bgcolor="white", height=360, margin=dict(t=50))
    fig.update_xaxes(gridcolor="#f0f0f0"); fig.update_yaxes(gridcolor="#f0f0f0")
    st.plotly_chart(fig, width="stretch")

    years = np.arange(1, horizon + 1)
    oc = result["outside_cash_per_trial_year"]
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=years, y=np.median(oc, axis=0), mode="lines", name="Typical year",
                  line=dict(color=GREEN, width=2.5)))
    fig2.add_trace(go.Scatter(x=years, y=np.percentile(oc, 90, axis=0), mode="lines",
                  name="Bad year (90th pct)", line=dict(color=RED, dash="dot")))
    fig2.add_trace(go.Scatter(x=years, y=np.percentile(oc, 10, axis=0), mode="lines",
                  name="Good year (10th pct)", line=dict(color=TEAL, dash="dot")))
    fig2.add_hline(y=max_top_up, line_dash="dash", line_color=RED,
                  annotation_text=f"Your ceiling: {_fmt_money(max_top_up)}")
    fig2.update_layout(title=dict(text="Out-of-pocket cash you'd need each year", font=dict(size=15)),
                      xaxis_title="Year", yaxis_title="Annual top-up ($)", plot_bgcolor="white",
                      height=360, margin=dict(t=50), hovermode="x unified")
    fig2.update_xaxes(gridcolor="#f0f0f0"); fig2.update_yaxes(gridcolor="#f0f0f0")
    st.plotly_chart(fig2, width="stretch")

with st.expander("🏛 Setup & tax rules used"):
    notes = []
    if effective_property_regime == "restricted_2027":
        notes.append("**Budget 2026-27 rules:** from Jul 2027, rental losses on this property can't reduce your "
                     "salary tax (they carry forward); capital gains use a transitional split. **Announcement only — "
                     "not yet law.**")
    if property_age == "new_build" and property_regime == "restricted_2027" and effective_property_regime == "current":
        notes.append("**New-build carve-out applied** — new builds keep current rules, so 'current' is used here.")
    if comparison_mode == "fair_fight":
        notes.append("**Equal-leverage mode:** margin-call risk (forced selling in a crash) is **not** modelled.")
    notes.append("Both strategies deploy the same total cash each year (equal-contribution comparison).")
    for nme in notes:
        st.markdown(f"- {nme}")
    st.markdown(f"""
- **Tax:** SA, marginal rate {mtr:.0%} (from ${income:,} income), FY2026 brackets
- **Property:** {property_age.replace('_', ' ').title()}, {asset_type.title()}, {_fmt_pct(gross_yield)} yield
- **Upfront cash:** {_fmt_money(upfront)} ({_fmt_money(deposit)} deposit + {_fmt_money(stamp_duty_amount)} stamp duty + ${buying_costs:,} buying costs)
- **Shares profile:** {portfolio_profile.replace('_', ' ').title()} (avg {PORTFOLIO_PROFILES[portfolio_profile]['return_mu']:.1%}, {PORTFOLIO_PROFILES[portfolio_profile]['franked']:.0%} franked)
- **Correlation:** {correlation:.2f} · **CPI:** {cpi:.1%} · **5,000 trials, fixed seed** (~±1-2% sampling noise on the headline)
""")

# ---------------------------------------------------------------------------
# Save scenario + disclaimer
# ---------------------------------------------------------------------------
scenario = json.dumps({
    "purchase_price": purchase_price, "deposit_pct": deposit_pct, "gross_yield_pct": gross_yield * 100,
    "income": income, "mtr": mtr, "loan_rate_pct": loan_rate * 100, "horizon": horizon,
    "max_top_up": max_top_up, "property_share_mix_pct": property_share_mix_pct,
    "portfolio_profile": portfolio_profile, "property_regime": property_regime,
}, indent=2)
st.download_button("⬇ Save this scenario (JSON)", scenario, file_name="property-vs-shares-scenario.json",
                   mime="application/json")
st.caption("Tip: this page's web address (URL) now holds your scenario — bookmark or copy it to come back or share.")

_render_html("""
<div class="disclaimer"><b>Not financial advice.</b> This is a scenario explorer for personal use, not a prediction
and not a recommendation. Simulations and past performance don't guarantee future results. Tax law, interest rates,
and property markets change, and the defaults may not match your circumstances. Verify each input against your own
lender quote, suburb rental data, and the ATO, and speak to a licensed financial adviser before making a decision.
South Australia tax tables only; single property; some costs (rates/insurance line items, margin-call risk) are
simplified. Budget 2026-27 rules are announcement-only and not yet legislated.</div>
""")
