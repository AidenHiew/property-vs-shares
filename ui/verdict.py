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
