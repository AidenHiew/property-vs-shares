"""Compare v2 — same-money property-vs-shares verdict (standalone screen).

Run: .venv/bin/streamlit run app_compare.py
Engine reused unchanged; see
docs/superpowers/specs/2026-06-19-property-vs-shares-compare-v2-design.md
"""
import streamlit as st

from model.duty import stamp_duty
from model.monte_carlo import run_monte_carlo
from model.normalisation import PORTFOLIO_PROFILES
from ui.common import GLOBAL_CSS, _render_html
from ui.verdict import (
    compute_verdict, render_affordability, render_cards,
    render_fairfight_spoiler, render_trust_line, render_win_line,
)

HORIZONS = [5, 10, 15, 20]
PROFILES = ["asx_only", "global", "blended"]


# ----- clamp helpers (read AND write, project rule) --------------------------
def clamp_horizon(v) -> int:
    try:
        v = int(v)
    except (ValueError, TypeError):
        return 10
    return v if v in HORIZONS else 10


def clamp_rate(v) -> float:
    try:
        v = float(v)
    except (ValueError, TypeError):
        return 0.062
    return max(0.0, min(0.30, v))


def clamp_deposit(v, price: float) -> float:
    try:
        v = float(v)
    except (ValueError, TypeError):
        return min(190_000.0, price)
    return max(0.0, min(v, price))


def clamp_topup(v) -> float:
    try:
        v = float(v)
    except (ValueError, TypeError):
        return 20_000.0
    return max(0.0, v)


# Generic clamped reader — a malformed/junk OR out-of-range URL value must fall
# back inside [lo, hi], never raise. Streamlit number_input raises if its `value=`
# is outside [min,max], so EVERY numeric default must already be clamped here
# (project rule — a "junk" in the URL once crashed the app, 6bab10e).
def _qp_clamped(key, default: float, lo: float, hi: float) -> float:
    try:
        v = float(st.query_params.get(key, default))
    except (ValueError, TypeError):
        return default
    return max(lo, min(hi, v))


def _qp(key, default):
    return st.query_params.get(key, default)


@st.cache_data
def cached_run(**kwargs):
    return run_monte_carlo(**kwargs)


def main() -> None:
    st.set_page_config(page_title="Property vs Shares — Compare", layout="wide", page_icon="🏠")
    _render_html(GLOBAL_CSS)

    # --- horizon toggle ---
    horizon = clamp_horizon(_qp("yrs", 10))
    horizon = st.segmented_control("Time horizon (years)", HORIZONS,
                                   default=horizon, key="cmp_horizon") or horizon

    # --- slim inputs (every numeric default pre-clamped to its widget domain) ---
    c1, c2, c3 = st.columns(3)
    with c1:
        price = st.number_input("Purchase price",
                                value=int(_qp_clamped("price", 950_000, 50_000, 50_000_000)),
                                step=10_000, min_value=50_000)
        deposit = clamp_deposit(_qp("dep", 190_000), price)
        deposit = st.number_input("Deposit", value=int(deposit), step=10_000,
                                  min_value=0, max_value=int(price))
        # rate stored in the URL as a percent (e.g. 6.2); clamp_rate works in fraction space.
        loan_rate = clamp_rate(_qp_clamped("rate", 6.2, 0.0, 30.0) / 100)
        loan_rate = st.number_input("Loan interest rate %", value=loan_rate * 100,
                                    step=0.1, min_value=0.0, max_value=30.0) / 100
    with c2:
        gross_yield = st.number_input("Gross rent yield %",
                                      value=_qp_clamped("yield", 3.5, 0.0, 15.0),
                                      step=0.1, min_value=0.0, max_value=15.0) / 100
        property_growth_mu = st.number_input("Property capital growth %/yr",
                                             value=_qp_clamped("grow", 5.5, -5.0, 20.0),
                                             step=0.1, min_value=-5.0, max_value=20.0) / 100
        vacancy_weeks = st.number_input("Vacancy (weeks/yr)",
                                        value=_qp_clamped("vac", 2.0, 0.0, 52.0),
                                        step=0.5, min_value=0.0, max_value=52.0)
    with c3:
        state = st.selectbox("State", ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "ACT", "NT"],
                             index=0)
        derived_duty = stamp_duty(state, price)
        upfront_costs = st.number_input("Upfront costs (stamp duty + fees)",
                                        value=int(_qp_clamped("upfront", int(derived_duty + 2_600),
                                                              0, 10_000_000)),
                                        step=1_000, min_value=0)
        profile = st.selectbox("Share portfolio", PROFILES,
                               index=PROFILES.index(_qp("port", "blended"))
                               if _qp("port", "blended") in PROFILES else 2)
        mtr = st.number_input("Marginal tax rate %",
                              value=_qp_clamped("mtr", 37.0, 0.0, 47.0),
                              step=1.0, min_value=0.0, max_value=47.0) / 100

    max_top_up = clamp_topup(_qp("topup", 20_000))
    max_top_up = st.number_input("Annual top-up you'd plan for", value=int(max_top_up),
                                 step=1_000, min_value=0)

    # --- persist clamped values to URL (write side of the rule) ---
    st.query_params.update({k: str(v) for k, v in {
        "yrs": horizon, "price": price, "dep": int(deposit),
        "rate": round(loan_rate * 100, 1), "yield": round(gross_yield * 100, 1),
        "grow": round(property_growth_mu * 100, 1), "vac": vacancy_weeks,
        "upfront": int(upfront_costs), "port": profile,
        "mtr": round(mtr * 100, 1), "topup": int(max_top_up),
    }.items()})

    # --- two cached runs ---
    prof = PORTFOLIO_PROFILES[profile]
    base = dict(
        trials=5000, horizon_years=horizon, purchase_price=price, deposit=deposit,
        stamp_duty=float(upfront_costs), buying_costs=0.0,
        loan_rate_mu=loan_rate, loan_rate_sigma=0.01, gross_yield=gross_yield,
        vacancy_weeks_mu=vacancy_weeks, vacancy_weeks_sigma=1.0, rental_yield_sigma=0.0,
        property_growth_mu=property_growth_mu, property_growth_sigma=0.12,
        management_fee_pct=0.07, maintenance_pct=0.008, property_age="established_pre_2017",
        asset_type="house", depreciation_override=None,
        share_return_mu=prof["return_mu"], share_return_sigma=prof["return_sigma"],
        portfolio_profile=profile, margin_loan_rate=0.085, correlation=0.3,
        mtr=mtr, cpi=0.025, drp=True, serviceability_ceiling=float(max_top_up), seed=42,
    )
    realistic = cached_run(mode="realistic", isolate_asset_quality=False, **base)
    fair_fight = cached_run(mode="fair_fight", isolate_asset_quality=True, **base)

    # --- compute + render ---
    v = compute_verdict(realistic, fair_fight, serviceability_ceiling=float(max_top_up),
                        deposit=deposit, upfront_costs=float(upfront_costs))
    leverage_l = price - (deposit + upfront_costs)

    _render_html(render_trust_line(v, horizon))
    _render_html(render_cards(v))
    _render_html(render_win_line(v))
    _render_html(render_fairfight_spoiler(v, leverage_l))
    with st.expander("See the side-by-side →"):
        st.write(f"Fair-fight shares median: ${v.fairfight_y:,.0f}")
    _render_html(render_affordability(v, horizon, float(max_top_up)))


if __name__ == "__main__":
    main()
