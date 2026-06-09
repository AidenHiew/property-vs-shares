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
from ui.common import (GREEN, TEAL, AMBER, RED, AMBER_DK, INK, MUTED, FAINT, LINE,
                       GLOBAL_CSS, _render_html, _fmt_money, _fmt_dollars, _fmt_pct)
from ui.persona import (compute_persona_sweep, find_optimal_mix,
                        render_persona_cards, render_comparison_table)
from ui.onboarding import render_hero, render_limitations, render_full_guide


# ============================================================================
# Small helpers
# ============================================================================
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

render_hero()

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
    annual_land_tax = st.number_input(
        "Annual land tax ($)", min_value=0, value=qp("landtax", int, 0), step=500,
        help="Off by default. A real, tax-deductible annual cost (varies by state and land value). "
             "Leaving it 0 makes property look slightly cheaper than reality.",
    )

    st.markdown("**The choice**")
    _custom = st.session_state.get("persona_pick") == "Custom"
    property_share_mix_pct = st.slider(
        "Custom mix (% property)", 0, 100, qp("mix", int, 50), step=10,
        disabled=not _custom,
        help="Enabled when you pick 'Custom' above. Otherwise the chosen persona sets the mix.",
    )
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
    "landtax": annual_land_tax,
    "persona": (st.session_state["persona_pick"] if "persona_pick" in st.session_state else qp("persona", str, "Balanced")),
    **({"mix": property_share_mix_pct} if (st.session_state["persona_pick"] if "persona_pick" in st.session_state else qp("persona", str, "Balanced")) == "Custom" else {}),
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
    annual_land_tax=annual_land_tax,
    mode=comparison_mode, margin_loan_rate=margin_loan_rate, isolate_asset_quality=isolate_asset_quality,
    correlation=correlation, mtr=mtr, cpi=cpi, drp=True, serviceability_ceiling=max_top_up, seed=42,
    return_distribution=return_distribution, t_df=t_df,
    loan_rate_distribution=return_distribution, loan_rate_t_df=t_df,
)


@st.cache_data(show_spinner="Running 5,000 simulated futures…")
def cached_run(**kwargs):
    return run_monte_carlo(**kwargs)


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
PERSONA_TO_THRESHOLD = {"Safe": 0.99, "Balanced": 0.95, "Wealth Maximizer": 0.85}
options = ["Safe", "Balanced", "Wealth Maximizer", "Custom"]
label_map = {k: (k + " ★" if k == "Balanced" and not stale else k) for k in options}
if stale:
    st.caption("Recommendations are stale — click ↻ Update recommendations.")
picked = st.segmented_control(
    "View breakdown for", options, format_func=lambda k: label_map[k],
    default=qp("persona", str, "Balanced"), key="persona_pick",
)
if picked is None:
    picked = "Balanced"
if picked == "Custom":
    breakdown_mix_pct = property_share_mix_pct
else:
    _row = find_optimal_mix(sweep_rows, PERSONA_TO_THRESHOLD[picked])
    breakdown_mix_pct = _row["mix_pct"] if _row else (balanced["mix_pct"] if balanced else 50)
recommended_mix = breakdown_mix_pct

# Run simulation for the selected breakdown mix
breakdown_mix = breakdown_mix_pct / 100
result = cached_run(trials=5000, property_share_mix=breakdown_mix, **run_kwargs)

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

# "What now?" guidance
_render_html(f"""
<div class="blurb" style="max-width:none;margin-top:6px;">
<b>What this means:</b> if you want both, the recommended split is the most wealth at that safety level — e.g. put the
property-share of your savings toward the property and the rest into shares. It is <i>not</i> a push to own both.
Next step: talk to a licensed financial adviser about your loan approval, tax, and goals.
</div>""")

render_limitations()

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

if breakdown_mix < 1.0:
    pp = int(breakdown_mix * 100)
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
    render_year_by_year_chart(result, horizon, breakdown_mix_pct, deflate, yearly_deflator)
    render_year_by_year_table(result, horizon, breakdown_mix_pct, deflate, yearly_deflator)

with st.expander("⚖️ Compare all property/shares mixes"):
    render_comparison_table(sweep_rows, recommended_mix)

with st.expander("🎲 Range of outcomes & cashflow stress"):
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=result["property_terminal_wealth"], name="Property",
                  opacity=0.65, nbinsx=40, marker_color=AMBER))
    fig.add_trace(go.Histogram(x=result["shares_terminal_wealth"], name="Shares",
                  opacity=0.65, nbinsx=40, marker_color=TEAL))
    if breakdown_mix < 1.0:
        fig.add_trace(go.Histogram(x=result["mixed_terminal_wealth"],
                      name=f"Mix ({breakdown_mix_pct}/{100-breakdown_mix_pct})",
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

render_full_guide()

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
    _render_html(f"""
<ul>
<li><b>Tax:</b> SA, marginal rate {mtr:.0%} (from <span>${income:,}</span> income), FY2026 brackets</li>
<li><b>Property:</b> {property_age.replace('_', ' ').title()}, {asset_type.title()}, {_fmt_pct(gross_yield)} yield</li>
<li><b>Upfront cash:</b> <span>{_fmt_money(upfront)}</span> (<span>{_fmt_money(deposit)}</span> deposit + <span>{_fmt_money(stamp_duty_amount)}</span> stamp duty + <span>${buying_costs:,}</span> buying costs)</li>
<li><b>Shares profile:</b> {portfolio_profile.replace('_', ' ').title()} (avg {PORTFOLIO_PROFILES[portfolio_profile]['return_mu']:.1%}, {PORTFOLIO_PROFILES[portfolio_profile]['franked']:.0%} franked)</li>
<li><b>Correlation:</b> {correlation:.2f} · <b>CPI:</b> {cpi:.1%} · <b>5,000 trials, fixed seed</b> (~±1-2% sampling noise on the headline)</li>
</ul>
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
Stamp duty is state-specific (selected above); income tax, CGT and negative gearing are federal. Single property; land tax is your flat input; some costs (rates/insurance, margin-call risk) are simplified. Budget 2026-27 rules are announcement-only and not yet legislated.</div>
""")
