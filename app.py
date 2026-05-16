"""Property vs Shares Streamlit UI. Imports the model engine and renders sliders + charts."""
import streamlit as st
import numpy as np
import plotly.graph_objects as go

from model.monte_carlo import run_monte_carlo
from model.tax import sa_stamp_duty
from model.normalisation import PORTFOLIO_PROFILES

st.set_page_config(page_title="Property vs Shares", layout="wide")

st.title("Property vs Shares — your scenario")

# --------------- Sidebar: STANDARD inputs ---------------
with st.sidebar:
    st.header("Standard inputs")
    purchase_price = st.number_input("Purchase price", value=700_000, step=10_000)
    deposit_pct = st.slider("Deposit %", 5, 50, 20)
    deposit = purchase_price * deposit_pct / 100

    loan_rate = st.slider("Loan rate (mean)", 3.0, 10.0, 6.0, step=0.1) / 100
    horizon = st.slider("Investment horizon (years)", 5, 40, 25)

    mtr_label_to_value = {"19%": 0.19, "30%": 0.30, "37%": 0.37, "45%": 0.45}
    mtr_label = st.selectbox("Marginal tax rate", list(mtr_label_to_value.keys()), index=2)
    mtr = mtr_label_to_value[mtr_label]

    property_age = st.selectbox(
        "Property age",
        ["new_build", "established_post_2017", "established_pre_2017"],
        index=1,
        format_func=lambda x: {
            "new_build": "New build",
            "established_post_2017": "Established (post-May-2017)",
            "established_pre_2017": "Established (pre-May-2017)",
        }[x],
    )
    asset_type = st.selectbox(
        "Asset type",
        ["house", "apartment", "townhouse"],
        format_func=str.title,
    )

    property_regime = st.selectbox(
        "Negative gearing & CGT regime",
        ["current", "restricted_2027"],
        index=1,  # default to NEW regime — matches today-purchase of established property
        format_func=lambda x: {
            "current": "Current rules (full NG + 50% CGT discount)",
            "restricted_2027": "Budget 2026-27 (NG quarantined + transitional CGT, FY2028+)",
        }[x],
        help="Federal Budget 2026-27 changes apply to established residential property "
             "bought after 7:30pm 12 May 2026, effective 1 July 2027. Pick 'Current rules' "
             "for new builds, grandfathered (pre-Budget) properties, or to compare baseline."
    )

    gross_yield = st.slider("Gross rental yield %", 2.0, 7.0, 4.0, step=0.1) / 100
    vacancy_weeks = st.slider("Vacancy (weeks/yr)", 0, 8, 2)

    portfolio_profile = st.selectbox(
        "Portfolio profile",
        ["asx_only", "global", "blended"],
        index=2,
        format_func=lambda x: {
            "asx_only": "ASX-only",
            "global": "Global (developed)",
            "blended": "Blended (50/50)",
        }[x],
    )

    max_top_up = st.number_input(
        "Max annual out-of-pocket top-up",
        value=20_000, step=1_000,
        help="Used to flag scenarios where property cashflow exceeds your serviceability."
    )

    with st.expander("Advanced", expanded=False):
        st.subheader("Volatility (σ) overrides")
        property_growth_sigma = st.slider("Property growth σ", 0.05, 0.20, 0.11, step=0.01)
        share_return_sigma = st.slider("Share return σ", 0.05, 0.30, 0.15, step=0.01)
        loan_rate_sigma = st.slider("Loan rate σ (pp)", 0.5, 2.0, 1.0, step=0.1) / 100
        rental_yield_sigma = st.slider("Rental yield σ (pp)", 0.1, 1.0, 0.5, step=0.1) / 100
        vacancy_weeks_sigma = st.slider("Vacancy σ (weeks)", 0.5, 4.0, 1.0, step=0.5)
        property_growth_mu = st.slider("Property growth μ", 0.0, 0.10, 0.055, step=0.005)
        share_return_mu = st.slider("Share return μ", 0.0, 0.15, 0.085, step=0.005)

        st.subheader("Correlation")
        corr_quick = st.radio("Quick-pick", [-0.1, 0.3, 0.6], index=1, horizontal=True,
                              format_func=lambda x: f"{x:.1f}")
        correlation = st.slider("Property–shares correlation", -1.0, 1.0, corr_quick, step=0.05)

        st.subheader("Mode B — counterfactual")
        margin_loan_rate = st.slider("Margin loan rate", 0.05, 0.12, 0.075, step=0.005)
        isolate_asset_quality = st.checkbox(
            "Isolate asset quality (pin shares loan rate to mortgage rate)",
            value=False,
            help="Counterfactual — retail investors cannot borrow against shares on mortgage terms."
        )

        st.subheader("Other")
        cpi = st.slider("CPI", 0.0, 0.05, 0.025, step=0.005)
        depreciation_override = st.number_input("Depreciation override (annual)", value=0, step=500)
        depreciation_override = depreciation_override if depreciation_override > 0 else None
        management_fee_pct = st.slider("Management fee %", 0.0, 0.12, 0.07, step=0.005)
        maintenance_pct = st.slider("Maintenance + insurance + rates % of value/yr", 0.005, 0.030, 0.012, step=0.001)

