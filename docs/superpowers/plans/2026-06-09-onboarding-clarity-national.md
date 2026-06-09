# Onboarding + Clarity + Australia-Wide — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Property vs Shares app understandable to first-time non-expert users, fix the persona/breakdown disconnect, and work for any Australian state (stamp duty per state + a flat land-tax input).

**Architecture:** Four phases. **A** (tax engine, `model/`) is independent and lands first — a typed stamp-duty evaluator for 8 states plus a flat land-tax field replacing SA-only logic. **B** (persona control) and **C** (onboarding) extract UI into a `ui/` package and fix state/UX. **D** is cross-cutting bug/cleanup. Each phase is shippable on its own; the suite stays green throughout.

**Tech Stack:** Python 3.11–3.13, Streamlit ≥1.57, NumPy, pytest. Run tests with `.venv/bin/python -m pytest`.

**Spec:** `docs/superpowers/specs/2026-06-09-onboarding-clarity-national-design.md`

---

## File Structure

- `model/duty.py` — NEW. `DUTY_SCHEDULES` (8 states, typed segments) + `stamp_duty(state, price)` evaluator. Pure, no Streamlit.
- `model/tax.py` — MODIFY. Retire `sa_stamp_duty`, `sa_land_tax`, `SA_DUTY_BANDS`, `SA_LAND_TAX_BANDS`, `SA_TRANSFER_FEE`.
- `model/property_strategy.py` — MODIFY. Replace per-value `sa_land_tax(v)` with flat `annual_land_tax` from inputs.
- `model/monte_carlo.py` — MODIFY. Thread `state` + `annual_land_tax` through.
- `ui/__init__.py`, `ui/onboarding.py`, `ui/persona.py` — NEW. Extract render + persona-state logic out of `app.py`.
- `app.py` — MODIFY. State dropdown, land-tax field, wire new modules, URL `persona` param, disclaimer, `$` audit, single CSS injection.
- `tests/test_duty.py`, `tests/test_land_tax_flat.py`, `tests/test_persona_control.py` — NEW.
- `mock_hero.py` — DELETE at end.

---

# PHASE A — National stamp duty + flat land tax

## Task A1: Typed stamp-duty evaluator + schedules

**Files:**
- Create: `model/duty.py`
- Test: `tests/test_duty.py`

- [ ] **Step 1: Write failing tests for the evaluator and mid-range points**

```python
# tests/test_duty.py
import pytest
from model.duty import stamp_duty, DUTY_SCHEDULES

def test_all_states_present():
    assert set(DUTY_SCHEDULES) == {"NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"}

def test_nsw_marginal_700k():
    # $372,001–$1,240,000 band: 1597 + 3.5% over 372k
    assert stamp_duty("NSW", 700_000) == pytest.approx(1_597 + 0.035 * (700_000 - 372_000), abs=1)

def test_sa_700k_no_transfer_fee():
    # SA $500k+ band: 21330 + 5.5% over 500k; transfer fee dropped vs old code
    assert stamp_duty("SA", 700_000) == pytest.approx(21_330 + 0.055 * (700_000 - 500_000), abs=1)

def test_qld_700k():
    # $540,001–$1,000,000: 17325 + 4.5% over 540k
    assert stamp_duty("QLD", 700_000) == pytest.approx(17_325 + 0.045 * (700_000 - 540_000), abs=1)

def test_tas_min_50_under_3k():
    assert stamp_duty("TAS", 2_000) == pytest.approx(50, abs=0.5)
    assert stamp_duty("TAS", 3_000) == pytest.approx(50, abs=0.5)

def test_zero_or_negative_price():
    assert stamp_duty("NSW", 0) == 0.0
    assert stamp_duty("VIC", -5) == 0.0
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_duty.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'model.duty'`

- [ ] **Step 3: Implement `model/duty.py` with the marginal + flat_pct evaluator and the marginal-only states**

