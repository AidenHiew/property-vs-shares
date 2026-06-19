# Property vs Shares — Compare v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a new standalone Streamlit screen (`app_compare.py`) that answers "buy this investment property, or put the same cash into shares?" with a same-money verdict plus an affordability ("what you'd cough up") panel — reusing the existing Monte Carlo engine unchanged.

**Architecture:** A pure compute module `ui/verdict.py` turns two engine result dicts (realistic + fair-fight) into one `VerdictNumbers` dataclass and renders it to HTML strings — all unit-testable with no Streamlit. `app_compare.py` is a thin Streamlit shell: collect inputs, clamp URL state, run the engine twice (cached), call `compute_verdict`, render. Zero engine changes.

**Tech Stack:** Python 3, Streamlit, NumPy, pytest, `streamlit.testing.v1.AppTest`.

## Global Constraints

- **Always run with `.venv/bin/python`** — bare python lacks streamlit/numpy. Tests: `.venv/bin/python -m pytest -q`.
- **Engine unchanged.** No edits to `model/`. `app.py`, `ui/persona.py`, existing tests untouched.
- **URL state clamped on BOTH read and write**, in the same change as the widget (project rule, see `CLAUDE.md` / crash commit `6bab10e`). Malformed/boundary query values must fall back to default, never crash.
- **Funding model:** the screen assumes the investor funds every shortfall and holds to term. No forced-sale concept, no solvent masking. Headline = `p_property_wins` over all trials. (Spec §1, §4, §7.)
- **Win line copy** must always carry "assuming you fund it" and link to the affordability panel (spec §5.4, §A).
- **`$T` single source:** `median_outside_cash_total` is the only "total top-up" figure — used identically in trust line and affordability panel (spec §B/§7).
- **Affordability panel never gates the verdict** — loudness scales with `$Z` vs `$C`, but verdict cards/badge are never suppressed (spec §5.6/§E).
- Spec: `docs/superpowers/specs/2026-06-19-property-vs-shares-compare-v2-design.md`.

---

## File Structure

- **Create `ui/verdict.py`** — pure compute (`VerdictNumbers` dataclass, `compute_verdict`, helpers `_badge_state`, `_crossover_year`, `_loudness`, `_cross_tab_j`) + HTML render functions (`render_*` returning strings). No Streamlit imports beyond reusing `ui/common.py` CSS/format helpers.
- **Create `app_compare.py`** — Streamlit entry point. Inputs (slim 10 + advanced expander), URL clamp read/write, two cached engine runs, calls `compute_verdict` + render functions.
- **Create `tests/test_verdict.py`** — unit tests for the pure compute layer (the bulk of the logic).
- **Create `tests/test_app_compare.py`** — `AppTest` smoke, URL/boundary, and framing-behaviour tests.

Engine return keys consumed (all already produced — verified `model/monte_carlo.py:268`+): `property_terminal_wealth`, `shares_terminal_wealth`, `p_property_wins`, `outside_cash_per_trial_year`, `median_outside_cash_total`, `worst_year_cash`, `property_cashflow_path`, `median_property_wealth`, `median_shares_wealth`.

---

## Task 1: `ui/verdict.py` — compute layer (`VerdictNumbers` + `compute_verdict`)

**Files:**
- Create: `ui/verdict.py`
- Test: `tests/test_verdict.py`

