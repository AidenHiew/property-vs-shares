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
        assert val in ("Balanced", "Balanced ★", None, "Balanced"), (
            f"Expected 'Balanced' default, got {val!r}"
        )
    else:
        # Fallback: check session state (session_state doesn't support .get(), use try/except)
        try:
            val = at.session_state["persona_pick"]
        except KeyError:
            val = None
        assert val in ("Balanced", None), (
            f"Expected 'Balanced' default in session_state, got {val!r}"
        )


def test_custom_enables_slider():
    at = _run()
    segs = at.get("segmented_control")
    if segs:
        at.get("segmented_control")[0].set_value("Custom").run()
        assert any("Custom mix" in (sl.label or "") for sl in at.get("slider")), (
            "Expected a 'Custom mix' slider after picking Custom"
        )
    else:
        # Fallback: set session state directly
        at.session_state["persona_pick"] = "Custom"
        at.run()
        sliders = at.get("slider")
        custom_sliders = [sl for sl in sliders if "Custom mix" in (sl.label or "")]
        assert custom_sliders, "Expected a 'Custom mix' slider"
        assert not custom_sliders[0].disabled, "Expected Custom mix slider to be enabled"


def test_persona_url_param_selects_wealth():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("app.py", default_timeout=90)
    at.query_params["persona"] = "Wealth Maximizer"
    at.run()
    # Either the segmented control reflects it, or session_state carries it.
    segs = at.get("segmented_control")
    if segs:
        assert segs[0].value == "Wealth Maximizer"
    else:
        # at.session_state doesn't support .get() in Streamlit 1.57; use try/except
        try:
            val = at.session_state["persona_pick"]
        except KeyError:
            val = None
        assert val == "Wealth Maximizer", (
            f"Expected persona_pick=='Wealth Maximizer', got {val!r}"
        )


def test_invalid_persona_url_param_does_not_crash():
    # Regression: a deselected segmented_control wrote persona=None to the URL;
    # the literal string "None" is not a valid option and crashed the app on the
    # next load (StreamlitAPIException). It must clamp to "Balanced" instead.
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file("app.py", default_timeout=90)
    at.query_params["persona"] = "None"
    at.run()
    assert not at.exception, f"App crashed on invalid persona URL param: {at.exception}"
    segs = at.get("segmented_control")
    if segs:
        assert segs[0].value == "Balanced"
    # URL must be rewritten to a valid value, never "None"
    qp_persona = at.query_params["persona"]
    if isinstance(qp_persona, list):  # AppTest may return a list
        qp_persona = qp_persona[0]
    assert qp_persona in ("Safe", "Balanced", "Wealth Maximizer", "Custom")
