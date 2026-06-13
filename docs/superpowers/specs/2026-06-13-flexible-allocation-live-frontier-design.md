# Design: Flexible allocation, live recompute, and the trust/downside layer

**Date:** 2026-06-13
**Status:** Draft for review
**Topic:** Expand the property-vs-shares tool beyond 3 fixed persona options into flexible, live allocation control — and close the trust/downside gaps a design review surfaced.

---

## 1. Summary

Today the tool offers three fixed persona cards (Safe / Balanced / Wealth Maximizer) plus a buried, disabled-by-default "Custom mix" slider, and the recommendations only refresh when the user clicks an "↻ Update recommendations" button (they go stale on every input change).

This redesign:

1. **Makes the whole allocation curve come from a single Monte Carlo run** (vectorised post-trial blend), which collapses the expensive 11-point sweep into the base run. This is the keystone — it makes everything below cheap.
2. **Adds flexible allocation control** — keep the reassuring 3 cards as the live default, and add a continuous "safety target" dial + free mix slider + an efficiency-frontier chart, one tap away.
3. **Makes recompute live** — changing an input auto-recomputes (debounced ~300ms); the ↻ button is removed and replaced with clear stale/updating micro-states.
4. **Closes the biggest gap a design review found** — the downside (the "bad ~27%") is currently hidden in a collapsed expander. This redesign surfaces, in plain dollars and up front, what being wrong costs.
5. **Folds in a batch of high-value design-review fixes** — plain-English headline with a dot grid, information-hierarchy reorder, card renames / softened steering, accessibility (contrast + colourblind), and mobile fallbacks.

A side-by-side **A/B scenario compare** (exactly two scenarios) follows as a separate phase, made cheap by the same engine work.

Audience is unchanged: non-expert "mum & dad" Australian investors. The tool remains explicitly **not financial advice**.

---

## 2. Locked decisions (from brainstorming)

These were decided with the user and a two-lane (modeling-expert + retail-investor) plus three-lane (UX / data-viz / trust+accessibility) design review. They are inputs to this spec, not open questions.

- **D1 — Best of both, not either/or.** Keep the 3 cards as the default hero *and* add the continuous dial/frontier. They are two readings of one curve.
- **D2 — Cards stay as default; dial/frontier live in an expander below them**, not replacing the cards.
- **D3 — Live = auto + clear states.** No manual button. Recompute fires automatically ~300ms after the user stops changing an input. While computing: dim the stale figures + show "updating…", then a brief "updated ✓". (Chosen over keeping a manual button or a bare spinner.)
- **D4 — A/B compare = exactly two scenarios** (not N).
- **D5 — Fold all high-value design-review fixes into this spec** (trust/downside, dot grid, hierarchy reorder, renames, a11y, mobile) — they are cheap relative to the engine work.

---

## 3. Engine architecture — the keystone (Phase 1)

### 3.1 The unlock (verified)

`model/monte_carlo.py:234-236` applies the property/shares blend as a **pure scalar operation on already-computed per-trial arrays**:

```python
mix = property_share_mix
mixed_terminal     = mix * p_terminal + (1 - mix) * s_terminal
mixed_outside_cash = mix * p_outside_cash   # only property has outside-cash demand
mixed_forced_flags = flag_forced_sales(mixed_outside_cash, serviceability_ceiling)
```

Because the blend happens *after* the trials are simulated, **every mix point can be derived from one run's `p_terminal`, `s_terminal`, and `p_outside_cash` arrays** — no re-simulation per mix. This is what makes the live dial and the frontier cheap.

### 3.2 The refactor

Introduce a pure function that builds the whole curve from the unblended per-trial arrays:

```
build_mix_curve(p_terminal, s_terminal, p_outside_cash, ceiling, mixes) -> list[MixPoint]
```

where `mixes = np.linspace(0, 1, N)` and each `MixPoint` carries:
`mix_pct, median_mixed_wealth, p_solvent, p_succeeds, p_mix_beats_pure_shares, worst_year_cash, forced_sale_rate`.

Vectorised over the mix axis (shape `(N, trials)`), the whole curve is a handful of NumPy reductions, sub-second at `trials=5000`.