**Interfaces:**
- Consumes: two engine result dicts from `run_monte_carlo` (realistic, fair_fight); scalars `serviceability_ceiling`, `deposit`, `upfront_costs`.
- Produces:
  - `@dataclass VerdictNumbers` with fields: `p_median, s_median, p_p10, p_p90, s_p10, s_p90: float`; `win_rate: int`; `leader: str` (`"property"|"shares"|"tie"`); `badge_state: str` (`"neutral"|"border"|"badge"`); `badge_label: str`; `close_note: bool`; `upfront_x, typical_t, worst_z, worst_max, fairfight_y: float`; `crossover_k: int | None`; `cross_tab_j: int`; `loudness: str` (`"quiet"|"amber"|"loud"`); `fairfight_shares_win: bool`.
  - `compute_verdict(realistic: dict, fair_fight: dict, *, serviceability_ceiling: float, deposit: float, upfront_costs: float) -> VerdictNumbers`
  - `_badge_state(win_rate_property: int) -> tuple[str, str, str]` returning `(leader, badge_state, badge_label)`
  - `_crossover_year(cashflow_path: np.ndarray) -> int | None`
  - `_loudness(worst_z: float, ceiling: float) -> str`
  - `_cross_tab_j(p_term, s_term, outside_cash, ceiling) -> int`

- [ ] **Step 1: Write the failing test for `_badge_state`**

```python
# tests/test_verdict.py
import numpy as np
import pytest
from ui.verdict import (
    VerdictNumbers, compute_verdict, _badge_state, _crossover_year,
    _loudness, _cross_tab_j,
)


def test_badge_state_neutral_band():
    # 45..55 inclusive → tie / neutral, no badge
    for wr in (45, 50, 55):
        leader, state, label = _badge_state(wr)
        assert leader == "tie"
        assert state == "neutral"
        assert label == ""


def test_badge_state_property_badge_at_60():
    leader, state, label = _badge_state(68)
    assert leader == "property"
    assert state == "badge"
    assert label == "Ahead in most futures"


def test_badge_state_property_border_between_55_and_60():
    leader, state, label = _badge_state(57)
    assert leader == "property"
    assert state == "border"
    assert label == ""


def test_badge_state_shares_lead_uses_complement():
    # property wins 30/100 → shares lead 70 → shares badge
    leader, state, label = _badge_state(30)
    assert leader == "shares"
    assert state == "badge"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_verdict.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'ui.verdict'`.

- [ ] **Step 3: Implement `_badge_state` (+ module scaffold)**

```python
# ui/verdict.py
"""Compare v2 verdict — pure compute + HTML render (no Streamlit state).

Turns two run_monte_carlo result dicts (realistic + fair-fight) into one
VerdictNumbers and renders it. Funding model: investor funds every shortfall,
holds to term — no forced-sale, no solvent masking (spec §1, §4, §7).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


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
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_verdict.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Write failing tests for `_crossover_year`, `_loudness`, `_cross_tab_j`**

```python
def test_crossover_year_returns_first_self_funding_year():
    # median cashflow negative years 1-2, positive from year 3 (1-based)
    cashflow = np.array([
        [-100, -50, 10, 20],
        [-120, -40, 30, 25],
        [-110, -45, 20, 22],
    ], dtype=float)  # (trials, years); median per col: -110,-45,20,22
    assert _crossover_year(cashflow) == 3


def test_crossover_year_none_when_never_positive():
    cashflow = np.array([
        [-100, -90, -80, -70],
        [-110, -95, -85, -75],
    ], dtype=float)
    assert _crossover_year(cashflow) is None


def test_loudness_tiers():
    assert _loudness(15_000, 20_000) == "quiet"   # Z <= C
    assert _loudness(30_000, 20_000) == "amber"    # C < Z < 2C
    assert _loudness(45_000, 20_000) == "loud"     # Z >= 2C


def test_cross_tab_j_counts_winning_unaffordable_futures():
    p_term = np.array([100., 100., 100., 50.])
    s_term = np.array([90., 90., 90., 90.])     # property wins trials 0,1,2
    # outside cash exceeds ceiling (20k) in some year for trials 0 and 3
    outside = np.array([
        [25_000, 0.],   # trial 0: wins AND over → counts
        [0., 0.],       # trial 1: wins, affordable
        [0., 0.],       # trial 2: wins, affordable
        [30_000, 0.],   # trial 3: loses (over but doesn't count)
    ])
    # 1 of 4 = 25
    assert _cross_tab_j(p_term, s_term, outside, 20_000) == 25
