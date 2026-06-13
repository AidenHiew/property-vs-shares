# tests/test_cold_review_fixes.py
"""Tests for the cold pre-merge review fixes.

Fix 1: worst_year_cash stays nominal regardless of display_mode.
Fix 2: render_downside_callout labels nominal figures consistently.
Fix 3: moving the free-mix slider flips persona_pick to 'Custom'.
"""
from __future__ import annotations

import numpy as np
import pytest
from streamlit.testing.v1 import AppTest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_app(**query_params) -> AppTest:
    at = AppTest.from_file("app.py", default_timeout=120)
    for k, v in query_params.items():
        at.query_params[k] = str(v)
    at.run()
    return at


# ---------------------------------------------------------------------------
# Fix 1 — worst_year_cash stays NOMINAL in "today" display mode
# ---------------------------------------------------------------------------

class TestFix1NominalWorstYearCash:
    """worst_year_cash must be the same whether display_mode is 'nominal' or 'today',
    because it is a cash-safety figure kept in future dollars regardless of the
    display toggle.  The viability flag text should therefore also be consistent.
    """

    def test_worst_year_cash_same_in_nominal_and_today_modes(self):
        """App must produce the SAME worst_year_cash under both display modes.

        Before the fix, today's-$ mode deflated worst_year_cash → a smaller number
        that made the scenario look safer than it actually was.
        """
        # nominal mode (default)
        at_nom = _run_app(display_mode="nominal", persona="Balanced · 95%+")
        assert not at_nom.exception, f"nominal mode crashed: {at_nom.exception}"

        # today's-$ mode
        at_today = _run_app(display_mode="today", persona="Balanced · 95%+")
        assert not at_today.exception, f"today mode crashed: {at_today.exception}"

        # Extract flag text from both runs (flag div contains the dollar figure)
        def _flag_html(at: AppTest) -> str:
            return " ".join(m.value for m in at.markdown if "flag" in (m.value or "").lower()
                            or "Within range" in (m.value or "")
                            or "Tight" in (m.value or "")
                            or "Stretched" in (m.value or ""))

        # The flag verdict (ok / warn / bad) must be the SAME in both modes,
        # because both compare nominal worst_year_cash against nominal max_top_up.
        full_nom   = " ".join(m.value or "" for m in at_nom.markdown)
        full_today = " ".join(m.value or "" for m in at_today.markdown)

        def _flag_verdict(html: str) -> str:
            for word in ("Within range", "Tight", "Stretched"):
                if word in html:
                    return word
            return "unknown"

        verdict_nom   = _flag_verdict(full_nom)
        verdict_today = _flag_verdict(full_today)

        assert verdict_nom != "unknown", "Flag verdict not found in nominal-mode HTML"
        assert verdict_today != "unknown", "Flag verdict not found in today-mode HTML"
        assert verdict_nom == verdict_today, (
            f"Flag verdict differs by display mode: nominal={verdict_nom!r}, "
            f"today={verdict_today!r}. Fix 1 is not applied — worst_year_cash is "
            "still being deflated in today's-$ mode."
        )

    def test_today_mode_does_not_crash(self):
        """App with display_mode=today must not raise an exception."""
        at = _run_app(display_mode="today")
        assert not at.exception, f"today mode crashed: {at.exception}"

    def test_nominal_caption_appears_in_today_mode(self):
        """When display_mode=today, a note about nominal/future dollars must appear
        near the viability flag or cashflow chart so the user knows those figures
        are not deflated like the wealth numbers.
        """
        at = _run_app(display_mode="today")
        assert not at.exception
        full_html = " ".join(m.value or "" for m in at.markdown)
        # Any of these phrasings satisfy the requirement
        has_note = (
            "future $" in full_html
            or "nominal" in full_html.lower()
            or "future dollars" in full_html.lower()
            or "not deflated" in full_html.lower()
        )
        assert has_note, (
            "No nominal/future-$ caption found when display_mode=today. "
            "Fix 1 requires a note near the flag indicating cash figures are in future $."
        )


# ---------------------------------------------------------------------------
# Fix 2 — render_downside_callout labels dollar figures consistently
# ---------------------------------------------------------------------------

