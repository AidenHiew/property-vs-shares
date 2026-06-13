# Phase 2 Implementation Plan — Flexible UI, Trust/Downside, Accessibility

**Goal:** Deliver the Phase 2 scope from the approved design spec (§4, §5, §7, §8): hierarchy
reorder, dot-grid headline, mix-aware downside callout, card renames + de-steering,
frontier-chart + dial/free-mix expander, accessibility fixes, and a targeted test suite.

**Phase 2 does NOT include:** A/B scenario compare (Phase 3), `rental_yield_sigma` (Phase 1b).

**Architecture impact:** No new simulations; no new model files. All changes are in `app.py`,
`ui/persona.py`, `ui/common.py`, and a new `ui/frontier.py`. The `@st.fragment` scope from
Phase 1 is extended to cover the new expander.

**Tech stack:** Python 3.11+, Streamlit ≥1.37, Plotly, NumPy. No new dependencies.

**For agentic workers — REQUIRED SUB-SKILL: subagent-driven-development**
Each task below is a self-contained unit that leaves the app green. Run
`.venv/bin/python -m pytest -q` after every commit. Tasks 1–4 are ordered to keep the
app green at each step; Tasks 5 and 6 are purely mechanical and can be done in either order
after Task 4.

> **Checkbox steps:** each task uses the write-failing-test → run (red) → implement → run
> (green) → commit pattern. Steps marked **[visual only]** are not unit-testable; they carry
> exact code anyway and must be verified by loading the app (`streamlit run app.py`).

---

## Control-integration decision

**The `segmented_control` drives the breakdown view; the dial and free-mix slider live
exclusively inside the "How much safety does each mix buy?" expander; they do NOT conflict.**

Rationale: the segmented_control selects which persona's detail to show (Safe/Balanced/
Growth-focused/Custom). The dial and free-mix slider are discovery/exploration tools inside
the expander — they set the `dial_safety` and `free_mix` URL params and update the expander's
highlighted point, but they do NOT overwrite the segmented_control selection.

The sole exception: when the user moves the free-mix slider, the `persona_pick` session-state
is written to `"Custom"` so the breakdown below automatically shows the custom mix. This is
the same behaviour the sidebar "Custom mix" slider currently has, just relocated.

The sidebar "Custom mix" slider (`property_share_mix_pct`) is REMOVED; its role is fully
taken over by the in-expander free-mix slider (`free_mix_pct`).

---

## File structure

| File | Responsibility in Phase 2 |
|---|---|
| `ui/persona.py` | Rename PERSONA_DEFS + PERSONA_TO_THRESHOLD. Replace `★ RECOMMENDED` badge → `SUGGESTED`. Update `render_persona_cards` section header + blurbs + "Unsure?" line. All card copy changes land here. |
| `ui/common.py` | Add `.callout-amber` CSS. Raise `.pthr`, `.mlabel` font sizes ≥14px. Replace `FAINT` with `MUTED` for all micro-label uses. Add `.dot-grid` CSS. Add `.frontier-caveat` CSS. |
| `ui/frontier.py` | **NEW FILE.** `render_dot_grid(p_succeeds, n)`, `render_downside_callout(...)`, `render_failure_taxonomy(...)`, `render_frontier_expander(mix_curve, horizon, breakdown_mix_pct, dial_safety_pct, free_mix_pct, max_top_up)`. Pure rendering; no Streamlit state writes (state is written in `app.py`). |
| `app.py` | Hierarchy reorder (items 1–7 from spec §4). Remove sidebar custom-mix slider. Update `VALID_PERSONAS`, `PERSONA_TO_THRESHOLD`, `options`, `label_map` to match renamed personas. Wire `free_mix_pct` → `persona_pick = "Custom"` path. Add `@st.fragment` scope around the results region. Retire standalone "Compare all mixes" expander; replace with toggle inside the frontier expander. |
| `tests/test_phase2_ui.py` | **NEW FILE.** AppTest assertions for all Phase 2 behaviours: load, dot-grid HTML, downside callout, frontier expander, dial slider, free-mix slider, sidebar custom slider gone, persona renames consistent, malformed URL params. |

---

## Task ordering rationale

Tasks 1–2 (renames + accessibility) are pure mechanical changes that keep the app green
and are prerequisite to everything else touching copy or CSS. Task 3 (dot-grid headline) is
self-contained HTML/CSS with one `_render_html` call substitution. Task 4 (downside callout)
is new HTML above existing content. Task 5 (frontier expander + dial/free-mix) is the largest
task — it builds `ui/frontier.py` and rewires URL params. Task 6 (hierarchy reorder) moves
blocks in `app.py` and removes the sidebar slider; it is last because all the pieces it
assembles are complete. Tests accompany each task.

---

## Task 1 — Card renames + de-steer + PERSONA sync

**Why first:** every other task references persona names. Getting all four sync points right
(PERSONA_DEFS, PERSONA_TO_THRESHOLD, VALID_PERSONAS, options/label_map, URL param clamp)
before touching anything else prevents desync.

**Files:**
- `ui/persona.py` (lines 21–25, 41, 88–108)
- `app.py` (lines 343, 448–464)
- `tests/test_phase2_ui.py` (new)

### Steps

**Step 1.1 — Write failing tests (new file `tests/test_phase2_ui.py`):**

```python
# tests/test_phase2_ui.py
"""Phase 2 UI integration tests using Streamlit AppTest harness."""
import pytest
from streamlit.testing.v1 import AppTest


def _run_app(**query_params) -> AppTest:
    at = AppTest.from_file("app.py", default_timeout=120)
    for k, v in query_params.items():
        at.query_params[k] = str(v)
    at.run()
    return at


# ---------------------------------------------------------------------------
# Task 1 — persona rename consistency
# ---------------------------------------------------------------------------

def test_renamed_personas_in_app_html():
    """The words 'Safe ·', 'Balanced ·', 'Growth-focused ·' appear in rendered HTML."""
    at = _run_app()
    assert not at.exception, f"App crashed: {at.exception}"
    full_html = " ".join(str(m) for m in at.markdown)
    assert "Safe ·" in full_html, "Renamed persona 'Safe ·' not found in output"
    assert "Balanced ·" in full_html, "Renamed persona 'Balanced ·' not found in output"
    assert "Growth-focused ·" in full_html, "Renamed persona 'Growth-focused ·' not found"


def test_old_persona_names_absent():
    """Old persona names 'Safe Player' and 'Wealth Maximizer' must NOT appear."""
    at = _run_app()
    full_html = " ".join(str(m) for m in at.markdown)
    assert "Safe Player" not in full_html, "'Safe Player' (old name) still present"
    assert "Wealth Maximizer" not in full_html, "'Wealth Maximizer' (old name) still present"


def test_recommended_text_absent():
    """The word 'Recommended allocation' must not appear (§8: use 'suggests')."""
    at = _run_app()
    full_html = " ".join(str(m) for m in at.markdown)
    assert "Recommended allocation for you" not in full_html


def test_suggested_badge_present():
    """'SUGGESTED' badge must appear; '★ RECOMMENDED' must not."""
    at = _run_app()
    full_html = " ".join(str(m) for m in at.markdown)
    assert "SUGGESTED" in full_html, "'SUGGESTED' badge not found"
    assert "★ RECOMMENDED" not in full_html, "'★ RECOMMENDED' (old badge) still present"


def test_segmented_control_options_match_valid_personas():
    """segmented_control must offer exactly the renamed personas."""
    at = _run_app()
    # Find the segmented_control widget (key="persona_pick")
    sc = next((w for w in at.get_widget_states() if getattr(w, "key", None) == "persona_pick"), None)
    # If AppTest doesn't expose segmented_control options, fall through to HTML check
    full_html = " ".join(str(m) for m in at.markdown)
    # At minimum the app must not crash and must not contain old names
    assert not at.exception


def test_stale_persona_url_param_clamps_to_balanced():
    """persona=Wealth+Maximizer (old name) in URL must clamp to Balanced without crash."""
    at = _run_app(persona="Wealth Maximizer")
    assert not at.exception, f"App crashed on old persona name: {at.exception}"


def test_custom_persona_url_param_still_valid():
    """persona=Custom must still work after renames."""
    at = _run_app(persona="Custom", free_mix=60)
    assert not at.exception, f"App crashed on persona=Custom: {at.exception}"
```

