# Report Export + Clickable Persona Cards — Design

**Status:** DRAFT — brainstorm in progress. Decisions below are locked; design
sections 2–6 still need to be presented/approved before writing the impl plan.
**Date:** 2026-06-10
**Project:** `property-vs-shares` (personal AU Monte Carlo tool, Streamlit + Python)

## Goal

Two output-improvement features:

1. **Rich exports** — replace the inputs-only JSON save with full **Excel, PDF,
   and Word** report downloads.
2. **Clickable persona cards** — clicking a recommendation card (Safe Player /
   Balanced / Wealth Maximizer) jumps the user straight to that persona's
   year-by-year breakdown.

(The existing JSON save stays — these are additive.)

## Locked decisions (from brainstorm)

| Question | Decision |
|---|---|
| Export content | **Full report: numbers + tables + embedded charts** |
| Report scope | **All three personas in full** (Safe, Balanced, Wealth Maximizer) |
| Delivery | **Three separate download buttons** (Excel / PDF / Word) |
| Card-click UX | **Cards become links** → set persona query param, rerun, auto-open + scroll to breakdown |
| Chart rendering | **matplotlib re-render → PNG** (NOT kaleido — kaleido is fragile on Streamlit Cloud) |
| Export architecture | **Approach A**: shared report-model + thin per-format renderers |

### Rejected approaches
- **Per-format from scratch** — triplicates table/chart logic, drifts. Rejected.
- **HTML → PDF/Word via weasyprint/pandoc** — needs cairo/pango/pandoc system
  deps, fragile on Cloud (same trap as the kaleido/redeploy issue we just hit). Rejected.

## Current-code facts (grounding)

- JSON save today = **inputs only** (11 fields), not results — `app.py:580-587`.
- Persona cards = **static HTML** via `st.markdown(unsafe_allow_html=True)`
  (`ui/persona.py` `render_persona_cards` → `ui/common.py:_render_html`), **not**
  Streamlit buttons. They live in the **main document (not an iframe)**, so they
  CAN become clickable `<a>` links that set query params + scroll anchors.
- Breakdown is driven by `st.segmented_control("View breakdown for", [...])`
  persisted to the `persona` query param (`app.py:414`), and sits inside a
  **collapsed `st.expander("📈 Year-by-year breakdown …")`** (`app.py:507`).
- `result` dict carries rich per-year paths (property/shares wealth, cashflow,
  tax, dividends, etc.) + terminal arrays. `sweep_rows` carries the mix-comparison table.
- No export libs installed yet (openpyxl / python-docx / reportlab / matplotlib
  all absent from `requirements.txt`).

## Architecture — Approach A (Section 1, presented & looks right pending confirm)

```
ui/export/
  __init__.py
  report_model.py   # build_report_data(run_kwargs, sweep_rows, horizon, deflate, …) -> ReportModel
  charts.py         # matplotlib re-renders -> PNG bytes (wealth paths, outcome hist, cashflow)
  xlsx.py           # to_xlsx(model) -> bytes   (openpyxl)
  pdf.py            # to_pdf(model)  -> bytes   (reportlab)
  docx.py           # to_docx(model) -> bytes   (python-docx)
```

- `ReportModel` = dataclass: scenario inputs, 3 persona summaries, per-persona
  year-by-year property & shares tables (plain row lists), mix-comparison table,
  pre-rendered chart PNGs.
- `app.py` calls `build_report_data(...)` **only when an export button is clicked**
  (lazy — does NOT slow normal use). Generating the report runs the sim for each
  of the 3 persona mixes (reuse cache for the already-selected one) + renders charts.
  Expect a few seconds; show a spinner.
- Pass model → chosen renderer → bytes → `st.download_button`.

## Open items (NOT yet designed — resume here)

- [ ] **Section 2 — Report content structure**: exact sections/sheets per format
  (Excel multi-sheet layout; PDF/Word page structure; which charts; deflation/
  "today's $" handling in the report).
- [ ] **Section 3 — Card-link + scroll/expand mechanics**: how the `<a href>`
  carries the full query string + a `view=breakdown` flag; how the breakdown
  expander is forced `expanded=True` on arrival; scroll-to-anchor method in
  Streamlit (JS injection via a tiny `components.html`, since reruns reset scroll).
- [ ] **Section 4 — Dependencies**: add `openpyxl`, `python-docx`, `reportlab`,
  `matplotlib` to `requirements.txt`; verify all install cleanly on Streamlit
  Cloud (pure-Python, should be fine). Reboot Cloud after merge (per the
  redeploy lesson).
- [ ] **Section 5 — Error handling**: per-format try/except so one broken
  renderer never crashes the app; guard empty/failed sweeps.
- [ ] **Section 6 — Testing**: unit-test each renderer produces valid non-empty
  bytes; test report-model assembly; AppTest that export buttons render and the
  card links carry the right params. Follow the persisted-state-as-untrusted-input
  rule for the new `view=breakdown` query param.

## Next step

Resume brainstorm at Section 2. Then write spec sections 2–6, get user review,
then `writing-plans`.