# --------------- Main pane: comparison radio + display toggle ---------------
col_mode, col_display = st.columns([2, 1])
with col_mode:
    mode = st.radio("Comparison mode", ["realistic", "fair_fight"], horizontal=True,
                    format_func=lambda x: {"realistic": "Realistic", "fair_fight": "Fair fight"}[x])
with col_display:
    display_mode = st.radio("Display", ["nominal", "today"], horizontal=True,
                            format_func=lambda x: {"nominal": "Nominal", "today": "Today's $"}[x])

# Compute stamp duty + buying costs from inputs
stamp_duty = sa_stamp_duty(purchase_price)
buying_costs = 2_600  # conveyancing + inspection + loan app

st.markdown(f"**Upfront cash deployed:** ${deposit + stamp_duty + buying_costs:,.0f} "
            f"(${deposit:,.0f} deposit + ${stamp_duty:,.0f} stamp duty + ${buying_costs:,.0f} buying costs)")

# Federal Budget 2026-27 regime banner
if property_regime == "restricted_2027":
    st.info(
        "🏛 **Federal Budget 2026-27 regime.** From FY2028: rental losses on this "
        "property are quarantined (no salary refund; carry forward to future residential "
        "income or capital gain). Terminal CGT splits at 1 Jul 2027 — gain accrued "
        "before commencement uses current 50% discount; gain after commencement uses "
        "CPI-indexed cost base + max(MTR, 30%) effective rate. Both changes are "
        "**announcement-only** (not yet legislated). Model assumes no other residential "
        "property income offsetting the loss pool."
    )

# Symmetric reinvestment banner
st.warning(
    "⚠ Both strategies deploy the same total capital each year. When property needs $X to "
    "feed negative gearing, shares invests the same $X. (Equal outside-cash contributions — ON.)"
)

# Margin call warning if Mode B
if mode == "fair_fight":
    st.error(
        "Mode B does not model margin-call risk. In a 30%+ share crash, your margin lender "
        "may force a sale at the bottom — this risk is real and is not captured below."
    )

# Run Monte Carlo (cached)
@st.cache_data(show_spinner="Running 5,000 Monte Carlo trials...")
def cached_run(**kwargs):
    return run_monte_carlo(**kwargs)

result = cached_run(
    trials=5000, horizon_years=horizon,
    purchase_price=purchase_price, deposit=deposit,
    stamp_duty=stamp_duty, buying_costs=buying_costs,
    loan_rate_mu=loan_rate, loan_rate_sigma=loan_rate_sigma,
    gross_yield=gross_yield,
    vacancy_weeks_mu=vacancy_weeks, vacancy_weeks_sigma=vacancy_weeks_sigma,
    rental_yield_sigma=rental_yield_sigma,
    property_growth_mu=property_growth_mu, property_growth_sigma=property_growth_sigma,
    share_return_mu=share_return_mu, share_return_sigma=share_return_sigma,
    management_fee_pct=management_fee_pct, maintenance_pct=maintenance_pct,
    property_age=property_age, asset_type=asset_type,
    depreciation_override=depreciation_override,
    property_regime=property_regime,
    portfolio_profile=portfolio_profile,
    mode=mode,
    margin_loan_rate=margin_loan_rate, isolate_asset_quality=isolate_asset_quality,
    correlation=correlation,
    mtr=mtr, cpi=cpi, drp=True,
    serviceability_ceiling=max_top_up,
    seed=42,
)