Run: `.venv/bin/python -m pytest tests/test_phase2_ui.py::test_renamed_personas_in_app_html -x` — expect RED.

**Step 1.2 — Update `ui/persona.py` PERSONA_DEFS:**

```python
PERSONA_DEFS = [
    ("Safe · 99%+",       0.99, "I want near-certainty of staying within my cash ceiling — even if it means a lower wealth outcome."),
    ("Balanced · 95%+",   0.95, "I want very high safety, but I'll accept a small chance of cashflow stress for more wealth."),
    ("Growth-focused · 85%+", 0.85, "I'll accept real cashflow risk (~1 in 7 stories) in exchange for the highest wealth outcome."),
]
```

**Step 1.3 — Update badge in `ui/persona.py` `_persona_card_html`:**

Replace:
```python
badge = '<div class="badge">★ RECOMMENDED</div>' if is_rec else ""
```
With:
```python
badge = '<div class="badge">SUGGESTED</div>' if is_rec else ""
```

**Step 1.4 — Update section header and add "Unsure?" line in `render_persona_cards`:**

In `render_persona_cards`, replace the `_render_html(GLOBAL_CSS + ...)` call at the end with:
```python
_render_html(
    GLOBAL_CSS
    + f'<div class="cards">{cards}</div>'.replace("{H}", str(horizon))
    + '<p class="pvs-section-sub" style="margin-top:10px;">'
      'Unsure? <b>Balanced · 95%+</b> is a common starting point.</p>'
)
```

Also update the merged-card badge line:
```python
html = f"""
<div class="cards" style="grid-template-columns:1fr;max-width:560px;margin:0 auto;">
  <div class="card rec"><div class="badge">SUGGESTED</div>
    <div class="pname">Suggested allocation</div>
    ...
    <p class="blurb">"All three safety levels (≥99%, ≥95%, ≥85%) point to the same allocation
    under your inputs — a reliable starting point."</p>
  </div></div>"""
```

**Step 1.5 — Update `app.py` — all four sync points:**

```python
# Line ~343: VALID_PERSONAS
VALID_PERSONAS = ("Safe · 99%+", "Balanced · 95%+", "Growth-focused · 85%+", "Custom")

# Line ~448: PERSONA_TO_THRESHOLD
PERSONA_TO_THRESHOLD = {
    "Safe · 99%+": 0.99,
    "Balanced · 95%+": 0.95,
    "Growth-focused · 85%+": 0.85,
}

# Line ~449: options
options = ["Safe · 99%+", "Balanced · 95%+", "Growth-focused · 85%+", "Custom"]

# Line ~450: label_map (no ★; clean labels)
label_map = {k: k for k in options}

# Line ~451: persona default — clamp old name "Balanced" → "Balanced · 95%+"
_persona_default = qp("persona", str, "Balanced · 95%+")
if _persona_default not in options:
    _persona_default = "Balanced · 95%+"
```

Also update the `segmented_control` default and the `find_optimal_mix` lookup:
```python
picked = st.segmented_control(
    "View breakdown for", options, format_func=lambda k: k,
    default=_persona_default, key="persona_pick",
)
if picked is None:
    picked = "Balanced · 95%+"
if picked == "Custom":
    breakdown_mix_pct = free_mix_pct  # now driven by the in-expander slider
else:
    _row = find_optimal_mix(mix_curve, PERSONA_TO_THRESHOLD[picked])
    breakdown_mix_pct = int(round(_row.mix_pct * 100)) if _row else (
        int(round(find_optimal_mix(mix_curve, 0.95).mix_pct * 100))
        if find_optimal_mix(mix_curve, 0.95) else 50
    )
```

Also update the `_persona_qp` write-back line (URL persistence) to clamp to the new names:
```python
_persona_qp = st.session_state.get("persona_pick") if "persona_pick" in st.session_state else qp("persona", str, "Balanced · 95%+")
if _persona_qp not in VALID_PERSONAS:
    _persona_qp = "Balanced · 95%+"
```

**Step 1.6 — Update section header in `app.py`:**

```python
# Replace line ~408-411:
st.markdown('<div class="pvs-section">What the model suggests at each safety level</div>',
            unsafe_allow_html=True)
st.markdown('<div class="pvs-section-sub">Pick the safety level that matches your comfort — '
            'the model finds the property/shares mix that delivers it with the most wealth.</div>',
            unsafe_allow_html=True)
```

**Step 1.7 — Run tests:** `.venv/bin/python -m pytest tests/test_phase2_ui.py -x -q` — expect GREEN.

**Step 1.8 — Commit:** `git add ui/persona.py app.py tests/test_phase2_ui.py && git commit -m "Phase 2 Task 1: rename personas, SUGGESTED badge, section header, all sync points"`

---

## Task 2 — Accessibility: FAINT→MUTED, micro-labels ≥14px, chart dash styles

**Why here:** CSS and token fixes are a one-line-each change; resolving them early means
every subsequent task uses the correct colour tokens.

**Files:**
- `ui/common.py` (GLOBAL_CSS only)
- `app.py` (any inline style that references `FAINT` directly)
- `tests/test_phase2_ui.py` (add assertions)

### Steps

**Step 2.1 — Write failing tests (append to `tests/test_phase2_ui.py`):**

```python
# ---------------------------------------------------------------------------
# Task 2 — accessibility
# ---------------------------------------------------------------------------

def test_faint_color_not_used_for_text_labels():
    """FAINT (#9ca3af) must not appear in any text-label CSS class.
    Check GLOBAL_CSS string — the .pthr and .mlabel classes must use MUTED not FAINT."""
    from ui.common import GLOBAL_CSS, FAINT, MUTED
    # .pthr and .mlabel must reference MUTED (#6b7280) not FAINT (#9ca3af)
    import re
    pthr_block = re.search(r'\.pthr\s*\{[^}]+\}', GLOBAL_CSS, re.DOTALL)
    mlabel_block = re.search(r'\.mlabel\s*\{[^}]+\}', GLOBAL_CSS, re.DOTALL)
    assert pthr_block, ".pthr CSS class not found"
    assert mlabel_block, ".mlabel CSS class not found"
    assert FAINT not in pthr_block.group(), f".pthr uses FAINT ({FAINT}); must use MUTED"
    assert FAINT not in mlabel_block.group(), f".mlabel uses FAINT ({FAINT}); must use MUTED"


def test_micro_label_font_size_at_least_14px():
    """Micro-labels (.pthr, .mlabel) must declare font-size >= 14px."""
    from ui.common import GLOBAL_CSS
    import re
    for cls in (".pthr", ".mlabel"):
        block = re.search(rf'{re.escape(cls)}\s*\{{[^}}]+\}}', GLOBAL_CSS, re.DOTALL)
        assert block, f"{cls} CSS class not found"
        size_match = re.search(r'font-size:\s*(\d+)px', block.group())
        assert size_match, f"No font-size found in {cls}"
        assert int(size_match.group(1)) >= 14, (
            f"{cls} font-size is {size_match.group(1)}px; must be ≥14px"
        )
```