```

- [ ] **Step 6: Run to verify the new tests fail**

Run: `.venv/bin/python -m pytest tests/test_verdict.py -q`
Expected: FAIL — `_crossover_year` / `_loudness` / `_cross_tab_j` not defined.

- [ ] **Step 7: Implement the three helpers**

```python
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
```

- [ ] **Step 8: Run to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_verdict.py -q`
Expected: PASS (8 tests).

- [ ] **Step 9: Write failing test for `compute_verdict` (integration of the dataclass)**

```python
def _fake_result(p_term, s_term, outside_cash, cashflow):
    """Minimal engine-shaped dict for compute_verdict."""
    p_term = np.asarray(p_term, float)
    s_term = np.asarray(s_term, float)
    outside_cash = np.asarray(outside_cash, float)
    cashflow = np.asarray(cashflow, float)
    return {
        "property_terminal_wealth": p_term,
        "shares_terminal_wealth": s_term,
        "p_property_wins": float((p_term > s_term).mean()),
        "outside_cash_per_trial_year": outside_cash,
        "median_outside_cash_total": float(np.median(outside_cash.sum(axis=1))),
        "worst_year_cash": float(np.percentile(outside_cash.max(axis=1), 90)),
        "median_property_wealth": float(np.median(p_term)),
        "median_shares_wealth": float(np.median(s_term)),
        "property_cashflow_path": cashflow,
    }


def test_compute_verdict_basic_property_lead():
    n = 100
    p_term = np.full(n, 200_000.0)
    s_term = np.full(n, 150_000.0)
    p_term[:32] = 100_000.0       # property wins 68/100
    outside = np.zeros((n, 4))
    outside[:, 0] = 5_000.0
    cashflow = np.tile(np.array([-5_000., -1_000., 500., 800.]), (n, 1))
    real = _fake_result(p_term, s_term, outside, cashflow)
    fair = _fake_result(s_term, p_term * 2, outside, cashflow)  # shares win fair-fight

    v = compute_verdict(real, fair, serviceability_ceiling=20_000,
                        deposit=190_000, upfront_costs=40_000)

    assert v.win_rate == 68
    assert v.leader == "property"
    assert v.badge_state == "badge"
    assert v.upfront_x == 230_000          # deposit + upfront_costs
    assert v.typical_t == 5_000.0          # median summed outside cash
    assert v.crossover_k == 3              # cashflow ≥0 from year 3
    assert v.fairfight_shares_win is True
    assert v.loudness == "quiet"           # Z (5k) <= C (20k)
```

- [ ] **Step 10: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_verdict.py::test_compute_verdict_basic_property_lead -q`
Expected: FAIL — `compute_verdict` not defined.

- [ ] **Step 11: Implement `VerdictNumbers` + `compute_verdict`**

```python
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
```

- [ ] **Step 12: Run the full verdict test file**

Run: `.venv/bin/python -m pytest tests/test_verdict.py -q`
Expected: PASS (9 tests).

- [ ] **Step 13: Commit**

```bash
git add ui/verdict.py tests/test_verdict.py
git commit -m "feat(compare-v2): verdict compute layer (VerdictNumbers + helpers)"
```

---

## Task 2: `ui/verdict.py` — HTML render functions

**Files:**
- Modify: `ui/verdict.py`
- Test: `tests/test_verdict.py`

**Interfaces:**
- Consumes: `VerdictNumbers`, horizon int, `$L` leverage float; `ui/common._fmt_money`.
- Produces:
  - `render_trust_line(v: VerdictNumbers, horizon: int) -> str`
  - `render_cards(v: VerdictNumbers) -> str` (two cards + verdict link clause + badge per state)
  - `render_win_line(v: VerdictNumbers) -> str` (always carries "assuming you fund it")
  - `render_affordability(v: VerdictNumbers, horizon: int, ceiling: float) -> str`
  - `render_fairfight_spoiler(v: VerdictNumbers, leverage_l: float) -> str`

Render functions return HTML strings (no `st.*`); `app_compare.py` passes them through `ui/common._render_html`. Tests assert on substrings.

- [ ] **Step 1: Write failing tests for the render functions**

```python
from ui.verdict import (
    render_trust_line, render_cards, render_win_line,
    render_affordability, render_fairfight_spoiler,
)