```python
"""National conveyance/stamp duty for an investment property purchase.

Each state's schedule is a list of typed segments evaluated against the
purchase price. Segment kinds:
  - "marginal": duty = base + rate * (price - lower_bound), for price in (lower, upper].
  - "flat_pct": duty = rate * price  (the WHOLE price), for price in (lower, upper].
NT uses a quadratic for price <= 525k; see model.duty._nt_duty.

Registration/transfer fees levied by separate agencies (Land Services SA,
NSW LRS, etc.) are NOT included — the app's buying_costs approximates them.
Foreign-purchaser surcharges are out of scope. Schedules are FY2025-26,
sourced from official state revenue offices 2026-06-09 (see spec).
"""

INF = float("inf")

# Each segment: (upper_bound, kind, a, b)
#   marginal: a = base_duty_at_lower_bound, b = marginal_rate
#   flat_pct: a is ignored (use None), b = flat rate on full price
DUTY_SCHEDULES = {
    "NSW": [
        (17_000,    "marginal", 0,       0.0125),
        (37_000,    "marginal", 212,     0.0150),
        (99_000,    "marginal", 512,     0.0175),
        (372_000,   "marginal", 1_597,   0.0350),
        (1_240_000, "marginal", 11_152,  0.0450),
        (3_721_000, "marginal", 50_212,  0.0550),
        (INF,       "marginal", 186_667, 0.0700),
    ],
    "VIC": [
        (25_000,     "marginal", 0,       0.014),
        (130_000,    "marginal", 350,     0.024),
        (960_000,    "marginal", 2_870,   0.060),
        (2_000_000,  "flat_pct", None,    0.055),   # 5.5% of FULL value
        (INF,        "marginal", 110_000, 0.065),   # lower bound = 2_000_000
    ],
    "QLD": [
        (5_000,     "marginal", 0,      0.000),
        (75_000,    "marginal", 0,      0.015),
        (540_000,   "marginal", 1_050,  0.035),
        (1_000_000, "marginal", 17_325, 0.045),
        (INF,       "marginal", 38_025, 0.0575),
    ],
    "WA": [
        (120_000, "marginal", 0,      0.0190),
        (150_000, "marginal", 2_280,  0.0285),
        (360_000, "marginal", 3_135,  0.0380),
        (725_000, "marginal", 11_115, 0.0475),
        (INF,     "marginal", 28_453, 0.0515),
    ],
    "SA": [
        (12_000,  "marginal", 0,      0.0100),
        (30_000,  "marginal", 120,    0.0200),
        (50_000,  "marginal", 480,    0.0300),
        (100_000, "marginal", 1_080,  0.0350),
        (200_000, "marginal", 2_830,  0.0400),
        (250_000, "marginal", 6_830,  0.0425),
        (300_000, "marginal", 8_955,  0.0475),
        (500_000, "marginal", 11_330, 0.0500),
        (INF,     "marginal", 21_330, 0.0550),
    ],
    "TAS": [
        (3_000,   "marginal", 50,     0.000),   # $50 flat minimum
        (25_000,  "marginal", 50,     0.0175),
        (75_000,  "marginal", 435,    0.0225),
        (200_000, "marginal", 1_560,  0.035),
        (375_000, "marginal", 5_935,  0.040),
        (725_000, "marginal", 12_935, 0.0425),
        (INF,     "marginal", 27_810, 0.045),
    ],
    "ACT": [
        (200_000,   "marginal", 0,      0.0120),
        (300_000,   "marginal", 2_400,  0.0220),
        (500_000,   "marginal", 4_600,  0.0340),
        (750_000,   "marginal", 11_400, 0.0432),
        (1_000_000, "marginal", 22_200, 0.0590),
        (1_455_000, "marginal", 36_950, 0.0640),
        (INF,       "flat_pct", None,   0.0454),  # 4.54% of FULL value
    ],
    # NT handled by _nt_duty (quadratic + flat_pct), not this segment loop.
}


def _eval_segments(segments, price):
    prev_upper = 0.0
    for upper, kind, a, b in segments:
        if price <= upper:
            if kind == "flat_pct":
                return b * price
            return a + (price - prev_upper) * b
        prev_upper = upper
    return 0.0  # unreachable (last upper is INF)


def _nt_duty(price):
    """NT: quadratic for price <= 525k, then flat % of full value."""
    if price <= 525_000:
        v = price / 1000.0
        return 0.06571441 * v * v + 15 * v
    if price < 3_000_000:
        return 0.0495 * price
    if price < 5_000_000:
        return 0.0575 * price
    return 0.0595 * price


def stamp_duty(state, price):
    """Conveyance/stamp duty for an investment purchase in `state` at `price`."""
    if price <= 0:
        return 0.0
    if state == "NT":
        return _nt_duty(price)
    return _eval_segments(DUTY_SCHEDULES[state], price)
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_duty.py -v`
Expected: PASS (all 6)