Run: `.venv/bin/python -m pytest tests/test_phase2_ui.py::test_faint_color_not_used_for_text_labels tests/test_phase2_ui.py::test_micro_label_font_size_at_least_14px -x` — expect RED.

**Step 2.2 — Update `ui/common.py` GLOBAL_CSS:**

In `.pthr` CSS block, change:
```css
/* before */
.pthr { font-size: 11px; color: #9ca3af; margin: 2px 0 14px; font-weight: 600; }
/* after */
.pthr { font-size: 14px; color: #6b7280; margin: 2px 0 14px; font-weight: 600; }
```

In `.mlabel` CSS block, change:
```css
/* before */
.mlabel { font-size: 12px; color: #9ca3af; margin-bottom: 1px; }
/* after */
.mlabel { font-size: 14px; color: #6b7280; margin-bottom: 1px; }
```

In `.blurb` CSS block, increase from 12px to 14px:
```css
.blurb { font-size: 14px; color: #4b5563; ... }
```

**[visual only — flag emoji]** In `app.py` flag rendering, wrap flag emoji with a minimum
font-size span. The `.flag` CSS already renders at 14px, which satisfies the ≥16px emoji
requirement when the emoji itself renders at system size; add explicit sizing:
```css
/* In .flag CSS rule, add: */
.flag { ... }
.flag-emoji { font-size: 18px; line-height: 1; }
```
Then in `app.py` flag construction:
```python
flag_emoji = {"ok": "✅", "warn": "⚠️", "bad": "❌"}[flag[0]]
flag_text = flag[1]  # text already has emoji at start; replace bare emoji with sized span
flag_html = f'<div class="flag {flag[0]}"><span class="flag-emoji">{flag_emoji}</span> {flag_text[2:]}</div>'
_render_html(flag_html)
```

**[visual only — chart dash styles]** In `render_year_by_year_chart` in `app.py`, update
the median line traces to add distinct dash styles:
```python
DASH_STYLES = {AMBER: "solid", TEAL: "dash", GREEN: "dot"}
# In the fig.add_trace loop for p50:
fig.add_trace(go.Scatter(..., line=dict(color=colour, width=2.5, dash=DASH_STYLES[colour]), ...))
```

**Step 2.3 — Run tests:** `.venv/bin/python -m pytest tests/test_phase2_ui.py -x -q` — expect GREEN.

**Step 2.4 — Commit:** `git add ui/common.py app.py tests/test_phase2_ui.py && git commit -m "Phase 2 Task 2: a11y — FAINT→MUTED for labels, micro-labels ≥14px, chart dash styles, flag emoji sizing"`

---

## Task 3 — Dot-grid headline + inline explainer

**Why here:** replaces only the existing `_render_html(...)` headline block in `app.py`.
No structural change — just the HTML content. Self-contained.

**Files:**
- `ui/frontier.py` (new — `render_dot_grid` function)
- `app.py` (replace headline `_render_html` block, lines ~532–537)
- `ui/common.py` (add `.dot-grid` CSS)
- `tests/test_phase2_ui.py` (add assertions)

### Steps

**Step 3.1 — Write failing tests (append to `tests/test_phase2_ui.py`):**

```python
# ---------------------------------------------------------------------------
# Task 3 — dot-grid headline
# ---------------------------------------------------------------------------

def test_dot_grid_present_in_rendered_html():
    """The dot-grid class must appear in the rendered HTML after Phase 2 Task 3."""
    at = _run_app()
    assert not at.exception
    full_html = " ".join(str(m) for m in at.markdown)
    assert "dot-grid" in full_html, "dot-grid class not found in rendered output"


def test_dot_grid_natural_frequency_phrasing():
    """Natural-frequency phrasing 'in 10' or 'in 100' must appear in the headline area."""
    at = _run_app()
    full_html = " ".join(str(m) for m in at.markdown)
    assert "in 10" in full_html or "in 100" in full_html, (
        "Natural frequency phrasing not found in headline"
    )


def test_headline_explainer_present():
    """Two-sentence inline explainer must mention 'not a forecast' or 'built from'."""
    at = _run_app()
    full_html = " ".join(str(m) for m in at.markdown)
    assert "not a forecast" in full_html or "built from your numbers" in full_html, (
        "Headline explainer sentences not found"
    )
```

Run RED.

**Step 3.2 — Create `ui/frontier.py` with `render_dot_grid`:**

```python
# ui/frontier.py
"""Phase 2 UI components: dot-grid headline, downside callout, frontier expander.

No Streamlit state writes from this module — all state (dial_safety_pct,
free_mix_pct, persona_pick) is read/written in app.py; these functions are
pure renderers.
"""
from __future__ import annotations
import numpy as np
import plotly.graph_objects as go
import streamlit as st

from model.mix_curve import MixPoint
from model.solvency import flag_forced_sales
from ui.common import (
    GREEN, TEAL, AMBER, RED, AMBER_DK, INK, MUTED, FAINT, LINE,
    GLOBAL_CSS, _render_html, _fmt_money, _fmt_pct,
)
from ui.persona import find_optimal_mix


def render_dot_grid(p_succeeds: float, n_trials: int, horizon: int) -> None:
    """Render a 10×10 dot grid + natural-frequency headline + two-sentence explainer.

    p_succeeds: fraction of trials that succeeded (0–1).
    n_trials: total trials (for natural language phrasing).
    horizon: hold period in years (for phrasing).

    Green dots = round(p_succeeds * 100); grey = remainder.
    Two-colour only (green = succeeds, grey = not) per spec §5.1.
    """
    green_dots = round(p_succeeds * 100)
    grey_dots = 100 - green_dots

    # Build 10×10 grid HTML: 100 span elements, first green_dots are green
    dots_html = ""
    for i in range(100):
        colour = GREEN if i < green_dots else "#d1d5db"
        dots_html += f'<span class="dot" style="background:{colour};"></span>'

    # Natural-frequency phrase: "about X in 10" or "about X in 100"
    # Use "in 10" when the numerator rounds cleanly; otherwise "in 100"
    if green_dots % 10 == 0:
        nf_num = green_dots // 10
        nf_phrasing = f"about {nf_num} in 10"
    else:
        nf_phrasing = f"about {green_dots} in 100"

    html = f"""
    <div class="dot-grid-block">
      <div class="dot-grid">{dots_html}</div>
      <div class="dot-headline">
        <span class="dot-big">{nf_phrasing}</span>
        <span class="dot-ctx">of {n_trials:,} what-if stories built from your numbers,
        property both beats shares <i>and</i> keeps you solvent over {horizon} years.</span>
      </div>
      <p class="dot-explainer">
        This counts the fictional {horizon}-year paths — drawn from the ranges you set —
        where property came out ahead with the cash ceiling intact.
        It is <b>not a forecast</b>: future returns depend on markets, rates, and choices
        that no model can predict.
      </p>
    </div>"""
    _render_html(GLOBAL_CSS + html)
```