def _sample_verdict(**over):
    base = dict(
        p_median=1_800_000., s_median=1_200_000.,
        p_p10=900_000., p_p90=3_200_000., s_p10=700_000., s_p90=2_100_000.,
        win_rate=68, leader="property", badge_state="badge",
        badge_label="Ahead in most futures", close_note=False,
        upfront_x=230_000., typical_t=85_000., crossover_k=7,
        worst_z=24_000., worst_max=140_000., cross_tab_j=18,
        loudness="amber", fairfight_y=3_090_000., fairfight_shares_win=True,
    )
    base.update(over)
    return VerdictNumbers(**base)


def test_win_line_always_has_funding_clause():
    html = render_win_line(_sample_verdict())
    assert "assuming you fund it" in html.lower()
    assert "68" in html


def test_cards_show_verdict_link_clause():
    html = render_cards(_sample_verdict())
    assert "fund every shortfall" in html.lower()
    assert "what you'd cough up" in html.lower()


def test_cards_neutral_state_has_no_badge_label():
    html = render_cards(_sample_verdict(badge_state="neutral", leader="tie", badge_label=""))
    assert "Ahead in most futures" not in html
    assert "too close to call" in html.lower()


def test_affordability_shows_crossover_year_when_present():
    html = render_affordability(_sample_verdict(crossover_k=7), horizon=20, ceiling=20_000)
    assert "year 7" in html.lower()
    assert "18" in html  # cross-tab J


def test_affordability_never_crosses_branch():
    html = render_affordability(_sample_verdict(crossover_k=None), horizon=20, ceiling=20_000)
    assert "doesn't fully cover its own costs" in html.lower()
    assert "year " not in html.lower().split("doesn't")[0][-12:]  # no "easing by year K" before the never-clause


def test_fairfight_spoiler_states_flip_when_shares_win():
    html = render_fairfight_spoiler(_sample_verdict(fairfight_shares_win=True), leverage_l=760_000)
    assert "never margin-call" in html.lower() or "never margin call" in html.lower()
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_verdict.py -q`
Expected: FAIL — render functions not defined.

- [ ] **Step 3: Implement the render functions**

```python
from ui.common import _fmt_money


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
        f'<span title="downside">(P10 downside ↓)</span></div>'
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
                   f'year <b>{v.crossover_k}</b> as rent catches up.')
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
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_verdict.py -q`
Expected: PASS (15 tests).

- [ ] **Step 5: Commit**

```bash
git add ui/verdict.py tests/test_verdict.py
git commit -m "feat(compare-v2): verdict HTML render functions"
```

---

## Task 3: `app_compare.py` — Streamlit shell + URL clamp + two-run wiring

**Files:**
- Create: `app_compare.py`
- Test: `tests/test_app_compare.py`

**Interfaces:**
- Consumes: `run_monte_carlo` (engine), `ui.verdict.compute_verdict` + render functions, `ui.common.GLOBAL_CSS/_render_html`, `model.duty.stamp_duty`, `model.normalisation.PORTFOLIO_PROFILES`.
- Produces: a runnable Streamlit app (`streamlit run app_compare.py`); a `_clamp_*` set of pure helpers importable by tests.

- [ ] **Step 1: Write the failing URL-clamp test**

```python
# tests/test_app_compare.py
import pytest
from app_compare import clamp_horizon, clamp_rate, clamp_deposit, clamp_topup


def test_clamp_horizon_valid_and_invalid():
    assert clamp_horizon(10) == 10
    assert clamp_horizon(7) == 10        # not in {5,10,15,20} → default 10
    assert clamp_horizon("None") == 10   # malformed
    assert clamp_horizon(20) == 20