- **Phase-1 task 0 (verification):** confirm `run_monte_carlo` returns (or can cheaply expose) the unblended `p_terminal`, `s_terminal`, and the per-trial-year `p_outside_cash` array. The current return dict already exposes `property_terminal_wealth`, `shares_terminal_wealth`, and `mixed_outside_cash_per_trial_year`; if the raw property outside-cash array isn't exposed, refactor the return to include it. **No behaviour change** — the single-mix path must produce byte-identical results.
- Replace `compute_persona_sweep` (11 runs × 2,000 trials) with `build_mix_curve` over the single 5,000-trial base run. Cards, frontier, and dial all read this one curve.
- **Curve resolution:** `N = 21` (every 5% property) as the default; the dial snaps to the nearest and interpolates the displayed figures linearly between adjacent points. (101 points is affordable too; 21 keeps the frontier chart and comparison table uncluttered. Revisit if interpolation feels coarse.)

### 3.3 Common random numbers (CRN)

Pass the **same seed to the base run** so all mix points share identical underlying return/rate/vacancy paths. Differences along the curve then reflect only the blend, not Monte Carlo noise — the "optimal mix" stops jumping between runs. (The existing seed / seed+1 split for decorrelating return vs loan-rate streams is preserved.)

### 3.4 Cheap rigor fixes (while in the engine)

- **Wire up `rental_yield_sigma`** — currently plumbed through the call path but hard-set to `0.0` in `app.py`. Expose a small default so rental income has realistic variance.
- **(Optional, flagged)** the property "overflow" share bucket compounds at a constant `SHARE_RETURN_FOR_OVERFLOW = 8.5%` rather than the trial's stochastic share path, slightly inflating property in bad-share futures. Low priority; note in code, defer fix.

### 3.5 Live-update state machine (Streamlit)

Define every state explicitly (the current design only handles "stale" via the button):

| State | Trigger | UI treatment |
|---|---|---|
| **Initial load** | first paint | spinner: "Running 5,000 simulated futures…"; main body gated until first curve ready |
| **Fresh** | curve matches current inputs | normal render |
| **Debouncing** | an input changed <300ms ago | keep showing previous figures, dimmed (`opacity:.6`) + inline "updating…" badge |
| **Recomputing** | debounce elapsed, run in flight | same dimmed state; spinner on the affected region |
| **Updated** | new curve ready | brief "updated ✓" pulse, then Fresh |
| **No-solvent-mix** | `build_mix_curve` finds no mix meeting a threshold | card shows "Not reachable at your cash ceiling — raise the ceiling or deposit"; never crash; all-None handled (today only Safe handles None) |
| **Error** | engine raises / OOM | friendly message: "Something went wrong — try a shorter horizon or smaller deposit." Wrap the run in try/except. |

- **Dial / mix slider are exempt from recompute** — they read the precomputed curve, so they update instantly (no debounce, no spinner).
- **Debounce implementation:** track an input-parameter hash in `st.session_state`; recompute only when it changes and a settle interval has passed. Prefer `st.fragment` to scope reruns to the results region if it fits; otherwise a session-state guard. Flag as an implementation detail to validate — native debounce isn't a first-class Streamlit primitive.

---

## 4. Information hierarchy & UI (Phase 2)

New top-to-bottom order of the main pane (reordered per the UX lane — the viability gate and the downside must precede the recommendations):