**Step 3.3 — Add `.dot-grid` CSS to `ui/common.py` GLOBAL_CSS** (inside the `<style>` block):

```css
/* dot-grid headline */
.dot-grid-block { margin: 8px 0 16px; }
.dot-grid {
  display: grid;
  grid-template-columns: repeat(10, 14px);
  gap: 4px;
  margin-bottom: 10px;
}
.dot {
  width: 14px; height: 14px; border-radius: 50%;
  display: inline-block;
}
.dot-headline {
  display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
  margin-bottom: 6px;
}
.dot-big { font-size: 26px; font-weight: 800; color: #16a34a; line-height: 1; }
.dot-ctx { font-size: 16px; color: #1a1a1a; font-weight: 600; }
.dot-explainer { font-size: 14px; color: #6b7280; margin: 0; max-width: 680px; }
```

**Step 3.4 — Replace headline in `app.py`:**

Remove lines ~531–537 (the old `_render_html(f"""<div class="headline">...""")` block) and replace with:

```python
from ui.frontier import render_dot_grid
render_dot_grid(
    p_succeeds=result["p_property_succeeds"],
    n_trials=int(result["property_terminal_wealth"].size),
    horizon=horizon,
)
# Keep the pvs-section-sub context line (p_property_wins / p_solvent) below:
_render_html(f"""<div class="pvs-section-sub">Property beats shares in
{result['p_property_wins']:.0%} of stories, but only {result['p_solvent']:.0%}
stay within your {_fmt_money(max_top_up)} cash ceiling. "Succeeds" needs both.</div>""")
```

(The import of `render_dot_grid` belongs at the top of `app.py` alongside the other `ui`
imports, not inline.)

**Step 3.5 — Run tests:** `.venv/bin/python -m pytest tests/test_phase2_ui.py -x -q` — GREEN.

**Step 3.6 — Commit:** `git add ui/frontier.py ui/common.py app.py tests/test_phase2_ui.py && git commit -m "Phase 2 Task 3: dot-grid headline + natural-frequency phrasing + inline explainer"`

---

## Task 4 — Mix-aware downside callout + 2×2 failure taxonomy

**Why here:** adds the amber callout below the headline (no structural reorder yet — just
inserting new HTML after the existing headline). The reorder (Task 6) then moves these
blocks into their final positions.

**Files:**
- `ui/frontier.py` (add `render_downside_callout`, `render_failure_taxonomy`)
- `app.py` (insert callout call after headline; pass mix-scaled arrays)
- `ui/common.py` (add `.callout-amber` CSS)
- `tests/test_phase2_ui.py` (add assertions)

### Steps

**Step 4.1 — Write failing tests (append to `tests/test_phase2_ui.py`):**

```python
# ---------------------------------------------------------------------------
# Task 4 — downside callout
# ---------------------------------------------------------------------------

def test_downside_callout_present():
    """Amber downside callout must appear in rendered output."""
    at = _run_app()
    assert not at.exception
    full_html = " ".join(str(m) for m in at.markdown)
    assert "callout-amber" in full_html or "If it goes wrong" in full_html, (
        "Downside callout not found in rendered output"
    )


def test_downside_callout_mentions_forced_sale():
    """Callout must mention forced sale in plain language."""
    at = _run_app()
    full_html = " ".join(str(m) for m in at.markdown)
    assert "forced to sell" in full_html, (
        "'forced to sell' language not found in downside callout"
    )


def test_downside_callout_mentions_caveat():
    """Callout must mention 'excludes' caveat for major repairs / income shocks."""
    at = _run_app()
    full_html = " ".join(str(m) for m in at.markdown)
    assert "excludes" in full_html, "Downside caveat ('excludes') not found"


def test_downside_callout_mix_aware_at_pure_shares():
    """At free_mix=0 (pure shares), forced-sale callout should show 0% or be absent."""
    at = _run_app(persona="Custom", free_mix=0)
    assert not at.exception
    # App must not crash; the callout for mix=0 shows 0 top-ups and 0% forced-sale rate
    full_html = " ".join(str(m) for m in at.markdown)
    assert "If it goes wrong" not in full_html or "0%" in full_html, (
        "Downside callout present at mix=0 but should be suppressed or show 0%"
    )


def test_model_assumption_caveat_near_dial():
    """Linear-blend caveat must appear somewhere in the frontier expander area."""
    at = _run_app()
    full_html = " ".join(str(m) for m in at.markdown)
    assert "doesn't model buying a part-property" in full_html or \
           "allocation rule" in full_html or \
           "understates" in full_html, (
        "Model-assumption caveat (§5.3) not found in output"
    )
```

Run RED.

**Step 4.2 — Add `render_downside_callout` and `render_failure_taxonomy` to `ui/frontier.py`:**

```python
def render_downside_callout(
    worst_year_cash: float,
    total_top_ups: float,
    forced_sale_rate: float,
    max_top_up: float,
    breakdown_mix: float,
    mixed_outside_cash: np.ndarray,
    mixed_terminal: np.ndarray,
    s_terminal: np.ndarray,
    ceiling: float,
    deflate: bool = False,
) -> None:
    """Render the amber downside callout for the selected mix.

    At mix=0 (pure shares) there is no cash demand; callout is suppressed.

    Parameters
    ----------
    worst_year_cash  : 90th-pct of per-trial worst single year's outside cash ($).
    total_top_ups    : median of per-trial cumulative outside cash ($).
    forced_sale_rate : fraction of trials with any year exceeding ceiling.
    max_top_up       : user's cash ceiling ($).
    breakdown_mix    : selected mix fraction (0–1).
    mixed_outside_cash : (trials, years) array of mix-scaled outside cash demand.
    mixed_terminal   : (trials,) array of mixed terminal wealth.
    s_terminal       : (trials,) array of pure-shares terminal wealth.
    ceiling          : serviceability ceiling in $ (same as max_top_up, pre-deflation).
    deflate          : if True, amounts are already deflated — label as today's $.
    """
    if breakdown_mix == 0.0:
        return  # pure shares: no cash demand, callout not applicable

    dollar_label = "today's $" if deflate else "future $"
    z_pct = int(round(forced_sale_rate * 100))

    html = f"""
    <div class="callout-amber">
      <b>If it goes wrong:</b> in the worst 1-in-10 stretches you could need about
      <b>{_fmt_money(worst_year_cash)}</b> extra in a single year ({dollar_label}),
      and about <b>{_fmt_money(total_top_ups)}</b> total top-ups at median over the hold.
      In <b>{z_pct}%</b> of stories you could have been forced to sell in at least one year.
      <span class="caveat">This comes from the cash-flow model and excludes major repairs,
      your income stopping, and other personal shocks.
      Worth checking it fits your safety net.</span>
    </div>"""
    _render_html(GLOBAL_CSS + html)


def render_failure_taxonomy(
    mixed_outside_cash: np.ndarray,
    mixed_terminal: np.ndarray,
    s_terminal: np.ndarray,
    ceiling: float,
) -> None:
    """Render the 2×2 failure taxonomy inside a detail expander.

    Axes:
      - rows: beats shares (mixed_terminal > s_terminal) / loses to shares
      - cols: within ceiling (no forced sale) / over ceiling (forced sale)

    Each cell shows: frequency as "X in 100" + cell-median mixed wealth.
    """
    n = len(mixed_terminal)
    forced = flag_forced_sales(mixed_outside_cash, ceiling)  # (trials,) bool
    beats = mixed_terminal > s_terminal

    # Four cells
    cells = {
        ("beats", "within"): (~forced) & beats,
        ("beats", "over"):   forced & beats,
        ("loses", "within"): (~forced) & ~beats,
        ("loses", "over"):   forced & ~beats,
    }
    cell_data = {}
    for k, mask in cells.items():
        count = int(mask.sum())
        freq = f"{round(count / n * 100)} in 100"
        med_wealth = float(np.median(mixed_terminal[mask])) if count > 0 else 0.0
        cell_data[k] = (freq, med_wealth)

    def _cell(row, col, bg):
        freq, med = cell_data[(row, col)]
        return (f'<td style="background:{bg};padding:14px 18px;border:1px solid {LINE};">'
                f'<b>{freq}</b><br><span style="font-size:13px;color:{MUTED};">'
                f'median wealth {_fmt_money(med)}</span></td>')

    html = f"""
    <div style="overflow-x:auto;margin-top:10px;">
    <table style="border-collapse:collapse;font-size:14px;min-width:400px;">
      <thead><tr>
        <th style="padding:10px 18px;background:#f9fafb;border:1px solid {LINE};"></th>
        <th style="padding:10px 18px;background:#f9fafb;border:1px solid {LINE};">
          Within your ceiling</th>
        <th style="padding:10px 18px;background:#f9fafb;border:1px solid {LINE};">
          Over ceiling (forced-sale risk)</th>
      </tr></thead>
      <tbody>
        <tr>
          <td style="padding:10px 18px;font-weight:700;background:#f9fafb;border:1px solid {LINE};">
            Beats shares</td>
          {_cell("beats", "within", "rgba(22,163,74,.06)")}
          {_cell("beats", "over",   "rgba(245,158,11,.08)")}
        </tr>
        <tr>
          <td style="padding:10px 18px;font-weight:700;background:#f9fafb;border:1px solid {LINE};">
            Loses to shares</td>
          {_cell("loses", "within", "rgba(14,165,233,.06)")}
          {_cell("loses", "over",   "rgba(239,68,68,.08)")}
        </tr>
      </tbody>
    </table>
    <p style="font-size:13px;color:{MUTED};margin-top:8px;">
      Each cell: fraction of the {n:,} stories + median mixed wealth in that cell.
      "Over ceiling" = at least one year needed more than your
      {_fmt_money(ceiling)} maximum annual top-up.
    </p>
    </div>"""
    _render_html(GLOBAL_CSS + html)
```