- [ ] **Step 5: Commit**

```bash
git add model/duty.py tests/test_duty.py
git commit -m "feat(duty): typed national stamp-duty evaluator for 8 states"
```

## Task A2: Boundary-discontinuity tests (the legislated jumps)

**Files:**
- Test: `tests/test_duty.py` (add)

- [ ] **Step 1: Add boundary tests asserting the legislated jumps (NOT continuity)**

```python
# tests/test_duty.py  (append)

def test_vic_960k_step_up():
    below = stamp_duty("VIC", 960_000)        # marginal: 2870 + 6% of (960k-130k)
    at = stamp_duty("VIC", 960_001)           # flat 5.5% of full
    assert below == pytest.approx(52_670, abs=1)
    assert at == pytest.approx(0.055 * 960_001, abs=1)   # ~52_800
    assert at > below                          # legislated step UP

def test_vic_2m_continuous_into_top_band():
    assert stamp_duty("VIC", 2_000_000) == pytest.approx(0.055 * 2_000_000, abs=1)  # 110_000
    assert stamp_duty("VIC", 2_000_001) == pytest.approx(110_000 + 0.065 * 1, abs=1)

def test_nt_quadratic_and_flat_seam():
    # quadratic at 525k
    v = 525_000 / 1000.0
    assert stamp_duty("NT", 525_000) == pytest.approx(0.06571441 * v * v + 15 * v, abs=1)
    # flat 4.95% just above
    assert stamp_duty("NT", 525_001) == pytest.approx(0.0495 * 525_001, abs=1)

def test_nt_3m_and_5m_jumps():
    assert stamp_duty("NT", 2_999_999) == pytest.approx(0.0495 * 2_999_999, abs=1)
    assert stamp_duty("NT", 3_000_000) == pytest.approx(0.0575 * 3_000_000, abs=1)  # +~24k
    assert stamp_duty("NT", 5_000_000) == pytest.approx(0.0595 * 5_000_000, abs=1)  # +~10k

def test_act_flat_top_band():
    # Below the top band uses marginal; at/above uses flat 4.54% of full value.
    assert stamp_duty("ACT", 1_455_000) == pytest.approx(36_950 + 0.064 * (1_455_000 - 1_000_000), abs=1)
    assert stamp_duty("ACT", 1_456_000) == pytest.approx(0.0454 * 1_456_000, abs=1)
```

> **Before coding-confidence note:** the ACT upper bound ($1,455,000) and its near-boundary step-down were flagged in review. These prices are far above the app's typical use (~$800k), so the schedule is correct for normal use; if the ACT calculator later shows a different exact crossover, adjust the `1_455_000` bound and this test together. Not a blocker for Phase A.

- [ ] **Step 2: Run to verify pass**

Run: `.venv/bin/python -m pytest tests/test_duty.py -v`
Expected: PASS (all, including the 5 new boundary tests)

- [ ] **Step 3: Commit**

```bash
git add tests/test_duty.py
git commit -m "test(duty): assert legislated VIC/ACT/NT boundary discontinuities"
```

## Task A3: Swap `app.py` to national stamp duty, retire `sa_stamp_duty`

**Files:**
- Modify: `app.py:15` (import), `app.py:506` (call), plus a new State selectbox in the sidebar
- Modify: `model/tax.py` (delete `SA_DUTY_BANDS`, `SA_TRANSFER_FEE`, `sa_stamp_duty`)

