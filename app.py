"""Property vs Shares Streamlit UI. Imports the model engine and renders sliders + charts."""
import streamlit as st
import numpy as np
import plotly.graph_objects as go

from model.monte_carlo import run_monte_carlo
from model.tax import sa_stamp_duty
from model.normalisation import PORTFOLIO_PROFILES


# --------------- Persona sweep helpers ---------------

@st.cache_data(show_spinner="Computing allocation recommendations...")
def compute_persona_sweep(**kwargs):
    """Run mix sweep at 11 points × 2000 trials. Returns list of dicts per mix point."""
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


PERSONA_DEFS = [
    ("Safe Player",      0.99, "I want a near-certainty of staying within my cash ceiling — even if it costs me some wealth."),
    ("Balanced",         0.95, "I want very high safety, but I'll accept a small chance of cashflow stress for more wealth."),
    ("Wealth Maximizer", 0.85, "I'll accept real risk of forced sale (~1 in 7 futures) in exchange for the highest wealth."),
]


def find_optimal_mix(rows, min_p_solvent):
    safe = [r for r in rows if r["p_solvent"] >= min_p_solvent]
    if not safe:
        return None  # caller handles
    return max(safe, key=lambda r: r["median_wealth"])


def _fmt_money(x):
    if x >= 1_000_000:
        return f"${x/1_000_000:.2f}M"
    elif x >= 1_000:
        return f"${x/1_000:.0f}k"
    return f"${x:.0f}"


def _fmt_pct(x):
    return f"{x*100:.1f}%"


def _card_css():
    return """
    .cards-container {
        display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 12px;
    }
    .card-rec {
        background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 24px;
        position: relative; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .card-rec.recommended { border: 2px solid #16a34a; }
    .recommended-badge {
        background: #16a34a; color: white; font-size: 11px; font-weight: 600;
        padding: 4px 10px; border-radius: 12px; display: inline-block; margin-bottom: 12px;
        letter-spacing: 0.3px;
    }
    .persona-name {
        font-size: 12px; font-weight: 600; color: #6b7280;
        text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;
    }
    .persona-threshold { font-size: 11px; color: #9ca3af; margin-bottom: 14px; font-weight: 500; }
    .allocation { font-size: 28px; font-weight: 700; color: #1a1a1a; line-height: 1.1; }
    .allocation-sub { font-size: 13px; color: #6b7280; margin-top: 2px; }
    .divider { height: 1px; background: #e5e7eb; margin: 16px 0; }
    .metric { margin-bottom: 10px; }
    .metric-label { font-size: 12px; color: #6b7280; margin-bottom: 2px; }
    .metric-value { font-size: 17px; font-weight: 600; color: #1a1a1a; }
    .blurb { font-size: 12px; color: #4b5563; font-style: italic; margin: 10px 0 0 0; }
    """


def _three_cards_html(resolved, safe_player_failed):
    """Build the 3-card grid HTML."""
    cards_html = ""
    for i, p in enumerate(resolved):
        name = p["name"]
        threshold = p["threshold"]
        blurb = p["blurb"]
        row = p["row"]
        is_recommended = (name == "Balanced")
        badge = '<div class="recommended-badge">★ Recommended</div>' if is_recommended else ''
        card_class = "card-rec recommended" if is_recommended else "card-rec"

        if i == 0 and safe_player_failed:
            cards_html += f"""
            <div class="{card_class}">
                {badge}
                <div class="persona-name">{name}</div>
                <div class="persona-threshold">Safety appetite: ≥{int(threshold*100)}% safe</div>
                <div class="allocation" style="font-size:18px;color:#dc2626;">Unreachable</div>
                <div class="divider"></div>
                <p class="blurb">No allocation reaches ≥{int(threshold*100)}% safety under your inputs.
                Try raising your serviceability ceiling or lowering MTR.</p>
            </div>
            """
            continue

        if row is None:
            continue

        mix_pct = row["mix_pct"]
        cards_html += f"""
        <div class="{card_class}">
            {badge}
            <div class="persona-name">{name}</div>
            <div class="persona-threshold">Safety appetite: ≥{int(threshold*100)}% safe</div>
            <div class="allocation">{mix_pct}% property</div>
            <div class="allocation-sub">{100-mix_pct}% shares</div>
            <div class="divider"></div>
            <div class="metric">
                <div class="metric-label">Typical wealth in 25 years</div>
                <div class="metric-value">{_fmt_money(row['median_wealth'])}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Chance never runs out of cash</div>
                <div class="metric-value">{_fmt_pct(row['p_solvent'])}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Worst year cash demand</div>
                <div class="metric-value">{_fmt_money(row['worst_year_cash'])}</div>
            </div>
            <div class="divider"></div>
            <p class="blurb">"{blurb}"</p>
        </div>
        """

    return f"""
    <style>
        {_card_css()}
    </style>
    <div class="cards-container">
        {cards_html}
    </div>
    """