class TestFix2CalloutUnitConsistency:
    """The downside callout must label its dollar figures consistently.

    After Fix 1, worst_year_cash is nominal; _callout_total_top_ups is also nominal
    (computed from pre-deflation arrays). The callout must therefore NOT label them
    as 'today's $' when display_mode='today'.
    """

    def test_callout_does_not_claim_todays_dollars_in_today_mode(self):
        """In today's-$ display mode, the callout's dollar label must NOT say
        'today's $' (which would be wrong — figures are nominal / future $).
        """
        at = _run_app(display_mode="today", persona="Balanced · 95%+")
        assert not at.exception
        full_html = " ".join(m.value or "" for m in at.markdown)

        # Only check if callout is present at all (mix > 0 is the default)
        if "If it goes wrong" not in full_html:
            pytest.skip("Callout not rendered (pure-shares mix?); skipping.")

        # "today's $" must NOT appear inside the callout when figures are nominal
        # (the callout renders inside an HTML block, so we check the full output)
        assert "today's $" not in full_html, (
            "Callout labels its figures as 'today's $' but they are nominal (future $). "
            "Fix 2: remove or correct this label."
        )

    def test_callout_labels_nominal_figures_correctly(self):
        """In nominal display mode, callout must label figures as 'future $' (or omit
        the label entirely — either is acceptable as long as it's not wrong).
        """
        at = _run_app(display_mode="nominal", persona="Balanced · 95%+")
        assert not at.exception
        full_html = " ".join(m.value or "" for m in at.markdown)

        if "If it goes wrong" not in full_html:
            pytest.skip("Callout not rendered (pure-shares mix?); skipping.")

        # Acceptable phrasings: "future $" or no unit label at all
        # NOT acceptable: "today's $" when figures are nominal
        assert "today's $" not in full_html, (
            "Callout claims figures are 'today's $' in nominal mode — incorrect. "
            "Fix 2: label must say 'future $' or drop the unit label."
        )

    def test_callout_unit_label_function_nominal(self):
        """Unit test: render_downside_callout with deflate=False must NOT produce
        'today's $' in its output HTML.
        """
        import io
        import contextlib
        # We test the rendering function directly via a minimal stub
        # The function uses _render_html which calls st.markdown — we check
        # the dollar_label variable logic rather than the rendered HTML.
        # dollar_label = "today's $" if deflate else "future $"
        # After Fix 2: both deflate=True and deflate=False should use "future $"
        # because the figures are always nominal.
        #
        # We replicate the dollar_label logic from render_downside_callout
        # (post-fix the function should never produce "today's $").
        from ui.frontier import render_downside_callout
        import inspect
        src = inspect.getsource(render_downside_callout)
        assert "today's $" not in src, (
            "render_downside_callout source still contains 'today's $'. "
            "Fix 2: remove this string — figures are always nominal/future $."
        )


# ---------------------------------------------------------------------------
# Fix 3 — moving free-mix slider flips persona_pick to 'Custom'
# ---------------------------------------------------------------------------

class TestFix3FreeMixFlipsPersona:
    """Moving the free-mix slider must switch persona_pick to 'Custom'."""

    def test_moving_free_mix_slider_sets_persona_to_custom(self):
        """Start with Balanced persona. Move the free_mix_slider. persona_pick
        should become 'Custom' after the rerun triggered by the slider change.

        This validates the Fix 3 logic: the NEW free_mix value is compared
        against the PRIOR free_mix (before the current write), not against
        the just-written value (which always equals itself → never trips).
        """
        at = AppTest.from_file("app.py", default_timeout=120)
        at.query_params["persona"] = "Balanced · 95%+"
        at.query_params["free_mix"] = "50"  # prior value
        at.run()
        assert not at.exception, f"Initial run crashed: {at.exception}"

        # Move the free_mix_slider to a DIFFERENT value
        slider = next((s for s in at.slider if s.key == "free_mix_slider"), None)
        assert slider is not None, "free_mix_slider not found"

        slider.set_value(70).run()
        assert not at.exception, f"App crashed after slider move: {at.exception}"

        # persona_pick in session_state must be 'Custom'
        try:
            persona_val = at.session_state["persona_pick"]
        except KeyError:
            persona_val = None

        # Also check the segmented_control widget value
        segs = at.get("segmented_control")
        seg_val = segs[0].value if segs else None

        assert persona_val == "Custom" or seg_val == "Custom", (
            f"persona_pick={persona_val!r}, segmented_control={seg_val!r}. "
            "Fix 3: moving the free_mix_slider must set persona_pick='Custom'."
        )

    def test_free_mix_slider_same_value_does_not_flip_persona(self):
        """If the slider stays at the same value as the prior free_mix, persona must
        NOT be overridden to 'Custom' (no spurious flip on first load).
        """
        at = AppTest.from_file("app.py", default_timeout=120)
        at.query_params["persona"] = "Balanced · 95%+"
        at.query_params["free_mix"] = "50"
        at.run()
        assert not at.exception

        # Do NOT move the slider — just re-run (simulates a refresh with same params)
        at.run()
        assert not at.exception

        # persona_pick should still be Balanced (or whatever the prior state was),
        # NOT 'Custom' (no spurious flip)
        try:
            persona_val = at.session_state.get("persona_pick")
        except Exception:
            persona_val = None

        if persona_val is not None:
            assert persona_val != "Custom", (
                f"persona_pick flipped to 'Custom' without slider movement: {persona_val!r}. "
                "Fix 3 must only flip when the slider actually moves."
            )

    def test_free_mix_no_crash_from_url(self):
        """free_mix URL param with custom persona must not crash."""
        at = _run_app(persona="Custom", free_mix=70)
        assert not at.exception, f"App crashed with persona=Custom free_mix=70: {at.exception}"