def test_clamp_rate_bounds():
    assert clamp_rate(0.062) == 0.062
    assert clamp_rate(-1) == 0.0
    assert clamp_rate(0.9) == 0.30       # cap at 30%
    assert clamp_rate("junk") == 0.062   # default


def test_clamp_deposit_not_above_price():
    assert clamp_deposit(190_000, price=950_000) == 190_000
    assert clamp_deposit(2_000_000, price=950_000) == 950_000
    assert clamp_deposit(-5, price=950_000) == 0


def test_clamp_topup_floor_zero():
    assert clamp_topup(20_000) == 20_000
    assert clamp_topup(-100) == 0
    assert clamp_topup("None") == 20_000
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_app_compare.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app_compare'`.

- [ ] **Step 3: Implement the clamp helpers + the app shell**

```python
# app_compare.py
"""Compare v2 — same-money property-vs-shares verdict (standalone screen).

Run: .venv/bin/streamlit run app_compare.py
Engine reused unchanged; see docs/superpowers/specs/2026-06-19-property-vs-shares-compare-v2-design.md
"""
import streamlit as st

from model.duty import stamp_duty
from model.monte_carlo import run_monte_carlo
from model.normalisation import PORTFOLIO_PROFILES
from ui.common import GLOBAL_CSS, _render_html
from ui.verdict import (
    compute_verdict, render_affordability, render_cards,
    render_fairfight_spoiler, render_trust_line, render_win_line,
)

HORIZONS = [5, 10, 15, 20]
PROFILES = ["asx_only", "global", "blended"]


# ----- clamp helpers (read AND write, project rule) --------------------------
def clamp_horizon(v) -> int:
    try:
        v = int(v)
    except (ValueError, TypeError):
        return 10
    return v if v in HORIZONS else 10


def clamp_rate(v) -> float:
    try:
        v = float(v)
    except (ValueError, TypeError):
        return 0.062
    return max(0.0, min(0.30, v))


def clamp_deposit(v, price: float) -> float:
    try:
        v = float(v)
    except (ValueError, TypeError):
        return min(190_000.0, price)
    return max(0.0, min(v, price))


def clamp_topup(v) -> float:
    try:
        v = float(v)
    except (ValueError, TypeError):
        return 20_000.0
    return max(0.0, v)


# Generic clamped reader — a malformed/junk OR out-of-range URL value must fall
# back inside [lo, hi], never raise. Streamlit number_input raises if its `value=`
# is outside [min,max], so EVERY numeric default must already be clamped here
# (project rule — a "junk" in the URL once crashed the app, 6bab10e).
def _qp_clamped(key, default: float, lo: float, hi: float) -> float:
    try:
        v = float(st.query_params.get(key, default))
    except (ValueError, TypeError):
        return default
    return max(lo, min(hi, v))


def _qp(key, default):
    return st.query_params.get(key, default)


def main() -> None:
    st.set_page_config(page_title="Property vs Shares — Compare", layout="wide", page_icon="🏠")
    _render_html(GLOBAL_CSS)

    # --- horizon toggle ---
    horizon = clamp_horizon(_qp("yrs", 10))
    horizon = st.segmented_control("Time horizon (years)", HORIZONS,
                                   default=horizon, key="cmp_horizon") or horizon

    # --- slim inputs (every numeric default pre-clamped to its widget domain) ---
    c1, c2, c3 = st.columns(3)
    with c1:
        price = st.number_input("Purchase price",
                                value=int(_qp_clamped("price", 950_000, 50_000, 50_000_000)),
                                step=10_000, min_value=50_000)
        deposit = clamp_deposit(_qp("dep", 190_000), price)
        deposit = st.number_input("Deposit", value=int(deposit), step=10_000,
                                  min_value=0, max_value=int(price))
        # rate stored in the URL as a percent (e.g. 6.2); clamp_rate works in fraction space.
        loan_rate = clamp_rate(_qp_clamped("rate", 6.2, 0.0, 30.0) / 100)
        loan_rate = st.number_input("Loan interest rate %", value=loan_rate * 100,
                                    step=0.1, min_value=0.0, max_value=30.0) / 100
    with c2:
        gross_yield = st.number_input("Gross rent yield %",
                                      value=_qp_clamped("yield", 3.5, 0.0, 15.0),
                                      step=0.1, min_value=0.0, max_value=15.0) / 100
        property_growth_mu = st.number_input("Property capital growth %/yr",
                                             value=_qp_clamped("grow", 5.5, -5.0, 20.0),
                                             step=0.1, min_value=-5.0, max_value=20.0) / 100
        vacancy_weeks = st.number_input("Vacancy (weeks/yr)",
                                        value=_qp_clamped("vac", 2.0, 0.0, 52.0),
                                        step=0.5, min_value=0.0, max_value=52.0)
    with c3:
        state = st.selectbox("State", ["NSW", "VIC", "QLD", "SA", "WA", "TAS", "ACT", "NT"],
                             index=0)
        derived_duty = stamp_duty(state, price)
        upfront_costs = st.number_input("Upfront costs (stamp duty + fees)",
                                        value=int(_qp_clamped("upfront", int(derived_duty + 2_600),
                                                              0, 10_000_000)),
                                        step=1_000, min_value=0)
        profile = st.selectbox("Share portfolio", PROFILES,
                               index=PROFILES.index(_qp("port", "blended"))
                               if _qp("port", "blended") in PROFILES else 2)
        mtr = st.number_input("Marginal tax rate %",
                              value=_qp_clamped("mtr", 37.0, 0.0, 47.0),
                              step=1.0, min_value=0.0, max_value=47.0) / 100

    max_top_up = clamp_topup(_qp("topup", 20_000))
    max_top_up = st.number_input("Annual top-up you'd plan for", value=int(max_top_up),
                                 step=1_000, min_value=0)

    # --- persist clamped values to URL (write side of the rule) ---
    st.query_params.update({k: str(v) for k, v in {
        "yrs": horizon, "price": price, "dep": int(deposit),
        "rate": round(loan_rate * 100, 1), "yield": round(gross_yield * 100, 1),
        "grow": round(property_growth_mu * 100, 1), "vac": vacancy_weeks,
        "port": profile, "mtr": round(mtr * 100, 1), "topup": int(max_top_up),
    }.items()})

    # --- two cached runs ---
    prof = PORTFOLIO_PROFILES[profile]
    base = dict(
        trials=5000, horizon_years=horizon, purchase_price=price, deposit=deposit,
        stamp_duty=float(upfront_costs), buying_costs=0.0,
        loan_rate_mu=loan_rate, loan_rate_sigma=0.01, gross_yield=gross_yield,
        vacancy_weeks_mu=vacancy_weeks, vacancy_weeks_sigma=1.0, rental_yield_sigma=0.0,
        property_growth_mu=property_growth_mu, property_growth_sigma=0.12,
        management_fee_pct=0.07, maintenance_pct=0.008, property_age="established_pre_2017",
        asset_type="house", depreciation_override=None,
        share_return_mu=prof["return_mu"], share_return_sigma=prof["return_sigma"],
        portfolio_profile=profile, margin_loan_rate=0.085, correlation=0.3,
        mtr=mtr, cpi=0.025, drp=True, serviceability_ceiling=float(max_top_up), seed=42,
    )
    realistic = cached_run(mode="realistic", isolate_asset_quality=False, **base)
    fair_fight = cached_run(mode="fair_fight", isolate_asset_quality=True, **base)

    # --- compute + render ---
    v = compute_verdict(realistic, fair_fight, serviceability_ceiling=float(max_top_up),
                        deposit=deposit, upfront_costs=float(upfront_costs))
    leverage_l = price - (deposit + upfront_costs)

    _render_html(render_trust_line(v, horizon))
    _render_html(render_cards(v))
    _render_html(render_win_line(v))
    _render_html(render_fairfight_spoiler(v, leverage_l))
    with st.expander("See the side-by-side →"):
        st.write(f"Fair-fight shares median: {v.fairfight_y:,.0f}")
    _render_html(render_affordability(v, horizon, float(max_top_up)))


@st.cache_data
def cached_run(**kwargs):
    return run_monte_carlo(**kwargs)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify the clamp tests pass**

Run: `.venv/bin/python -m pytest tests/test_app_compare.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add app_compare.py tests/test_app_compare.py
git commit -m "feat(compare-v2): app_compare shell + URL clamp + two-run wiring"
```

---

## Task 4: `app_compare.py` — AppTest smoke + boundary + framing tests

**Files:**
- Modify: `tests/test_app_compare.py`

**Interfaces:**
- Consumes: `streamlit.testing.v1.AppTest` against `app_compare.py`; `compute_verdict` for direct framing assertions.

- [ ] **Step 1: Write the failing AppTest smoke + boundary tests**

```python
from streamlit.testing.v1 import AppTest