def _merged_card_html(row):
    """Single card shown when all 3 safety thresholds resolve to the same mix."""
    mix_pct = row["mix_pct"]
    return f"""
    <style>{_card_css()}</style>
    <div class="cards-container" style="grid-template-columns:1fr;max-width:600px;margin:0 auto;">
        <div class="card-rec recommended">
            <div class="recommended-badge">★ Recommended</div>
            <div class="persona-name">Optimal allocation</div>
            <div class="allocation">{mix_pct}% property</div>
            <div class="allocation-sub">{100-mix_pct}% shares</div>
            <div class="divider"></div>
            <div class="metric">
                <div class="metric-label">Typical wealth in 25 years</div>
                <div class="metric-value">{_fmt_money(row['median_wealth'])}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Chance never runs out of cash</div>
                <div class="metric-value">{_fmt_pct(row['p_solvent'])}</div>
            </div>
            <div class="divider"></div>
            <p class="blurb">"All three safety thresholds (≥99%, ≥95%, ≥85%) point to the same allocation under your current inputs — pick this with confidence."</p>
        </div>
    </div>
    """


def render_persona_cards(rows):
    """Render the 3 persona cards as styled HTML via st.markdown.
    Handles merge case (all 3 resolve to same mix) and impossible case (no ≥99% safe)."""
    resolved = []
    for name, threshold, blurb in PERSONA_DEFS:
        opt = find_optimal_mix(rows, threshold)
        resolved.append({"name": name, "threshold": threshold, "blurb": blurb, "row": opt})

    safe_player_failed = resolved[0]["row"] is None

    if not safe_player_failed:
        mix_pcts = {p["row"]["mix_pct"] for p in resolved}
        if len(mix_pcts) == 1:
            single_mix = resolved[1]["row"]
            html = _merged_card_html(single_mix)
            st.markdown(html, unsafe_allow_html=True)
            return

    html = _three_cards_html(resolved, safe_player_failed)
    st.markdown(html, unsafe_allow_html=True)


