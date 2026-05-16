"""Mockup: year-by-year wealth fan chart.

Visualises how wealth evolves over the holding period for each strategy
(Property / Shares / Mix at 50%). Pre-tax mark-to-market wealth — what
the strategy would be worth if liquidated at end of each year.

Run from the project root with the venv active:
    PYTHONPATH=. python notebooks/wealth_fan_mockup.py

Outputs `notebooks/wealth_fan_mockup.html` (interactive) which auto-opens.

Decision-relevance:
- Median lines show the *typical* path — half the futures are above, half below
- Shaded bands show p10–p90 — the *range of plausible futures*
- Hover any year to see the exact value for that strategy
- Diverging bands over time = uncertainty compounds
- A band that goes negative or near-zero = forced-sale territory
"""
import numpy as np
import plotly.graph_objects as go
import subprocess
import os
from notebooks.scenario_sweep import BASE, run


# ---------- Run the model with mix=0.5 to get all three wealth paths ----------

print("Running Monte Carlo at mix=50% under restricted_2027 regime...")
result = run(
    property_regime="restricted_2027",
    property_share_mix=0.5,
)

horizon = BASE["horizon_years"]
years = np.arange(1, horizon + 1)


# ---------- Compute median + percentile bands per strategy ----------

def quantiles(path: np.ndarray):
    """Return (median, p10, p90, p25, p75) each shape (horizon,)."""
    return (
        np.median(path, axis=0),
        np.percentile(path, 10, axis=0),
        np.percentile(path, 90, axis=0),
        np.percentile(path, 25, axis=0),
        np.percentile(path, 75, axis=0),
    )


strategies = [
    ("Property only", "property_wealth_path", "#2D3142"),
    ("Shares only", "shares_wealth_path", "#558B6E"),
    ("Mix 50/50", "mixed_wealth_path", "#BC4749"),
]


# ---------- Build the figure ----------

fig = go.Figure()

for label, key, color in strategies:
    path = result[key]
    median, p10, p90, p25, p75 = quantiles(path)
    median_M = median / 1e6
    p10_M = p10 / 1e6
    p90_M = p90 / 1e6
    p25_M = p25 / 1e6
    p75_M = p75 / 1e6

    rgb = {
        "#2D3142": "45, 49, 66",
        "#558B6E": "85, 139, 110",
        "#BC4749": "188, 71, 73",
    }[color]

    # p10-p90 band — wider, lighter
    fig.add_trace(go.Scatter(
        x=np.concatenate([years, years[::-1]]),
        y=np.concatenate([p90_M, p10_M[::-1]]),
        fill="toself",
        fillcolor=f"rgba({rgb}, 0.08)",
        line=dict(color=f"rgba({rgb}, 0)", width=0),
        showlegend=False,
        name=f"{label} — 80% range",
        hoverinfo="skip",
    ))

    # p25-p75 band — narrower, darker
    fig.add_trace(go.Scatter(
        x=np.concatenate([years, years[::-1]]),
        y=np.concatenate([p75_M, p25_M[::-1]]),
        fill="toself",
        fillcolor=f"rgba({rgb}, 0.15)",
        line=dict(color=f"rgba({rgb}, 0)", width=0),
        showlegend=False,
        name=f"{label} — 50% range",
        hoverinfo="skip",
    ))

    # Median line — most prominent
    fig.add_trace(go.Scatter(
        x=years,
        y=median_M,
        mode="lines",
        name=label,
        line=dict(color=color, width=3),
        hovertemplate=(
            f"<b>{label}</b><br>"
            "Year %{x}<br>"
            "Typical wealth: $%{y:.2f}M<br>"
            "<extra></extra>"
        ),
    ))


# ---------- Annotations ----------

# IO-period end annotation (year 5 is the loan IO transition)
fig.add_vline(
    x=5.5, line_dash="dot", line_color="#999", line_width=1,
    annotation_text="IO period ends → P&I starts",
    annotation_position="top",
    annotation_font=dict(size=10, color="#666"),
)

# Annotate where each strategy ends up at year 25
for label, key, color in strategies:
    final_median_M = np.median(result[key], axis=0)[-1] / 1e6
    fig.add_annotation(
        x=horizon, y=final_median_M,
        text=f"<b>${final_median_M:.2f}M</b>",
        showarrow=False,
        xshift=45,
        yshift=0,
        font=dict(size=12, color=color),
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor=color,
        borderwidth=1,
        borderpad=4,
    )


# ---------- Layout ----------

fig.update_layout(
    title=dict(
        text="<b>How does wealth grow over time?</b><br>"
             "<span style='font-size:13px;color:#666'>"
             "Bold line = typical (median) outcome each year. "
             "Shaded bands = range of plausible futures (50% and 80% of trials). "
             "Wider band = more uncertainty.</span>",
        font=dict(size=22, color="#222"),
        x=0.02, xanchor="left",
        y=0.97, yanchor="top",
    ),
    xaxis=dict(
        title=dict(text="Year", font=dict(size=13)),
        tickfont=dict(size=12, color="#444"),
        gridcolor="#EEE",
        zeroline=False,
        showline=True, linecolor="#CCC",
        dtick=5,
    ),
    yaxis=dict(
        title=dict(text="Wealth (mark-to-market, pre-tax)", font=dict(size=13)),
        tickprefix="$",
        ticksuffix="M",
        tickfont=dict(size=12, color="#444"),
        gridcolor="#EEE",
        zeroline=True, zerolinecolor="#CCC",
        showline=True, linecolor="#CCC",
    ),
    plot_bgcolor="white",
    paper_bgcolor="white",
    height=620,
    width=1050,
    margin=dict(l=70, r=140, t=110, b=70),  # extra right margin for terminal annotations
    legend=dict(
        x=0.02, y=0.97,
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor="#DDD",
        borderwidth=1,
        font=dict(size=12),
    ),
    hoverlabel=dict(
        bgcolor="white",
        font_size=12,
        bordercolor="#999",
    ),
    hovermode="x unified",  # show all 3 strategies' values at the hovered year
)


# ---------- Write + open ----------

out_path = os.path.abspath("notebooks/wealth_fan_mockup.html")
fig.write_html(out_path, include_plotlyjs="cdn")

print(f"\nMockup written to: {out_path}")
print(f"Opening in browser...\n")
subprocess.run(["open", out_path], check=False)


# ---------- Print summary table for reference ----------

print("Reference — median wealth at key years (pre-tax mark-to-market):")
print(f"{'Year':>5}  {'Property':>12}  {'Shares':>12}  {'Mix 50/50':>12}")
print("-" * 50)
key_years = [1, 5, 10, 15, 20, horizon]
for y in key_years:
    p = np.median(result["property_wealth_path"][:, y-1])
    s = np.median(result["shares_wealth_path"][:, y-1])
    m = np.median(result["mixed_wealth_path"][:, y-1])
    print(f"{y:>5}  ${p:>10,.0f}  ${s:>10,.0f}  ${m:>10,.0f}")
