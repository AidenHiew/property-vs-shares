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

# --------------- Main pane: comparison radio + display toggle ---------------
col_mode, col_display = st.columns([2, 1])
with col_mode:
    mode = st.radio("Comparison mode", ["realistic", "fair_fight"], horizontal=True,
                    format_func=lambda x: {"realistic": "Realistic", "fair_fight": "Fair fight"}[x])
with col_display:
    display_mode = st.radio("Display", ["nominal", "today"], horizontal=True,
                            format_func=lambda x: {"nominal": "Nominal", "today": "Today's $"}[x])

st.write("Tool initialised. Charts and metrics arrive in subsequent tasks.")
