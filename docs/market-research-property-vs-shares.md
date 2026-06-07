# Property vs Shares Calculator — Market Research

*Research date: 2026-05-10. Market: Australia (Adelaide-based user). Proposed model: free web tool, donation + ads monetisation.*

## 1. Existing Tools

### Australia — direct competitors

- **[Best ETFs Australia — Property v Shares v Offset Calculator](https://www.bestetfs.com.au/tools/property-shares-offset/)** — run by **The Rask Group**. The closest direct competitor. Free, three-way side-by-side comparison (property / shares / offset), models negative gearing, franking, CGT, stamp duty, leverage, depreciation. Charts plus risk/liquidity ratings. Funnels to paid "Rask Core" membership. Recently maintained.
- **[austax.tools — Negative Gearing Calculator](https://austax.tools/negative-gearing-calculator/)** — 1–30 yr property vs ETF projection with CGT, selling costs, year-by-year gearing flip. Uses 2025-26 ATO rates. Free.
- **[Property Tax Tools](https://propertytaxtools.com.au/calculators/investment-property-calculator/)** — ROI / CAGR / cash-on-cash, separate franking-credits calc. Free, well-maintained.
- **[InvestmentPropertyCalculator.com.au](https://www.investmentpropertycalculator.com.au/)** — downloadable Excel; dated UI but comprehensive.
- **[Your Mortgage](https://www.yourmortgage.com.au/calculators/negative-gearing)**, **[YIP Magazine](https://www.yourinvestmentpropertymag.com.au/calculators/negative-gearing)**, **[Savings.com.au](https://www.savings.com.au/calculators/negative-gearing-calculator)**, **[TMS Financial](https://www.tmsfinancial.com.au/negative-gearing-calculator/)** — all single-purpose negative-gearing calcs, lead-gen for brokers / accountants.
- **[Moneysmart (ASIC)](https://moneysmart.gov.au/)** — has compound-interest, managed-funds-fee, mortgage and super calcs but **no property-vs-shares comparison tool**. Surprising gap given their mandate.
- **[Hudson Financial Planning](https://hudsonfinancialplanning.com.au/resources/education-reports/investing-in-property-vs-shares/)** and **[ProSolution](https://prosolution.com.au/property-versus-shares/)** — articles with embedded modelling, not interactive tools.
- **Big banks (CBA / NAB / Westpac / ANZ)**, **Domain / PropTrack / CoreLogic** — mortgage and yield calcs only; no head-to-head shares comparison.
- **Sharesight / Pearler / Stake** — portfolio trackers, not comparison calculators. Sharesight lets you add property as a custom asset but doesn't model negative gearing or depreciation.
- **Blogs**: [Aussie Firebug](https://www.aussiefirebug.com/property-vs-shares/) and [Strong Money Australia](https://strongmoneyaustralia.com/) cover the debate qualitatively; AFB has a super-vs-outside-super calc but no full P-vs-S simulator.

### International (context only)

- **NYT Rent vs Buy** (paywalled, US property tax model) — gold-standard UX but not investment-vs-investment.
- **BiggerPockets, Empower (ex-Personal Capital)** — US tax-coded; useless for AU users.

## 2. Gaps in the Market

The Rask tool is genuinely good and covers the hardest tax mechanics. Realistic gaps:

- **Sequence-of-returns / Monte Carlo** — everything uses flat-% growth assumptions. None show distributions or downside scenarios.
- **Land tax by state** — SA-specific land-tax thresholds rarely modelled; almost all tools assume NSW or generic.
- **SMSF-buying-property** scenarios — barely covered outside paid accountant tools.
- **Cashflow-over-time visualisation** — most show end-state numbers, not the year-7 "can I actually afford this?" cashflow squeeze.
- **Honest sensitivity analysis** — "what if rates hit 8%? what if vacancy is 8 weeks? what if ETFs return 6% not 9%?" toggles are rare.
- **Behavioural / liquidity framing** — Rask gestures at this; nobody does it well.
- **Mobile UX** — most existing tools are desktop-form-heavy and hostile on phones.

## 3. Monetisation Reality Check

**Donations + ads is brutal at low traffic.** Finance-niche RPMs are genuinely high ($30–50 in Tier-1 markets per [Publift / MonetizeMore](https://www.monetizemore.com/ad-revenue-calculator/)), but you need **tens of thousands of monthly sessions** before that's coffee money. AU finance-calc traffic is dominated by SEO incumbents (Moneysmart, big banks, Canstar, Finder) who outrank a new domain for years. Donations on free finance tools rarely cross hobby-income territory — the few examples that work (Wikipedia, ProPublica) have brand and mission moats. A solo calculator does not.

**Realistic outcome at 12 months:** sub-$200 / month from AdSense + maybe one $50 PayPal donation. Affiliate links to brokers (Pearler, Stake, Vanguard) or accountants would dwarf both — but you said no paid product, and affiliates blur into "advice" fast.

### AFSL / regulatory — important and **not as scary as feared**

ASIC has an explicit carve-out: **[Instrument 2026/41 — Generic Financial Calculator Relief](https://www.asic.gov.au/about-asic/news-centre/news-items/asic-updates-relief-instrument-for-generic-financial-calculators/)**. A free generic calculator that does numerical projections without recommending a specific product can avoid AFSL requirements, provided you don't promote / advertise specific financial products and include appropriate assumptions disclosure. RG 244 also distinguishes "factual information" (no licence) from "general advice" (licence needed). Practical guardrails: clear "general info, not personal advice" disclaimer, no "you should" language, no broker recommendations beyond neutral mentions, document your assumptions. Every existing competitor relies on this carve-out — it's well-trodden.

## 4. Verdict

**The space is saturated for the obvious version.** Rask's tool already does the 80 % case competently and has SEO + brand. Yet another negative-gearing calculator is dead on arrival.

**There is a narrow opening** if you build something genuinely better on one of:

1. **Monte Carlo / sensitivity-first UX** — "here's the 10th–90th percentile range, not a single fake number"; nobody in AU does this well.
2. **State-specific tax accuracy** (SA land tax, stamp duty bands) with a clean mobile UI.
3. **Cashflow-stress visualisation** showing the year-by-year squeeze.

**Donation + ads monetisation is essentially fake revenue at any realistic traffic level you'll hit in year one.** Build it only if you'd build it anyway as a portfolio piece, learning project, or genuine public good. If the goal is income, this is the wrong vehicle — a paid SaaS for AU accountants / buyer's agents using the same engine would make 50–100× more for the same engineering effort. If the goal is to scratch the itch and ship something useful, the Monte Carlo angle is the only differentiation that's actually open.

**Bottom line: don't build "another property vs shares calculator." Build "the only one that shows a probability distribution and stress-tests cashflow," or don't bother.**

## 5. What you'd need to build the differentiated version (high level)

If you proceeded, the minimum viable feature set would be:

- **Inputs** — deposit, loan rate, term, property price, expected rent, vacancy, growth & yield assumptions, share return & dividend assumptions, marginal tax rate, state (for stamp duty / land tax), holding period.
- **Tax engine** — negative gearing, franking credits (with refund), CGT 50 % discount, stamp duty bands per state, depreciation, selling costs.
- **Comparison engine** — equal-capital-deployed normalisation (so you're not comparing $100 k unleveraged shares vs $500 k leveraged property).
- **Outputs** — year-by-year cashflow chart, terminal net-wealth distribution (Monte Carlo with adjustable volatility), stress-test sliders (rate shock, vacancy shock, return shock).
- **Disclaimers** — ASIC-compliant general-info / not-personal-advice wording per RG 244.
- **No account, no email gate** — competitive differentiator vs lead-gen calculators.

Stack would be small: a single-page web app (e.g. Next.js + Tailwind), pure-client computation (no backend = no PII, no hosting cost beyond Vercel free tier), AdSense + a "buy me a coffee" link.

---

*Sources*

- [Best ETFs Australia — Property v Shares v Offset Calculator](https://www.bestetfs.com.au/tools/property-shares-offset/)
- [austax.tools Negative Gearing Calculator](https://austax.tools/negative-gearing-calculator/)
- [Property Tax Tools](https://propertytaxtools.com.au/calculators/investment-property-calculator/)
- [Moneysmart (ASIC)](https://moneysmart.gov.au/)
- [ASIC Generic Financial Calculator Relief Instrument 2026/41](https://www.asic.gov.au/about-asic/news-centre/news-items/asic-updates-relief-instrument-for-generic-financial-calculators/)
- [ASIC RG 244 — General Advice vs Information](https://www.asic.gov.au/regulatory-resources/find-a-document/regulatory-guides/rg-244-giving-information-general-advice-and-scaled-advice/)
- [Aussie Firebug — Property vs Shares](https://www.aussiefirebug.com/property-vs-shares/)
- [Hudson Financial Planning — 10-Year Leveraged Comparison](https://hudsonfinancialplanning.com.au/resources/education-reports/investing-in-property-vs-shares/)
- [Publisher Collective AdSense Revenue Calculator](https://www.publisher-collective.com/blog/adsense-revenue-calculator)