def test_app_loads_without_exception():
    at = AppTest.from_file("app_compare.py", default_timeout=60).run()
    assert not at.exception


def test_malformed_url_params_do_not_crash():
    # Junk EVERY numeric param — none may raise (number_input value= must be pre-clamped).
    at = AppTest.from_file("app_compare.py", default_timeout=60)
    for key in ("yrs", "price", "dep", "rate", "yield", "grow", "vac",
                "upfront", "mtr", "topup", "port"):
        at.query_params[key] = "None"
    at.run()
    assert not at.exception


def test_out_of_range_url_params_do_not_crash():
    # Wildly out-of-range numerics must clamp into the widget domain, not raise.
    at = AppTest.from_file("app_compare.py", default_timeout=60)
    at.query_params["rate"] = "999"
    at.query_params["yield"] = "999"
    at.query_params["grow"] = "-999"
    at.query_params["mtr"] = "999"
    at.run()
    assert not at.exception


def test_zero_topup_boundary_runs():
    at = AppTest.from_file("app_compare.py", default_timeout=60)
    at.query_params["topup"] = "0"
    at.run()
    assert not at.exception
```

- [ ] **Step 2: Run to verify they fail (or pass-on-build)**

Run: `.venv/bin/python -m pytest tests/test_app_compare.py -q`
Expected: the three AppTest cases run; if `app_compare.py` from Task 3 is correct they PASS. If any raise, fix `app_compare.py` until green. (TDD note: these are smoke guards; they may pass immediately against a correct Task 3.)

- [ ] **Step 3: Write framing-behaviour tests (direct compute_verdict)**

```python
import numpy as np
from ui.verdict import compute_verdict


