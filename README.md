# Property vs Shares Model

Personal-use Monte Carlo simulator comparing AU residential investment property vs shares.

See full design spec at `../2026-05-11-property-vs-shares-design-v2.md`.

## Status

**v1 shipped 2026-05-11.** **v1.1 + UI redesign shipped 2026-05-16.** **v2 (2026-06-07):** full
"mum & dad" usability redesign — plain-English recommendation-first UI, year-by-year breakdown
(wealth fan chart + per-year financial table), income→tax-rate, not-financial-advice disclaimer,
input validation, URL-shareable scenarios, semantic-colour design system, and a finance fix that
taxes the overflow share bucket (dividend tax + terminal CGT). **123/123 tests passing.**

**Headline finding for the default scenario under restricted_2027 regime:** the optimal allocation
is **~60% property / 40% shares**, not 100% property — beyond 60% the strategy is solvent in fewer
than 95% of futures and the wealth gain doesn't justify the risk. Under current rules, pure
property remains rational. See `BACKLOG.md` "Done since v1" for the full session ledger.

Outstanding work is only larger v1.2 features (Mode B margin calls, idiosyncratic shocks, capex
events, offset account, other states) — tracked in [`BACKLOG.md`](./BACKLOG.md).

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Browser opens to a tool with sliders. Drag them, see the headline change live.

## Deploy (shareable link for non-technical users)

Hosted free on **Streamlit Community Cloud** straight from this GitHub repo:

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with the GitHub account that owns this repo.
2. **Create app** → pick `AidenHiew/property-vs-shares`, branch `main`, main file `app.py`.
3. Under **Advanced settings**, set Python version to **3.13** (the repo targets 3.11–3.13; the local
   `.venv` is 3.14 but Cloud doesn't use it).
4. **Deploy.** Dependencies install from `requirements.txt`; the app is then a URL anyone can open.

A tuned scenario lives in the page URL (query params), so you can bookmark or share a specific setup.

## Test

```bash
pytest -v
```

## Key features

- **Recommendation-first UI** — three persona cards (Safe / Balanced / Wealth Maximizer)
  lead the main pane. Each represents a safety appetite (≥99% / ≥95% / ≥85% chance of
  staying within your serviceability ceiling); the optimizer computes the allocation that
  delivers that safety with the most wealth. Allocations shift dynamically with inputs.
- **Allocation-mix slider (0–100% property)** — wealth-level blend per Monte Carlo trial.
  PM-grade reframing of the "property vs shares" question into "what mix?"
- **Joint success metric** — `P(property wins AND stays solvent)`. The honest headline
  that accounts for trials where the strategy "won on paper" but the user would have
  been forced to sell along the way.
- **Federal Budget 2026-27 regime toggle** — restricted negative gearing (rental losses
  quarantined to residential property income/gains) + transitional CGT (50% discount on
  pre-commencement gain, indexed cost base + ≥30% effective rate on post-commencement
  gain). Both effective 1 Jul 2027 for established residential property bought after 12
  May 2026. New builds auto-coupled to current rules per the announcement carve-out.
- **Opt-in Student-t innovations** — fatter-tailed returns AND loan-rate distributions
  (df=5 default; AU rates are empirically fat-tailed: 1989, 2022). Realized σ rescaled to
  match user-specified σ. Toggle in Advanced.
- **Two comparison modes:** Realistic (what investors actually do) and Fair fight
  (matched leverage exposure).
- **Equal outside-cash contributions** — both strategies deploy identical total capital
  each year.
- **AU tax engine:** FY2026 Stage 3 brackets, negative gearing, franking credits with
  refund, CGT 50% discount, SA stamp duty + land tax (acquisition costs included in CGT
  cost base per ATO rules), depreciation per property age.
- **5,000 Monte Carlo trials** with correlated property & share returns (plus a 2,000-trial
  mix sweep at 11 points to drive the persona recommendations).
- **Standard / Advanced inputs split** — clean default form, power-user knobs behind one
  expander.
- **Detail expanders** for the curious: comparison table across all 11 mix points
  (highlighting the recommended row), and the original terminal-wealth histogram +
  cashflow-stress chart (now demoted from lead).
- **Year-by-year wealth path arrays** exposed on the result objects (`wealth_per_year`)
  for any future path-dependent visualization or analysis.

## Known limitations (v1)

- South Australia only for state-level taxes
- Investment property only (no PPOR)
- Single property at a time (no portfolio mode)
- Mode B does not model margin-call risk (warning surfaced in UI)
- Buy-and-hold share portfolio (no mid-period rebalancing CGT)
- Excludes Medicare Levy / MLS, HECS, SMSF, capital works recapture, LMI

See spec §15 (Open assumptions) and §16 (v1.1 backlog) for full detail.

## When tax law changes

Most updates only require editing `config.py` (brackets, rates, thresholds).

**Federal Budget 2026-27 — modelled.** Restricted negative gearing AND transitional CGT
(50% discount → CPI-indexed cost base + 30%-min effective rate). Both effective 1 Jul 2027
for established residential property bought after 7:30pm 12 May 2026. Toggle "Negative
gearing & CGT regime" in the sidebar. Design rationale and review feedback in
`docs/2026-05-16-budget-2026-27-design.md`.

⚠ Both changes are **announcement-only and not yet legislated**. The model uses simplified
interpretations:
- `max(MTR, 30%)` floor for the 30% minimum rate (does not model bracket creep,
  Medicare levy, or offsets)
- Loss pool assumes the investor has no other residential property income or gains
- Commencement value = modelled property value at end of model year 1 (transitional split)
- Selling costs allocated to post-commencement; Div 43 split by year claimed
- Loss pool offsets post-commencement gain only (conservative — pool cannot reach back
  into the pre-commencement period)

Revisit when legislation passes.
