"""Mockup: efficient frontier visualisation of the allocation-mix decision.

This is a standalone visualisation — does NOT touch app.py. Purpose: see whether
the frontier framing actually lands before committing to an app redesign.

Run from the project root with the venv active:
    PYTHONPATH=. python notebooks/frontier_mockup.py

Outputs `notebooks/frontier_mockup.html` (interactive) which auto-opens in browser.
"""
import numpy as np
import plotly.graph_objects as go
import subprocess
import os
from notebooks.scenario_sweep import run


# ---------- Compute the frontier under both regimes ----------

mixes = np.linspace(0, 1, 11)  # 0%, 10%, 20%, ..., 100% property

frontier_data = {}
for regime in ("current", "restricted_2027"):
    medians_M = []
    solvencies_pct = []
    p_beats_shares = []
    for mix in mixes:
        r = run(property_regime=regime, property_share_mix=float(mix))
        medians_M.append(r["median_mixed_wealth"] / 1e6)
        solvencies_pct.append(r["p_mix_solvent"] * 100)
        p_beats_shares.append(r["p_mix_beats_pure_shares"] * 100)
    frontier_data[regime] = {
        "median_M": medians_M,
        "solvent_pct": solvencies_pct,
        "beats_pct": p_beats_shares,
    }


# ---------- Build the figure ----------

fig = go.Figure()

palette = {
    "current": "#2D3142",           # graphite — calm, baseline
    "restricted_2027": "#BC4749",   # warm red — the riskier regime
}
labels = {
    "current": "Current rules",
    "restricted_2027": "Budget 2026-27 (restricted)",
}

for regime in ("current", "restricted_2027"):
    d = frontier_data[regime]
    fig.add_trace(go.Scatter(
        x=d["median_M"],
        y=d["solvent_pct"],
        mode="lines+markers+text",
        name=labels[regime],
        line=dict(color=palette[regime], width=3),
        marker=dict(size=11, color=palette[regime],
                    line=dict(color="white", width=1.5)),
        text=[f"{int(m*100)}%" for m in mixes],
        textposition="top center",
        textfont=dict(size=10, color="#666"),
        hovertemplate=(
            "<b>" + labels[regime] + "</b><br>"
            "Property mix: %{text}<br>"
            "Median wealth: $%{x:.2f}M<br>"
            "P(solvent): %{y:.1f}%<br>"
            "Beats pure shares: %{customdata:.1f}%"
            "<extra></extra>"
        ),
        customdata=d["beats_pct"],
    ))


# ---------- Annotations: the "knee" + the current default ----------

# Knee for restricted_2027 is roughly at mix=50% (last point with >99% solvent)
restricted = frontier_data["restricted_2027"]
knee_idx = 5  # mix=50%
fig.add_annotation(
    x=restricted["median_M"][knee_idx],
    y=restricted["solvent_pct"][knee_idx],
    text=(
        "<b>The knee.</b><br>"
        "Left = safe & near-peak wealth.<br>"
        "Right = small extra wealth, big solvency loss."
    ),
    showarrow=True,
    arrowhead=2,
    arrowcolor="#666",
    arrowsize=1.2,
    arrowwidth=1.5,
    ax=120, ay=80,
    bgcolor="rgba(255,255,255,0.95)",
    bordercolor="#999",
    borderwidth=1,
    borderpad=8,
    font=dict(size=11, color="#222"),
    align="left",
)

# Shade the "danger zone" (mix > ~60% under restricted regime)
fig.add_vrect(
    x0=restricted["median_M"][6],  # mix=60%
    x1=max(restricted["median_M"]) + 0.05,
    fillcolor="#BC4749",
    opacity=0.06,
    layer="below",
    line_width=0,
)
fig.add_annotation(
    x=restricted["median_M"][8],  # ~80% mix
    y=18,
    text="Danger zone<br>(under restricted_2027)",
    showarrow=False,
    font=dict(size=10, color="#BC4749"),
    align="center",
)


# ---------- Layout: clean, sparse, modern ----------

fig.update_layout(
    title=dict(
        text="<b>Allocation frontier</b><br>"
             "<span style='font-size:13px;color:#666'>"
             "Each point is a property/shares mix. Up-and-to-the-right is better. "
             "Numbers above each point = % property allocation."
             "</span>",
        font=dict(size=22, color="#222"),
        x=0.02, xanchor="left",
        y=0.97, yanchor="top",
    ),
    xaxis=dict(
        title=dict(text="Median terminal wealth", font=dict(size=13)),
        tickprefix="$",
        ticksuffix="M",
        tickfont=dict(size=12, color="#444"),
        gridcolor="#EEE",
        zeroline=False,
        showline=True, linecolor="#CCC",
    ),
    yaxis=dict(
        title=dict(text="P(strategy stays solvent)", font=dict(size=13)),
        ticksuffix="%",
        range=[0, 108],
        tickfont=dict(size=12, color="#444"),
        gridcolor="#EEE",
        zeroline=False,
        showline=True, linecolor="#CCC",
    ),
    plot_bgcolor="white",
    paper_bgcolor="white",
    height=600,
    width=950,
    margin=dict(l=70, r=40, t=110, b=70),
    legend=dict(
        x=0.02, y=0.18,
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
)

# Reference line at P(solvent) = 95% — common "near-safe" threshold
fig.add_hline(
    y=95, line_dash="dash", line_color="#AAA", line_width=1,
    annotation_text="95% solvent", annotation_position="bottom left",
    annotation_font=dict(size=10, color="#888"),
)


# ---------- Write + open ----------

out_path = os.path.abspath("notebooks/frontier_mockup.html")
fig.write_html(out_path, include_plotlyjs="cdn")

print(f"Mockup written to: {out_path}")
print(f"Opening in browser…")
subprocess.run(["open", out_path], check=False)