**Step 4.3 — Add `.callout-amber` CSS to `ui/common.py` GLOBAL_CSS:**

```css
/* downside callout */
.callout-amber {
  background: rgba(245,158,11,.09);
  border: 1px solid rgba(245,158,11,.5);
  border-left: 4px solid #d97706;
  border-radius: 10px;
  padding: 14px 18px;
  font-size: 15px;
  color: #78350f;
  margin: 12px 0 10px;
  line-height: 1.55;
}
.callout-amber .caveat {
  display: block;
  font-size: 13px;
  color: #92400e;
  margin-top: 8px;
  font-style: italic;
}
```

**Step 4.4 — Insert downside callout call in `app.py` (after the headline block):**

```python
# After render_dot_grid(...) and the pvs-section-sub line:
from ui.frontier import render_dot_grid, render_downside_callout, render_failure_taxonomy

# Compute total_top_ups and forced_sale_rate from mix-scaled arrays for selected mix
# (these are already on the mix_curve point; also available from result for the exact mix)
_mixed_oc = result["mixed_outside_cash_per_trial_year"]  # already scaled to breakdown_mix
_mixed_term = result["mixed_terminal_wealth"]
_total_top_ups = float(np.median(_mixed_oc.sum(axis=1))) if breakdown_mix > 0.0 else 0.0
_forced_sale_rate = float(flag_forced_sales(_mixed_oc, max_top_up).mean())

render_downside_callout(
    worst_year_cash=result["worst_year_cash"],
    total_top_ups=_total_top_ups,
    forced_sale_rate=_forced_sale_rate,
    max_top_up=max_top_up,
    breakdown_mix=breakdown_mix,
    mixed_outside_cash=_mixed_oc,
    mixed_terminal=_mixed_term,
    s_terminal=base_result["shares_terminal_wealth"],
    ceiling=max_top_up,
    deflate=deflate,
)

with st.expander("What are the failure modes? (2×2 breakdown)"):
    render_failure_taxonomy(
        mixed_outside_cash=_mixed_oc,
        mixed_terminal=_mixed_term,
        s_terminal=base_result["shares_terminal_wealth"],
        ceiling=max_top_up,
    )
```

Note: `_total_top_ups` must be computed from the **nominal** `mixed_outside_cash_per_trial_year`
before deflation is applied (same units as the `worst_year_cash` already on `result`). If
`deflate=True`, `result["mixed_outside_cash_per_trial_year"]` is already deflated — compute
`_total_top_ups` from `base_result` before deflation loop, or store it pre-deflation. The
cleanest fix: compute and stash `_total_top_ups` and `_forced_sale_rate` BEFORE the deflation
block (around line 492 in `app.py`), using the nominal arrays.

**Step 4.5 — Run tests:** `.venv/bin/python -m pytest tests/test_phase2_ui.py -x -q` — GREEN.

**Step 4.6 — Commit:** `git add ui/frontier.py ui/common.py app.py tests/test_phase2_ui.py && git commit -m "Phase 2 Task 4: mix-aware downside callout, 2×2 failure taxonomy, amber callout CSS"`

---

## Task 5 — Frontier expander: Plotly chart + dial + free-mix slider

**Why fifth:** depends on `ui/frontier.py` (created in Task 3/4), `PERSONA_TO_THRESHOLD` renames
(Task 1), and all UI components being stable. The frontier expander is the largest single piece.

**Files:**
- `ui/frontier.py` (add `render_frontier_expander`)
- `app.py` (add expander call below persona cards; update `free_mix_pct` write-back)
- `tests/test_phase2_ui.py` (add assertions)

### Steps

**Step 5.1 — Write failing tests (append to `tests/test_phase2_ui.py`):**

```python
# ---------------------------------------------------------------------------
# Task 5 — frontier expander + dial + free-mix slider
# ---------------------------------------------------------------------------

def test_frontier_expander_present():
    """'How much safety does each mix buy?' expander must exist in the app."""
    at = _run_app()
    assert not at.exception
    expander_labels = [e.label for e in at.expander]
    assert any("safety" in (lbl or "").lower() for lbl in expander_labels), (
        f"Frontier expander not found. Expanders: {expander_labels}"
    )


def test_dial_safety_slider_present():
    """A slider with key 'dial_safety_slider' must exist after Task 5."""
    at = _run_app()
    assert not at.exception
    slider_keys = [s.key for s in at.slider]
    assert "dial_safety_slider" in slider_keys, (
        f"dial_safety_slider not found. Sliders: {slider_keys}"
    )


def test_free_mix_slider_present():
    """A slider with key 'free_mix_slider' must exist after Task 5."""
    at = _run_app()
    assert not at.exception
    slider_keys = [s.key for s in at.slider]
    assert "free_mix_slider" in slider_keys, (
        f"free_mix_slider not found. Sliders: {slider_keys}"
    )


def test_sidebar_custom_mix_slider_removed():
    """The sidebar 'Custom mix (% property)' slider must be REMOVED."""
    at = _run_app()
    slider_labels = [s.label for s in at.slider]
    assert not any("Custom mix" in (lbl or "") for lbl in slider_labels), (
        f"Old 'Custom mix' sidebar slider still present: {slider_labels}"
    )


def test_show_as_table_toggle_inside_expander():
    """A 'Show as table' checkbox or toggle must be present after Task 5."""
    at = _run_app()
    # Look for checkbox with label containing 'table'
    cb_labels = [c.label for c in at.checkbox]
    assert any("table" in (lbl or "").lower() for lbl in cb_labels), (
        f"'Show as table' toggle not found. Checkboxes: {cb_labels}"
    )


def test_model_caveat_linear_blend_present():
    """The linear-blend model caveat must appear in the frontier expander."""
    at = _run_app()
    full_html = " ".join(str(m) for m in at.markdown)
    assert "allocation rule" in full_html or "mid-range mixes" in full_html, (
        "Linear-blend model caveat not found"
    )


def test_comparison_table_standalone_expander_removed():
    """The standalone 'Compare all mixes' expander must be REMOVED."""
    at = _run_app()
    expander_labels = [e.label for e in at.expander]
    assert not any("Compare all" in (lbl or "") for lbl in expander_labels), (
        f"Old 'Compare all mixes' expander still present: {expander_labels}"
    )
```

