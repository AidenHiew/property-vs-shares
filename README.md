# Property vs Shares Model

Personal-use Monte Carlo simulator comparing AU residential investment property vs shares.

See full design spec at `../2026-05-11-property-vs-shares-design-v2.md`.

## Status

**v1 shipped 2026-05-11.** All 27 planned tasks complete, 66/66 tests passing, end-to-end smoke
validated (default scenario: P(property wins) ≈ 76%, median property $2.11M vs shares $1.14M,
worst-year cash $15.9k, P(solvent) 99.7%).

Outstanding follow-ups before using this for a *second* real allocation decision are tracked in
[`BACKLOG.md`](./BACKLOG.md) — start there when picking the project up again.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Browser opens to a tool with sliders. Drag them, see the headline change live.

## Test

```bash
pytest -v
```

## Key features

- **Two comparison modes:** Realistic (what investors actually do) and Fair fight (matched leverage exposure).
- **Equal outside-cash contributions:** both strategies deploy identical total capital each year.
- **Solvency tracking:** flags trials where property cashflow exceeds your serviceability ceiling.
- **AU tax engine:** FY2026 Stage 3 brackets, negative gearing, franking credits with refund, CGT 50% discount, SA stamp duty + land tax, depreciation per property age.
- **5,000 Monte Carlo trials** with correlated property & share returns.
- **Standard / Advanced inputs split** — clean default form, power-user knobs behind one expander.

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
