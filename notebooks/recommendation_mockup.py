"""Mockup: 'pick an allocation' UI — persona cards vs comparison table.

Replaces chart-based decision UI with a recommendation-first layout.
Two framings shown side-by-side in one HTML page so the user can pick
which one lands.

Run from the project root with the venv active:
    PYTHONPATH=. python notebooks/recommendation_mockup.py

Outputs `notebooks/recommendation_mockup.html` (static HTML) which auto-opens.
"""
import os
import subprocess
import numpy as np
from notebooks.scenario_sweep import run, BASE


# ---------- Compute the data ----------

print("Running mix sweep under restricted_2027 regime, BASE scenario...")
# Sweep at 5% increments so personas (25/50/75) AND table (every 10%) both have data
mixes_pct = list(range(0, 101, 5))
rows = []
for mix_pct in mixes_pct:
    r = run(property_regime="restricted_2027", property_share_mix=mix_pct / 100)
    rows.append({
        "mix_pct": mix_pct,
        "median_wealth": r["median_mixed_wealth"],
        "p_solvent": r["p_mix_solvent"],
        "worst_year_cash": float(np.percentile(r["mixed_outside_cash_per_trial_year"].max(axis=1), 90)),
        "p_beats_shares": r["p_mix_beats_pure_shares"],
    })

# Recommendation: highest wealth subject to P(solvent) >= 0.95
safe_rows = [row for row in rows if row["p_solvent"] >= 0.95]
recommended = max(safe_rows, key=lambda r: r["median_wealth"]) if safe_rows else rows[0]
rec_mix = recommended["mix_pct"]

# Three personas — clean preset percentages
PERSONAS = [
    ("Safe Player", 25, "You sleep well every night. The worst-year cash demand never breaches your ceiling. You won't get rich quick, but you also won't be forced to sell at the bottom of a downturn."),
    ("Balanced", 50, "The Goldilocks zone for most people. Captures most of property's upside while keeping cashflow stress within tolerance in 99%+ of futures."),
    ("Wealth Maximizer", 75, "Betting on the good futures. Highest typical wealth, but about 1 in 5 futures forces you to sell at a bad moment because cashflow exceeds your ceiling."),
]


# ---------- Render HTML ----------

def fmt_money(x):
    if x >= 1_000_000:
        return f"${x/1_000_000:.2f}M"
    elif x >= 1_000:
        return f"${x/1_000:.0f}k"
    else:
        return f"${x:.0f}"


def fmt_pct(x):
    return f"{x*100:.1f}%"


def get_row(mix_pct):
    return next(r for r in rows if r["mix_pct"] == mix_pct)


# Build persona cards HTML
cards_html = ""
for persona_name, mix_pct, blurb in PERSONAS:
    row = get_row(mix_pct)
    is_recommended = (mix_pct == rec_mix) or (
        # If rec_mix is between two persona mixes, mark Balanced as recommended
        rec_mix not in [p[1] for p in PERSONAS] and persona_name == "Balanced"
    )
    badge_html = '<div class="recommended-badge">★ Recommended for your scenario</div>' if is_recommended else ''
    card_class = "card recommended" if is_recommended else "card"
    cards_html += f"""
        <div class="{card_class}">
            {badge_html}
            <div class="persona-name">{persona_name}</div>
            <div class="allocation">{mix_pct}% property</div>
            <div class="allocation-sub">{100-mix_pct}% shares</div>
            <div class="divider"></div>
            <div class="metric">
                <div class="metric-label">Typical wealth in 25 years</div>
                <div class="metric-value">{fmt_money(row['median_wealth'])}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Chance you never run out of cash</div>
                <div class="metric-value">{fmt_pct(row['p_solvent'])}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Worst year cash demand</div>
                <div class="metric-value">{fmt_money(row['worst_year_cash'])}</div>
            </div>
            <div class="divider"></div>
            <p class="blurb">"{blurb}"</p>
        </div>"""


# Build comparison table HTML — render only the every-10% rows for scannability
table_rows = [r for r in rows if r["mix_pct"] % 10 == 0]
table_rows_html = ""
for row in table_rows:
    is_rec = row["mix_pct"] == rec_mix
    row_class = "table-row recommended-row" if is_rec else "table-row"
    rec_marker = '<span class="star">★</span>' if is_rec else ""
    table_rows_html += f"""
        <tr class="{row_class}">
            <td class="mix-cell">{row['mix_pct']}% {rec_marker}</td>
            <td>{fmt_money(row['median_wealth'])}</td>
            <td>{fmt_pct(row['p_solvent'])}</td>
            <td>{fmt_money(row['worst_year_cash'])}</td>
            <td>{fmt_pct(row['p_beats_shares'])}</td>
        </tr>"""