- [ ] **Step 1: Add a State selectbox in the sidebar property section.** Find the sidebar "The property" block (where `purchase_price` etc. are defined) and add, near the top of that block:

```python
state = st.sidebar.selectbox(
    "State",
    ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"],
    index=["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"].index(qp("state", str, "SA")),
    help="Sets stamp duty for your purchase. Income tax, CGT and negative gearing are federal (same Australia-wide).",
)
```

- [ ] **Step 2: Replace the import and the stamp-duty call.**

In `app.py` change line 15 region:
```python
from model.tax import sa_stamp_duty
```
to:
```python
from model.duty import stamp_duty
```

Change line 506:
```python
stamp_duty = sa_stamp_duty(purchase_price)
```
to (rename the local to avoid shadowing the imported function):
```python
stamp_duty_amount = stamp_duty(state, purchase_price)
```
Then update the three downstream uses: line 508 `upfront = deposit + stamp_duty + buying_costs` → `... + stamp_duty_amount + ...`; line 518 `stamp_duty=stamp_duty,` → `stamp_duty=stamp_duty_amount,`; and the assumptions f-string near line 698 `{_fmt_money(stamp_duty)}` → `{_fmt_money(stamp_duty_amount)}`.

- [ ] **Step 3: Add `state` to the URL persistence block** (the `st.query_params.update` at line 495):
```python
    "state": state,
```

- [ ] **Step 4: Delete the dead SA stamp-duty code from `model/tax.py`** (lines 106–133: `SA_DUTY_BANDS`, `SA_TRANSFER_FEE`, `sa_stamp_duty`).

- [ ] **Step 5: Run the app to verify it boots and duty changes with state**

Run: `.venv/bin/streamlit run app.py --server.port 8503 --server.headless true` then `curl -s -o /dev/null -w "%{http_code}" http://localhost:8503` → expect `200`. Stop it after.

- [ ] **Step 6: Run full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (any test importing `sa_stamp_duty` must be updated to `stamp_duty("SA", ...)` minus the old $181 fee — search `grep -rn sa_stamp_duty tests/`).

- [ ] **Step 7: Commit**

```bash
git add app.py model/tax.py tests/
git commit -m "feat(app): per-state stamp duty via State selector; retire sa_stamp_duty"
```

## Task A4: Replace per-value land tax with a flat editable field

**Files:**
- Test: `tests/test_land_tax_flat.py`
- Modify: `model/property_strategy.py:179-196`, its `PropertyInputs` dataclass, `model/monte_carlo.py`, `app.py`
- Modify: `model/tax.py` (delete `SA_LAND_TAX_BANDS`, `sa_land_tax`)

- [ ] **Step 1: Write a failing test that a flat land tax raises annual cost and is deductible**

```python
# tests/test_land_tax_flat.py
import numpy as np
from model.property_strategy import PropertyInputs, simulate_property_trial

def _base_inputs(annual_land_tax):
    h = 10
    return PropertyInputs(
        purchase_price=700_000, deposit=140_000,
        loan_rate_path=np.full(h, 0.06), loan_term_years=30, io_period_years=5,
        gross_yield=0.04, vacancy_weeks_path=np.zeros(h), capital_growth_path=np.full(h, 0.05),
        management_fee_pct=0.07, maintenance_pct=0.01, property_age="established_post_2017",
        asset_type="house", depreciation_override=None, mtr=0.37, cpi=0.025, horizon_years=h,
        selling_costs_pct=0.025, acquisition_costs=30_000, property_regime="current",
        overflow_dividend_yield=0.04, overflow_franked_portion=0.8,
        annual_land_tax=annual_land_tax,
    )

def test_land_tax_zero_is_baseline():
    r = simulate_property_trial(_base_inputs(0.0))
    assert r.other_costs_path is not None

def test_land_tax_increases_cost_and_deducts():
    r0 = simulate_property_trial(_base_inputs(0.0))
    r1 = simulate_property_trial(_base_inputs(3_000.0))
    # Year-1 other costs rise by exactly the flat amount.
    assert r1.other_costs_path[0] - r0.other_costs_path[0] == 3_000.0
    # Net terminal-wealth drag is positive but less than full land tax (deductible at MTR).
    drag = r0.terminal_after_tax_wealth + r0.overflow_share_terminal_value \
         - (r1.terminal_after_tax_wealth + r1.overflow_share_terminal_value)
    assert drag > 0
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_land_tax_flat.py -v`
Expected: FAIL — `PropertyInputs` has no field `annual_land_tax`.