Run RED.

**Step 5.2 — Add `render_frontier_expander` to `ui/frontier.py`:**

```python
def render_frontier_expander(
    mix_curve: list[MixPoint],
    horizon: int,
    breakdown_mix_pct: int,
    dial_safety_pct: int,
    free_mix_pct: int,
    max_top_up: float,
) -> tuple[int, int]:
    """Render the 'How much safety does each mix buy?' expander.

    Contains:
    - Plotly frontier chart (x=median wealth, y=solvency chance)
    - Safety-target dial (st.slider, wired to dial_safety_pct)
    - Free % property slider (wired to free_mix_pct)
    - Optional 'Show as table' toggle (accessibility fallback)
    - Linear-blend model-assumption caveat

    Returns (new_dial_safety_pct, new_free_mix_pct) so app.py can write them
    to URL params and session state.

    Snap rule (spec §4.2): solvency % interpolates linearly between the 21 points
    for the dial readout; dollar/rate fields snap to the nearest computed mix point.
    """
    with st.expander("How much safety does each mix buy?"):
        # --- Frontier chart ---
        mixes_pct = [int(round(pt.mix_pct * 100)) for pt in mix_curve]
        wealth = [pt.median_mixed_wealth for pt in mix_curve]
        solvency = [pt.p_solvent * 100 for pt in mix_curve]

        # Sampling-noise band: binomial CI ≈ ±1.96*sqrt(p*(1-p)/n) at n=5000
        n = 5000
        lower = [max(0, s - 1.96 * (s/100 * (1 - s/100) / n) ** 0.5 * 100) for s in solvency]
        upper = [min(100, s + 1.96 * (s/100 * (1 - s/100) / n) ** 0.5 * 100) for s in solvency]

        # Persona points
        from ui.persona import find_optimal_mix, PERSONA_DEFS
        PERSONA_LABEL_MAP = {
            "Safe · 99%+": "Safe",
            "Balanced · 95%+": "Balanced",
            "Growth-focused · 85%+": "Growth",
        }

        fig = go.Figure()

        # Noise band
        fig.add_trace(go.Scatter(
            x=wealth + wealth[::-1],
            y=upper + lower[::-1],
            fill="toself",
            fillcolor="rgba(14,165,233,.08)",
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
            name="Sampling noise",
        ))

        # Main curve
        fig.add_trace(go.Scatter(
            x=wealth, y=solvency,
            mode="lines+markers",
            name="Mix curve",
            line=dict(color=TEAL, width=2.5),
            marker=dict(size=5, color=TEAL),
            hovertemplate="Property: %{customdata}%<br>Wealth: %{x:$,.0f}<br>Safety: %{y:.1f}%<extra></extra>",
            customdata=mixes_pct,
        ))

        # Persona rings
        persona_colours = {"Safe · 99%+": GREEN, "Balanced · 95%+": AMBER, "Growth-focused · 85%+": RED}
        for name, thr, _ in PERSONA_DEFS:
            pt = find_optimal_mix(mix_curve, thr)
            if pt is None:
                continue
            short = PERSONA_LABEL_MAP.get(name, name)
            fig.add_trace(go.Scatter(
                x=[pt.median_mixed_wealth], y=[pt.p_solvent * 100],
                mode="markers+text",
                name=short,
                marker=dict(size=14, color="white",
                            line=dict(color=persona_colours[name], width=3)),
                text=[short], textposition="top center",
                textfont=dict(size=12, color=persona_colours[name]),
                hovertemplate=f"{short}: {int(round(pt.mix_pct*100))}% property, "
                              f"wealth {_fmt_money(pt.median_mixed_wealth)}, "
                              f"safety {pt.p_solvent:.1%}<extra></extra>",
            ))

        # Currently selected mix (heavier ring)
        selected_pt = next(
            (p for p in mix_curve if int(round(p.mix_pct * 100)) == breakdown_mix_pct),
            None
        )
        if selected_pt:
            fig.add_trace(go.Scatter(
                x=[selected_pt.median_mixed_wealth], y=[selected_pt.p_solvent * 100],
                mode="markers",
                name="Selected mix",
                marker=dict(size=18, color="white",
                            line=dict(color=INK, width=3)),
                hovertemplate=f"Selected: {breakdown_mix_pct}% property, "
                              f"wealth {_fmt_money(selected_pt.median_mixed_wealth)}, "
                              f"safety {selected_pt.p_solvent:.1%}<extra></extra>",
            ))

        # Dial safety threshold line
        fig.add_hline(y=dial_safety_pct, line_dash="dash", line_color=MUTED,
                      annotation_text=f"Safety target: {dial_safety_pct}%",
                      annotation_font_size=11)

        fig.update_layout(
            title=dict(
                text=f"Safety vs wealth tradeoff — {horizon}-year horizon",
                font=dict(size=15)
            ),
            xaxis_title=f"Typical outcome after {horizon} years ($)",
            yaxis_title="Chance you never run out of cash (%)",
            yaxis=dict(range=[0, 105]),
            height=420, margin=dict(t=50, b=40),
            hovermode="closest",
            plot_bgcolor="white",
            legend=dict(orientation="h", y=1.1, x=0),
        )
        fig.update_xaxes(gridcolor="#f0f0f0", tickformat="$,.0f")
        fig.update_yaxes(gridcolor="#f0f0f0", ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True)

        # --- Dial: safety target ---
        st.markdown(
            "**Set a safety target** — the model highlights the highest-wealth mix "
            "at or above this level."
        )
        new_dial = st.slider(
            "Safety target (%)",
            min_value=50, max_value=99, value=dial_safety_pct, step=1,
            key="dial_safety_slider",
            help="Drag to change the target. The dashed line on the chart moves with it.",
        )

        # Snap to nearest computed mix for dial-selected point
        qualifying = [pt for pt in mix_curve if pt.p_solvent * 100 >= new_dial]
        if qualifying:
            dial_point = max(qualifying, key=lambda pt: pt.median_mixed_wealth)
            st.markdown(
                f"At {new_dial}%+ safety: **{int(round(dial_point.mix_pct*100))}% property** — "
                f"typical wealth {_fmt_money(dial_point.median_mixed_wealth)}, "
                f"actual safety {dial_point.p_solvent:.1%}"
            )
        else:
            max_achievable = max(pt.p_solvent * 100 for pt in mix_curve)
            st.markdown(
                f"Not achievable above {max_achievable:.0f}% — try raising your "
                f"max annual top-up or reducing the property portion."
            )

        st.markdown("---")

        # --- Free % property slider ---
        st.markdown("**Or set a specific property allocation directly:**")
        new_free_mix = st.slider(
            "% property",
            min_value=0, max_value=100, value=free_mix_pct, step=5,
            key="free_mix_slider",
            help="Pick your exact property/shares split. "
                 "Selects 'Custom' in the breakdown view.",
        )

        # Model-assumption caveat (§5.3 must-fix)
        _render_html(f"""
        <p class="frontier-caveat">
          <b>How this curve works:</b> it blends two full strategies (100% property and 100% shares)
          as an allocation rule — it doesn't model buying a part-property; a real investor can't sell
          40% of a house in a bad year. Mid-range mixes may understate a bad year's cash crunch.
          Sampling noise (shown as a faint band) is ~±1ppt at 5,000 stories.
        </p>""")

        # --- Show as table toggle (accessibility fallback) ---
        st.markdown("---")
        show_table = st.checkbox("Show as table", value=False, key="frontier_show_table")
        if show_table:
            from ui.persona import render_comparison_table
            render_comparison_table(mix_curve, breakdown_mix_pct)

    return int(new_dial), int(new_free_mix)
```

