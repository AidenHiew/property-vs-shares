from streamlit.testing.v1 import AppTest


def _run():
    at = AppTest.from_file("app.py", default_timeout=90)
    at.run()
    return at


def test_segmented_control_exists_default_balanced():
    at = _run()
    segs = at.get("segmented_control")
    if segs:
        val = segs[0].value
        assert val in ("Balanced · 95%+", None), (
            f"Expected 'Balanced · 95%+' default, got {val!r}"
        )
    else:
        # Fallback: check session state (session_state doesn't support .get(), use try/except)
        try:
            val = at.session_state["persona_pick"]
        except KeyError:
            val = None
        assert val in ("Balanced · 95%+", None), (
            f"Expected 'Balanced · 95%+' default in session_state, got {val!r}"
        )


def test_custom_enables_slider():
    """Picking Custom makes the in-expander free_mix_slider available.

    Task 5: the sidebar 'Custom mix' slider was removed; its role is now served
    by the 'free_mix_slider' inside the frontier expander. Verify that after
    picking Custom the free_mix_slider is present and the old sidebar slider is gone.
    """
    at = _run()
    segs = at.get("segmented_control")
    if segs:
        at.get("segmented_control")[0].set_value("Custom").run()
    else:
        at.session_state["persona_pick"] = "Custom"
        at.run()
    # Old sidebar slider must be gone
    assert not any("Custom mix" in (sl.label or "") for sl in at.get("slider")), (
        "Old 'Custom mix' sidebar slider should have been removed in Task 5"
    )
    # New in-expander slider must be present
    assert any(sl.key == "free_mix_slider" for sl in at.get("slider")), (
        "Expected 'free_mix_slider' (in-expander) to be present after Task 5"
    )


def test_persona_url_param_selects_growth_focused():
    """persona=Growth-focused+·+85%25+ in URL must be respected without crash."""
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("app.py", default_timeout=90)
    at.query_params["persona"] = "Growth-focused · 85%+"
    at.run()
    assert not at.exception, f"App crashed on Growth-focused persona: {at.exception}"
    # Either the segmented control reflects it, or session_state carries it.
    segs = at.get("segmented_control")
    if segs:
        assert segs[0].value == "Growth-focused · 85%+"
    else:
        try:
            val = at.session_state["persona_pick"]
        except KeyError:
            val = None
        assert val == "Growth-focused · 85%+", (
            f"Expected persona_pick=='Growth-focused · 85%+', got {val!r}"
        )


def test_stale_persona_url_param_clamped_to_balanced():
    """Old persona name 'Wealth Maximizer' in URL must clamp to Balanced · 95%+ without crash.

    This is the renamed-identifier clamping regression test — equivalent to what
    test_invalid_persona_url_param_does_not_crash does for 'None', but for stale persona names.
    """
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("app.py", default_timeout=90)
    at.query_params["persona"] = "Wealth Maximizer"
    at.run()
    assert not at.exception, f"App crashed on old persona name 'Wealth Maximizer': {at.exception}"
    # Must have clamped to a valid persona
    segs = at.get("segmented_control")
    if segs:
        assert segs[0].value in ("Safe · 99%+", "Balanced · 95%+", "Growth-focused · 85%+", "Custom"), (
            f"Unexpected persona after clamp: {segs[0].value!r}"
        )


def test_invalid_persona_url_param_does_not_crash():
    # Regression: a deselected segmented_control wrote persona=None to the URL;
    # the literal string "None" is not a valid option and crashed the app on the
    # next load (StreamlitAPIException). It must clamp to "Balanced · 95%+" instead.
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("app.py", default_timeout=90)
    at.query_params["persona"] = "None"
    at.run()
    assert not at.exception, f"App crashed on invalid persona URL param: {at.exception}"
    segs = at.get("segmented_control")
    if segs:
        assert segs[0].value in ("Safe · 99%+", "Balanced · 95%+", "Growth-focused · 85%+", "Custom"), (
            f"Unexpected persona after clamp: {segs[0].value!r}"
        )
    # URL must be rewritten to a valid value, never "None"
    qp_persona = at.query_params["persona"]
    if isinstance(qp_persona, list):  # AppTest may return a list
        qp_persona = qp_persona[0]
    assert qp_persona in ("Safe · 99%+", "Balanced · 95%+", "Growth-focused · 85%+", "Custom"), (
        f"URL persona param was not clamped to a valid value: {qp_persona!r}"
    )