- [ ] **Step 3: Add `annual_land_tax` to `PropertyInputs`** (in `model/property_strategy.py`, add a field, e.g. after `mtr`):
```python
    annual_land_tax: float = 0.0
```

- [ ] **Step 4: Replace the land-tax computation** at `model/property_strategy.py:177-180`:
```python
    # Land tax (annual, on unimproved land value at start of year).
    # Year 1 land value = purchase_price * LAND_VALUE_PCT (e.g. $420k for a house at $700k).
    land_value_path = start_of_year_values * LAND_VALUE_PCT[inputs.asset_type]
    land_tax_path = np.array([sa_land_tax(v) for v in land_value_path])
```
with:
```python
    # Land tax: flat user-supplied annual amount, constant across the horizon.
    # (Per-state land-tax tables are out of scope; this is editable in the UI, default 0.)
    land_tax_path = np.full(h, inputs.annual_land_tax)
```
Remove the now-unused `sa_land_tax` import at the top of the file (line ~21) and the `LAND_VALUE_PCT`/`land_value_path` line if `land_value_path` is unused elsewhere (grep first: `grep -n land_value_path model/property_strategy.py`).

- [ ] **Step 5: Thread `annual_land_tax` through `model/monte_carlo.py`.** Add a parameter `annual_land_tax: float = 0.0` to `run_monte_carlo`'s signature, and pass it into the `PropertyInputs(...)` construction (near line 153) as `annual_land_tax=annual_land_tax,`.

- [ ] **Step 6: Add the sidebar field and wire it in `app.py`.** In the "Your money" sidebar block add:
```python
annual_land_tax = st.sidebar.number_input(
    "Annual land tax ($)", min_value=0, value=qp("landtax", int, 0), step=500,
    help="Off by default. A real, tax-deductible annual cost (varies by state and land value). "
         "Leaving it 0 makes property look slightly cheaper than reality.",
)
```
Add `annual_land_tax=annual_land_tax,` to `run_kwargs` (line ~516) and `"landtax": annual_land_tax,` to the URL block (line 495).

- [ ] **Step 7: Delete `SA_LAND_TAX_BANDS` and `sa_land_tax`** from `model/tax.py` (lines 136–157).

- [ ] **Step 8: Run land-tax tests + full suite**

Run: `.venv/bin/python -m pytest tests/test_land_tax_flat.py -v && .venv/bin/python -m pytest -q`
Expected: PASS. (Update/delete any old test referencing `sa_land_tax` — `grep -rn sa_land_tax tests/`.)

- [ ] **Step 9: Commit**

```bash
git add model/ app.py tests/test_land_tax_flat.py
git commit -m "feat: flat editable land-tax field replaces SA-only land-tax schedule"
```

---

# PHASE B — Persona segmented control

## Task B1: Extract persona logic into `ui/persona.py`

**Files:**
- Create: `ui/__init__.py` (empty), `ui/persona.py`
- Modify: `app.py` (move `PERSONA_DEFS`, `compute_persona_sweep`, `find_optimal_mix`, `_persona_card_html`, `render_persona_cards`, `render_comparison_table` out; import them)

- [ ] **Step 1: Create `ui/__init__.py`** (empty file).

- [ ] **Step 2: Move the persona functions** (`app.py:164-263` region) verbatim into `ui/persona.py`, adding the imports they need at the top:
```python
import json
import numpy as np
import streamlit as st
from model.monte_carlo import run_monte_carlo
```
Keep `_render_html`, `_fmt_money`, `_fmt_pct`, `GLOBAL_CSS` usage by importing them — for this step, move `_render_html`/`_fmt_money`/`_fmt_pct`/`GLOBAL_CSS` into a small `ui/common.py` and import from there in both `app.py` and `ui/persona.py` (DRY). Create `ui/common.py` with those four helpers + the palette constants.