html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Allocation recommendation — UI mockups</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    color: #1a1a1a;
    background: #f8f9fa;
    margin: 0;
    padding: 40px 60px;
    line-height: 1.5;
  }}
  h1 {{
    font-size: 26px;
    font-weight: 700;
    margin: 0 0 8px 0;
    color: #1a1a1a;
  }}
  .subtitle {{
    color: #666;
    font-size: 14px;
    margin: 0 0 36px 0;
  }}
  .scenario-context {{
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    padding: 12px 18px;
    margin-bottom: 40px;
    font-size: 13px;
    color: #4b5563;
  }}
  .scenario-context strong {{ color: #1a1a1a; }}

  h2 {{
    font-size: 18px;
    font-weight: 600;
    margin: 50px 0 6px 0;
    color: #1a1a1a;
    border-bottom: 2px solid #e5e7eb;
    padding-bottom: 10px;
  }}
  h2:first-of-type {{ margin-top: 0; }}
  .section-subtitle {{
    color: #6b7280;
    font-size: 13px;
    margin: 0 0 28px 0;
  }}

  /* ----- Persona cards ----- */
  .cards-container {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
  }}
  .card {{
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 28px;
    position: relative;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    transition: box-shadow 0.2s;
  }}
  .card:hover {{
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  }}
  .card.recommended {{
    border: 2px solid #16a34a;
    background: #fff;
  }}
  .recommended-badge {{
    background: #16a34a;
    color: white;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 12px;
    display: inline-block;
    margin-bottom: 14px;
    letter-spacing: 0.3px;
  }}
  .persona-name {{
    font-size: 13px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
  }}
  .allocation {{
    font-size: 32px;
    font-weight: 700;
    color: #1a1a1a;
    line-height: 1.1;
  }}
  .allocation-sub {{
    font-size: 14px;
    color: #6b7280;
    margin-top: 2px;
  }}
  .divider {{
    height: 1px;
    background: #e5e7eb;
    margin: 20px 0;
  }}
  .metric {{
    margin-bottom: 12px;
  }}
  .metric-label {{
    font-size: 12px;
    color: #6b7280;
    margin-bottom: 2px;
  }}
  .metric-value {{
    font-size: 18px;
    font-weight: 600;
    color: #1a1a1a;
  }}
  .blurb {{
    font-size: 13px;
    color: #4b5563;
    font-style: italic;
    margin: 12px 0 0 0;
  }}

  /* ----- Comparison table ----- */
  .table-wrapper {{
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }}
  thead {{
    background: #f9fafb;
    border-bottom: 2px solid #e5e7eb;
  }}
  th {{
    text-align: left;
    padding: 14px 20px;
    font-weight: 600;
    color: #374151;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }}
  td {{
    padding: 14px 20px;
    border-bottom: 1px solid #f3f4f6;
    color: #1a1a1a;
  }}
  tbody tr:last-child td {{
    border-bottom: none;
  }}
  tbody tr:hover {{
    background: #f9fafb;
  }}
  .recommended-row {{
    background: #f0fdf4 !important;
    font-weight: 600;
  }}
  .recommended-row td {{
    color: #15803d;
  }}
  .star {{
    color: #16a34a;
    margin-left: 4px;
  }}
  .mix-cell {{
    font-weight: 500;
  }}

  /* ----- Footnote ----- */
  .footnote {{
    margin-top: 40px;
    padding: 20px;
    background: #f3f4f6;
    border-left: 4px solid #6b7280;
    border-radius: 4px;
    font-size: 13px;
    color: #4b5563;
  }}
  .footnote strong {{ color: #1a1a1a; }}
</style>
</head>
<body>
  <h1>Allocation recommendation — UI mockups</h1>
  <p class="subtitle">Two ways to present the same answer. Pick which one feels right.</p>

  <div class="scenario-context">
    <strong>Scenario:</strong> $700k property, 20% deposit, 25-year horizon, 37% MTR, $20k cashflow ceiling, Budget 2026-27 regime.
    <br>
    <strong>Recommendation logic:</strong> highest typical wealth subject to ≥95% chance of avoiding forced sale.
  </div>

  <h2>Option A — Persona cards (Wealthfront-style)</h2>
  <p class="section-subtitle">User reads three short stories, picks the one that matches their personality. The recommended card is highlighted.</p>

  <div class="cards-container">
    {cards_html}
  </div>

  <h2>Option C — Comparison table with recommended row</h2>
  <p class="section-subtitle">Dense, scannable. All 11 mix points shown; the recommended one highlighted in green.</p>

  <div class="table-wrapper">
    <table>
      <thead>
        <tr>
          <th>Property mix</th>
          <th>Typical wealth (25y)</th>
          <th>Chance never runs out of cash</th>
          <th>Worst year cash demand</th>
          <th>Beats pure shares</th>
        </tr>
      </thead>
      <tbody>
        {table_rows_html}
      </tbody>
    </table>
  </div>

  <div class="footnote">
    <strong>Which one lands?</strong> Option A is more consumer-friendly — three personalities, pick one.
    Option C is denser — closer to spreadsheet thinking, all numbers visible.
    Both compute the recommendation the same way. Both could live in the app simultaneously
    (table as the detailed reference, cards as the lead).
  </div>
</body>
</html>
"""

out_path = os.path.abspath("notebooks/recommendation_mockup.html")
with open(out_path, "w") as f:
    f.write(html)

print(f"\nMockup written to: {out_path}")
print(f"Recommended mix (max wealth subject to P(solvent) >= 95%): {rec_mix}%")
print(f"Opening in browser...\n")
subprocess.run(["open", out_path], check=False)


# Reference table
print("Reference — full mix sweep, restricted_2027 regime, BASE scenario:")
print(f"{'Mix %':>6}  {'Typical $':>12}  {'P(solvent)':>11}  {'Worst yr $':>11}  {'Beats shr':>10}")
print("-" * 60)
for r in rows:
    marker = " *RECOMMENDED" if r["mix_pct"] == rec_mix else ""
    print(f"{r['mix_pct']:>5}%  {fmt_money(r['median_wealth']):>12}  "
          f"{fmt_pct(r['p_solvent']):>11}  {fmt_money(r['worst_year_cash']):>11}  "
          f"{fmt_pct(r['p_beats_shares']):>10}{marker}")