def render_comparison_table(rows, recommended_mix):
    """Render the comparison table as styled HTML inside an expander."""
    table_rows_html = ""
    for row in rows:
        is_rec = row["mix_pct"] == recommended_mix
        row_class = "table-row-rec" if is_rec else ""
        star = ' <span style="color:#16a34a;">★</span>' if is_rec else ""
        table_rows_html += f"""
        <tr class="{row_class}">
            <td>{row['mix_pct']}%{star}</td>
            <td>{_fmt_money(row['median_wealth'])}</td>
            <td>{_fmt_pct(row['p_solvent'])}</td>
            <td>{_fmt_money(row['worst_year_cash'])}</td>
            <td>{_fmt_pct(row['p_beats_shares'])}</td>
        </tr>
        """
    html = f"""
    <style>
        .table-rec {{ width: 100%; border-collapse: collapse; font-size: 14px;
            background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;}}
        .table-rec thead {{ background: #f9fafb; }}
        .table-rec th {{ text-align: left; padding: 12px 16px; font-weight: 600;
            color: #374151; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;
            border-bottom: 2px solid #e5e7eb;}}
        .table-rec td {{ padding: 12px 16px; border-bottom: 1px solid #f3f4f6; color: #1a1a1a;}}
        .table-rec tr:last-child td {{ border-bottom: none; }}
        .table-rec .table-row-rec {{ background: #f0fdf4; font-weight: 600; }}
        .table-rec .table-row-rec td {{ color: #15803d; }}
    </style>
    <table class="table-rec">
        <thead><tr>
            <th>Property mix</th><th>Typical wealth (25y)</th>
            <th>Chance never runs out of cash</th><th>Worst year cash</th>
            <th>Beats pure shares</th>
        </tr></thead>
        <tbody>{table_rows_html}</tbody>
    </table>
    """
    st.markdown(html, unsafe_allow_html=True)

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

    property_share_mix_pct = st.slider(
        "Property share of allocation (%)",
        0, 100, 100, step=5,
        help="100% = pure property strategy (current default). 0% = pure shares. "
             "Anything in between is a weighted blend per Monte Carlo trial — preserves "
             "the property↔shares correlation structure automatically. Treats the property "
             "as continuously divisible (you can't actually own 60% of a house, but the "
             "model is for scoping a decision, not literal ownership)."
    )
    property_share_mix = property_share_mix_pct / 100

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
        # rental_yield_sigma slider hidden in v1 — it was wired through to run_monte_carlo
        # but never consumed (PropertyInputs takes a scalar gross_yield). Re-expose when
        # yield path-stochasticity is implemented (BACKLOG v1.2).
        rental_yield_sigma = 0.0
        vacancy_weeks_sigma = st.slider("Vacancy σ (weeks)", 0.5, 4.0, 1.0, step=0.5)
        property_growth_mu = st.slider("Property growth μ", 0.0, 0.10, 0.055, step=0.005)
        share_return_mu = st.slider("Share return μ", 0.0, 0.15, 0.085, step=0.005)

        st.subheader("Return distribution")
        return_distribution = st.selectbox(
            "Return distribution",
            ["gaussian", "student_t"],
            index=0,
            format_func=lambda x: {
                "gaussian": "Gaussian (normal — default)",
                "student_t": "Student-t (fatter tails, more honest about crashes)",
            }[x],
            help="Gaussian under-states tail risk. Student-t with df=5 matches empirical "
                 "equity kurtosis (~5-6) AND captures fat-tailed rate shocks (e.g. AU 1989, "
                 "2022). Realized σ is rescaled to match your specified σ. Applied to property "
                 "growth, share return, AND loan rate."
        )
        if return_distribution == "student_t":
            t_df = st.slider("Student-t degrees of freedom", 3, 30, 5,
                             help="Lower = fatter tails. df=5 matches equity returns; "
                                  "df=30+ ≈ Gaussian. df must be > 2 for finite variance.")
        else:
            t_df = 5  # unused

        st.subheader("Correlation")
        corr_quick = st.radio("Quick-pick", [-0.1, 0.3, 0.6], index=1, horizontal=True,
                              format_func=lambda x: f"{x:.1f}")
        correlation = st.slider("Property–shares correlation", -1.0, 1.0, corr_quick, step=0.05)

        # Budget 2026-27 new-build carve-out override (only relevant for new builds
        # selected with restricted_2027 regime — otherwise this checkbox is no-op).
        if property_age == "new_build":
            st.subheader("Budget 2026-27 new-build carve-out")
            override_new_build_carveout = st.checkbox(
                "Override carve-out (apply restricted rules to new build anyway)",
                value=False,
                help="Per the Budget 2026-27 announcement, new builds retain full "
                     "negative gearing and can elect either CGT method. The model "
                     "auto-applies 'current' rules for new builds regardless of the "
                     "regime selector. Tick this to model the counterfactual where "
                     "the carve-out is removed in future legislation."
            )
        else:
            override_new_build_carveout = False

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

# Apply Budget 2026-27 new-build carve-out unless explicitly overridden.
# Per the announcement, new builds retain full NG and can elect either CGT method.
if property_age == "new_build" and not override_new_build_carveout:
    effective_property_regime = "current"
else:
    effective_property_regime = property_regime

# Federal Budget 2026-27 regime banner
if effective_property_regime == "restricted_2027":
    st.info(
        "🏛 **Federal Budget 2026-27 regime.** From FY2028: rental losses on this "
        "property are quarantined (no salary refund; carry forward to future residential "
        "income or capital gain). Terminal CGT splits at 1 Jul 2027 — gain accrued "
        "before commencement uses current 50% discount; gain after commencement uses "
        "CPI-indexed cost base + max(MTR, 30%) effective rate. Both changes are "
        "**announcement-only** (not yet legislated). Model assumes no other residential "
        "property income offsetting the loss pool."
    )

