# Design — Onboarding, Clarity & Australia-Wide pass

**Date:** 2026-06-09
**Status:** Approved direction; spec under review
**Scope:** Four coordinated changes to the Property vs Shares Streamlit app, all serving one goal — a first-time, non-expert ("mum & dad") user lands, understands what they're seeing, gets a recommendation that matches the detail below it, and can run it for any Australian state.

---

## Part 1 — Onboarding hero + bottom guide

**Problem:** A new user lands with no idea what the tool does, what to enter, or its limits. Assumptions exist but are buried in a collapsed "Setup & tax rules used" expander at the very bottom.

**Solution (one-page, approach A — mocked on :8502; refined to "lighter" weight per UX review):**

> **IMPORTANT — replace, don't stack.** `app.py` already has a hero (`pvs-h1` + `pvs-sub`, ~lines 365–370). The new onboarding **replaces** that existing hero. Do NOT add a second hero above it.

Top of page (above the calculator):
1. **Hero (replaces the existing one)** — `🏡 Property vs Shares — should you buy an investment property, buy shares, or mix both?` + a plain-English sub-line: what it does (5,000 what-if futures for *your* numbers), that it shows wealth + cashflow safety, and that it's a what-if explorer, **not advice**.
2. **Slim "How to use" banner** — a single compact horizontal strip (NOT three tall green cards): `1 Enter your numbers → 2 Read your recommendation → 3 Dig into the breakdown`. One line of helper text each, lightweight. Keeps the cards as the visual hero.

Below the persona cards (NOT above):
3. **Amber "Before you trust the numbers" callout** — moved below the cards so users see output before caveats. Limitations: state-tax caveat, single property, simplified costs, **land tax = user-supplied flat field (default 0)**, Budget 2026-27 announcement-only, not financial advice.

Bottom of page:
4. **"📖 Full guide & assumptions" expander** — absorbs the existing "Setup & tax rules used" content and adds: *What am I looking at?* (the same-cash fair-race explanation), *What each input means* (input glossary — reference depth, no workflow narrative to avoid overlap with the slim banner), *Key terms* (solvent, typical wealth, safety appetite), *Assumptions & limits*. **Assumptions must include the flat-MTR disclaimer:** *"Tax uses your current marginal rate held flat for the whole period — it does not model bracket creep, the Medicare levy, per-year income changes, or a rental loss dropping you a bracket. Your marginal rate drives negative gearing, CGT (both sides), and dividend/franking tax."* Plus the land-tax-default-0 note (Part 4).

**Files:** `app.py` / new `ui/onboarding.py` (see Architecture). Replace existing hero; remove/merge the existing bottom "Setup & tax rules" expander into the new guide.

---

## Part 2 — Fix the persona ↔ breakdown disconnect

**Problem:** The persona cards *look* clickable but are static HTML. The headline + year-by-year breakdown below are driven by the **sidebar mix slider**, not the recommended persona. Result: cards say "50% property recommended" while the breakdown shows whatever the slider/URL holds (e.g. 100%) — a confusing contradiction. User intuition is "click Wealth Maximizer → see its breakdown."

**Solution:**
- Add a **segmented control** directly under the persona cards: `View breakdown for: [Safe] [Balanced ★] [Wealth Maximizer] [Custom]`. Default = Balanced (the recommendation). Use `st.segmented_control` — available since Streamlit 1.36; repo pins **≥1.57**, so it is safe.
- The selection drives the **mix used for the headline + year-by-year breakdown** below. Picking a persona shows *that* persona's mix breakdown.

**State precedence — RESOLVED (was deferred; UX review flagged it as load-bearing):**
- The **segmented control is ALWAYS the single driver** of the breakdown mix. No "last-touched-wins", no hidden session-state flag.
- **"Custom" is the 4th option** in the segmented control. The sidebar mix slider is **greyed/disabled unless "Custom" is selected.** Selecting Custom enables the slider; the breakdown then follows the slider. This removes the dual-control contradiction entirely.
- **Stale-sweep handling:** when inputs changed but the sweep hasn't rerun (`stale == True`), suppress the ★ on Balanced and disable/grey the persona options (show the "↻ Update recommendations" prompt) so the control can't act on stale recommendations.

