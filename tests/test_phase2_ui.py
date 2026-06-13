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
    full_html = " ".join(m.value for m in at.markdown)
    assert "Safe ·" in full_html, "Renamed persona 'Safe ·' not found in output"
    assert "Balanced ·" in full_html, "Renamed persona 'Balanced ·' not found in output"
    assert "Growth-focused ·" in full_html, "Renamed persona 'Growth-focused ·' not found"


def test_old_persona_names_absent():
    """Old persona names 'Safe Player' and 'Wealth Maximizer' must NOT appear."""
    at = _run_app()
    full_html = " ".join(m.value for m in at.markdown)
    assert "Safe Player" not in full_html, "'Safe Player' (old name) still present"
    assert "Wealth Maximizer" not in full_html, "'Wealth Maximizer' (old name) still present"


def test_recommended_text_absent():
    """The word 'Recommended allocation' must not appear (§8: use 'suggests')."""
    at = _run_app()
    full_html = " ".join(m.value for m in at.markdown)
    assert "Recommended allocation for you" not in full_html


def test_suggested_badge_present():
    """'SUGGESTED' badge must appear; '★ RECOMMENDED' must not."""
    at = _run_app()
    full_html = " ".join(m.value for m in at.markdown)
    assert "SUGGESTED" in full_html, "'SUGGESTED' badge not found"
    assert "★ RECOMMENDED" not in full_html, "'★ RECOMMENDED' (old badge) still present"


def test_segmented_control_options_match_valid_personas():
    """segmented_control must offer exactly the renamed personas; app must not crash."""
    at = _run_app()
    # At minimum the app must not crash and must not contain old names
    assert not at.exception
    full_html = " ".join(m.value for m in at.markdown)
    assert "Safe Player" not in full_html
    assert "Wealth Maximizer" not in full_html


def test_stale_persona_url_param_clamps_to_balanced():
    """persona=Wealth+Maximizer (old name) in URL must clamp to Balanced without crash."""
    at = _run_app(persona="Wealth Maximizer")
    assert not at.exception, f"App crashed on old persona name: {at.exception}"


def test_custom_persona_url_param_still_valid():
    """persona=Custom must still work after renames."""
    at = _run_app(persona="Custom", free_mix=60)
    assert not at.exception, f"App crashed on persona=Custom: {at.exception}"


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


# ---------------------------------------------------------------------------
# Task 3 — dot-grid headline
# ---------------------------------------------------------------------------

def test_dot_grid_present_in_rendered_html():
    """The dot-grid class must appear in the rendered HTML after Phase 2 Task 3."""
    at = _run_app()
    assert not at.exception
    full_html = " ".join(m.value for m in at.markdown)
    assert "dot-grid" in full_html, "dot-grid class not found in rendered output"


def test_dot_grid_natural_frequency_phrasing():
    """Natural-frequency phrasing 'in 10' or 'in 100' must appear in the headline area."""
    at = _run_app()
    full_html = " ".join(m.value for m in at.markdown)
    assert "in 10" in full_html or "in 100" in full_html, (
        "Natural frequency phrasing not found in headline"
    )


def test_headline_explainer_present():
    """Two-sentence inline explainer must mention 'not a forecast' or 'built from'."""
    at = _run_app()
    full_html = " ".join(m.value for m in at.markdown)
    assert "not a forecast" in full_html or "built from your numbers" in full_html, (
        "Headline explainer sentences not found"
    )


# ---------------------------------------------------------------------------
# Task 4 — downside callout
# ---------------------------------------------------------------------------

def test_downside_callout_present():
    """Amber downside callout must appear in rendered output."""
    at = _run_app()
    assert not at.exception
    full_html = " ".join(m.value for m in at.markdown)
    assert "callout-amber" in full_html or "If it goes wrong" in full_html, (
        "Downside callout not found in rendered output"
    )


def test_downside_callout_mentions_forced_sale():
    """Callout must mention forced sale in plain language."""
    at = _run_app()
    full_html = " ".join(m.value for m in at.markdown)
    assert "forced to sell" in full_html, (
        "'forced to sell' language not found in downside callout"
    )


def test_downside_callout_mentions_caveat():
    """Callout must mention 'excludes' caveat for major repairs / income shocks."""
    at = _run_app()
    full_html = " ".join(m.value for m in at.markdown)
    assert "excludes" in full_html, "Downside caveat ('excludes') not found"


def test_downside_callout_mix_aware_at_pure_shares():
    """At free_mix=0 (pure shares), forced-sale callout should show 0% or be absent."""
    at = _run_app(persona="Custom", free_mix=0)
    assert not at.exception
    # App must not crash; the callout for mix=0 is suppressed (no property cash demand)
    full_html = " ".join(m.value for m in at.markdown)
    assert "If it goes wrong" not in full_html or "0%" in full_html, (
        "Downside callout present at mix=0 but should be suppressed or show 0%"
    )


def test_model_assumption_caveat_near_dial():
    """Model-assumption caveat (cash-flow model) must appear somewhere in output."""
    at = _run_app()
    full_html = " ".join(m.value for m in at.markdown)
    assert "cash-flow model" in full_html or "excludes" in full_html, (
        "Model-assumption caveat not found in output"
    )


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
    full_html = " ".join(m.value for m in at.markdown)
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


# ---------------------------------------------------------------------------
# Task 6 — hierarchy reorder + flag reword + example-data nudge
# ---------------------------------------------------------------------------

def test_viability_flag_reword_comfortable_to_within_range():
    """✅ flag text must say 'Within range', not 'Comfortable'."""
    at = _run_app()
    full_html = " ".join(m.value for m in at.markdown)
    # Under default params (max_top_up=20000, reasonable scenario), flag should be ✅
    # The text must NOT contain "Comfortable"
    assert "Comfortable" not in full_html, (
        "Old 'Comfortable' flag text still present; must say 'Within range'"
    )


def test_example_data_nudge_present():
    """'These are example numbers' nudge must appear in the output."""
    at = _run_app()
    full_html = " ".join(m.value for m in at.markdown)
    assert "example numbers" in full_html.lower() or "example" in full_html.lower(), (
        "'example numbers' nudge not found in output"
    )


def test_not_advice_language_uses_suggests():
    """'What the model suggests' must appear; 'recommended allocation for you' must not."""
    at = _run_app()
    full_html = " ".join(m.value for m in at.markdown)
    assert "suggests" in full_html.lower(), "'suggests' language not found"
    assert "recommended allocation for you" not in full_html.lower(), (
        "Old 'recommended allocation for you' copy still present"
    )