1. **Example-data nudge** — "These are example numbers — change them in the left panel to match your situation." (one `st.info`-style callout).
2. **Viability flag** — the ✅/⚠️/❌ feasibility flag, moved **above** the cards (it's the "is this even viable for me?" gate). Reword the ✅ case from "Comfortable" to "**Within range** — the worst single year stays inside your $X ceiling." ("Comfortable" over-reassures.)
3. **Headline** — dot grid + plain words (see §5).
4. **Downside callout** — what the bad outcomes cost, in dollars, up front (see §5).
5. **Cards** — renamed, live points on the curve (see §4.1).
6. **"See why each mix sits where it does →"** — an expander (not labelled "Fine-tune") holding the frontier chart + safety dial + free mix slider (see §4.2).
7. **Existing detail expanders** — year-by-year, compare-all-mixes table, distributions/stress, tax/setup. Largely unchanged; see §7 redundancy note.

### 4.1 Cards

- Rename to descriptive, non-steering labels: **"Safe · 99%", "Balanced · 95%", "Growth-focused · 85%"** (drop "Wealth Maximizer" — aspirational steering in a not-advice tool).
- **Remove the ★** on Balanced; replace with one attributable line: "Unsure? **Balanced (95% safety)** is a common starting point."
- Rename the section header "Recommended allocation for you" → "**What the model suggests at each safety level**."
- Cards are now live (read from the curve); no ↻ button, no stale banner.

### 4.2 Frontier + dial expander

- **Name it plainly:** "How much safety does each mix buy?" (not "efficiency frontier", not "Fine-tune").
- **Chart:** x = "Typical outcome after 25 years" ($), y = "Chance you never run out of cash" (0–100%). Every mix is a point on the curve; the 3 cards are 3 labelled rings on it (callout labels, not in-place clutter); the recommended mix is a heavier ring. Add a thin **±sampling-noise band** (binomial CI, ≈±0.6ppt at n=5000) so the curve doesn't imply false precision.
- **Safety dial** = a `st.slider` beside the chart (true on-chart drag isn't supported in Plotly-in-Streamlit). Dragging it moves a threshold line along the curve and updates the recommended-mix ring. Use Plotly `transition` for a soft move between the 21 points so it reads as sliding, not jumping.
- **Free mix slider** (% property) for users who want to pick a specific split directly.
- **Remove the sidebar "Custom mix" slider** — this expander supersedes it (kills the split-brain affordance).

---

## 5. Trust & downside layer (folded into Phase 2 — elevated from "Phase 4")

This is the **single biggest gap** all three design lanes independently flagged: the downside currently lives in a collapsed expander, so the tool's effective output is one-sidedly positive.

### 5.1 Headline you can read

- Replace the bare "73%" with a **10×10 dot grid** (73 filled green, 27 grey) beside the number, and phrase it as a natural frequency: "**about 7 in 10** of 5,000 what-if **stories built from your numbers**…".
- **Inline two-sentence explainer** directly under the headline (not a tooltip, not the footer): the number is *not a forecast* — it's the count of fictional 25-year paths, drawn from the ranges the user set, that ended with property ahead and the cash ceiling intact. Avoid "probability", "statistically", "Monte Carlo".

### 5.2 Downside in dollars, up front

A callout immediately below the headline (amber, not buried):

> "**If it goes wrong:** in the worst 1-in-10 stretches you could need about **$X extra in a single year** (`worst_year_cash`, already computed), and about **$Y total top-ups** over the hold. In **Z%** of stories the property would likely have to be sold before the end (`forced_sale_rate`, from the existing `flag_forced_sales`). Worth checking this fits your safety net."

- `forced_sale_rate` is a **real model output** (`flag_forced_sales` / `mixed_forced_flags`), so we can state it honestly rather than hand-waving.
- Words: "could need", "bad stretches", "stories where things go wrong". Avoid "risk/failure/loss/worst case".
- Detail (in an expander, kept): a **2×2 failure taxonomy** — rows beats/loses shares, columns within/over cash ceiling — each cell with a frequency ("18 in 100") and a dollar anchor. Clearer for laypeople than the terminal-wealth histogram.

---

## 6. A/B scenario compare (Phase 3)

- A control near the inputs (not a top-of-page toggle, which is a dead state on first visit): "**Save snapshot** / **Compare to saved**."
- Save **Scenario A = the input parameters** (not the result arrays — avoids memory bloat and stale arrays); recompute B's curve live.
- Display: two compact headline mini-cards (typical outcome + solvency % each) + **one overlaid frontier chart** — Scenario A solid, Scenario B dashed (same asset-semantic colours; distinguish scenarios by line *style*, not hue). Shade the gap between the curves and draw the safety-target reference line so the *difference* is the primary read.
- **Mobile:** side-by-side `st.columns(2)` does **not** stack on Streamlit mobile; degrade to `st.tabs()` (A / B / Compare). True side-by-side is tablet+ (≥768px).
- Exactly two scenarios (D4).

---

## 7. Accessibility (folded, Phase 2)

- **Contrast:** `FAINT (#9ca3af)` fails WCAG AA (~2.9:1) and is used for small labels — replace with `MUTED (#6b7280)` for all text. Raise micro-labels (currently 11–12px) to **≥14px** (audience skews 40–60s).
- **Colourblind:** the green/red semantic system must not be colour-only. Keep the "RECOMMENDED" text badge; ensure the feasibility-flag emoji is ≥16px; give chart lines distinct **dash styles** (property vs shares vs mix) in addition to colour.
- **Sliders/segmented control:** add a visible hint where a control's enabled-state depends on another; note `st.segmented_control` ARIA completeness is uncertain — validate keyboard/screenreader, fall back to `st.radio` if it's a dead zone.
- **Numeracy:** the dot grid doubles as a natural-frequency aid; add "(about 7 in 10)" alongside any bare percentage in the headline.

---

## 8. Out of scope (YAGNI)

- **Deeper model** (offset account, second property/portfolio, margin-call mode, capex, mid-period rebalancing) — explicitly deferred. The design review ranked this a trap until the UX and current model are solid.
- **More than two** compare scenarios.
- **"% property ahead by year"** temporal line and **retiring the terminal-wealth histogram** — reasonable later polish; deferred (note the histogram becomes partly redundant with the frontier + 2×2 taxonomy).
- **A precise "forced sale" economic model** beyond the existing ceiling-breach flag — we use `flag_forced_sales` as-is and word the downside as "would likely have to be sold", not a precise fire-sale loss.

---

## 9. Testing

Per the project's hard-won rule (`CLAUDE.md`): test malformed/boundary inputs explicitly, not just the happy path — "tests pass" ≠ "works" (a shared URL once crashed with 138 green tests).

- **Engine equivalence:** `build_mix_curve` at a given mix must match a full single-mix `run_monte_carlo` for that mix (regression guard; the refactor must not change numbers).
- **CRN smoothness:** with a fixed seed, the curve's `p_solvent` is near-monotonic in mix and the recommended mix is stable across repeated runs.
- **No-solvent-mix:** a scenario where no mix clears a threshold returns a sentinel and renders the "Not reachable" state for *all* affected cards without raising (today only Safe handles None).
- **Live state:** input-hash change flips to debouncing/recomputing then back to fresh; dial moves do **not** trigger recompute.
- **A/B snapshot:** saving Scenario A captures parameters; changing inputs doesn't mutate A; B recomputes independently.
- **Persisted/shared state:** keep the existing malformed-URL persona test pattern; extend to any new URL params (dial position, safety target, scenario snapshot).
- **Deflation:** today's-$ paths still correct after the curve refactor.

---

## 10. Phasing

Each phase ships standalone.

- **Phase 1 — Engine + live:** verify/expose unblended arrays → `build_mix_curve` → CRN → remove sweep & ↻ button → live state machine → `rental_yield_sigma`. Tests in §9.
- **Phase 2 — Flexible UI + trust/downside + a11y:** hierarchy reorder, dot-grid headline + explainer, downside-in-dollars callout + 2×2 taxonomy, cards renamed/de-steered, frontier+dial expander, remove sidebar custom slider, accessibility fixes.
- **Phase 3 — A/B compare:** snapshot + overlaid frontier + mobile `st.tabs()` fallback.

---

## 11. Open assumptions / risks

- **Streamlit debounce** is not a first-class primitive; `st.fragment` scoping is the preferred path but needs validation. If it can't be made to feel right, fall back to a session-state settle guard.
- **Plotly-in-Streamlit** can't do true on-chart drag; the dial is a separate slider with an animated transition — acceptable for a personal tool, imperfect at fast dragging.
- **Curve resolution** (21 points + interpolation) assumed adequate; revisit if the dial feels coarse near flat optima.
- **Mobile** remains a Streamlit weak spot (sidebar collapses to a hamburger that hides the entire input flow); A/B is tablet+ / tabbed. A fuller mobile pass is out of scope here.
