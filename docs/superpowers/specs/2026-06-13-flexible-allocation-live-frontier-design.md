# Design: Flexible allocation, live recompute, and the trust/downside layer

**Date:** 2026-06-13
**Status:** Draft for review — **rev 2** (incorporates a 3-lane adversarial spec review: engineering-feasibility, completeness/ambiguity, finance-domain-correctness)
**Topic:** Expand the property-vs-shares tool beyond 3 fixed persona options into flexible, live allocation control — and close the trust/downside gaps a design review surfaced.

> **Rev 2 changelog (what the adversarial review changed):** added a mix-aware-downside contract and a model-assumption caveat for the linear blend (it understates intermediate-mix cash stress); made the single-run output mapping explicit (every chart derives post-hoc, no second simulation); pinned the deflation + comparison-mode contract for the curve; replaced the unachievable "300ms timer + ✓ pulse" with a feasible Streamlit mechanism and surfaced the base-run cost; defined `$Y total top-ups` and `forced_sale_rate` precisely; **scheduled `rental_yield_sigma` as its own Phase 1b** (correlated-with-vacancy, calibrated — kept out of the byte-identical refactor but no longer dropped); added new-URL-param guards and downgraded A/B snapshots to session-state-only; resolved the "Compare all mixes" table fate; tightened not-advice language.

---

## 1. Summary

Today the tool offers three fixed persona cards (Safe / Balanced / Wealth Maximizer) plus a buried, disabled-by-default "Custom mix" slider, and the recommendations only refresh when the user clicks an "↻ Update recommendations" button (they go stale on every input change).

This redesign:

1. **Derives the whole allocation curve from a single Monte Carlo run** (vectorised post-trial blend), collapsing the 11-point sweep into the base run. Keystone — it makes everything below cheap.
2. **Adds flexible allocation control** — keep the reassuring 3 cards as the live default, add a continuous "safety target" dial + free mix slider + a plain-language tradeoff chart, one tap away.
3. **Makes recompute automatic** — changing an input auto-recomputes (no manual button); allocation controls (dial/mix) are instant.
4. **Closes the biggest gap the design review found** — the downside (the "bad ~27%") is currently buried in a collapsed expander. Surface, in plain dollars and up front, what being wrong costs — computed correctly for the *selected mix*.
5. **Folds in high-value design-review fixes** — dot-grid headline, hierarchy reorder, card renames / softened steering, accessibility, mobile fallbacks.

A side-by-side **A/B scenario compare** (exactly two scenarios) follows as a separate phase.

Audience unchanged: non-expert "mum & dad" Australian investors. The tool remains explicitly **not financial advice**.

---

## 2. Locked decisions (with rev-2 refinements)

- **D1 — Best of both, not either/or.** Keep the 3 cards as the default hero *and* add the continuous dial/frontier — two readings of one curve.
- **D2 — Cards stay as default; dial/frontier in an expander below them**, not replacing the cards.
- **D3 (refined) — Auto recompute, no manual button.** Recompute fires automatically when an input changes (mechanism in §3.5). Allocation controls (dial, free-mix) never recompute — they read the precomputed curve, so they are instant. **Refinement from review:** the literal "~300ms debounce timer" and "updated ✓ pulse" are *not* achievable in pure Streamlit (no native timer; full-rerun DOM). Replaced with: input-hash-guarded recompute + a "recalculating…" spinner + stale-dim of prior figures. A true timed debounce / ✓-pulse is possible only via a JS component — **deferred**, not in scope.
- **D4 — A/B compare = exactly two scenarios** (not N).
- **D5 — Fold all high-value design-review fixes in** (trust/downside, dot grid, hierarchy reorder, renames, a11y, mobile).

---

## 3. Engine architecture — the keystone (Phase 1)

### 3.1 The unlock (verified)

`model/monte_carlo.py:234-237` applies the blend as pure post-trial algebra on already-computed per-trial arrays:

```python
mix = property_share_mix
mixed_terminal     = mix * p_terminal + (1 - mix) * s_terminal
mixed_outside_cash = mix * p_outside_cash            # only property carries outside-cash demand
mixed_forced_flags = flag_forced_sales(mixed_outside_cash, serviceability_ceiling)
```

