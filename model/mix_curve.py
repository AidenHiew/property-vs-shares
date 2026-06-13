# model/mix_curve.py
"""Pure mix-curve builder. No Streamlit imports.

Derives the full allocation efficiency curve from a single Monte Carlo base
run's unblended per-trial arrays. All mix points are computed post-hoc via
linear algebra — no re-simulation per mix.

See spec §3.2, §5.3 for metric definitions.
"""
from __future__ import annotations
from dataclasses import dataclass

import numpy as np

from model.solvency import flag_forced_sales


@dataclass
class MixPoint:
    """One point on the mix efficiency curve.

    mix_pct: fraction of portfolio in property (0.0 = pure shares, 1.0 = pure property).
    median_mixed_wealth: median terminal wealth at this mix across all trials ($).
    p_solvent: fraction of trials where mixed_outside_cash never exceeds ceiling.
    p_succeeds: fraction of trials solvent AND mixed beats pure shares.
    p_mix_beats_pure_shares: fraction of trials where mixed_terminal > s_terminal AND solvent.
    worst_year_cash: 90th-percentile of per-trial worst single year's outside cash (§5.3).
    total_top_ups: median of per-trial cumulative outside cash over the hold (§5.3).
    forced_sale_rate: fraction of trials with any year breaching ceiling (§5.3).
    """
    mix_pct: float
    median_mixed_wealth: float
    p_solvent: float
    p_succeeds: float
    p_mix_beats_pure_shares: float
    worst_year_cash: float
    total_top_ups: float
    forced_sale_rate: float


def build_mix_curve(
    p_terminal: np.ndarray,
    s_terminal: np.ndarray,
    p_outside_cash: np.ndarray,
    ceiling: float,
    mixes: np.ndarray | None = None,
) -> list[MixPoint]:
    """Build the allocation efficiency curve from one base run's unblended arrays.

    Parameters
    ----------
    p_terminal : (trials,) float — pure-property terminal after-tax wealth per trial.
    s_terminal : (trials,) float — pure-shares terminal after-tax wealth per trial.
    p_outside_cash : (trials, horizon) float — pure-property outside-cash demand per trial-year.
        Scale by mix to get mixed outside-cash demand (only property carries cash demand).
    ceiling : float — serviceability ceiling in $ (same units as p_outside_cash).
    mixes : 1-D float array of mix fractions to evaluate. Defaults to np.linspace(0, 1, 21).

    Returns
    -------
    list[MixPoint] of length len(mixes), ordered by ascending mix_pct.

    Metric definitions (spec §5.3):
      worst_year_cash  = percentile(mixed_outside_cash.max(axis=1), 90)
      total_top_ups    = median(mixed_outside_cash.sum(axis=1))
      forced_sale_rate = mean(flag_forced_sales(mixed_outside_cash, ceiling))
      p_solvent        = 1 - forced_sale_rate
      p_succeeds       = mean(mixed_terminal > s_terminal AND NOT forced_sale)
      p_mix_beats_pure_shares = p_succeeds   (alias; strictly: solvent AND beats shares)
      median_mixed_wealth = median(mix * p_terminal + (1-mix) * s_terminal)

    CRN guarantee: all mixes share the same underlying trial paths (one base run,
    fixed seed). The curve reflects the blend, not sampling noise.

    Deflation contract: this function operates entirely in nominal dollars.
    Apply deflation per-render outside this function; never pass deflated arrays in.
    """
    if mixes is None:
        mixes = np.linspace(0.0, 1.0, 21)

    points: list[MixPoint] = []

    for mix in mixes:
        mixed_terminal = mix * p_terminal + (1.0 - mix) * s_terminal
        mixed_outside_cash = mix * p_outside_cash  # shares carry no outside-cash demand

        forced_flags = flag_forced_sales(mixed_outside_cash, ceiling)
        forced_sale_rate = float(forced_flags.mean())
        p_solvent = 1.0 - forced_sale_rate

        # p_succeeds: solvent AND mixed beats pure shares
        beats_shares = mixed_terminal > s_terminal
        p_succeeds = float((beats_shares & ~forced_flags).mean())
        p_mix_beats_pure_shares = p_succeeds  # same definition per spec output mapping

        median_mixed_wealth = float(np.median(mixed_terminal))

        # Downside metrics (spec §5.3) — mix=0.0 gives zeros (no property cash demand)
        worst_year_cash = float(
            np.percentile(mixed_outside_cash.max(axis=1), 90)
        ) if mix > 0.0 else 0.0

        total_top_ups = float(
            np.median(mixed_outside_cash.sum(axis=1))
        ) if mix > 0.0 else 0.0

        points.append(MixPoint(
            mix_pct=float(mix),
            median_mixed_wealth=median_mixed_wealth,
            p_solvent=p_solvent,
            p_succeeds=p_succeeds,
            p_mix_beats_pure_shares=p_mix_beats_pure_shares,
            worst_year_cash=worst_year_cash,
            total_top_ups=total_top_ups,
            forced_sale_rate=forced_sale_rate,
        ))

    return points