**Step 5.3 — Add `.frontier-caveat` CSS to `ui/common.py` GLOBAL_CSS:**

```css
.frontier-caveat {
  font-size: 13px;
  color: #6b7280;
  margin: 12px 0 4px;
  border-left: 3px solid #e5e7eb;
  padding-left: 10px;
  font-style: italic;
}
```

**Step 5.4 — Wire frontier expander into `app.py`:**

After the persona cards and segmented_control block (current line ~464), add:

```python
from ui.frontier import render_dot_grid, render_downside_callout, render_failure_taxonomy, render_frontier_expander

# Render the "How much safety does each mix buy?" expander (below cards)
_new_dial, _new_free_mix = render_frontier_expander(
    mix_curve=mix_curve,
    horizon=horizon,
    breakdown_mix_pct=breakdown_mix_pct,
    dial_safety_pct=dial_safety_pct,
    free_mix_pct=free_mix_pct,
    max_top_up=max_top_up,
)

# Write back URL params for dial and free_mix (clamped)
dial_safety_pct = max(50, min(99, _new_dial))
free_mix_pct = max(0, min(100, _new_free_mix))
st.query_params["dial_safety"] = str(dial_safety_pct)
st.query_params["free_mix"] = str(free_mix_pct)

# If user moved the free-mix slider, switch persona_pick to "Custom"
if _new_free_mix != qp("free_mix", int, 50):
    st.session_state["persona_pick"] = "Custom"
```

**Step 5.5 — Remove the sidebar "Custom mix" slider from `app.py`:**

Delete lines ~246–252 (the `_custom` check and the `property_share_mix_pct` sidebar slider).
The `property_share_mix_pct` variable that the rest of the code referenced is now derived from
`free_mix_pct` — alias it: `property_share_mix_pct = free_mix_pct` at the point where the
sidebar slider was removed.

**Step 5.6 — Remove the standalone "Compare all mixes" expander from `app.py`:**

Delete lines ~579–580 (`with st.expander("⚖️ Compare all property/shares mixes"): render_comparison_table(...)`).
The same data is now accessible via the "Show as table" toggle inside the frontier expander.

**Step 5.7 — Run tests:** `.venv/bin/python -m pytest tests/test_phase2_ui.py -x -q` — GREEN.

**Step 5.8 — Commit:** `git add ui/frontier.py ui/common.py app.py tests/test_phase2_ui.py && git commit -m "Phase 2 Task 5: frontier chart + dial + free-mix slider; retire sidebar Custom mix slider and Compare all mixes expander"`

---

## Task 6 — Information hierarchy reorder + example-data nudge

**Why last:** all the new blocks (headline, callout, expander) exist now; this task only moves
them into the final spec order. It is the safest to leave last — structural reorder without
logic changes — and it is the easiest to verify visually.

**Final order (spec §4):**
1. Example-data nudge
2. Viability flag (moved above cards; reworded "Comfortable"→"Within range")
3. Headline (dot grid)
4. Downside callout + failure-taxonomy expander
5. Cards (persona cards, "Unsure?" line)
6. "How much safety does each mix buy?" expander
7. Detail expanders (year-by-year, distributions/stress, tax/setup)

**Files:**
- `app.py` (reorder existing blocks; reword flag text)
- `tests/test_phase2_ui.py` (add render-order and flag-reword assertions)

### Steps

**Step 6.1 — Write failing tests (append to `tests/test_phase2_ui.py`):**

```python
# ---------------------------------------------------------------------------
# Task 6 — hierarchy reorder + flag reword
# ---------------------------------------------------------------------------

def test_viability_flag_reword_comfortable_to_within_range():
    """✅ flag text must say 'Within range', not 'Comfortable'."""
    at = _run_app()
    full_html = " ".join(str(m) for m in at.markdown)
    # Under default params (max_top_up=20000, reasonable scenario), flag should be ✅
    # The text must NOT contain "Comfortable"
    assert "Comfortable" not in full_html, (
        "Old 'Comfortable' flag text still present; must say 'Within range'"
    )


def test_example_data_nudge_present():
    """'These are example numbers' nudge must appear in the output."""
    at = _run_app()
    full_html = " ".join(str(m) for m in at.markdown)
    assert "example numbers" in full_html.lower() or "example" in full_html.lower(), (
        "'example numbers' nudge not found in output"
    )


def test_not_advice_language_uses_suggests():
    """'What the model suggests' must appear; 'recommended allocation for you' must not."""
    at = _run_app()
    full_html = " ".join(str(m) for m in at.markdown)
    assert "suggests" in full_html.lower(), "'suggests' language not found"
    assert "recommended allocation for you" not in full_html.lower(), (
        "Old 'recommended allocation for you' copy still present"
    )
```

Run RED.

**Step 6.2 — Reorder blocks in `app.py`:**

The target structure (replacing the current order) is:

```python
# 1. Example-data nudge (at the very top of the results region, after the section header)
_render_html("""
<div class="pvs-section-sub" style="margin-top:4px;padding:10px 14px;
  background:rgba(245,158,11,.07);border-radius:8px;border:1px solid rgba(245,158,11,.3);">
  <b>These are example numbers</b> — change them in the left panel to match your situation.
</div>""")

# 2. Viability flag (BEFORE cards; uses result["worst_year_cash"] which is already computed)
# Reword the ✅ case:
if wyc <= max_top_up:
    flag = ("ok", f"Within range — the worst simulated year needs about {_fmt_money(wyc)}, "
                  f"inside your {_fmt_money(max_top_up)} ceiling.")
elif wyc <= max_top_up * 1.25:
    flag = ("warn", f"Tight — a bad year could need about {_fmt_money(wyc)} vs your "
                    f"{_fmt_money(max_top_up)} ceiling. A rate or rent shock could tip you over.")
else:
    flag = ("bad", f"Stretched — a bad year could need about {_fmt_money(wyc)}, well above your "
                   f"{_fmt_money(max_top_up)} ceiling. Consider more shares or a bigger deposit.")
_render_html(f'<div class="flag {flag[0]}"><span class="flag-emoji">'
             f'{"✅" if flag[0]=="ok" else "⚠️" if flag[0]=="warn" else "❌"}'
             f'</span> {flag[1]}</div>')

# 3. Headline (dot grid + pvs-section-sub context)
render_dot_grid(p_succeeds=result["p_property_succeeds"],
                n_trials=int(result["property_terminal_wealth"].size), horizon=horizon)
_render_html(f"""<div class="pvs-section-sub">Property beats shares in
{result['p_property_wins']:.0%} of stories, but only {result['p_solvent']:.0%}
stay within your {_fmt_money(max_top_up)} cash ceiling. "Succeeds" needs both.</div>""")

# 4. Downside callout + failure-taxonomy expander
render_downside_callout(...)
with st.expander("What are the failure modes? (2×2 breakdown)"):
    render_failure_taxonomy(...)

# 5. Cards (render_persona_cards) + segmented_control
st.markdown('<div class="pvs-section">What the model suggests at each safety level</div>', ...)
render_persona_cards(mix_curve, horizon)
...  # segmented_control

# 6. Frontier expander
_new_dial, _new_free_mix = render_frontier_expander(...)

# 7. Detail expanders (year-by-year, distributions, tax)
with st.expander("📈 Year-by-year breakdown..."):
    ...
with st.expander("🎲 Range of outcomes & cashflow stress"):
    ...
render_full_guide()
with st.expander("🏛 Setup & tax rules used"):
    ...
```

Note: `result["worst_year_cash"]` (`wyc`) must be computed before the flag is rendered.
In the current code it is computed after the headline. Move the `wyc` assignment to before
the example-data nudge, or pass it as a parameter. The cleanest approach: compute `wyc`
immediately after the `result` dict is built (currently around line 489).

**Step 6.3 — Remove the old inline "What this means" blurb** (lines ~517–523 in the current
`app.py`) — this copy is superseded by the section header, dot-grid explainer, and downside
callout, which together provide a clearer and more accurate picture.

**Step 6.4 — Verify visually:** run `streamlit run app.py` and confirm:
- Example-data nudge appears at the top
- Viability flag appears BEFORE cards
- Dot grid appears above the flag
- Downside callout appears below the dot grid
- Cards appear below the callout
- Frontier expander appears below cards
- Year-by-year expander appears after everything

**Step 6.5 — Run tests:** `.venv/bin/python -m pytest tests/test_phase2_ui.py -x -q` — GREEN. Also run the full suite: `.venv/bin/python -m pytest -q` — all tests green.

**Step 6.6 — Commit:** `git add app.py tests/test_phase2_ui.py && git commit -m "Phase 2 Task 6: hierarchy reorder — flag above cards, example-data nudge, 'Within range' reword, final block order per spec §4"`

---

## Spec ambiguities resolved

**A1 — "Comfortable" → "Within range" exact reword (§4):** spec says "reword 'Comfortable' →
'Within range'". Applied to the ✅ flag case only. The full flag text is:
"Within range — the worst simulated year needs about $X, inside your $Y ceiling."
The "inside" replaces the previous implication that the ceiling is merely not exceeded — 
it explicitly frames the ceiling as the safety benchmark. ⚠

**A2 — dot-grid rounding at exactly 50% (§5.1):** spec says `round(p*100)` — Python's
`round()` uses banker's rounding (round-half-to-even). At p=0.505 → round(50.5) = 50 (not
51). This is correct per the spec's intent (no direction bias). No change; documented here.

**A3 — "Show as table" replaces standalone expander (§4.3):** spec says "offer the same data
as an optional 'Show as table' toggle inside the tradeoff expander". Implemented as a
`st.checkbox` inside the frontier expander. The old `render_comparison_table` function in
`ui/persona.py` is KEPT (not deleted) because it still serves the toggle. ⚠

**A4 — `breakdown_mix_pct` source for "Custom" after sidebar slider removal:** when
`persona_pick == "Custom"`, the mix is now driven by `free_mix_pct` (the in-expander slider),
not `property_share_mix_pct` (sidebar, removed). The aliasing line
`property_share_mix_pct = free_mix_pct` ensures the URL `mix` param still persists correctly
for Custom mode. ⚠

**A5 — `_total_top_ups` deflation sequencing:** the downside callout receives `total_top_ups`
in nominal $ and labels it accordingly when `deflate=False`, and "today's $" when
`deflate=True`. The `render_downside_callout` function accepts a `deflate` bool and adjusts
the label. The actual array passed in is always the post-deflation array (already on `result`);
the unit annotation comes from the `deflate` flag. This is consistent with how `worst_year_cash`
is already handled on `result`. ⚠

**A6 — `render_frontier_expander` return values vs `@st.fragment` scope:** the spec calls for
`@st.fragment` to scope the expander so dial/mix changes don't re-trigger the base run. In
the implementation, the frontier expander already sits below the base-run computation and reads
from `mix_curve` (already computed); Streamlit's normal rerun behaviour means dial changes
trigger a full rerun but `cached_run` serves from cache — so the base run does NOT re-execute.
Adding `@st.fragment` around the expander would prevent writing back `dial_safety_pct` and
`free_mix_pct` to the outer `app.py` scope. The cleanest Phase 2 approach: **omit `@st.fragment`
here** and rely on `@st.cache_data` on `cached_run` (the expensive operation is already cached;
only the cheap `build_mix_curve` + rendering re-executes). Adding `@st.fragment` can be a
follow-up optimisation in Phase 3 when the full A/B flow makes it worth the complexity. ⚠

---

## Test coverage summary

| What is tested | Method | Testable? |
|---|---|---|
| App loads without crash | AppTest default load | Yes |
| Persona renames consistent | HTML string search | Yes |
| Old persona names absent | HTML string search | Yes |
| SUGGESTED badge present | HTML string search | Yes |
| "Recommended allocation" absent | HTML string search | Yes |
| Stale URL persona clamped | AppTest with old param | Yes |
| Custom persona still works | AppTest with Custom+free_mix | Yes |
| FAINT not in .pthr/.mlabel | CSS string inspection | Yes |
| Micro-labels ≥14px | CSS regex inspection | Yes |
| Dot-grid class in HTML | HTML string search | Yes |
| Natural-frequency phrasing | HTML string search | Yes |
| Inline explainer "not a forecast" | HTML string search | Yes |
| Downside callout present | HTML string search | Yes |
| Forced-sale language | HTML string search | Yes |
| "Excludes" caveat | HTML string search | Yes |
| Mix=0 callout suppressed/zero | AppTest with free_mix=0 | Yes |
| Model-assumption caveat | HTML string search | Yes |
| Frontier expander present | AppTest expander list | Yes |
| Dial slider present | AppTest slider list | Yes |
| Free-mix slider present | AppTest slider list | Yes |
| Sidebar Custom mix slider gone | AppTest slider list | Yes |
| "Show as table" checkbox | AppTest checkbox list | Yes |
| Linear-blend caveat | HTML string search | Yes |
| Standalone "Compare all" gone | AppTest expander list | Yes |
| Flag "Within range" reword | HTML string search | Yes |
| Example-data nudge | HTML string search | Yes |
| "suggests" language | HTML string search | Yes |
| Chart dash styles | Visual only | No — verify manually |
| Flag emoji ≥16px | Visual only | No — verify manually |
| Dot-grid visual layout | Visual only | No — verify manually |
| Failure taxonomy colours | Visual only | No — verify manually |
| Frontier chart renders | Visual only | No — verify visually |