Every mix point — and every per-trial-year path — is derivable from one run's unblended arrays. No re-simulation per mix.

### 3.2 The `build_mix_curve` refactor

A pure function builds the curve from the base run's unblended arrays:

```
build_mix_curve(p_terminal, s_terminal, p_outside_cash, p_wealth_path, s_wealth_path,
                ceiling, mixes) -> list[MixPoint]
```

`mixes = np.linspace(0, 1, N)`, default **N = 21** (every 5% property). Each `MixPoint` carries, **all computed from the mix-scaled arrays** (see §5.3 — this is a correctness must-fix):
`mix_pct, median_mixed_wealth, p_solvent, p_succeeds, p_mix_beats_pure_shares, worst_year_cash, total_top_ups, forced_sale_rate`.

Vectorised over the mix axis; arrays are at most `(21, 5000, 40)` ≈ 32 MB — fine.

**Output mapping (must be explicit — the single-run win is illusory otherwise).** Every downstream output maps to exactly one source; **nothing triggers a second `run_monte_carlo` call**:

| Output | Source |
|---|---|
| 3 cards, frontier chart, dial readout | `build_mix_curve` (the curve) |
| Year-by-year wealth fan, per-year tables | post-hoc blend of base-run paths: `mix·p_wealth_path + (1-mix)·s_wealth_path` (verified: `monte_carlo.py:261` does exactly this internally) |
| Terminal-wealth histogram, cashflow-stress chart | post-hoc on base-run per-trial arrays at the selected mix |
| Downside callout + tiles (worst-year cash, total top-ups, forced-sale rate) | mix-scaled arrays at the **selected** mix (§5.3) |

- **Phase-1 Task 0 (verify):** confirm `run_monte_carlo` exposes raw property-only `p_outside_cash` per-trial-year (engineering review located it as `outside_cash_per_trial_year`, raw, ~line 210) and the unblended `p_wealth_path` / `s_wealth_path`. If anything is internal-only, refactor the return to expose it. **Byte-identical** single-mix results required (regression gate).
- Replace `compute_persona_sweep` (11×2,000) with `build_mix_curve` over the single 5,000-trial run; remove its `↻` button + `sweep_key`/`stale` session-state machinery.

### 3.3 Common random numbers (CRN)

Same seed for the base run → all mixes share identical return/rate/vacancy draws; curve reflects the blend, not noise. Preserve the existing seed / seed+1 split (returns vs loan-rate decorrelation).