- [ ] **Step 3: Update `app.py` imports**:
```python
from ui.common import GLOBAL_CSS, _render_html, _fmt_money, _fmt_pct, _fmt_dollars
from ui.persona import (compute_persona_sweep, find_optimal_mix,
                        render_persona_cards, render_comparison_table)
```
Remove the moved definitions from `app.py`.

- [ ] **Step 4: Run full suite + boot app**

Run: `.venv/bin/python -m pytest -q` then boot on :8503 and `curl` for `200`.
Expected: PASS + 200. (Pure refactor — behaviour unchanged.)

- [ ] **Step 5: Commit**

```bash
git add ui/ app.py
git commit -m "refactor(ui): extract persona + common helpers into ui/ package"
```

## Task B2: Segmented control drives the breakdown; "Custom" enables the slider

**Files:**
- Test: `tests/test_persona_control.py`
- Modify: `app.py` (persona section ~585, breakdown mix source ~538, sidebar mix slider)

- [ ] **Step 1: Write an AppTest that selecting a persona sets the breakdown mix**

```python
# tests/test_persona_control.py
from streamlit.testing.v1 import AppTest

def _run():
    at = AppTest.from_file("app.py", default_timeout=60)
    at.run()
    return at

def test_segmented_control_exists_with_default_balanced():
    at = _run()
    seg = [s for s in at.get("segmented_control")]
    assert seg, "expected a segmented control for persona selection"
    assert seg[0].value in ("Balanced", "Balanced ★")

def test_custom_enables_slider():
    at = _run()
    seg = at.get("segmented_control")[0]
    seg.set_value("Custom").run()
    # The custom mix slider should be present/enabled when Custom is chosen.
    assert any("Custom mix" in (sl.label or "") for sl in at.get("slider"))
```

> Note: `at.get("segmented_control")` works for `st.segmented_control`. If the installed Streamlit exposes it under a different proxy key, fall back to `st.radio(horizontal=True)` and query `at.radio`. Confirm with `.venv/bin/python -c "import streamlit as st; print(hasattr(st,'segmented_control'))"` (expect `True` on ≥1.57).

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_persona_control.py -v`
Expected: FAIL — no segmented control yet.

- [ ] **Step 3: Add the segmented control under the persona cards** (replace the `recommended_mix` block ~585-587). After `render_persona_cards(...)`:
```python
balanced = find_optimal_mix(sweep_rows, 0.95)
PERSONA_TO_THRESHOLD = {"Safe": 0.99, "Balanced": 0.95, "Wealth Maximizer": 0.85}
options = ["Safe", "Balanced", "Wealth Maximizer", "Custom"]
label_map = {k: (k + " ★" if k == "Balanced" and not stale else k) for k in options}

picked = st.segmented_control(
    "View breakdown for", options, format_func=lambda k: label_map[k],
    default=qp("persona", str, "Balanced"), key="persona_pick",
)
if picked is None:
    picked = "Balanced"

if picked == "Custom":
    breakdown_mix_pct = property_share_mix_pct  # from the sidebar Custom slider
else:
    row = find_optimal_mix(sweep_rows, PERSONA_TO_THRESHOLD[picked])
    breakdown_mix_pct = row["mix_pct"] if row else (balanced["mix_pct"] if balanced else 50)