# Carve-out notice: fires when user picked restricted_2027 but new-build override
# kept current rules applied
if (
    property_age == "new_build"
    and property_regime == "restricted_2027"
    and effective_property_regime == "current"
):
    st.success(
        "🏠 **New-build carve-out auto-applied.** You selected the Budget 2026-27 "
        "regime, but per the announcement, **new builds retain full negative gearing** "
        "and can elect either CGT method. Running 'current' rules. Tick the override "
        "in Advanced if you want to model the counterfactual where the carve-out is "
        "removed."
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
    property_regime=effective_property_regime,
    portfolio_profile=portfolio_profile,
    mode=mode,
    margin_loan_rate=margin_loan_rate, isolate_asset_quality=isolate_asset_quality,
    correlation=correlation,
    mtr=mtr, cpi=cpi, drp=True,
    serviceability_ceiling=max_top_up,
    seed=42,
    return_distribution=return_distribution, t_df=t_df,
    loan_rate_distribution=return_distribution,
    loan_rate_t_df=t_df,
    property_share_mix=property_share_mix,
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
    # worst_year_cash: recompute from the already-correctly-deflated per-year array
    # (the previous `worst_year_cash / deflator` used horizon's deflator regardless of
    # which year was actually worst — error up to ~80% of full deflator for early-horizon
    # worst years).
    result["worst_year_cash"] = float(
        np.percentile(result["outside_cash_per_trial_year"].max(axis=1), 90)
    )
    result["mixed_terminal_wealth"] = result["mixed_terminal_wealth"] / deflator
    result["median_mixed_wealth"] = result["median_mixed_wealth"] / deflator
    result["mixed_outside_cash_per_trial_year"] = (
        result["mixed_outside_cash_per_trial_year"] / yearly_deflator
    )

# --------------- Persona sweep + recommendation section ---------------
sweep_kwargs = dict(
    horizon_years=horizon, purchase_price=purchase_price, deposit=deposit,
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
    property_regime=effective_property_regime,
    portfolio_profile=portfolio_profile, mode=mode,
    margin_loan_rate=margin_loan_rate, isolate_asset_quality=isolate_asset_quality,
    correlation=correlation, mtr=mtr, cpi=cpi, drp=True,
    serviceability_ceiling=max_top_up, seed=42,
    return_distribution=return_distribution, t_df=t_df,
    loan_rate_distribution=return_distribution, loan_rate_t_df=t_df,
)

st.subheader("Recommended allocation for your scenario")
st.caption(
    "Pick your safety appetite below — the optimizer figures out the allocation. "
    "Want to override? Adjust the 'Property share of allocation' slider in the sidebar."
)
sweep_rows = compute_persona_sweep(**sweep_kwargs)
render_persona_cards(sweep_rows)

balanced_row = find_optimal_mix(sweep_rows, 0.95)
recommended_mix_for_table = balanced_row["mix_pct"] if balanced_row else None

st.markdown("---")

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

if property_share_mix < 1.0:
    prop_pct = int(property_share_mix * 100)
    shr_pct = 100 - prop_pct
    st.subheader(
        f"Mix ({prop_pct}% property / {shr_pct}% shares) beats pure shares "
        f"in **{result['p_mix_beats_pure_shares']:.0%}** of futures."
    )
    st.caption(
        f"Median mixed wealth: ${result['median_mixed_wealth']:,.0f} · "
        f"P(mix stays solvent): {result['p_mix_solvent']:.0%}"
    )

# Supporting metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Median property wealth", f"${result['median_property_wealth']:,.0f}")
m2.metric("Median shares wealth", f"${result['median_shares_wealth']:,.0f}")
m3.metric("Worst-year cash needed", f"${result['worst_year_cash']:,.0f}")
m4.metric("P(strategy stays solvent)", f"{result['p_solvent']:.0%}")

with st.expander("▾ Compare all allocations (table)"):
    render_comparison_table(sweep_rows, recommended_mix_for_table)

with st.expander("▾ Show distributions and cashflow detail"):
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
    if property_share_mix < 1.0:
        fig.add_trace(go.Histogram(
            x=result["mixed_terminal_wealth"],
            name=f"Mix ({int(property_share_mix*100)}/{int((1-property_share_mix)*100)})",
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
- **Negative gearing:** {effective_property_regime} rules (raw selector: {property_regime}; new-build carve-out: {'applied' if property_age == 'new_build' and not override_new_build_carveout else 'n/a'})
- **Property:** {property_age.replace('_', ' ').title()}, {asset_type.title()}
- **Portfolio profile:** {portfolio_profile.replace('_', ' ').title()} (μ {PORTFOLIO_PROFILES[portfolio_profile]['return_mu']:.1%}, σ {PORTFOLIO_PROFILES[portfolio_profile]['return_sigma']:.1%}, {PORTFOLIO_PROFILES[portfolio_profile]['franked']:.0%} franked)
- **Correlation (property ↔ shares):** {correlation:.2f}
- **Monte Carlo:** 5,000 trials, fixed seed (reproducible)
- **CPI:** {cpi:.1%} applied to rent and holding costs annually
- **Buy-and-hold share portfolio** — no mid-period rebalancing CGT events
- **Disclaimer:** Normal distributions; does not predict severe market crashes (fat-tail events)
- **Counterfactual mode (if Mode B isolated):** assumes margin loan at mortgage rate — not real-world available
""")