**URL contract — RESOLVED:** the current `?mix=` query param fights the persona control on shared-link load. **Replace `?mix=` with `?persona=` (values: safe/balanced/wealth/custom; custom also carries `?mix=`).** On load, map `persona` → segmented-control selection. This keeps shareable links working without a slider-vs-persona conflict.

This **also fixes the recommendation/breakdown mismatch** (Part 3 item 2) for free — the breakdown now follows the chosen recommendation.

**Note on figures (document in guide):** persona cards come from the 2,000-trial sweep; headline tiles/breakdown from the 5,000-trial main run. Median wealth / worst-year cash will differ slightly between the two. Either align trial counts or state this in the guide. Decision: **state it in the guide** (cheaper than 2.5× sweep cost). Also ensure deflation (Today's-$ toggle) is applied consistently — sweep currently isn't deflated; either deflate sweep figures or note cards are always nominal.

**Why a segmented control, not clickable cards:** Streamlit's injected-HTML cards can't cleanly be interactive buttons; a native segmented control is reliable, obvious, and accessible. Same UX outcome.

**Files:** `app.py` / new `ui/persona.py` (persona section + the breakdown section's mix source).

---

## Part 3 — Two bug fixes

1. **`$` LaTeX rendering glitch** — Streamlit markdown treats `$...$` as inline LaTeX, italicising any text between two dollar signs. This is **app-wide**, not one line: `_fmt_money()` returns strings like `"$700k"`, and f-strings interpolate `${income:,}` / `${buying_costs:,}` directly into `st.markdown` bodies (e.g. lines ~696–701). Fix: **audit every `st.markdown` call containing a `$`.** Escape with `\$` is version-fragile; prefer wrapping dollar values in an HTML `<span>` (the app already uses `unsafe_allow_html=True`) or routing plain dollar text through `st.text`/`st.write`. Add a visual smoke check (Chrome) confirming no stray italics remain.
2. **Recommendation/breakdown mismatch** — resolved by Part 2.

**Files:** `app.py`.

---

## Part 4 — Australia-wide stamp duty (hybrid), land tax excluded

**Problem:** Stamp duty is hardcoded to SA (`sa_stamp_duty`). Only stamp duty + land tax are state-specific; income tax, negative gearing, CGT, franking are all federal and already national.

**Decisions:**
- **Hybrid state selector:** a **State** dropdown in the sidebar (NSW/VIC/QLD/WA/SA/TAS/ACT/NT). Selecting a state **prefills an editable stamp-duty field** from that state's official schedule. User can override the prefilled number (safety net for stale tables / edge cases).
- **Land tax: USER-SUPPLIED FLAT FIELD (decision changed from "exclude entirely").** Replace the per-state `sa_land_tax` schedule with a single editable sidebar input: **"Annual land tax ($), default 0"**, applied as a constant annual holding cost for the full horizon. Rationale: the tax review showed land tax is *material* over a 25-year hold for NSW/VIC (~$21–53k PV, net of the lost deduction), so silently excluding it understates the property's cost. A flat field keeps the engine simple (no per-state land-tax tables/upkeep) while letting users who care include a real figure.
  - **Wiring:** feed the flat amount into the existing `cash_costs_path` AND the taxable-income deduction (land tax is deductible). The existing cost+deduction plumbing then yields the correct **net annual drag of `land_tax × (1 − MTR)`** automatically — do not special-case it.
  - **Default 0** preserves current behaviour by default, but now visibly and controllably. Guide states: "Land tax is off by default. It's a real annual cost (often $1k–$15k+ depending on state and land value) and is tax-deductible — enter your state's figure for an accurate property cost. Leaving it 0 makes property look slightly cheaper than reality."
- **Out of scope:** per-state land-tax *tables*, WA MRIT, foreign-purchaser / absentee surcharges (stamp duty AND land tax), land-value basis. (The flat field replaces all the land-tax modelling complexity.)

### 4a. Typed band evaluator

The current `sa_stamp_duty` is a simple marginal-band function. National data needs **three band shapes**:

1. **Marginal** — `(upper, base_at_lower, rate)`; duty = base + rate × (price − lower). Most states.
2. **Flat-% of full value** — within the band, duty = pct × full price (NOT marginal). VIC $960k–$2M, ACT top band, NT upper bands.
3. **Quadratic** — NT for value ≤ $525,000: `D = 0.06571441 × V² + 15 × V`, where `V = price / 1000`.

Design: represent each state's schedule as a list of typed segments; a generic evaluator handles `marginal` and `flat_pct` segments; NT's quadratic lower range is a small dedicated branch. `stamp_duty(state, price)` dispatches. The `FLAT` placeholder in the tables below is a sentinel (segment kind = `flat_pct`, duty = `rate × full price`), distinct from a marginal base of 0 — make the data representation explicit (a `kind` tag per segment, not a magic base value).

**KNOWN, LEGISLATED DISCONTINUITIES (verified — these are NOT bugs; tests must assert them, and the evaluator must not assume duty rises monotonically by $1):**
- **VIC** — step **UP** +$130 at $960,000→$960,001 (marginal $52,670 → flat 5.5% = $52,800).
- **ACT** — the flat 4.54%-of-full-value top band crosses the last marginal band around $1,454,301, producing a small step **DOWN** (~$13) near the $1,455,000 boundary. **Verify the exact upper bound and behaviour against the ACT Revenue online calculator at $1,454,000 / $1,455,000 / $1,456,000 before coding** — the spec's $1,455,000 boundary may need adjusting to $1,454,301.
- **NT** — step **UP** +$24,000 at $3,000,000 (4.95%→5.75% of full value) and +$10,000 at $5,000,000 (5.75%→5.95%).
- **VIC above $2M band:** state its lower bound explicitly as $2,000,000 in the data — do not rely on iterator state, because the preceding FLAT band breaks the usual "lower = previous upper" chain.
- **TAS first band** `(3_000, 50, 0.0)` is a degenerate marginal band giving a flat $50 minimum for any price ≤ $3,000 — document as intentional; evaluator's `base + rate×(price−lower)` with lower=0 handles it.

**Rounding:** use each state's **officially published** base figures verbatim (e.g. NSW $212, WA $28,453) even where exact arithmetic gives a half-dollar — the official table is the source of truth. Tests assert official values, not recomputed ones.

**SA transfer fee:** the old `sa_stamp_duty` adds a fixed SA transfer/registration fee. The new national `stamp_duty()` should **drop state-specific registration fees** (they're separate-agency fees, e.g. Land Services SA / LRS) and let the existing `buying_costs` input approximate them. Document this so SA results shift slightly vs the old code (and update the SA parity test accordingly).

### 4b. Verified stamp-duty schedules (FY2025-26, all ✅ direct-fetched from official state revenue offices 2026-06-09)

Tuples are `(upper_price_bound, base_duty_at_lower_bound, marginal_rate)` unless flagged FLAT (flat-% of full value) or noted.

**NSW** — Revenue NSW (marginal):
```
(17_000,      0,       0.0125)
(37_000,      212,     0.0150)
(99_000,      512,     0.0175)
(372_000,     1_597,   0.0350)
(1_240_000,   11_152,  0.0450)
(3_721_000,   50_212,  0.0550)
(None,        186_667, 0.0700)
```

**VIC** — SRO Victoria (non-PPR). $960k–$2M band is FLAT 5.5% of full value:
```
(25_000,      0,       0.014)   # marginal
(130_000,     350,     0.024)   # marginal
(960_000,     2_870,   0.060)   # marginal
(2_000_000,   FLAT,    0.055)   # flat 5.5% of FULL dutiable value
(None,        110_000, 0.065)   # marginal above $2M
```

**QLD** — QRO (general transfer duty, marginal):
```
(5_000,       0,       0.000)
(75_000,      0,       0.015)
(540_000,     1_050,   0.035)
(1_000_000,   17_325,  0.045)
(None,        38_025,  0.0575)
```

**WA** — RevenueWA (general rate, marginal):
```
(120_000,     0,       0.0190)
(150_000,     2_280,   0.0285)
(360_000,     3_135,   0.0380)
(725_000,     11_115,  0.0475)
(None,        28_453,  0.0515)
```

**SA** — RevenueSA (conveyance, marginal; refreshes current code):
```
(12_000,      0,       0.010)
(30_000,      120,     0.020)
(50_000,      480,     0.030)
(100_000,     1_080,   0.035)
(200_000,     2_830,   0.040)
(250_000,     6_830,   0.0425)
(300_000,     8_955,   0.0475)
(500_000,     11_330,  0.050)
(None,        21_330,  0.055)
```

**TAS** — SRO Tasmania (marginal; first band $50 flat minimum):
```
(3_000,       50,      0.000)   # $50 flat minimum
(25_000,      50,      0.0175)
(75_000,      435,     0.0225)
(200_000,     1_560,   0.035)
(375_000,     5_935,   0.040)
(725_000,     12_935,  0.0425)
(None,        27_810,  0.045)
```

**ACT** — ACT Revenue Office (non-owner-occupier). Top band FLAT 4.54% of full value:
```
(200_000,     0,       0.0120)  # marginal
(300_000,     2_400,   0.0220)  # marginal
(500_000,     4_600,   0.0340)  # marginal
(750_000,     11_400,  0.0432)  # marginal
(1_000_000,   22_200,  0.0590)  # marginal
(1_455_000,   36_950,  0.0640)  # marginal
(None,        FLAT,    0.0454)  # flat 4.54% of FULL value above $1.455M
```

**NT** — Territory Revenue Office (Stamp Duty Act 1978 Sch 1). Quadratic ≤ $525k, then flat-% of full value:
```
price <= 525_000:  D = 0.06571441 * (price/1000)**2 + 15 * (price/1000)
525_000 < price < 3_000_000:   0.0495 * price   # flat of full value
3_000_000 <= price < 5_000_000: 0.0575 * price  # flat of full value
price >= 5_000_000:             0.0595 * price   # flat of full value
```
**NT has no land tax** (confirmed — irrelevant now land tax is excluded).

**Provenance:** every figure ✅ read directly from the official revenue office this session (8 parallel Sonnet research agents, 2026-06-09); NSW land tax & VIC flat-band independently re-verified by direct fetch on the main thread. Source URLs captured in the agent transcripts; key pages: revenue.nsw.gov.au, sro.vic.gov.au, qro.qld.gov.au, wa.gov.au (Treasury), revenuesa.sa.gov.au, sro.tas.gov.au, revenue.act.gov.au, legislation.nt.gov.au.

**Files:** `model/tax.py` (new `DUTY_SCHEDULES` + typed evaluator + `stamp_duty(state, price)`; retire `sa_stamp_duty` + `sa_land_tax` + `SA_LAND_TAX_BANDS`), `model/property_strategy.py` (replace per-value `sa_land_tax(v)` at line ~180 with the flat user-supplied annual amount; keep it in `cash_costs_path` (193) and the deduction (196) so the `×(1−MTR)` net is automatic; `land_value_path` likely becomes unused — remove if so), `model/monte_carlo.py` (thread `state` + `annual_land_tax` through), `app.py` / `ui/` (state dropdown, editable stamp-duty field prefilled from state, editable annual-land-tax field default 0; clean up the now-dead `sa_stamp_duty` import at line 16; update the disclaimer at line ~722 from "South Australia tax tables only" to national).

---

## Part 5 — Symmetric shares breakdown (table + build chart)

**Problem:** The year-by-year breakdown gives property 8 columns ([app.py:336](app.py)) but shares only ONE ("Shares value"). Users can't see *how* share value grows — cash injected vs dividends reinvested vs market growth — so the comparison feels unfair/opaque.

**Solution:**
- **Split the single breakdown table into two parallel tables:** "Property — year by year" (existing columns, unchanged) and a new "Shares — year by year".
- **Shares table columns (full parity):** `Year · Cash injected · Dividends reinvested · Capital growth · Dividend tax · Share value`.
  - *Cash injected* = the year's external contribution (= property's out-of-pocket cash; identical by design — this is the fair-comparison anchor).
  - *Dividends reinvested* = gross dividends (DRP on).
  - *Capital growth* = price-appreciation slice of the portfolio that year.
  - *Dividend tax* = net dividend tax paid (after franking).
  - *Share value* = end-of-year mark-to-market (existing).
- **New stacked-area "What builds your share value" chart:** cumulative cash injected + cumulative reinvested dividends + cumulative market growth, stacking up to the median share-value line. Visual parity with the property equity story.

**Engine surfacing (most data already exists):**
- Already surfaced: `shares_dividend_path`, `shares_dividend_tax_path`, `shares_wealth_path`.
- **NEW per-year paths to add** to `SharesResult` + `run_monte_carlo` output:
  - `shares_contribution_path` — the `external_contributions` array per trial (currently set at [monte_carlo.py:200](model/monte_carlo.py) but not surfaced).
  - `shares_capital_growth_path` — `portfolio_value_before_year × capital_return` per year (the price-appreciation $; `capital_return = total_return − dividend_yield`, already computed inside `simulate_shares_trial`, [shares_strategy.py:75-76](model/shares_strategy.py)).
- Both new paths must be added to the deflation `per_year_keys` list ([app.py:548](app.py)) so Today's-$ mode scales them.

**Files:** `model/shares_strategy.py` (two new `SharesResult` fields + populate them), `model/monte_carlo.py` (allocate + surface the two arrays), `app.py`/`ui/` (split table into two; new stacked-area chart; add keys to deflation list).

## Testing

- **Duty evaluator — mandated boundary points** (assert exact official values, including the legislated jumps — do NOT write a monotonic-continuity assertion):
  - VIC: $959,999 / $960,000 / **$960,001** (assert +$130 step-up) / $2,000,000.
  - ACT: $1,454,000 / **$1,455,000** / $1,456,000 (assert the step-down once the exact bound is calculator-verified).
  - NT: $524,999 / $525,000 / $525,001 (quadratic↔flat seam) / $2,999,999 / **$3,000,000** (+$24k) / $4,999,999 / **$5,000,000** (+$10k).
  - SA: parity vs the *old* `sa_stamp_duty` MINUS the dropped transfer fee (update expected value).
  - TAS: any price ≤ $3,000 returns exactly $50.
  - One mid-range point per state (~$700k) cross-checked against that state's official online calculator.
- **Land tax flat field:** property-strategy tests — annual cost includes the flat amount; the taxable-income deduction includes it; net drag ≈ `amount × (1 − MTR)`; default 0 reproduces the no-land-tax baseline.
- **Persona control — all four code paths** (not just happy path): (a) three personas → same mix (merged single card), (b) Safe Player unreachable (no ≥99% allocation), (c) stale sweep + persona switch (★ suppressed, control disabled), (d) `?persona=` URL param maps to the right selection on load; Custom enables the slider.
- **`$` rendering:** visual smoke check (Chrome) — no stray italics anywhere dollar amounts appear.
- Full suite (currently 123 tests) green before/after; new tests added for the above.

## Architecture (adopted from review)

`app.py` is ~720 lines and this work adds render + state logic. Since Part 4 already touches `model/`, do a **focused split** (not speculative refactoring):
- `ui/onboarding.py` — hero, slim how-to banner, amber callout, full-guide expander.
- `ui/persona.py` — persona sweep, card rendering, segmented control + state precedence.
- Model logic stays in `model/`; `app.py` becomes orchestration only.
- Inject `GLOBAL_CSS` **once** at page load (currently re-injected per component — fragile); fix the `{H}` string-`replace` templating to a named format/f-string while touching `ui/persona.py`.

## Out of scope (documented as assumptions/limits)

- Per-state land-tax *tables* — replaced by a single user-supplied flat annual field (default 0).
- WA MRIT, foreign-purchaser & absentee surcharges (stamp duty AND land tax), land-value basis.
- State registration / transfer fees (Land Services SA, NSW LRS, etc. — separate agencies) — `buying_costs` approximates incidental costs.
- Per-state first-home / owner-occupier concessions (tool models an investment purchase).

## Cleanup

- Remove the disposable `mock_hero.py` once Part 1 is implemented.

## Review provenance

This spec was revised after two parallel adversarial expert reviews (2026-06-09): an AU-tax/financial-modeling lens and a Streamlit-UX/architecture lens. Folded in: band-discontinuity test mandates, the `×(1−MTR)` land-tax framing, the segmented-control state-precedence + URL-param resolution, the app-wide `$`-audit scope, the ui/ module split, and the onboarding "lighter" weight. User decisions: land tax → flat editable field (default 0); onboarding → lighter (slim banner, callout below cards).