recommended_mix = breakdown_mix_pct
```

- [ ] **Step 4: Make the breakdown use `breakdown_mix_pct`.** The main run at line 538 currently uses `property_share_mix` (derived from the sidebar slider). Change the breakdown/headline run to use the picked mix:
```python
breakdown_mix = breakdown_mix_pct / 100
result = cached_run(trials=5000, property_share_mix=breakdown_mix, **run_kwargs)
```
Move the `result = cached_run(...)` call to AFTER the persona control so `breakdown_mix` is defined (the headline/tiles/breakdown all consume `result`). The persona sweep (2,000 trials) still runs before, independently.

- [ ] **Step 5: Reframe the sidebar mix slider as "Custom mix (advanced)" and disable unless Custom.** Where `property_share_mix_pct` is defined in the sidebar:
```python
_custom = st.session_state.get("persona_pick") == "Custom"
property_share_mix_pct = st.sidebar.slider(
    "Custom mix (% property)", 0, 100, qp("mix", int, 50), step=10,
    disabled=not _custom,
    help="Enabled when you pick ‘Custom’ above. Otherwise the chosen persona sets the mix.",
)
property_share_mix = property_share_mix_pct / 100
```

- [ ] **Step 6: Run persona tests + full suite + visual check**

Run: `.venv/bin/python -m pytest tests/test_persona_control.py -q && .venv/bin/python -m pytest -q`
Expected: PASS. Then boot :8503, screenshot, confirm picking each persona changes the headline mix.

- [ ] **Step 7: Commit**

```bash
git add app.py tests/test_persona_control.py
git commit -m "feat(persona): segmented control drives breakdown; Custom enables slider"
```

## Task B3: URL `persona` param + stale-sweep ★ suppression

**Files:**
- Modify: `app.py` (URL block ~495; the `stale` handling already feeds `label_map`)

- [ ] **Step 1: Replace `mix` with `persona` in the URL persistence block.** In the `st.query_params.update({...})` dict, remove `"mix": property_share_mix_pct,` and add:
```python
    "persona": st.session_state.get("persona_pick", "Balanced"),
```
Keep `mix` ONLY when Custom is active, so a shared Custom link reproduces the slider:
```python
    **({"mix": property_share_mix_pct} if st.session_state.get("persona_pick") == "Custom" else {}),
```

- [ ] **Step 2: Verify stale suppression already wired.** Confirm `label_map` uses `not stale` so the ★ disappears when inputs changed without a sweep rerun (added in B2 Step 3). Add a guard so a stale sweep disables non-Custom personas:
```python
picked = st.segmented_control(
    "View breakdown for", options, format_func=lambda k: label_map[k],
    default=qp("persona", str, "Balanced"), key="persona_pick",
    disabled=stale,  # can't act on stale recommendations; Custom still reachable via slider
)
```
(If `disabled=stale` blocks Custom too, instead render a one-line `st.caption("Recommendations stale — click ↻ Update.")` when `stale` and leave the control enabled. Pick whichever the AppTest in Step 3 confirms.)

- [ ] **Step 3: Add an AppTest for the URL param mapping**

```python
# tests/test_persona_control.py  (append)
def test_persona_url_param_selects_wealth():
    at = AppTest.from_file("app.py", default_timeout=60)
    at.query_params["persona"] = "Wealth Maximizer"
    at.run()
    seg = at.get("segmented_control")[0]
    assert seg.value == "Wealth Maximizer"
```

- [ ] **Step 4: Run + commit**

Run: `.venv/bin/python -m pytest tests/test_persona_control.py -q`
Expected: PASS
```bash
git add app.py tests/test_persona_control.py
git commit -m "feat(persona): persona URL param + stale-sweep star suppression"
```

---

# PHASE C — Onboarding

## Task C1: `ui/onboarding.py` — hero, slim banner, callout, guide

**Files:**
- Create: `ui/onboarding.py`
- Modify: `app.py` (replace the existing hero ~365-370; place callout after persona section; replace bottom "Setup & tax rules" expander)

- [ ] **Step 1: Create `ui/onboarding.py`** with four render functions (reuse `ui/common._render_html` + `GLOBAL_CSS`, plus the slim-banner/limits/step CSS from `mock_hero.py`):

```python
"""Onboarding: hero, slim how-to banner, limitations callout, full guide.
Render functions are pure Streamlit; no model logic."""
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
            '<div class="grow">SA→national stamp duty (FY2025-26); income tax FY2026 brackets · '
            '<b>Tax uses your current marginal rate held flat for the whole period — no bracket creep, Medicare '
            'levy, per-year income changes, or a rental loss dropping you a bracket. Your marginal rate drives '
            'negative gearing, CGT (both sides) and dividend/franking tax.</b> · land tax = your flat input (0 = '
            'excluded) · single property · 5,000 trials · Budget 2026-27 announcement-only. '
            '<b>Not financial advice.</b></div>')
