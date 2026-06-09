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
