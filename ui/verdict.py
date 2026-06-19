"""Compare v2 verdict — pure compute + HTML render (no Streamlit state).

Turns two run_monte_carlo result dicts (realistic + fair-fight) into one
VerdictNumbers and renders it. Funding model: investor funds every shortfall,
holds to term — no forced-sale, no solvent masking (spec §1, §4, §7).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ui.common import _fmt_money


# ===========================================================================
# Compute layer
# ===========================================================================
def _badge_state(win_rate_property: int) -> tuple[str, str, str]:
    """Gate the winner treatment on the win-rate, not the median (spec §5.3).

    45–55 inclusive → neutral tie. Otherwise the leading side gets a badge at
    ≥60, border only at 55–60.
    """
    if 45 <= win_rate_property <= 55:
        return "tie", "neutral", ""
    leader = "property" if win_rate_property > 55 else "shares"
    leading_rate = win_rate_property if leader == "property" else 100 - win_rate_property
    if leading_rate >= 60:
        return leader, "badge", "Ahead in most futures"
    return leader, "border", ""


def _crossover_year(cashflow_path: np.ndarray) -> int | None:
    """First 1-based year where the median-across-trials property cashflow is ≥ 0.

    Returns None if the median never turns positive within the horizon (spec
    §5.6 'doesn't cover its costs within N years' branch).
    """
    median_by_year = np.median(cashflow_path, axis=0)
    positive = np.where(median_by_year >= 0)[0]
    if positive.size == 0:
        return None
    return int(positive[0]) + 1  # 1-based year


def _loudness(worst_z: float, ceiling: float) -> str:
    """Affordability-panel visual loudness — never gates the verdict (spec §5.6)."""
    if ceiling <= 0 or worst_z <= ceiling:
        return "quiet"
    if worst_z >= 2 * ceiling:
        return "loud"
    return "amber"


def _cross_tab_j(p_term: np.ndarray, s_term: np.ndarray,
                 outside_cash: np.ndarray, ceiling: float) -> int:
    """Of property's winning futures, the % that needed > ceiling in some year."""
    win_mask = p_term > s_term
    over_plan = (outside_cash > ceiling).any(axis=1)
    return int(round(float((win_mask & over_plan).mean()) * 100))


@dataclass
class VerdictNumbers:
    # verdict (all trials, no masking)
    p_median: float
    s_median: float
    p_p10: float
    p_p90: float
    s_p10: float
    s_p90: float
    win_rate: int            # round(p_property_wins * 100)
    leader: str              # "property" | "shares" | "tie"
    badge_state: str         # "neutral" | "border" | "badge"
    badge_label: str
    close_note: bool         # median clearly diverges but win-rate neutral
    # affordability
    upfront_x: float
    typical_t: float
    crossover_k: int | None
    worst_z: float
    worst_max: float
    cross_tab_j: int
    loudness: str            # "quiet" | "amber" | "loud"
    # fair-fight
    fairfight_y: float
    fairfight_shares_win: bool


def compute_verdict(realistic: dict, fair_fight: dict, *,
                    serviceability_ceiling: float,
                    deposit: float, upfront_costs: float) -> VerdictNumbers:
    p = np.asarray(realistic["property_terminal_wealth"], float)
    s = np.asarray(realistic["shares_terminal_wealth"], float)
    p_p10, p_p90 = (float(x) for x in np.percentile(p, [10, 90]))
    s_p10, s_p90 = (float(x) for x in np.percentile(s, [10, 90]))
    p_median = float(np.median(p))
    s_median = float(np.median(s))

    win_rate = int(round(realistic["p_property_wins"] * 100))
    leader, badge_state, badge_label = _badge_state(win_rate)

    # close_note: badge neutral but medians clearly apart (>5% gap) — spec §5.3 D
    gap = abs(p_median - s_median) / max(p_median, s_median, 1.0)
    close_note = (badge_state == "neutral") and (gap > 0.05)

    outside = np.asarray(realistic["outside_cash_per_trial_year"], float)
    worst_z = float(realistic["worst_year_cash"])
    worst_max = float(outside.max())

    fair_p = float(fair_fight["median_property_wealth"])
    fair_s = float(fair_fight["median_shares_wealth"])

    return VerdictNumbers(
        p_median=p_median, s_median=s_median,
        p_p10=p_p10, p_p90=p_p90, s_p10=s_p10, s_p90=s_p90,
        win_rate=win_rate, leader=leader,
        badge_state=badge_state, badge_label=badge_label, close_note=close_note,
        upfront_x=float(deposit + upfront_costs),
        typical_t=float(realistic["median_outside_cash_total"]),
        crossover_k=_crossover_year(np.asarray(realistic["property_cashflow_path"], float)),
        worst_z=worst_z, worst_max=worst_max,
        cross_tab_j=_cross_tab_j(p, s, outside, serviceability_ceiling),
        loudness=_loudness(worst_z, serviceability_ceiling),
        fairfight_y=fair_s,
        fairfight_shares_win=fair_s > fair_p,
    )


# ===========================================================================
# Render layer — pure HTML strings (app_compare passes through _render_html)
# ===========================================================================
def render_trust_line(v: VerdictNumbers, horizon: int) -> str:
    return (
        f'<p class="pvs-section-sub">You\'d put in about '
        f'<b>{_fmt_money(v.upfront_x)} upfront</b>, plus about '
        f'<b>{_fmt_money(v.typical_t)} total</b> over the {horizon} years as the '
        f'property needs it — and the shares side received that same cash. '
        f'Both plans feed in the identical money; the difference is what each '
        f'gives back.</p>'
    )


def _card(title: str, icon: str, median: float, p10: float, p90: float,
          state: str, label: str) -> str:
    badge = f'<div class="badge">{label}</div>' if (state == "badge" and label) else ""
    klass = "card rec" if state in ("badge", "border") else "card"
    return (
        f'<div class="{klass}">{badge}'
        f'<div class="pname">{icon} {title}</div>'
        f'<div class="alloc">{_fmt_money(median)}</div>'
        f'<div class="alloc-sub">usually between {_fmt_money(p10)} and {_fmt_money(p90)} '
        f'<span title="downside">(P10 downside &darr;)</span></div>'
        f'</div>'
    )


def render_cards(v: VerdictNumbers) -> str:
    if v.badge_state == "neutral":
        p_state = s_state = "neutral"
        neutral = ('<p class="pvs-section-sub">Too close to call — property and '
                   'shares land within a whisker of each other.')
        if v.close_note:
            neutral += " Typically richer, but it's close across futures."
        neutral += "</p>"
    else:
        p_state = v.badge_state if v.leader == "property" else "card"
        s_state = v.badge_state if v.leader == "shares" else "card"
        neutral = ""
    p_label = v.badge_label if v.leader == "property" else ""
    s_label = v.badge_label if v.leader == "shares" else ""
    cards = (
        '<div class="cards" style="grid-template-columns:1fr 1fr;">'
        + _card("Property", "🏠", v.p_median, v.p_p10, v.p_p90, p_state, p_label)
        + _card("Shares", "📈", v.s_median, v.s_p10, v.s_p90, s_state, s_label)
        + '</div>'
    )
    link = ('<p class="pvs-section-sub">These assume you fund every shortfall and '
            'never sell — see <b>what you\'d cough up</b> below.</p>')
    return cards + neutral + link


def render_win_line(v: VerdictNumbers) -> str:
    if v.leader == "shares":
        n = 100 - v.win_rate
        who = "shares come out ahead"
    else:
        n = v.win_rate
        who = "property comes out ahead"
    return (
        f'<div class="dot-headline"><span class="dot-big">{n}/100</span>'
        f'<span class="dot-ctx">Assuming you fund it every year, {who} in about '
        f'{n} of every 100 futures.</span></div>'
        f'<p class="dot-explainer">We simulate thousands of possible market '
        f'outcomes; these are how often each side comes out ahead.</p>'
    )


def render_affordability(v: VerdictNumbers, horizon: int, ceiling: float) -> str:
    flag_klass = {"quiet": "ok", "amber": "warn", "loud": "warn"}[v.loudness]
    if v.crossover_k is not None:
        typical = (f'About <b>{_fmt_money(v.typical_t)}</b> total over {horizon} years, '
                   f'on top of the deposit — heaviest early, easing by about '
                   f'<b>year {v.crossover_k}</b> as rent catches up.')
    else:
        typical = (f'About <b>{_fmt_money(v.typical_t)}</b> total over {horizon} years, '
                   f'on top of the deposit — still costing you cash in year {horizon}; '
                   f"it doesn't fully cover its own costs within the horizon.")
    return (
        f'<div class="flag {flag_klass}">'
        f'<b>What you\'d cough up</b> — both plans feed in this same cash; this is '
        f'just whether you could find it for the property.<br>'
        f'· Upfront: <b>{_fmt_money(v.upfront_x)}</b> (deposit + stamp duty + buying costs)<br>'
        f'· Typical: {typical}<br>'
        f'· Rough year: up to <b>{_fmt_money(v.worst_z)}</b> in a single worst year '
        f'(worst ~1 in 10). Worst we modelled at all: {_fmt_money(v.worst_max)}.<br>'
        f'· In about <b>{v.cross_tab_j}</b> of property\'s winning futures, you\'d have '
        f'needed more than your {_fmt_money(ceiling)} plan in some year.'
        f'</div>'
    )


def render_fairfight_spoiler(v: VerdictNumbers, leverage_l: float) -> str:
    if v.fairfight_shares_win:
        flip = (f' At equal borrowing, shares actually win — landing about '
                f'{_fmt_money(v.fairfight_y)}.')
    else:
        flip = (f' At equal borrowing, shares land about {_fmt_money(v.fairfight_y)}; '
                f"property's lead here is mostly the cheap loan.")
    return (
        f'<p class="pvs-section-sub">Property is ahead mainly because the bank lends '
        f'you {_fmt_money(leverage_l)} you never put in yourself. That leverage works '
        f'both ways.{flip} (The modelled margin loan never margin-calls — a best-case '
        f'for shares, not a true apples-to-apples.)</p>'
    )