```

- [ ] **Step 2: Wire into `app.py`.** Replace the existing hero markdown (~365-370) with `from ui.onboarding import render_hero, render_limitations, render_full_guide` (top) and `render_hero()` at that spot. Call `render_limitations()` immediately AFTER the persona "What now?" blurb (after line ~595, before `st.markdown("---")`). Replace the bottom "Setup & tax rules used" expander with `render_full_guide()`.

- [ ] **Step 3: Boot + visual check**

Run: boot :8503, screenshot. Confirm: one hero (not two), slim banner, amber callout below the cards, guide expander at bottom with the flat-MTR + land-tax assumptions.

- [ ] **Step 4: Run full suite + commit**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS
```bash
git add ui/onboarding.py app.py
git commit -m "feat(onboarding): hero, slim how-to, limitations callout, full guide"
```

---

# PHASE D — Bugs + cleanup

## Task D1: `$` LaTeX audit, disclaimer, CSS, mock cleanup

**Files:**
- Modify: `app.py` (every `st.markdown`/`_render_html` containing `$`; disclaimer ~722; CSS injection)
- Delete: `mock_hero.py`

- [ ] **Step 1: Find every dollar-sign risk**

Run: `grep -n '\$' app.py ui/*.py | grep -iv 'http'`
Inspect each `st.markdown`/`_render_html` string. Dollar amounts produced by `_fmt_money()` (e.g. `"$700k"`) and f-strings like `${income:,}` render as LaTeX between two `$`.

- [ ] **Step 2: Fix by wrapping dollar values in a span** (the app already uses `unsafe_allow_html=True`). For the assumptions/upfront line near 698, wrap interpolations:
```python
f'<span>{_fmt_money(stamp_duty_amount)}</span>'
```
For any plain-text dollar that is NOT in an HTML context, escape the literal `$` as `\\$` or route through `st.write`. Concretely, the known offender (upfront cash line) becomes a single HTML `_render_html(...)` string with each `$` inside a `<span>` so no two bare `$` bracket text.

- [ ] **Step 3: Update the disclaimer** (~line 722) — change `South Australia tax tables only; single property; ...` to:
```
Stamp duty is state-specific (selected above); income tax, CGT and negative gearing are federal. Single property; land tax is your flat input; some costs (rates/insurance, margin-call risk) are simplified. Budget 2026-27 rules are announcement-only and not yet legislated.
```

- [ ] **Step 4: Inject `GLOBAL_CSS` once.** Ensure `_render_html(GLOBAL_CSS)` (or a single `st.markdown(GLOBAL_CSS, ...)`) runs once at page top; remove `GLOBAL_CSS +` prefixes from per-component calls in `ui/persona.py` and the `render_*` onboarding functions (keep the component-specific CSS).

- [ ] **Step 5: Delete the disposable mock**

```bash
rm mock_hero.py
```

- [ ] **Step 6: Visual smoke check — no stray italics**

Boot :8503, open the guide + assumptions, screenshot, confirm all dollar amounts render upright (no italic LaTeX).

- [ ] **Step 7: Full suite + commit**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS (123 + new tests)
```bash
git add app.py ui/ && git rm mock_hero.py
git commit -m "fix(app): $ LaTeX audit, national disclaimer, single CSS inject, drop mock"
```

---

## Final verification

- [ ] Full suite green: `.venv/bin/python -m pytest -q`
- [ ] App boots and renders: hero (single), slim banner, persona segmented control switches the breakdown, amber callout below cards, guide expander with flat-MTR + land-tax assumptions, state selector changes stamp duty, land-tax field changes property cost.
- [ ] `grep -rn 'sa_stamp_duty\|sa_land_tax' .` returns nothing (dead code gone).
- [ ] Shareable URL round-trips `state`, `persona`, and `landtax`.