def _result(p_term, s_term, outside, cashflow):
    p_term, s_term = np.asarray(p_term, float), np.asarray(s_term, float)
    outside, cashflow = np.asarray(outside, float), np.asarray(cashflow, float)
    return {
        "property_terminal_wealth": p_term, "shares_terminal_wealth": s_term,
        "p_property_wins": float((p_term > s_term).mean()),
        "outside_cash_per_trial_year": outside,
        "median_outside_cash_total": float(np.median(outside.sum(axis=1))),
        "worst_year_cash": float(np.percentile(outside.max(axis=1), 90)),
        "median_property_wealth": float(np.median(p_term)),
        "median_shares_wealth": float(np.median(s_term)),
        "property_cashflow_path": cashflow,
    }


def test_near_tie_is_neutral_no_badge():
    n = 100
    p = np.full(n, 100_000.0); s = np.full(n, 100_000.0)
    p[:50] = 110_000.0; s[50:] = 110_000.0   # ~50/50
    r = _result(p, s, np.zeros((n, 3)), np.zeros((n, 3)))
    v = compute_verdict(r, r, serviceability_ceiling=20_000, deposit=190_000, upfront_costs=40_000)
    assert v.badge_state == "neutral"
    assert v.badge_label == ""


def test_affordability_loud_does_not_change_badge():
    # property dominates wealth (badge) AND worst-year cash is huge (loud panel)
    n = 100
    p = np.full(n, 300_000.0); s = np.full(n, 100_000.0)   # property wins 100/100
    outside = np.zeros((n, 3)); outside[:, 0] = 80_000.0     # Z >> C
    r = _result(p, s, outside, np.full((n, 3), -1_000.0))
    v = compute_verdict(r, r, serviceability_ceiling=20_000, deposit=190_000, upfront_costs=40_000)
    assert v.loudness == "loud"
    assert v.badge_state == "badge"      # verdict NOT suppressed by loud panel
    assert v.leader == "property"


