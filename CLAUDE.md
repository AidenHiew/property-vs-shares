# CLAUDE.md — property-vs-shares

Personal AU Monte Carlo tool (property vs shares), Streamlit + Python. Auto mode
(personal, no regulatory exposure). Defers to workspace `../CLAUDE.md` and global
`~/.claude/CLAUDE.md` for risk tiers, methodology, and hard stops — not restated here.

## Running things

- **Always use `.venv/bin/python`** — bare `python`/`python3` lack streamlit and others.
- Tests: `.venv/bin/python -m pytest -q`.
- Dev server: `.venv/bin/streamlit run app.py` (has run on :8501 / :8503).

## Persisted / shared state — treat as untrusted input

This app round-trips widget state through the URL query-params (shareable scenarios).
A real production crash came from this: a deselected `segmented_control` set
`persona_pick` to `None`, written to the URL as the string `"None"`, which is not a
valid option and raised `StreamlitAPIException` on the next load (see commit `6bab10e`).

Rules for any value that persists to a URL, saved JSON, or config:

1. **Clamp to the valid domain on BOTH write and read**, in the **same commit** as the
   widget — never defer the guard to a later fix. A control that can be deselected can
   emit `None`; serialize only valid-domain values.
2. **Test the malformed/boundary input explicitly**, not just the happy path. "Tests
   pass" did not mean "works" here — 138 tests were green while a shared URL crashed,
   because every test used valid persona values. For persisted/shared state, add a test
   that feeds an invalid/stale value (e.g. `query_params["persona"] = "None"`) and
   asserts no exception + a clamped result. Pattern:
   `tests/test_persona_control.py::test_invalid_persona_url_param_does_not_crash`.

## Layout

- `app.py` — Streamlit UI + URL state.
- `model/` — engine (`monte_carlo.py`, `*_strategy.py`, `duty.py` national stamp duty, `tax.py`).
- `ui/` — extracted helpers (`common.py`, `persona.py`, `onboarding.py`).
- `docs/` — specs/plans/reviews; `docs/superpowers/` for spec+plan artifacts.
