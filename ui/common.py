import streamlit as st

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
  .pthr {{ font-size: 14px; color: {MUTED}; margin: 2px 0 14px; font-weight: 600; }}
  .alloc {{ font-size: 30px; font-weight: 800; color: {INK}; line-height: 1.05; }}
  .card.rec .alloc {{ color: {GREEN}; }}
  .alloc-sub {{ font-size: 13px; color: {MUTED}; margin-top: 2px; }}
  .hr {{ height: 1px; background: {LINE}; margin: 15px 0; }}
  .mrow {{ margin-bottom: 9px; }}
  .mlabel {{ font-size: 14px; color: {MUTED}; margin-bottom: 1px; }}
  .mval {{ font-size: 17px; font-weight: 700; color: {INK}; }}
  .blurb {{ font-size: 14px; color: #4b5563; font-style: italic; background: #f9fafb;
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
  .flag-emoji {{ font-size: 18px; line-height: 1; }}

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

  /* dot-grid headline */
  .dot-grid-block {{ margin: 8px 0 16px; }}
  .dot-grid {{
    display: grid;
    grid-template-columns: repeat(10, 14px);
    gap: 4px;
    margin-bottom: 10px;
  }}
  .dot {{
    width: 14px; height: 14px; border-radius: 50%;
    display: inline-block;
  }}
  .dot-headline {{
    display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
    margin-bottom: 6px;
  }}
  .dot-big {{ font-size: 26px; font-weight: 800; color: #16a34a; line-height: 1; }}
  .dot-ctx {{ font-size: 16px; color: #1a1a1a; font-weight: 600; }}
  .dot-explainer {{ font-size: 14px; color: #6b7280; margin: 0; max-width: 680px; }}

  /* downside callout */
  .callout-amber {{
    background: rgba(245,158,11,.09);
    border: 1px solid rgba(245,158,11,.5);
    border-left: 4px solid #d97706;
    border-radius: 10px;
    padding: 14px 18px;
    font-size: 15px;
    color: #78350f;
    margin: 12px 0 10px;
    line-height: 1.55;
  }}
  .callout-amber .caveat {{
    display: block;
    font-size: 13px;
    color: #92400e;
    margin-top: 8px;
    font-style: italic;
  }}

  /* frontier expander caveat */
  .frontier-caveat {{
    font-size: 13px;
    color: #6b7280;
    margin: 12px 0 4px;
    border-left: 3px solid #e5e7eb;
    padding-left: 10px;
    font-style: italic;
  }}

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
# Small formatting helpers
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


def _render_html(html: str) -> None:
    """Render raw HTML via st.markdown, stripping per-line indentation so the
    markdown parser doesn't treat indented lines as code blocks."""
    flat = "\n".join(line.lstrip() for line in html.strip().split("\n"))
    st.markdown(flat, unsafe_allow_html=True)