if display_mode == "today":
    # Deflate terminal values to today's purchasing power.
    # Note: mutating the returned dict in-place is safe here because st.cache_data returns
    # a copy of the cached value (Streamlit deep-copies on cache hit), so we don't corrupt
    # the cache. If behaviour changes, switch to result_display = dict(result) below.
    deflator = (1 + cpi) ** horizon
    result["property_terminal_wealth"] = result["property_terminal_wealth"] / deflator
    result["shares_terminal_wealth"] = result["shares_terminal_wealth"] / deflator
    result["median_property_wealth"] = result["median_property_wealth"] / deflator
    result["median_shares_wealth"] = result["median_shares_wealth"] / deflator
    # Outside cash is per-year; deflate each year by its own deflator
    yearly_deflator = (1 + cpi) ** np.arange(1, horizon + 1)
    result["outside_cash_per_trial_year"] = result["outside_cash_per_trial_year"] / yearly_deflator
    result["worst_year_cash"] = result["worst_year_cash"] / deflator  # rough; use horizon's deflator

# Headline
st.header(
    f"Property **succeeds** for you in **{result['p_property_succeeds']:.0%}** "
    f"of {result['property_terminal_wealth'].size:,} simulated {horizon}-year futures."
)
st.caption(
    f"Property beats shares in {result['p_property_wins']:.0%} of trials, "
    f"but only {result['p_solvent']:.0%} stay within your ${max_top_up:,} serviceability ceiling. "
    f"'Succeeds' = both, jointly."
)

# Supporting metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Median property wealth", f"${result['median_property_wealth']:,.0f}")
m2.metric("Median shares wealth", f"${result['median_shares_wealth']:,.0f}")
m3.metric("Worst-year cash needed", f"${result['worst_year_cash']:,.0f}")
m4.metric("P(strategy stays solvent)", f"{result['p_solvent']:.0%}")

st.subheader("Terminal wealth distribution")
fig = go.Figure()
fig.add_trace(go.Histogram(
    x=result["property_terminal_wealth"], name="Property",
    opacity=0.6, nbinsx=50,
))
fig.add_trace(go.Histogram(
    x=result["shares_terminal_wealth"], name="Shares",
    opacity=0.6, nbinsx=50,
))
fig.update_layout(barmode="overlay", xaxis_title="Terminal wealth ($)", yaxis_title="Trials")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Cashflow stress")
years = np.arange(1, horizon + 1)
median_cashflow = np.median(result["outside_cash_per_trial_year"], axis=0)
p90_cashflow = np.percentile(result["outside_cash_per_trial_year"], 90, axis=0)
p10_cashflow = np.percentile(result["outside_cash_per_trial_year"], 10, axis=0)

fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=years, y=median_cashflow, mode="lines", name="Median"))
fig2.add_trace(go.Scatter(x=years, y=p90_cashflow, mode="lines", name="90th %ile (worst)",
                          line=dict(dash="dot")))
fig2.add_trace(go.Scatter(x=years, y=p10_cashflow, mode="lines", name="10th %ile (best)",
                          line=dict(dash="dot")))
fig2.add_hline(y=max_top_up, line_dash="dash", line_color="red",
               annotation_text=f"Your serviceability ceiling: ${max_top_up:,}")
fig2.update_layout(xaxis_title="Year", yaxis_title="Annual out-of-pocket cash ($)")
st.plotly_chart(fig2, use_container_width=True)

with st.expander("Assumptions used in this run", expanded=False):
    st.markdown(f"""
- **Tax:** SA, MTR {mtr:.0%}, FY2026 Stage 3 brackets
- **Negative gearing:** current FY2026 rules ⚠ law potentially changing in Budget 2026-27
- **Property:** {property_age.replace('_', ' ').title()}, {asset_type.title()}
- **Portfolio profile:** {portfolio_profile.replace('_', ' ').title()} (μ {PORTFOLIO_PROFILES[portfolio_profile]['return_mu']:.1%}, σ {PORTFOLIO_PROFILES[portfolio_profile]['return_sigma']:.1%}, {PORTFOLIO_PROFILES[portfolio_profile]['franked']:.0%} franked)
- **Correlation (property ↔ shares):** {correlation:.2f}
- **Monte Carlo:** 5,000 trials, fixed seed (reproducible)
- **CPI:** {cpi:.1%} applied to rent and holding costs annually
- **Buy-and-hold share portfolio** — no mid-period rebalancing CGT events
- **Disclaimer:** Normal distributions; does not predict severe market crashes (fat-tail events)
- **Counterfactual mode (if Mode B isolated):** assumes margin loan at mortgage rate — not real-world available
""")