def test_t_single_source_matches_engine_key():
    n = 50
    outside = np.zeros((n, 4)); outside[:, 0] = 6_000.0; outside[:, 1] = 4_000.0
    r = _result(np.full(n, 2.0), np.full(n, 1.0), outside, np.zeros((n, 4)))
    v = compute_verdict(r, r, serviceability_ceiling=20_000, deposit=190_000, upfront_costs=40_000)
    assert v.typical_t == r["median_outside_cash_total"]   # one source, not recomputed
```

- [ ] **Step 4: Run the whole file**

Run: `.venv/bin/python -m pytest tests/test_app_compare.py -q`
Expected: PASS (all smoke + boundary + framing tests).

- [ ] **Step 5: Commit**

```bash
git add tests/test_app_compare.py
git commit -m "test(compare-v2): AppTest smoke, URL boundary, framing behaviour"
```

---

## Task 5: Final verification — full suite + manual launch

**Files:** none (verification only).

- [ ] **Step 1: Run the entire test suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS — all pre-existing tests still green (engine + existing app untouched) plus the new `test_verdict.py` and `test_app_compare.py`.

- [ ] **Step 2: Launch the app and eyeball the verdict**

Run: `.venv/bin/streamlit run app_compare.py`
Expected: loads sub-second after first compute; verdict cards, win-line, affordability panel render; toggling horizon and editing inputs recomputes without error; the URL gains query params and a reload restores the scenario.

- [ ] **Step 3: Confirm timing holds**

Run (sanity): a 5,000-trial realistic + fair-fight pair completes well under a second (spec §4 measured 592ms). If the UI feels sluggish, confirm `cached_run` is hit on repeat (Streamlit cache).

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "chore(compare-v2): final verification pass"
```

---

## Out of scope (per spec §10)

No mix curve / persona cards, no PPOR, no realistic-margin fair-fight, no PDF export, no engine change, no forced-sale/repricing model.

**Intentional v1 deferrals (spec elements deliberately not in this plan — flagged so coverage isn't overstated):**
1. **Sparkline (spec §5.6)** — the affordability panel ships with the four text figures + cross-tab `J`; the per-year median+P10–P90 band chart is a polish follow-up, not a blocker.
2. **Advanced expander (spec §6)** — the slim-10 inputs are built; the advanced overrides (`*_sigma`, `management_fee_pct`, `maintenance_pct`, `correlation`, `cpi`, distribution knobs, `seed`, etc.) are **hardcoded to sensible defaults in the `base` dict** for v1 rather than surfaced as widgets. Exposing them is a mechanical follow-up; defaults match the engine's so the slim panel produces a valid run.
3. **Fair-fight side-by-side detail (spec §5.5)** — the always-visible one-line spoiler (the load-bearing honesty piece) is fully built; the expander currently shows a minimal figure, with full medians+ranges a polish follow-up.

These are all additive polish; the verdict, affordability panel, funding-model framing, and URL-clamp safety — the spec's substance — are fully covered by Tasks 1–5.