- **False-precision guard:** CRN makes the curve *look* smooth by design. Show a sampling-noise band (binomial CI ≈ ±0.6ppt at n=5000 on the solvency axis); also note the **wealth axis** carries ≈±2–3% noise, so the "suggested mix" near a flat optimum should be described as a *range*, not a precise point.
- **Student-t caveat (verify):** under `return_distribution="student_t"`, sampling may consume a different number of variates per trial than Gaussian; confirm the "same underlying paths across mixes" guarantee still holds (it should, since there's only one run, but verify the RNG-stream usage).

### 3.4 Rigor fixes — scoped

- **`rental_yield_sigma`: now scheduled as Phase 1b** (see §11), *not* deferred. It is currently plumbed but *unused* (`monte_carlo.py` comment ~line 129; `app.py:305` hard-sets `0.0`), so it does nothing today. It matters for this redesign because the new thesis is downside-honesty: with rent able to move only via vacancy, the bad-year cash crunch is understated. It is sequenced **after** the byte-identical refactor (Phase 1) so the regression gate still proves the refactor changed no numbers; Phase 1b then deliberately changes them with its own before/after calibration check. Implementation contract in §11 (correlated-with-vacancy, calibrated — naive independent σ would double-count vacancy and *overstate* swings).
- **Overflow bucket** (`SHARE_RETURN_FOR_OVERFLOW = 8.5%` constant) — slightly flatters property in bad-share futures; documented, deferred.

### 3.5 Recompute mechanism + state machine (feasible Streamlit)

Mechanism (replaces D3's unachievable timer): on each rerun, hash the *input* parameters into `st.session_state`. If the hash changed, recompute the base run (cached via `@st.cache_data` on the input kwargs) and stash the result in session state; otherwise render the stashed result. Scope the results region in an `st.fragment` so allocation-only interactions (dial/mix) rerun just the fragment and never recompute. **Dial/free-mix are exempt from recompute entirely** (curve lookup only).

| State | Trigger | UI |
|---|---|---|
| Initial load | first paint, no stashed result | spinner "Running 5,000 simulated futures…"; gate the results region |
| Fresh | input-hash matches stash | normal render |
| Recomputing | input-hash changed | render stashed (previous) result dimmed (`opacity:.6`) + "recalculating…" spinner on the results region |
| No-solvent-mix | no mix meets a card/dial threshold | "Not reachable at your cash ceiling — raise the ceiling or deposit"; applies to **all** cards (today only Safe handles `None`); the dial shows a "not achievable above X%" annotation rather than a ring |
| Error | engine raises | `try/except` → "Something went wrong — try a shorter horizon or smaller deposit." (no try/except exists today) |

- **Performance reality (review):** the base run is a Python per-trial loop — likely **multi-second cold**, not sub-second (only `build_mix_curve` is sub-second). With no button, it fires on every input change. Acceptance target to validate in Phase-1 Task 0: **cold base run p95 ≤ ~3s on the reference machine**; if it exceeds this, the fallback is to run it in a background thread (Streamlit ≥1.37) so the dimmed-stale UI stays interactive — *not* to reintroduce a manual button (D3). Either way, dial/mix stay instant.

---

## 4. Information hierarchy & UI (Phase 2)

Main-pane order (UX-lane reorder — viability + downside precede recommendations):

1. **Example-data nudge** — "These are example numbers — change them in the left panel."
2. **Viability flag** — the ✅/⚠️/❌ feasibility flag, moved **above** the cards. Reword the ✅ case from "Comfortable" → "**Within range** — the worst single year stays inside your $X ceiling." Flag uses the **selected-mix** downside (§5.3), not pure-property.
3. **Headline** — dot grid + plain words (§5.1).
4. **Downside callout** — dollars, up front (§5.2–5.3).
5. **Cards** — renamed, live (§4.1).
6. **"See why each mix sits where it does →"** expander — the tradeoff chart + safety dial + free-mix slider (§4.2).
7. **Detail expanders** — year-by-year, distributions/stress, tax/setup (see §4.3 for the comparison-table fate).

### 4.1 Cards

- Rename: **"Safe · 99%", "Balanced · 95%", "Growth-focused · 85%"** (drop "Wealth Maximizer").
- **Remove the ★**; one attributable line: "Unsure? **Balanced (95% safety)** is a common starting point."
- Section header "Recommended allocation for you" → "**What the model suggests at each safety level**." Use "suggests/selects", never "recommended", anywhere in the UI (not-advice; see §8).
- **Card label semantics (review):** each card is `find_optimal_mix` = *the highest-wealth mix whose `p_solvent ≥ threshold`*. The plotted point on the chart is that mix, whose actual solvency may sit slightly above the threshold. Label format: "Balanced · 95%+" (the "+" signals "at least"), and the card shows the point's *actual* solvency. If two cards resolve to the same mix, merge into one card (preserve today's merge behaviour).

### 4.2 Tradeoff chart + dial expander

- **Plain name:** "How much safety does each mix buy?" (not "efficiency frontier", not "Fine-tune").
- **Chart:** x = "Typical outcome after N years" ($), y = "Chance you never run out of cash" (0–100%). Each mix a point; the 3 cards are labelled rings; the selected mix a heavier ring. Add the §3.3 noise band.
- **Dial** = `st.slider` (true on-chart drag isn't supported in Plotly-in-Streamlit). Moves a threshold line; the suggested-mix ring is the highest-wealth mix at/above the dialed safety.
  - **Edges/degenerate (review):** above max achievable solvency → no ring + "not achievable above X%"; below the min → ring snaps to the highest-wealth mix. **Non-monotonic / multi-intersection:** when the threshold line crosses the curve at more than one mix, select per `find_optimal_mix` (max wealth among qualifying) and mark only that point; do not draw multiple rings.
- **Interpolation rule (review):** probabilities (`p_solvent`, `p_succeeds`) interpolate linearly between the 21 points for the dial readout; **dollar/rate fields** (`worst_year_cash`, `total_top_ups`, `forced_sale_rate`) are nonlinear — **snap to the nearest computed mix point**, don't interpolate.
- **Free mix slider** (% property) for direct selection. **Remove the sidebar "Custom mix" slider** (kills the split-brain).

### 4.3 "Compare all mixes" table (resolved)

The existing `render_comparison_table` is now **redundant with the tradeoff chart** (same per-mix data). Decision: **retire the standalone table**; offer the same data as an optional "Show as table" toggle *inside* the tradeoff expander (accessibility fallback for the chart). This fixes the dangling cross-reference that existed in rev 1.

---

## 5. Trust & downside layer (folded into Phase 2 — elevated)

The single biggest gap all design lanes flagged: the downside is currently opt-in (collapsed expander), making the tool's effective output one-sidedly positive.

### 5.1 Headline you can read

- Replace bare "73%" with a **10×10 dot grid** + natural frequency: "**about 7 in 10** of 5,000 what-if **stories built from your numbers**…". **Dot rounding (review):** `round(p_succeeds * 100)` filled green; remaining grey; if the 2×2 taxonomy colours are shown elsewhere, the grid stays two-colour (green = succeeds, grey = not) for legibility.
- **Inline two-sentence explainer** under the headline (not tooltip/footer): the number is *not a forecast* — it's the count of fictional N-year paths, drawn from the ranges the user set, that ended with property ahead and the cash ceiling intact. Avoid "probability/statistically/Monte Carlo".

### 5.2 Downside callout (up front)

Amber callout below the headline, **for the selected mix**:

> "**If it goes wrong:** in the worst 1-in-10 stretches you could need about **$X extra in a single year**, and about **$Y total top-ups (at median) over the hold**. In **Z%** of stories you could have been forced to sell in at least one year. *This comes from the cash-flow model and excludes major repairs, your income stopping, and other personal shocks.* Worth checking it fits your safety net."

- Detail (expander, kept): the **2×2 failure taxonomy** — beats/loses shares × within/over ceiling — each cell a frequency ("18 in 100") + a dollar anchor (cell-median mixed wealth). Define all four cell colours; keep consistent with the dot grid's green/grey.

### 5.3 Downside metric definitions (must be exact + mix-aware)

The current code computes these from the **pure-property** array even when a mix is selected (`app.py:450` uses raw `outside_cash_per_trial_year`) — a correctness bug. All must be recomputed from `mixed_outside_cash = mix · p_outside_cash` at the **selected** mix, in **consistent units** (pick today's-$ or nominal for the whole callout, not mixed):

- **`worst_year_cash` ($X)** = `percentile(mixed_outside_cash.max(axis=1), 90)` — "worst single year, 1-in-10".
- **`total_top_ups` ($Y)** = `median(mixed_outside_cash.sum(axis=1))` — "cumulative top-ups over the hold, at median". State it's the median of per-trial sums (≠ sum of medians). Not additive with $X — label clearly.
- **`forced_sale_rate` (Z%)** = `mean(flag_forced_sales(mixed_outside_cash, ceiling))`. `flag_forced_sales` = `(cash > ceiling).any(axis=1)` — a **single-year** breach detector. Word as "**could have been forced to sell in at least one year**" (accurate), not "would likely have to be sold". Note it is relative to the *user's* ceiling.

**Model-assumption caveat (must-fix — finance lane).** The blend `mixed = mix·property + (1-mix)·shares` and `mixed_outside_cash = mix·p_outside_cash` is a **portfolio-allocation device, not a fractional-property model** — you cannot buy 0.6 of a house, and a real mixed investor cannot sell 40% of the property in a bad year. The linear cash scaling therefore **understates worst-case cash stress at intermediate mixes**. Surface a one-line caveat near the dial/curve ("This blends two full strategies to show an allocation rule — it doesn't model buying a part-property; mid-range mixes may understate a bad year's cash crunch."), and word intermediate-mix downside conservatively.

---

## 6. A/B scenario compare (Phase 3)

- Control near the inputs: "**Save snapshot** / **Compare to saved**" (not a top-of-page toggle — dead state on first visit).
- **Scenario A = the input parameters** (not result arrays). Recompute B's curve live.
- **Persistence (review):** A/B snapshots live in **`st.session_state` only** — *not* the URL. A full parameter snapshot would exceed practical URL limits (~2,000 chars) and risk the project's known malformed-param crash. Snapshots do **not** survive refresh; the existing single-scenario URL persistence is unchanged. (Do not advertise A/B as "shareable".)
- Display: two compact headline mini-cards + **one overlaid tradeoff chart** — A solid, B dashed, same asset-semantic colours (distinguish scenarios by line *style*, not hue); shade the gap; draw the safety-target reference line so the *difference* is primary.
- **Guards (review):** force both scenarios to the **same display mode** (today's-$ vs nominal) and label each scenario with the **regime / comparison-mode it was saved under** (recompute A from its saved params, not the current selectors). If horizons differ, the x-axes differ → **don't overlay**; fall back to two stacked mini-charts with a note.
- **Mobile:** `st.columns(2)` doesn't stack on Streamlit mobile → degrade to `st.tabs()` (A / B / Compare). True side-by-side is tablet+ (≥768px).

---

## 7. Accessibility (folded, Phase 2)

- **Contrast:** `FAINT (#9ca3af)` fails WCAG AA (~2.9:1) — replace with `MUTED (#6b7280)` for text; micro-labels (11–12px) → **≥14px** (audience skews 40–60s).
- **Colourblind:** never colour-only. Keep the "RECOMMENDED/SUGGESTED" text badge; flag emoji ≥16px; chart lines get distinct **dash styles** (property/shares/mix) in addition to colour.
- **Controls:** visible hint where a control's enabled-state depends on another; validate `st.segmented_control` keyboard/screenreader — fall back to `st.radio` if it's a dead zone.
- **Numeracy:** dot grid + "(about 7 in 10)" beside any bare percentage.
- **Acceptance protocol:** run axe-core (via Playwright) on the Fresh, Recomputing, and No-solvent-mix states at 380px and 1280px — zero AA violations.

---

## 8. Not-advice / ethics (folded)

- Replace **every** "recommended" with "suggests / what the model selects" (incl. chart/ring descriptions) — "recommendation to a retail client" has AU regulatory weight.
- The downside callout carries the "excludes repairs / income shocks / other personal shocks" caveat (§5.2).
- A one-line **model-risk caveat** sits adjacent to any solvency % in the main flow (not only the footer): the % is the fraction of model paths, sensitive to the assumptions you entered; tax changes are announcement-only.
- Keep the existing four not-advice disclaimers.

---

## 9. Out of scope (YAGNI)

- **Deeper model** (offset account, 2nd property/portfolio, margin-call mode, capex, mid-period rebalancing) — deferred (review ranked it a trap until UX + model are solid).
- **> 2 compare scenarios; A/B URL-sharing.**
- **"% property ahead by year" line; retiring the terminal-wealth histogram** — later polish.
- **A precise forced-sale economic model** beyond the ceiling-breach flag.

---

## 10. Testing

Per project rule (`CLAUDE.md`): test malformed/boundary inputs explicitly — "tests pass" ≠ "works" (a shared URL once crashed with 138 green tests).

- **Engine equivalence:** `build_mix_curve` at a mix == a full single-mix `run_monte_carlo` for that mix (byte-identical regression; the refactor changes no numbers).
- **Mix-aware downside:** `worst_year_cash`/`total_top_ups`/`forced_sale_rate` at the selected mix are computed from `mix·p_outside_cash`, not pure property; at mix=0 (pure shares) worst-year cash and forced-sale rate are **0**.
- **CRN smoothness:** fixed seed → `p_solvent` near-monotonic in mix; suggested mix stable across repeated runs; verify under both `gaussian` and `student_t`.
- **Rent variance (Phase 1b):** `rental_yield_sigma = 0` → byte-identical to Phase 1; `> 0` → total rental-income variance rises ≤~30% vs vacancy-only (no double-count); the rent-level shock is correlated with vacancy and drawn from a distinct RNG stream (`seed+2`, uncorrelated with return paths).
- **Deflation contract:** curve built in nominal $; deflation applied per-render; deflated and nominal callouts never mixed; today's-$ paths still correct.
- **comparison_mode:** curve recomputes on mode switch and is labelled with the active mode.
- **States:** input-hash change → Recomputing → Fresh; dial/mix moves never recompute; all three cards handle `None`; `try/except` renders the error state.
- **New persisted state:** clamp dial-safety + free-mix on read *and* write (extend the existing malformed-persona URL test to the new params); A/B snapshot is session-only and never written to the URL.
- **A/B:** saving A captures params; changing inputs doesn't mutate A; B recomputes; differing-horizon overlay falls back to stacked charts.

---

## 11. Phasing

- **Phase 1 — Engine + auto-recompute:** verify/expose unblended arrays (Task 0, incl. perf p95 target) → `build_mix_curve` (mix-aware metrics) → CRN → output mapping (no second run) → remove sweep + `↻` button → input-hash recompute + `st.fragment` + state machine + `try/except`. Tests §10. **Gate: byte-identical single-mix results.**
- **Phase 1b — Rent-level variance:** lands *after* Phase 1's byte-identical gate, then deliberately changes the numbers. Implementation contract:
  - Generate a per-year rent-level path and consume it in the property trial loop (today `rental_yield_sigma` is plumbed but the loop ignores it — `gross_yield` is a scalar; this requires patching the loop, not just a config default).
  - **Correlate the rent-level shock with vacancy** (bad markets bring empty weeks *and* soft rent together) so it doesn't double-count the income variance vacancy already models. Give it a distinct RNG stream (e.g. `seed+2`) so it doesn't correlate with the return paths.
  - Default shape: AR(1) persistence ≈0.7, annual innovation σ≈0.5% (slow structural rent drift, not i.i.d. white noise). Expose a small UI default; keep it in the Advanced group.
  - **Acceptance:** total annual rental-income variance rises sensibly vs vacancy-only (target ≤~30% increase, not ~2×); the downside callout's bad-year cash rises modestly, not implausibly; a before/after snapshot documents the deliberate number change (the only place the refactor's "no number change" rule is intentionally broken).
- **Phase 2 — Flexible UI + trust/downside + a11y:** hierarchy reorder, dot-grid headline + explainer, mix-aware downside callout + caveat + 2×2 taxonomy, cards renamed/de-steered, tradeoff+dial expander (+ table-as-toggle), remove sidebar custom slider, a11y fixes, "suggested" language sweep.
- **Phase 3 — A/B compare:** session-only snapshot + overlaid/ stacked tradeoff + same-display-mode/regime guards + mobile `st.tabs()`.

Each phase ships standalone.

---

## 12. Open assumptions / risks

- **Streamlit recompute UX:** input-hash + `st.fragment` is the chosen mechanism; a timed debounce + "✓ pulse" would need a JS component (deferred). Validate the fragment scopes correctly (inputs in sidebar, results region in the fragment reading from session state).
- **Base-run cost** (multi-second cold) is the main live-feel risk; background-thread fallback if p95 > ~3s. No manual button (D3).
- **Plotly-in-Streamlit** can't do on-chart drag; dial is a slider with an animated transition between the 21 points (imperfect at fast dragging).
- **Linear-blend honesty** (§5.3 caveat) — the curve is an allocation-rule device, not a fractional-property model; intermediate-mix cash stress is understated.
- **Curve resolution** (21 points + snap/interpolate split) assumed adequate; revisit near flat optima.
- **Mobile** remains a Streamlit weak spot (sidebar collapses to a hamburger hiding the inputs); A/B is tablet+/tabbed. A fuller mobile pass is out of scope.
