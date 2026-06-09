"""Onboarding: hero, slim how-to banner, limitations callout, full guide.
Pure Streamlit render functions; no model logic."""
import streamlit as st
from ui.common import _render_html, GLOBAL_CSS

ONBOARDING_CSS = """
<style>
  .pvs-steps { display:flex; gap:18px; flex-wrap:wrap; margin:10px 0 4px; font-size:13px; color:#374151; }
  .pvs-steps b { color:#1a1a1a; }
  .limits { background:rgba(245,158,11,.08); border:1px solid rgba(245,158,11,.4); border-radius:10px;
            padding:12px 16px; font-size:12.5px; color:#92400e; margin:14px 0 2px; line-height:1.6; }
  .limits b { color:#78350f; }
  .gsec { font-size:14px; font-weight:700; color:#1a1a1a; margin:14px 0 4px; }
  .grow { font-size:13px; color:#374151; line-height:1.7; }
  .grow b { color:#1a1a1a; }
</style>
"""

def render_hero():
    _render_html(GLOBAL_CSS + ONBOARDING_CSS +
        '<div class="pvs-h1">🏡 Property vs Shares — should you buy an investment property, '
        'buy shares, or mix both?</div>'
        '<div class="pvs-sub">Thinking of buying an investment property, or putting the same money into '
        'shares? This tool runs <b>5,000 possible 25-year futures</b> for <b>your</b> numbers and shows which '
        'path tends to leave you wealthier — and whether you could ride out the bad years without running short '
        'on cash. A <b>what-if explorer, not a prediction or financial advice.</b></div>'
        '<div class="pvs-steps"><span><b>1</b> Enter your numbers (sidebar)</span>'
        '<span><b>2</b> Read your recommendation</span>'
        '<span><b>3</b> Dig into the breakdown</span></div>')

def render_limitations():
    _render_html(ONBOARDING_CSS +
        '<div class="limits"><b>Before you trust the numbers:</b> stamp duty is state-specific (pick your state); '
        'income tax, CGT and negative gearing are federal · single property · simplified costs · '
        '<b>land tax is a flat field, off by default</b> · Budget 2026-27 rules are <b>announcement-only, not law</b> · '
        'defaults may not match you — check against your lender quote, suburb data and the ATO. '
        '<b>Not financial advice.</b></div>')

def render_full_guide():
    with st.expander("📖  Full guide & assumptions", expanded=False):
        _render_html(ONBOARDING_CSS +
            '<div class="gsec">What am I looking at?</div>'
            '<div class="grow">Two ways to invest the same money: <b>buy a rental property</b> (with a mortgage) vs '
            '<b>put the identical cash into a diversified share portfolio</b>. Every dollar the property needs — '
            'deposit, costs, yearly top-ups — goes into shares instead, so it is a fair, like-for-like race across '
            'thousands of random futures.</div>'
            '<div class="gsec">What each input means</div>'
            '<div class="grow">• <b>State</b> — sets stamp duty.<br>• <b>Purchase price</b> / <b>Deposit %</b> — '
            'price and your upfront cash.<br>• <b>Taxable income</b> — sets your marginal tax rate.<br>'
            '• <b>Rental yield %</b>, <b>Mortgage rate %</b>, <b>Years</b>.<br>'
            '• <b>Annual land tax ($)</b> — off by default; deductible; enter your state figure for accuracy.<br>'
            '• <b>Max annual top-up</b> — your cash ceiling in a bad year.</div>'
            '<div class="gsec">Key terms</div>'
            '<div class="grow">• <b>Solvent</b> — never needed more than your cash ceiling.<br>'
            '• <b>Typical wealth</b> — the median across futures.<br>'
            '• <b>Safety appetite</b> — how often you stay within the ceiling (≥99/95/85%).</div>'
            '<div class="gsec">Assumptions & limits</div>'
            '<div class="grow">National stamp duty (FY2025-26); income tax FY2026 brackets · '
            '<b>Tax uses your current marginal rate held flat for the whole period — no bracket creep, Medicare '
            'levy, per-year income changes, or a rental loss dropping you a bracket. Your marginal rate drives '
            'negative gearing, CGT (both sides) and dividend/franking tax.</b> · land tax = your flat input (0 = '
            'excluded) · single property · 5,000 trials · Budget 2026-27 announcement-only. '
            '<b>Not financial advice.</b></div>')
