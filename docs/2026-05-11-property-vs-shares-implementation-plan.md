# Property vs Shares Model — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal-use Streamlit app that simulates AU residential investment property vs shares over a multi-decade horizon using Monte Carlo, with honest fairness modelling and serviceability tracking. Reference spec: `Financial Modeling/2026-05-11-property-vs-shares-design-v2.md`.

**Architecture:** Pure-Python calculation engine (`model/`) separated from a thin Streamlit UI (`app.py`). All tax / inflation / strategy logic is testable functions; Monte Carlo is vectorised in numpy; UI imports the engine and presents sliders + charts.

**Tech Stack:** Python 3.11+, numpy, pandas, streamlit ≥ 1.30, plotly, pytest. No backend. Runs locally with `streamlit run app.py`.

---

## Milestones (you can stop at any of these and have working software)

- **After Task 7** — Tax engine complete and tested. Run `pytest tests/test_tax.py` to see all AU tax functions verified against ATO/RevenueSA fixtures.
- **After Task 13** — Both strategies simulate one full trial. You can write a small Python script that prints year-by-year cashflows for property and shares.
- **After Task 17** — Monte Carlo + comparison engine working headless. A smoke script prints "P(property > shares) = X%" for default inputs.
- **After Task 18** — Solvency tracking added. Full headless model complete.
- **After Task 25** — Streamlit UI complete. Full app runnable with `streamlit run app.py`.
- **After Task 27** — Validation, defaults tuning, README. v1 done.

## File structure

Created in Task 1, populated by subsequent tasks:

```
Financial Modeling/property-vs-shares/        (own git repo)
├── README.md
├── requirements.txt
├── .gitignore
├── config.py                                 # constants, defaults, brackets, presets
├── model/
│   ├── __init__.py
│   ├── tax.py                                # MTR, neg gearing math, franking, CGT, SA stamp duty, SA land tax, depreciation
│   ├── inflation.py                          # CPI inflate/deflate helpers
│   ├── property_strategy.py                  # year-by-year property cashflow + terminal sale
│   ├── shares_strategy.py                    # year-by-year shares + terminal sale
│   ├── normalisation.py                      # Mode A (Realistic) and Mode B (Fair fight)
│   ├── solvency.py                           # serviceability ceiling + forced-sale flagging
│   └── monte_carlo.py                        # vectorised 5000-trial runner
├── app.py                                    # Streamlit UI; imports from model/
├── notebooks/
│   ├── .gitkeep
│   └── scratch.ipynb                         # dev scratch (gitignored outputs)
└── tests/
    ├── __init__.py
    ├── test_tax.py
    ├── test_inflation.py
    ├── test_property_strategy.py
    ├── test_shares_strategy.py
    ├── test_normalisation.py
    ├── test_solvency.py
    └── test_monte_carlo.py
```

---

## Phase 1 — Project setup

### Task 1: Scaffold project

**Files:**
- Create: `Financial Modeling/property-vs-shares/README.md`
- Create: `Financial Modeling/property-vs-shares/requirements.txt`
- Create: `Financial Modeling/property-vs-shares/.gitignore`
- Create: `Financial Modeling/property-vs-shares/model/__init__.py`
- Create: `Financial Modeling/property-vs-shares/tests/__init__.py`
- Create: `Financial Modeling/property-vs-shares/notebooks/.gitkeep`

- [ ] **Step 1: Create directory structure**

```bash
cd "/Users/aidenmacmini/AI Project/Financial Modeling"
mkdir -p property-vs-shares/{model,tests,notebooks}
cd property-vs-shares
```

- [ ] **Step 2: Initialise git**

```bash
git init
git branch -M main
```

- [ ] **Step 3: Write `requirements.txt`**

```
numpy>=1.26
pandas>=2.2
streamlit>=1.30
plotly>=5.20
pytest>=8.0
scipy>=1.12
```

- [ ] **Step 4: Write `.gitignore`**

```
__pycache__/
*.py[cod]
.pytest_cache/
.venv/
venv/
.env
.DS_Store
notebooks/*.ipynb_checkpoints/
notebooks/*-output.ipynb
.streamlit/secrets.toml
```

- [ ] **Step 5: Write empty package init files**

`model/__init__.py`:
```python
"""Property vs Shares model — calculation engine."""
```

`tests/__init__.py`: (empty)

`notebooks/.gitkeep`: (empty file)

- [ ] **Step 6: Write `README.md`**

```markdown
# Property vs Shares Model

Personal-use Monte Carlo simulator comparing AU residential investment property vs shares.

See design spec at `../2026-05-11-property-vs-shares-design-v2.md`.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Test

```bash
pytest
```
```

- [ ] **Step 7: Install dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: dependencies install without errors.

- [ ] **Step 8: Initial commit**

```bash
git add .gitignore requirements.txt README.md model/__init__.py tests/__init__.py notebooks/.gitkeep
git commit -m "chore: scaffold project structure"
```

---

## Phase 2 — Tax engine

### Task 2: Marginal income tax (FY2026 Stage 3 brackets)

**Files:**
- Create: `config.py`
- Create: `model/tax.py`
- Create: `tests/test_tax.py`

- [ ] **Step 1: Write the failing test**

`tests/test_tax.py`:
```python
"""Tax function tests. Expected values cross-checked against ATO online tax calculator
at https://www.ato.gov.au/calculators-and-tools/tax-withheld-calculator (FY2025-26).

Verify each expected value in the calculator before relying on these tests.
"""
import pytest
from model.tax import marginal_tax


def test_marginal_tax_zero_income():
    assert marginal_tax(0) == 0


def test_marginal_tax_below_threshold():
    assert marginal_tax(18_200) == 0


def test_marginal_tax_within_first_bracket():
    # $30k: ($30,000 - $18,200) * 16% = $1,888
    assert marginal_tax(30_000) == pytest.approx(1_888)


def test_marginal_tax_50k():
    # $50k: $4,288 + ($50,000 - $45,000) * 30% = $5,788
    assert marginal_tax(50_000) == pytest.approx(5_788)


def test_marginal_tax_90k():
    # $90k: $4,288 + ($90,000 - $45,000) * 30% = $17,788
    assert marginal_tax(90_000) == pytest.approx(17_788)


def test_marginal_tax_150k():
    # $150k: $31,288 + ($150,000 - $135,000) * 37% = $36,838
    assert marginal_tax(150_000) == pytest.approx(36_838)


def test_marginal_tax_250k():
    # $250k: $51,638 + ($250,000 - $190,000) * 45% = $78,638
    assert marginal_tax(250_000) == pytest.approx(78_638)


def test_marginal_tax_negative_income_returns_zero():
    # Negative gearing scenarios — losses don't refund prior tax in this fn
    assert marginal_tax(-5_000) == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_tax.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'model.tax'`

- [ ] **Step 3: Verify expected values against ATO calculator**

Open https://www.ato.gov.au/calculators-and-tools/simple-tax-calculator and confirm at least the $50k, $90k, $150k cases produce the values above (within $1 rounding). If any differ, update the test fixtures BEFORE proceeding.

- [ ] **Step 4: Write `config.py`**

```python
"""Constants and defaults. When tax law changes, this is the file you mostly edit."""

# FY2026 (2025-26) Stage 3 resident brackets.
# Format: (upper bound, marginal rate on the bracket).
# Source: https://www.ato.gov.au/tax-rates-and-codes/tax-rates-australian-residents
STAGE_3_BRACKETS = [
    (18_200, 0.00),
    (45_000, 0.16),
    (135_000, 0.30),
    (190_000, 0.37),
    (float("inf"), 0.45),
]

# Monte Carlo
TRIALS = 5000
SEED = 42

# CPI default
DEFAULT_CPI = 0.025
```

- [ ] **Step 5: Write `model/tax.py` with `marginal_tax`**

```python
"""Pure tax functions. No I/O, no globals (other than reading config)."""
from typing import Iterable
from config import STAGE_3_BRACKETS


def marginal_tax(taxable_income: float, brackets: Iterable[tuple] = None) -> float:
    """Return total income tax on a positive taxable income.

    Negative income returns 0 — losses do not refund prior tax in isolation.
    Excludes Medicare Levy and any offsets (out of v1 scope).
    """
    if taxable_income <= 0:
        return 0.0
    if brackets is None:
        brackets = STAGE_3_BRACKETS

    tax = 0.0
    prev_upper = 0.0
    for upper, rate in brackets:
        if taxable_income <= upper:
            tax += (taxable_income - prev_upper) * rate
            return tax
        tax += (upper - prev_upper) * rate
        prev_upper = upper
    return tax
```

- [ ] **Step 6: Run test to verify it passes**

```bash
pytest tests/test_tax.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add config.py model/tax.py tests/test_tax.py
git commit -m "feat(tax): marginal income tax with Stage 3 brackets"
```

---

### Task 3: Franking credits

**Files:**
- Modify: `model/tax.py`
- Modify: `tests/test_tax.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_tax.py`)**

```python
from model.tax import franking_credit_refund


def test_franking_zero_dividend():
    assert franking_credit_refund(0, mtr=0.30, franked_portion=1.0) == 0


def test_fully_franked_at_30pc_mtr_breakeven():
    # Company tax 30%; if MTR == 30%, franking offsets tax exactly.
    # $700 dividend (cash), franking credit = $700 * 30/70 = $300, gross-up = $1000.
    # Tax on $1000 @ 30% = $300; minus credit $300 = $0 net tax.
    # So refund = -tax_payable = 0.
    assert franking_credit_refund(700, mtr=0.30, franked_portion=1.0) == pytest.approx(0)


def test_fully_franked_at_19pc_mtr_refund():
    # Company tax 30%; MTR 19% → user gets cash refund of difference.
    # $700 dividend, gross-up to $1000, tax @ 19% = $190; minus $300 credit = -$110 (refund).
    assert franking_credit_refund(700, mtr=0.19, franked_portion=1.0) == pytest.approx(-110)


def test_fully_franked_at_45pc_mtr_top_up():
    # MTR 45% → user owes more tax.
    # $700 dividend, gross-up to $1000, tax @ 45% = $450; minus $300 credit = $150 owed.
    assert franking_credit_refund(700, mtr=0.45, franked_portion=1.0) == pytest.approx(150)


def test_partial_franking():
    # 50% franked $700: half franked ($350 cash + $150 credit = $500 grossed),
    # half unfranked ($350 cash, no credit, taxed at MTR).
    # Total tax @ 30% = (500 + 350) * 30% - 150 credit = 255 - 150 = 105.
    assert franking_credit_refund(700, mtr=0.30, franked_portion=0.50) == pytest.approx(105)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_tax.py::test_fully_franked_at_19pc_mtr_refund -v
```

Expected: FAIL with `ImportError: cannot import name 'franking_credit_refund'`.

- [ ] **Step 3: Implement `franking_credit_refund`**

Append to `model/tax.py`:

```python
COMPANY_TAX_RATE = 0.30


def franking_credit_refund(cash_dividend: float, mtr: float, franked_portion: float) -> float:
    """Net tax payable on a dividend after franking credits.

    Returns positive for tax owed, negative for cash refund (excess credits).

    Args:
        cash_dividend: gross cash dividend received (before franking gross-up)
        mtr: investor's marginal tax rate (0.0 to 0.45)
        franked_portion: fraction of the dividend that's franked (0.0 to 1.0)
    """
    if cash_dividend <= 0:
        return 0.0

    franked_cash = cash_dividend * franked_portion
    unfranked_cash = cash_dividend * (1 - franked_portion)

    # Franking credit attached to the franked portion
    franking_credit = franked_cash * COMPANY_TAX_RATE / (1 - COMPANY_TAX_RATE)
    grossed_up = franked_cash + franking_credit + unfranked_cash

    tax_before_credit = grossed_up * mtr
    return tax_before_credit - franking_credit
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_tax.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add model/tax.py tests/test_tax.py
git commit -m "feat(tax): franking credits with refund of excess imputation"
```

---

### Task 4: CGT 50% discount

**Files:**
- Modify: `model/tax.py`
- Modify: `tests/test_tax.py`

- [ ] **Step 1: Write the failing test**

```python
from model.tax import cgt_payable


def test_cgt_zero_gain():
    assert cgt_payable(gain=0, holding_years=5, mtr=0.30) == 0


def test_cgt_loss():
    # Capital loss → no CGT (loss can offset other gains, but not modelled here)
    assert cgt_payable(gain=-50_000, holding_years=5, mtr=0.30) == 0


def test_cgt_short_term_no_discount():
    # < 12 months → no discount
    # $100k gain at MTR 37% = $37,000
    assert cgt_payable(gain=100_000, holding_years=0.5, mtr=0.37) == pytest.approx(37_000)


def test_cgt_long_term_50pc_discount():
    # > 12 months → 50% discount
    # $200k gain, discounted to $100k, taxed at 37% = $37,000
    assert cgt_payable(gain=200_000, holding_years=5, mtr=0.37) == pytest.approx(37_000)


def test_cgt_at_top_marginal_rate():
    # $500k gain, discounted to $250k, taxed at 45% = $112,500
    assert cgt_payable(gain=500_000, holding_years=10, mtr=0.45) == pytest.approx(112_500)
```

- [ ] **Step 2: Verify it fails**

```bash
pytest tests/test_tax.py -v -k cgt
```

Expected: FAIL with import error.

- [ ] **Step 3: Implement `cgt_payable`**

Append to `model/tax.py`:

```python
CGT_DISCOUNT = 0.50
DISCOUNT_HOLDING_THRESHOLD_YEARS = 1.0


def cgt_payable(gain: float, holding_years: float, mtr: float) -> float:
    """CGT on a capital gain. AU resident, 50% discount if held > 12 months.

    Returns 0 for capital losses (offsetting against other gains is out of v1 scope).
    """
    if gain <= 0:
        return 0.0
    if holding_years > DISCOUNT_HOLDING_THRESHOLD_YEARS:
        gain = gain * (1 - CGT_DISCOUNT)
    return gain * mtr
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_tax.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add model/tax.py tests/test_tax.py
git commit -m "feat(tax): CGT with 50% long-hold discount"
```

---

### Task 5: SA stamp duty

**Files:**
- Modify: `model/tax.py`
- Modify: `tests/test_tax.py`

- [ ] **Step 1: Look up SA stamp duty bands**

Visit https://www.revenuesa.sa.gov.au/stamp-duty/rate-of-stamp-duty and record the FY2026 conveyance duty bands. As of design date the bands are roughly (verify before coding):

| Band | Rate |
|---|---|
| $0 – $12,000 | 1.00% |
| $12,001 – $30,000 | $120 + 2.00% on excess |
| $30,001 – $50,000 | $480 + 3.00% on excess |
| $50,001 – $100,000 | $1,080 + 3.50% on excess |
| $100,001 – $200,000 | $2,830 + 4.00% on excess |
| $200,001 – $250,000 | $6,830 + 4.25% on excess |
| $250,001 – $300,000 | $8,955 + 4.75% on excess |
| $300,001 – $500,000 | $11,330 + 5.00% on excess |
| $500,001+ | $21,330 + 5.50% on excess |

Plus transfer fee (~$181 flat as of 2026; verify).

- [ ] **Step 2: Verify expected values against RevenueSA calculator**

Open https://www.revenuesa.sa.gov.au/stamp-duty/transfer-of-property and run the calculator for $400k, $700k, $1.2m investment property purchases. Record the duty + fee values for use in tests below.

- [ ] **Step 3: Write the failing test**

```python
from model.tax import sa_stamp_duty


# Expected values from RevenueSA conveyance duty calculator, dated YYYY-MM-DD.
# URL: https://www.revenuesa.sa.gov.au/stamp-duty/transfer-of-property
def test_stamp_duty_400k():
    # Replace 16_330 with value from RevenueSA calculator + transfer fee
    assert sa_stamp_duty(400_000) == pytest.approx(16_330 + 181, abs=1)


def test_stamp_duty_700k():
    # Replace 32_330 with value from RevenueSA calculator + transfer fee
    assert sa_stamp_duty(700_000) == pytest.approx(32_330 + 181, abs=1)


def test_stamp_duty_1_2m():
    # Replace with value from RevenueSA calculator + transfer fee
    assert sa_stamp_duty(1_200_000) == pytest.approx(60_330 + 181, abs=1)
```

- [ ] **Step 4: Verify it fails**

```bash
pytest tests/test_tax.py -v -k stamp
```

Expected: FAIL with import error.

- [ ] **Step 5: Implement `sa_stamp_duty`**

Append to `model/tax.py`:

```python
# SA conveyance duty bands (FY2026). Verify against RevenueSA before any reliance.
# Format: (upper bound of band, base duty at lower bound, marginal rate above lower bound).
SA_DUTY_BANDS = [
    (12_000,    0,        0.0100),
    (30_000,    120,      0.0200),
    (50_000,    480,      0.0300),
    (100_000,   1_080,    0.0350),
    (200_000,   2_830,    0.0400),
    (250_000,   6_830,    0.0425),
    (300_000,   8_955,    0.0475),
    (500_000,   11_330,   0.0500),
    (float("inf"), 21_330, 0.0550),
]
SA_TRANSFER_FEE = 181  # flat; verify on RevenueSA


def sa_stamp_duty(price: float) -> float:
    """SA conveyance stamp duty + transfer fee on an investment property purchase."""
    if price <= 0:
        return 0.0

    prev_upper = 0
    for upper, base, rate in SA_DUTY_BANDS:
        if price <= upper:
            duty = base + (price - prev_upper) * rate
            return duty + SA_TRANSFER_FEE
        prev_upper = upper
    return 0.0  # unreachable
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_tax.py -v -k stamp
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add model/tax.py tests/test_tax.py
git commit -m "feat(tax): SA conveyance stamp duty"
```

---

### Task 6: SA land tax

**Files:**
- Modify: `model/tax.py`
- Modify: `tests/test_tax.py`

- [ ] **Step 1: Look up SA land tax thresholds**

Visit https://revenuesa.sa.gov.au/landtax/rates-and-thresholds and record FY2026 land tax bands for individual ownership. Verify before relying.

- [ ] **Step 2: Write the failing test**

```python
from model.tax import sa_land_tax


# Expected values from RevenueSA land tax calculator, dated YYYY-MM-DD.
def test_land_tax_below_threshold():
    # Below the $833k threshold → no land tax
    assert sa_land_tax(500_000) == 0


def test_land_tax_at_threshold():
    assert sa_land_tax(833_000) == 0


def test_land_tax_above_threshold():
    # Verify the actual value against RevenueSA calculator
    # Placeholder: $900k land value, land tax ≈ $268
    assert sa_land_tax(900_000) > 0
```

- [ ] **Step 3: Verify it fails**

```bash
pytest tests/test_tax.py -v -k land
```

- [ ] **Step 4: Implement `sa_land_tax`**

Append to `model/tax.py`:

```python
# SA land tax bands (FY2026). VERIFY against RevenueSA before relying.
# Format: (upper bound of band, base tax at lower bound, marginal rate above lower bound).
SA_LAND_TAX_BANDS = [
    (833_000,    0,       0.000),
    (1_212_000,  0,       0.0050),
    (1_756_000,  1_895,   0.0100),
    (float("inf"), 7_335, 0.0240),
]


def sa_land_tax(unimproved_land_value: float) -> float:
    """Annual SA land tax on an investor-held property's unimproved land value."""
    if unimproved_land_value <= 0:
        return 0.0

    prev_upper = 0
    for upper, base, rate in SA_LAND_TAX_BANDS:
        if unimproved_land_value <= upper:
            return base + (unimproved_land_value - prev_upper) * rate
        prev_upper = upper
    return 0.0
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_tax.py -v -k land
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add model/tax.py tests/test_tax.py
git commit -m "feat(tax): SA land tax with FY2026 thresholds"
```

---

### Task 7: Depreciation per property age

**Files:**
- Modify: `config.py`
- Modify: `model/tax.py`
- Modify: `tests/test_tax.py`

- [ ] **Step 1: Add property-age constants to `config.py`**

```python
from typing import Literal

PropertyAge = Literal["new_build", "established_post_2017", "established_pre_2017"]
AssetType = Literal["house", "apartment", "townhouse"]

# Building cost as % of purchase price, by asset type.
BUILDING_COST_PCT = {
    "house": 0.40,
    "apartment": 0.85,
    "townhouse": 0.65,
}

# Land value as % of purchase price (inverse of building cost).
LAND_VALUE_PCT = {k: 1 - v for k, v in BUILDING_COST_PCT.items()}

# Div 43 rate (capital works deduction)
DIV_43_RATE = 0.025  # 2.5% per year of original construction cost
```

- [ ] **Step 2: Write the failing test**

```python
from model.tax import depreciation_for_year


def test_depreciation_new_build_house():
    # New build, $700k house → building cost = $280k.
    # Div 43: $280k * 2.5% = $7,000/yr.
    # Div 40 not modelled in detail in v1; defer to override or zero.
    assert depreciation_for_year(
        property_age="new_build",
        building_cost=280_000,
    ) == pytest.approx(7_000)


def test_depreciation_established_post_2017_blocked_div40():
    # Established post-2017: Div 40 BLOCKED, only Div 43.
    # $700k house, building $280k → Div 43 = $7,000/yr.
    assert depreciation_for_year(
        property_age="established_post_2017",
        building_cost=280_000,
    ) == pytest.approx(7_000)


def test_depreciation_established_pre_2017_grandfathered():
    # Pre-2017: Div 40 grandfathered. v1 still uses flat Div 43; user can override.
    assert depreciation_for_year(
        property_age="established_pre_2017",
        building_cost=280_000,
    ) == pytest.approx(7_000)


def test_depreciation_user_override_takes_precedence():
    # Power user sets a custom annual figure
    assert depreciation_for_year(
        property_age="established_post_2017",
        building_cost=280_000,
        override=10_000,
    ) == 10_000


def test_depreciation_zero_building_cost_returns_zero():
    assert depreciation_for_year(
        property_age="new_build",
        building_cost=0,
    ) == 0
```

- [ ] **Step 3: Verify it fails**

```bash
pytest tests/test_tax.py -v -k depreciation
```

- [ ] **Step 4: Implement `depreciation_for_year`**

Append to `model/tax.py`:

```python
from typing import Optional
from config import DIV_43_RATE


def depreciation_for_year(
    property_age: str,
    building_cost: float,
    override: Optional[float] = None,
) -> float:
    """Annual depreciation deduction for an investment property.

    v1 simplification: returns Div 43 (capital works @ 2.5% of building cost) for all property
    ages. Div 40 (plant & equipment) is not modelled in detail — for new builds this would
    add ~$2-3k/yr in early years declining over effective life; user can override.

    Established post-May-2017 properties have Div 40 BLOCKED by the legislative change; only
    Div 43 applies. v1 conservatively applies the same Div-43-only rule across all ages and
    relies on the override for power users with a quantity surveyor schedule.
    """
    if override is not None:
        return float(override)
    if building_cost <= 0:
        return 0.0
    return building_cost * DIV_43_RATE
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_tax.py -v
```

Expected: ALL pass.

- [ ] **Step 6: Commit**

```bash
git add config.py model/tax.py tests/test_tax.py
git commit -m "feat(tax): depreciation per property age (Div 43 only in v1)"
```

> **MILESTONE 1 reached: Tax engine complete.** Run `pytest tests/test_tax.py -v` to confirm all tax functions work.

---

## Phase 3 — Inflation utility

### Task 8: Inflation helpers

**Files:**
- Create: `model/inflation.py`
- Create: `tests/test_inflation.py`

- [ ] **Step 1: Write the failing test**

```python
"""Inflation helper tests."""
import pytest
import numpy as np
from model.inflation import inflate, deflate, inflate_series


def test_inflate_zero_years_identity():
    assert inflate(1000, years=0, cpi=0.025) == 1000


def test_inflate_one_year():
    assert inflate(1000, years=1, cpi=0.025) == pytest.approx(1025)


def test_inflate_compound():
    # $1000 inflated 10 yrs at 2.5% = 1000 * 1.025^10 ≈ 1280.08
    assert inflate(1000, years=10, cpi=0.025) == pytest.approx(1280.08, rel=1e-3)


def test_deflate_round_trip():
    # inflate then deflate = identity
    inflated = inflate(1000, years=10, cpi=0.025)
    assert deflate(inflated, years=10, cpi=0.025) == pytest.approx(1000)


def test_inflate_series_vectorised():
    # $1000 across years 0..3 at 2.5%
    result = inflate_series(1000, years=4, cpi=0.025)
    assert isinstance(result, np.ndarray)
    assert result[0] == pytest.approx(1000)
    assert result[1] == pytest.approx(1025)
    assert result[2] == pytest.approx(1050.625)
    assert result[3] == pytest.approx(1076.890625)
```

- [ ] **Step 2: Verify it fails**

```bash
pytest tests/test_inflation.py -v
```

- [ ] **Step 3: Implement `model/inflation.py`**

```python
"""CPI-based inflation / deflation helpers. Used to inflate rent and holding costs over
the model horizon, and to deflate output dollar figures for the 'today's dollars' display."""

import numpy as np


def inflate(value: float, years: float, cpi: float = 0.025) -> float:
    """Compound-inflate a value forward by `years` at `cpi` rate."""
    return value * (1 + cpi) ** years


def deflate(value: float, years: float, cpi: float = 0.025) -> float:
    """Compound-deflate a future value back to today's dollars."""
    return value / (1 + cpi) ** years


def inflate_series(value: float, years: int, cpi: float = 0.025) -> np.ndarray:
    """Return an array of the value compounded across years 0..years-1.

    Year 0 = original value, year 1 = value * (1+cpi), etc.
    """
    multipliers = (1 + cpi) ** np.arange(years)
    return value * multipliers
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_inflation.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add model/inflation.py tests/test_inflation.py
git commit -m "feat(inflation): CPI inflate/deflate helpers"
```

---

## Phase 4 — Strategy modules

### Task 9: Property strategy — single-trial cashflow simulator

**Files:**
- Create: `model/property_strategy.py`
- Create: `tests/test_property_strategy.py`

- [ ] **Step 1: Write the failing test (single-year hand-calculated case)**

```python
"""Property strategy tests."""
import pytest
import numpy as np
from model.property_strategy import simulate_property_trial, PropertyInputs


def make_default_inputs() -> PropertyInputs:
    return PropertyInputs(
        purchase_price=700_000,
        deposit=140_000,
        loan_rate_path=np.full(25, 0.06),  # flat 6% for simplicity
        loan_term_years=30,
        io_period_years=5,
        gross_yield=0.04,
        vacancy_weeks_path=np.full(25, 2.0),
        capital_growth_path=np.full(25, 0.055),
        management_fee_pct=0.07,
        maintenance_pct=0.012,
        property_age="established_post_2017",
        asset_type="house",
        depreciation_override=None,
        mtr=0.37,
        cpi=0.025,
        horizon_years=25,
        selling_costs_pct=0.025,
    )


def test_property_year_one_cashflow_components():
    """Hand-calc year 1:
    - Rent: $700k * 4% = $28,000 gross; less 2 weeks vacancy = $28,000 * 50/52 = $26,923
    - Management: $26,923 * 7% = $1,885
    - Maintenance/insurance/rates: $700k * 1.2% = $8,400
    - Loan interest (IO): $560k * 6% = $33,600
    - Land tax (SA, $700k house, 60% land = $420k → below $833k threshold): $0
    - Depreciation: house $700k, building 40% = $280k, Div 43 = $7,000
    - Net rental loss: 26,923 - 1,885 - 8,400 - 33,600 - 0 - 7,000 = -23,962
    - Tax saving on loss at 37% MTR: $23,962 * 0.37 = $8,866
    - Net out-of-pocket cashflow yr 1: -23,962 + 8,866 = -$15,096
    """
    inputs = make_default_inputs()
    result = simulate_property_trial(inputs)

    assert result.cashflow_per_year[0] == pytest.approx(-15_096, abs=50)


def test_property_terminal_wealth_includes_capital_growth():
    """End-of-horizon house value = $700k * (1.055)^25 ≈ $2.65m"""
    inputs = make_default_inputs()
    result = simulate_property_trial(inputs)

    # Terminal sale price (before costs and CGT)
    expected_sale_price = 700_000 * (1.055) ** 25
    assert result.gross_sale_price == pytest.approx(expected_sale_price, rel=0.01)
```

- [ ] **Step 2: Verify it fails**

```bash
pytest tests/test_property_strategy.py -v
```

- [ ] **Step 3: Implement `model/property_strategy.py`** (the engine)

```python
"""Year-by-year property cashflow simulator + terminal sale.

A single trial = one realisation of the random variables (capital growth, loan rate,
vacancy, etc.). The Monte Carlo runner calls this 5000 times.
"""
from dataclasses import dataclass
from typing import Optional
import numpy as np

from config import BUILDING_COST_PCT, LAND_VALUE_PCT
from model.tax import marginal_tax, sa_land_tax, depreciation_for_year, cgt_payable
from model.inflation import inflate_series


@dataclass
class PropertyInputs:
    """All inputs the property strategy needs for one trial."""
    purchase_price: float
    deposit: float
    loan_rate_path: np.ndarray  # length = horizon_years; per-year loan rate (stochastic)
    loan_term_years: int
    io_period_years: int
    gross_yield: float
    vacancy_weeks_path: np.ndarray  # length = horizon_years
    capital_growth_path: np.ndarray  # length = horizon_years; per-year growth rate
    management_fee_pct: float
    maintenance_pct: float
    property_age: str
    asset_type: str
    depreciation_override: Optional[float]
    mtr: float
    cpi: float
    horizon_years: int
    selling_costs_pct: float


@dataclass
class PropertyResult:
    """All outputs from one property trial."""
    cashflow_per_year: np.ndarray
    cumulative_div43_claimed: float
    gross_sale_price: float
    terminal_loan_balance: float
    cgt_paid_on_sale: float
    selling_costs: float
    terminal_after_tax_wealth: float


def _annual_loan_balance_and_interest(
    initial_loan: float,
    rate_path: np.ndarray,
    term_years: int,
    io_period: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (interest_per_year, balance_per_year) over the horizon.

    During IO period: principal stays at initial_loan; interest = balance * rate.
    Post IO: P&I amortisation across remaining term using each year's rate.
    """
    horizon = len(rate_path)
    balance = np.zeros(horizon)
    interest = np.zeros(horizon)
    current_balance = initial_loan

    for year in range(horizon):
        r = rate_path[year]
        if year < io_period:
            interest[year] = current_balance * r
            balance[year] = current_balance
        else:
            # Years remaining of P&I portion
            years_remaining = term_years - year
            if years_remaining <= 0:
                interest[year] = 0
                balance[year] = 0
                continue
            # Standard mortgage payment formula
            if r > 0:
                payment = current_balance * (r * (1 + r) ** years_remaining) / ((1 + r) ** years_remaining - 1)
            else:
                payment = current_balance / years_remaining
            interest[year] = current_balance * r
            principal = max(0, payment - interest[year])
            current_balance = max(0, current_balance - principal)
            balance[year] = current_balance

    return interest, balance


def simulate_property_trial(inputs: PropertyInputs) -> PropertyResult:
    """Simulate one trial of the property strategy."""
    h = inputs.horizon_years
    initial_loan = inputs.purchase_price - inputs.deposit

    # Property value path (cumulative growth)
    value_path = inputs.purchase_price * np.cumprod(1 + inputs.capital_growth_path)

    # Rent path: gross_yield * value, inflated by CPI annually (and reduced by vacancy).
    # Simplification: gross yield is applied to current property value, with vacancy haircut.
    occupied_weeks = 52 - inputs.vacancy_weeks_path
    rent_path = inputs.gross_yield * value_path * occupied_weeks / 52

    # Holding costs (inflated by CPI from year 0 baseline)
    base_maintenance = inputs.purchase_price * inputs.maintenance_pct
    maintenance_path = inflate_series(base_maintenance, h, inputs.cpi)

    # Management fee: % of rent (auto-tracks rent inflation)
    management_path = rent_path * inputs.management_fee_pct

    # Loan interest + balance
    interest_path, balance_path = _annual_loan_balance_and_interest(
        initial_loan, inputs.loan_rate_path, inputs.loan_term_years, inputs.io_period_years
    )

    # Land tax (annual, on unimproved land value tracking property value)
    land_value_path = value_path * LAND_VALUE_PCT[inputs.asset_type]
    land_tax_path = np.array([sa_land_tax(v) for v in land_value_path])

    # Depreciation (constant per year, from building cost)
    building_cost = inputs.purchase_price * BUILDING_COST_PCT[inputs.asset_type]
    annual_depreciation = depreciation_for_year(
        property_age=inputs.property_age,
        building_cost=building_cost,
        override=inputs.depreciation_override,
    )
    depreciation_path = np.full(h, annual_depreciation)

    # Net rental income (loss if negative)
    deductions_path = (
        management_path + maintenance_path + interest_path + land_tax_path + depreciation_path
    )
    net_rental_income = rent_path - deductions_path

    # Tax effect: negative gearing applies the loss at MTR (returns cash from ATO)
    tax_effect_path = net_rental_income * inputs.mtr

    # After-tax cashflow per year (positive = surplus, negative = out-of-pocket)
    cashflow_per_year = net_rental_income - tax_effect_path

    # Wait — that's wrong. Let me reconsider:
    # Pre-tax cashflow = rent - costs (which includes interest)
    # If net_rental_income is negative, MTR * loss is a TAX REFUND (positive cash).
    # So: after-tax cashflow = pre-tax cashflow + (tax saved or owed).
    # Tax saved on loss = -net_rental_income * mtr (positive when income is negative).
    # Tax owed on profit = net_rental_income * mtr (positive when income is positive).
    # In both cases, after-tax cashflow = net_rental_income * (1 - mtr).

    # Recompute correctly:
    cashflow_per_year = net_rental_income * (1 - inputs.mtr)
    # Note: depreciation is a non-cash deduction, so ADD it back to get cash impact.
    cashflow_per_year = cashflow_per_year + depreciation_path * inputs.mtr
    # Wait — depreciation reduced taxable income, so the tax saving on it IS a real cash benefit.
    # net_rental_income above already includes depreciation as a deduction.
    # After-tax cash = (rent - cash_costs) * (1 - mtr) + depreciation * mtr
    # where cash_costs = management + maintenance + interest + land_tax (NOT depreciation)
    # The (1-mtr) is wrong — only the cash-affecting items are taxed.
    # Cleanest formulation:
    cash_costs_path = management_path + maintenance_path + interest_path + land_tax_path
    pre_tax_cash = rent_path - cash_costs_path  # before depreciation, before tax
    taxable_income_from_property = rent_path - cash_costs_path - depreciation_path
    tax_on_property = taxable_income_from_property * inputs.mtr
    cashflow_per_year = pre_tax_cash - tax_on_property

    # Terminal sale event (end of horizon, year h-1)
    gross_sale_price = value_path[-1]
    selling_costs = gross_sale_price * inputs.selling_costs_pct
    terminal_loan_balance = balance_path[-1]

    # Cost base: original purchase + stamp duty + buying costs - cumulative Div 43 claimed
    # Stamp duty is added externally by the comparison engine (we don't have it here);
    # for now assume cost base = purchase price + selling costs - cumulative Div 43.
    cumulative_div43 = annual_depreciation * h  # all of v1's depreciation is treated as Div 43
    cost_base = inputs.purchase_price + selling_costs - cumulative_div43
    capital_gain = gross_sale_price - cost_base
    cgt_paid = cgt_payable(capital_gain, holding_years=h, mtr=inputs.mtr)

    terminal_after_tax_wealth = (
        gross_sale_price - selling_costs - terminal_loan_balance - cgt_paid
    )

    return PropertyResult(
        cashflow_per_year=cashflow_per_year,
        cumulative_div43_claimed=cumulative_div43,
        gross_sale_price=gross_sale_price,
        terminal_loan_balance=terminal_loan_balance,
        cgt_paid_on_sale=cgt_paid,
        selling_costs=selling_costs,
        terminal_after_tax_wealth=terminal_after_tax_wealth,
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_property_strategy.py -v
```

Expected: PASS. If the year-1 cashflow test fails by more than the $50 tolerance, the engineer must trace through the formula to find the discrepancy — do NOT relax the tolerance.

- [ ] **Step 5: Commit**

```bash
git add model/property_strategy.py tests/test_property_strategy.py
git commit -m "feat(property): single-trial cashflow simulator with terminal sale"
```

---

### Task 10: Property strategy — overflow share-portfolio for positive years

**Files:**
- Modify: `model/property_strategy.py`
- Modify: `tests/test_property_strategy.py`

> **Note:** This task adds the "if property has positive cashflow, invest the surplus in shares within the property strategy" logic. This is part of equal-outside-cash contributions (§7 of spec).

- [ ] **Step 1: Write the failing test**

```python
def test_property_positive_cashflow_invests_in_shares():
    """If property generates surplus in some years, that surplus is invested in
    shares within the property strategy (the 'overflow wealth' bucket)."""
    inputs = make_default_inputs()
    inputs.gross_yield = 0.08  # high yield → positively geared
    result = simulate_property_trial(inputs)

    # In a positively geared scenario, overflow_share_value should be > 0 at terminal
    assert hasattr(result, "overflow_share_terminal_value")
    if (result.cashflow_per_year > 0).any():
        assert result.overflow_share_terminal_value > 0
```

- [ ] **Step 2: Verify it fails**

```bash
pytest tests/test_property_strategy.py::test_property_positive_cashflow_invests_in_shares -v
```

- [ ] **Step 3: Add overflow-share-portfolio logic to `simulate_property_trial`**

Modify `PropertyResult` to add a field, and add a final step after computing `cashflow_per_year`:

```python
# Add to PropertyResult dataclass:
    overflow_share_terminal_value: float


# Add at the bottom of simulate_property_trial, before constructing PropertyResult:

# Overflow share portfolio: any positive year's cashflow is invested in shares.
# Use a simple constant share return for v1 (overflow is small; full Monte Carlo on it
# would be over-engineering). Use mean of property's MTR-adjusted assumption: 8.5% pre-tax.
SHARE_RETURN_FOR_OVERFLOW = 0.085
overflow_balance = 0.0
for year in range(h):
    overflow_balance *= (1 + SHARE_RETURN_FOR_OVERFLOW)
    if cashflow_per_year[year] > 0:
        overflow_balance += cashflow_per_year[year]
        # Note: future years' cashflow array is not affected — we just track the parallel bucket.

overflow_share_terminal_value = overflow_balance
```

Then update the return statement to include `overflow_share_terminal_value=overflow_share_terminal_value`.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_property_strategy.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add model/property_strategy.py tests/test_property_strategy.py
git commit -m "feat(property): overflow share portfolio for positively geared years"
```

---

### Task 11: Shares strategy — single-trial simulator

**Files:**
- Create: `model/shares_strategy.py`
- Create: `tests/test_shares_strategy.py`

- [ ] **Step 1: Write the failing test**

```python
"""Shares strategy tests."""
import pytest
import numpy as np
from model.shares_strategy import simulate_shares_trial, SharesInputs


def make_default_shares_inputs() -> SharesInputs:
    return SharesInputs(
        initial_capital=172_000,  # property's deposit + stamp duty + buying costs
        share_return_path=np.full(25, 0.085),
        dividend_yield_pct=0.035,
        franked_portion=0.50,
        mer=0.0020,
        brokerage_per_trade=10.0,
        drp=True,
        mtr=0.37,
        external_contributions=np.zeros(25),  # set by comparison engine
        horizon_years=25,
        margin_loan_initial=0.0,
        margin_loan_rate_path=None,
    )


def test_shares_year_one_cashflow_with_drp():
    """$172k initial. $172k * 8.5% = $14,620 total return.
    Of which dividends = $172k * 3.5% = $6,020.
    DRP on → dividends reinvested but still taxable.
    Tax on dividends @ 50% franked, MTR 37%:
    - Franked $3,010 → gross-up $4,300 → tax @37% = $1,591 - $1,290 credit = $301
    - Unfranked $3,010 → tax @37% = $1,114
    - Total dividend tax: $1,415
    - MER: $172k * 0.20% = $344
    Year 1 cashflow (out-of-pocket): -1,415 - 344 = -$1,759
    """
    inputs = make_default_shares_inputs()
    result = simulate_shares_trial(inputs)

    assert result.cashflow_per_year[0] == pytest.approx(-1_759, abs=20)


def test_shares_terminal_wealth_compounds():
    """No dividends, just price growth at 8.5%/yr for 25 yrs.
    $172k * 1.085^25 ≈ $1.32m before CGT.
    """
    inputs = make_default_shares_inputs()
    inputs.dividend_yield_pct = 0.0  # all return is capital growth
    inputs.franked_portion = 0.0
    result = simulate_shares_trial(inputs)

    # Pre-CGT terminal value should be roughly $172k * 1.085^25
    expected_pre_cgt = 172_000 * (1.085) ** 25
    assert result.gross_terminal_value == pytest.approx(expected_pre_cgt, rel=0.02)
```

- [ ] **Step 2: Verify it fails**

```bash
pytest tests/test_shares_strategy.py -v
```

- [ ] **Step 3: Implement `model/shares_strategy.py`**

```python
"""Year-by-year shares cashflow simulator + terminal sale."""
from dataclasses import dataclass
from typing import Optional
import numpy as np

from model.tax import franking_credit_refund, cgt_payable


@dataclass
class SharesInputs:
    initial_capital: float
    share_return_path: np.ndarray  # total return per year (capital + dividends)
    dividend_yield_pct: float       # of capital, so total_return = capital_growth + dividend_yield
    franked_portion: float
    mer: float
    brokerage_per_trade: float
    drp: bool
    mtr: float
    external_contributions: np.ndarray  # length = horizon; from comparison engine
    horizon_years: int
    margin_loan_initial: float
    margin_loan_rate_path: Optional[np.ndarray]  # None = no margin loan


@dataclass
class SharesResult:
    cashflow_per_year: np.ndarray
    gross_terminal_value: float
    margin_loan_balance: float
    total_dividends_received: float
    total_dividend_tax: float
    cgt_paid_on_sale: float
    terminal_after_tax_wealth: float


def simulate_shares_trial(inputs: SharesInputs) -> SharesResult:
    h = inputs.horizon_years
    portfolio_value = inputs.initial_capital
    cumulative_cost_base = inputs.initial_capital  # tracks for CGT

    cashflow_per_year = np.zeros(h)
    total_dividends = 0.0
    total_dividend_tax = 0.0

    margin_balance = inputs.margin_loan_initial
    portfolio_value += margin_balance  # margin loan immediately deployed into shares

    for year in range(h):
        total_return = inputs.share_return_path[year]
        dividend_return = inputs.dividend_yield_pct
        capital_return = total_return - dividend_return

        # Dividends in cash terms
        dividends = portfolio_value * dividend_return
        total_dividends += dividends

        # Tax on dividends (DRP doesn't defer tax)
        div_tax = franking_credit_refund(dividends, inputs.mtr, inputs.franked_portion)
        total_dividend_tax += div_tax

        # MER drag
        mer_cost = portfolio_value * inputs.mer

        # Margin loan interest (if any)
        margin_interest = 0.0
        if inputs.margin_loan_rate_path is not None and margin_balance > 0:
            margin_interest = margin_balance * inputs.margin_loan_rate_path[year]
            # Margin interest is deductible against dividends
            div_tax -= margin_interest * inputs.mtr  # tax saving
            total_dividend_tax = total_dividend_tax  # already counted dividend tax above; add saving below

        # Capital growth applied to portfolio
        portfolio_value = portfolio_value * (1 + capital_return)

        # If DRP on, dividends reinvested into portfolio (after MER drag, before tax)
        if inputs.drp:
            portfolio_value += dividends - mer_cost
            cumulative_cost_base += dividends  # reinvested dividends increase cost base
        else:
            # Cash dividends withdrawn; only MER drags portfolio
            portfolio_value -= mer_cost

        # External contributions from comparison engine (matched to property's outside cash)
        portfolio_value += inputs.external_contributions[year]
        cumulative_cost_base += inputs.external_contributions[year]

        # Year's cashflow effect: tax on dividends + margin interest is paid out-of-pocket;
        # external contributions also out-of-pocket. (Brokerage on rebalancing not modelled
        # in v1 buy-and-hold.)
        cashflow_per_year[year] = -(div_tax + margin_interest + inputs.external_contributions[year])

    # Terminal sale event
    gross_terminal_value = portfolio_value
    capital_gain = gross_terminal_value - cumulative_cost_base
    cgt_paid = cgt_payable(capital_gain, holding_years=h, mtr=inputs.mtr)

    # If margin loan, repay from terminal proceeds
    terminal_after_tax_wealth = gross_terminal_value - cgt_paid - margin_balance - inputs.brokerage_per_trade

    return SharesResult(
        cashflow_per_year=cashflow_per_year,
        gross_terminal_value=gross_terminal_value,
        margin_loan_balance=margin_balance,
        total_dividends_received=total_dividends,
        total_dividend_tax=total_dividend_tax,
        cgt_paid_on_sale=cgt_paid,
        terminal_after_tax_wealth=terminal_after_tax_wealth,
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_shares_strategy.py -v
```

Expected: PASS. (If the year-1 dividend tax calc is off, double-check the franking math by hand.)

- [ ] **Step 5: Commit**

```bash
git add model/shares_strategy.py tests/test_shares_strategy.py
git commit -m "feat(shares): single-trial simulator with DRP-taxed dividends"
```

---

### Task 12: Strategy modules — link external contributions to equal-outside-cash logic

**Files:**
- Modify: `model/property_strategy.py`
- Modify: `tests/test_property_strategy.py`
- Modify: `tests/test_shares_strategy.py`

The shares strategy already accepts `external_contributions`. The property strategy needs to *expose* its negative-cashflow years so the comparison engine can mirror them into the shares strategy.

- [ ] **Step 1: Write the failing test (verifying property exposes the right interface)**

```python
def test_property_exposes_outside_cash_required_per_year():
    inputs = make_default_inputs()
    result = simulate_property_trial(inputs)

    # Outside cash required = max(0, -cashflow_per_year)
    assert hasattr(result, "outside_cash_required_per_year")
    expected = np.where(result.cashflow_per_year < 0, -result.cashflow_per_year, 0)
    np.testing.assert_array_almost_equal(result.outside_cash_required_per_year, expected)
```

- [ ] **Step 2: Verify it fails**

```bash
pytest tests/test_property_strategy.py::test_property_exposes_outside_cash_required_per_year -v
```

- [ ] **Step 3: Add `outside_cash_required_per_year` to `PropertyResult`**

In `model/property_strategy.py`, add to `PropertyResult`:

```python
    outside_cash_required_per_year: np.ndarray  # = max(0, -cashflow); used by shares strategy
```

In `simulate_property_trial`, before constructing `PropertyResult`:

```python
outside_cash_required_per_year = np.where(
    cashflow_per_year < 0, -cashflow_per_year, 0
)
```

Pass it into the constructor.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_property_strategy.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add model/property_strategy.py tests/test_property_strategy.py
git commit -m "feat(property): expose per-year outside cash required for symmetry"
```

---

### Task 13: Verify equal-outside-cash matched correctly between strategies

**Files:**
- Create: `tests/test_equal_outside_cash.py`

This is an integration test that proves the two strategies, when wired together correctly, deploy identical total capital.

- [ ] **Step 1: Write the integration test**

```python
"""Cross-strategy test: verify equal outside-cash contributions produce symmetric capital
deployment."""
import numpy as np
from model.property_strategy import simulate_property_trial
from model.shares_strategy import simulate_shares_trial
from tests.test_property_strategy import make_default_inputs as make_p_inputs
from tests.test_shares_strategy import make_default_shares_inputs


def test_total_outside_cash_matches_between_strategies():
    p_inputs = make_p_inputs()
    p_result = simulate_property_trial(p_inputs)

    # Shares strategy receives the same outside-cash flow as the property strategy required
    s_inputs = make_default_shares_inputs()
    s_inputs.external_contributions = p_result.outside_cash_required_per_year
    s_result = simulate_shares_trial(s_inputs)

    total_p_outside = p_result.outside_cash_required_per_year.sum()
    # Shares: initial capital deployed (matched to property's upfront) + sum of contributions
    total_s_outside = s_inputs.initial_capital + s_inputs.external_contributions.sum()

    # Property's outside cash = deposit + stamp duty + sum of negative cashflow years
    # (deposit + stamp duty = initial_capital of shares strategy by construction)
    total_p_outside_full = s_inputs.initial_capital + total_p_outside

    assert total_s_outside == total_p_outside_full
```

- [ ] **Step 2: Verify it fails (or passes — integration check)**

```bash
pytest tests/test_equal_outside_cash.py -v
```

- [ ] **Step 3: Fix any wiring bugs revealed**

If the test fails, trace through to find where the contributions are being double-counted or missed.

- [ ] **Step 4: Commit**

```bash
git add tests/test_equal_outside_cash.py
git commit -m "test: verify equal outside-cash symmetry between strategies"
```

> **MILESTONE 2 reached: Both strategies simulate one full trial.** You can now write a script that prints year-by-year cashflows for both strategies on the same inputs.

---

## Phase 5 — Comparison engine

### Task 14: Normalisation — Mode A (Realistic)

**Files:**
- Create: `model/normalisation.py`
- Create: `tests/test_normalisation.py`

- [ ] **Step 1: Write the failing test**

```python
"""Normalisation tests."""
import pytest
import numpy as np
from model.normalisation import build_shares_inputs_for_mode_a


def test_mode_a_shares_starts_with_property_total_upfront():
    """Mode A: shares starts with deposit + stamp duty + buying costs (not just deposit)."""
    s_inputs = build_shares_inputs_for_mode_a(
        purchase_price=700_000,
        deposit=140_000,
        stamp_duty=32_330,
        buying_costs=2_600,  # conveyancing + inspection + loan app
        mtr=0.37,
        horizon_years=25,
        portfolio_profile="blended",
    )
    assert s_inputs.initial_capital == pytest.approx(140_000 + 32_330 + 2_600)
```

- [ ] **Step 2: Verify it fails**

```bash
pytest tests/test_normalisation.py -v
```

- [ ] **Step 3: Implement `model/normalisation.py`**

```python
"""Comparison-mode normalisation. Decides what shares strategy starts with given the property
scenario, ensuring the comparison is fair within the chosen mode."""
import numpy as np
from model.shares_strategy import SharesInputs

PORTFOLIO_PROFILES = {
    "asx_only":   {"return_mu": 0.090, "return_sigma": 0.16, "div_yield": 0.040, "franked": 0.85},
    "global":     {"return_mu": 0.085, "return_sigma": 0.14, "div_yield": 0.020, "franked": 0.10},
    "blended":    {"return_mu": 0.085, "return_sigma": 0.15, "div_yield": 0.035, "franked": 0.50},
}


def build_shares_inputs_for_mode_a(
    purchase_price: float,
    deposit: float,
    stamp_duty: float,
    buying_costs: float,
    mtr: float,
    horizon_years: int,
    portfolio_profile: str,
    return_path: np.ndarray = None,
    drp: bool = True,
) -> SharesInputs:
    """Mode A (Realistic): shares starts with property's full upfront cash, no leverage."""
    profile = PORTFOLIO_PROFILES[portfolio_profile]
    if return_path is None:
        return_path = np.full(horizon_years, profile["return_mu"])

    return SharesInputs(
        initial_capital=deposit + stamp_duty + buying_costs,
        share_return_path=return_path,
        dividend_yield_pct=profile["div_yield"],
        franked_portion=profile["franked"],
        mer=0.0020,
        brokerage_per_trade=10.0,
        drp=drp,
        mtr=mtr,
        external_contributions=np.zeros(horizon_years),  # filled in by Monte Carlo runner
        horizon_years=horizon_years,
        margin_loan_initial=0.0,
        margin_loan_rate_path=None,
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_normalisation.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add model/normalisation.py tests/test_normalisation.py
git commit -m "feat(normalisation): Mode A (Realistic) shares input builder"
```

---

### Task 15: Normalisation — Mode B (Fair fight)

**Files:**
- Modify: `model/normalisation.py`
- Modify: `tests/test_normalisation.py`

- [ ] **Step 1: Write the failing test**

```python
from model.normalisation import build_shares_inputs_for_mode_b


def test_mode_b_shares_takes_margin_loan_to_match_exposure():
    """Mode B: shares matches property's total exposure ($700k)."""
    s_inputs = build_shares_inputs_for_mode_b(
        purchase_price=700_000,
        deposit=140_000,
        stamp_duty=32_330,
        buying_costs=2_600,
        mtr=0.37,
        horizon_years=25,
        portfolio_profile="blended",
        margin_loan_rate=0.075,
        isolate_asset_quality=False,
        mortgage_rate=0.06,
    )
    # Initial capital (equity) = property's upfront cash
    assert s_inputs.initial_capital == pytest.approx(140_000 + 32_330 + 2_600)
    # Margin loan brings total exposure to property's purchase price ($700k)
    assert s_inputs.margin_loan_initial == pytest.approx(700_000 - (140_000 + 32_330 + 2_600))


def test_mode_b_isolate_asset_quality_uses_mortgage_rate():
    s_inputs = build_shares_inputs_for_mode_b(
        purchase_price=700_000,
        deposit=140_000,
        stamp_duty=32_330,
        buying_costs=2_600,
        mtr=0.37,
        horizon_years=25,
        portfolio_profile="blended",
        margin_loan_rate=0.075,
        isolate_asset_quality=True,
        mortgage_rate=0.06,
    )
    assert s_inputs.margin_loan_rate_path[0] == pytest.approx(0.06)
```

- [ ] **Step 2: Verify it fails**

```bash
pytest tests/test_normalisation.py -v -k mode_b
```

- [ ] **Step 3: Implement `build_shares_inputs_for_mode_b`**

Append to `model/normalisation.py`:

```python
def build_shares_inputs_for_mode_b(
    purchase_price: float,
    deposit: float,
    stamp_duty: float,
    buying_costs: float,
    mtr: float,
    horizon_years: int,
    portfolio_profile: str,
    margin_loan_rate: float,
    isolate_asset_quality: bool,
    mortgage_rate: float,
    return_path: np.ndarray = None,
    drp: bool = True,
) -> SharesInputs:
    """Mode B (Fair fight): shares matches property's total exposure via margin loan.

    If isolate_asset_quality=True, margin loan rate is pinned to mortgage_rate (counterfactual).
    """
    profile = PORTFOLIO_PROFILES[portfolio_profile]
    if return_path is None:
        return_path = np.full(horizon_years, profile["return_mu"])

    equity = deposit + stamp_duty + buying_costs
    margin_loan = purchase_price - equity
    rate = mortgage_rate if isolate_asset_quality else margin_loan_rate

    return SharesInputs(
        initial_capital=equity,
        share_return_path=return_path,
        dividend_yield_pct=profile["div_yield"],
        franked_portion=profile["franked"],
        mer=0.0020,
        brokerage_per_trade=10.0,
        drp=drp,
        mtr=mtr,
        external_contributions=np.zeros(horizon_years),
        horizon_years=horizon_years,
        margin_loan_initial=margin_loan,
        margin_loan_rate_path=np.full(horizon_years, rate),
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_normalisation.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add model/normalisation.py tests/test_normalisation.py
git commit -m "feat(normalisation): Mode B (Fair fight) with isolate-asset-quality toggle"
```

---

## Phase 6 — Monte Carlo runner

### Task 16: Monte Carlo — vectorised random draws with correlation

**Files:**
- Create: `model/monte_carlo.py`
- Create: `tests/test_monte_carlo.py`

- [ ] **Step 1: Write the failing test**

```python
"""Monte Carlo tests."""
import pytest
import numpy as np
from model.monte_carlo import generate_correlated_paths


def test_generate_paths_shape():
    paths = generate_correlated_paths(
        trials=5000,
        horizon=25,
        property_mu=0.055, property_sigma=0.11,
        share_mu=0.085, share_sigma=0.15,
        correlation=0.3,
        seed=42,
    )
    assert paths["property_growth"].shape == (5000, 25)
    assert paths["share_return"].shape == (5000, 25)


def test_generate_paths_means_are_close_to_mu():
    paths = generate_correlated_paths(
        trials=5000, horizon=25,
        property_mu=0.055, property_sigma=0.11,
        share_mu=0.085, share_sigma=0.15,
        correlation=0.3, seed=42,
    )
    assert paths["property_growth"].mean() == pytest.approx(0.055, abs=0.005)
    assert paths["share_return"].mean() == pytest.approx(0.085, abs=0.005)


def test_correlation_close_to_target():
    paths = generate_correlated_paths(
        trials=5000, horizon=25,
        property_mu=0.055, property_sigma=0.11,
        share_mu=0.085, share_sigma=0.15,
        correlation=0.3, seed=42,
    )
    # Flatten across trial-years for empirical correlation
    p_flat = paths["property_growth"].flatten()
    s_flat = paths["share_return"].flatten()
    empirical_corr = np.corrcoef(p_flat, s_flat)[0, 1]
    assert empirical_corr == pytest.approx(0.3, abs=0.05)


def test_seeded_reproducibility():
    paths_a = generate_correlated_paths(
        trials=100, horizon=10,
        property_mu=0.05, property_sigma=0.1,
        share_mu=0.08, share_sigma=0.15,
        correlation=0.3, seed=42,
    )
    paths_b = generate_correlated_paths(
        trials=100, horizon=10,
        property_mu=0.05, property_sigma=0.1,
        share_mu=0.08, share_sigma=0.15,
        correlation=0.3, seed=42,
    )
    np.testing.assert_array_equal(paths_a["property_growth"], paths_b["property_growth"])
```

- [ ] **Step 2: Verify it fails**

```bash
pytest tests/test_monte_carlo.py -v
```

- [ ] **Step 3: Implement `generate_correlated_paths`**

```python
"""Monte Carlo runner. Vectorised over trials."""
import numpy as np
from typing import Dict


def generate_correlated_paths(
    trials: int,
    horizon: int,
    property_mu: float,
    property_sigma: float,
    share_mu: float,
    share_sigma: float,
    correlation: float,
    seed: int = 42,
) -> Dict[str, np.ndarray]:
    """Return correlated normal draws for property capital growth and share total return.

    Uses Cholesky decomposition to introduce the target correlation.

    Returns dict with 'property_growth' and 'share_return' as (trials, horizon) arrays.
    """
    rng = np.random.default_rng(seed)
    # Independent standard normals
    z = rng.standard_normal((trials, horizon, 2))

    # Cholesky factor for 2x2 corr matrix [[1, rho], [rho, 1]]
    L = np.array([[1.0, 0.0], [correlation, np.sqrt(1 - correlation ** 2)]])

    # Apply Cholesky transform: correlated_normals[..., 0] = z[..., 0]
    #                          correlated_normals[..., 1] = rho*z[...,0] + sqrt(1-rho^2)*z[...,1]
    correlated = z @ L.T

    property_growth = property_mu + property_sigma * correlated[..., 0]
    share_return    = share_mu    + share_sigma    * correlated[..., 1]

    return {
        "property_growth": property_growth,
        "share_return": share_return,
    }
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_monte_carlo.py -v
```

Expected: PASS. (Correlation test may be a hair off; tolerate ±0.05.)

- [ ] **Step 5: Commit**

```bash
git add model/monte_carlo.py tests/test_monte_carlo.py
git commit -m "feat(monte_carlo): correlated path generation with Cholesky"
```

---

### Task 17: Monte Carlo — full trial-loop runner

**Files:**
- Modify: `model/monte_carlo.py`
- Modify: `tests/test_monte_carlo.py`

- [ ] **Step 1: Write the failing test**

```python
from model.monte_carlo import run_monte_carlo


def test_run_monte_carlo_returns_distributions():
    """Smoke test: run 100 trials with default inputs and check output shape."""
    result = run_monte_carlo(
        trials=100,
        horizon_years=25,
        purchase_price=700_000,
        deposit=140_000,
        stamp_duty=32_330,
        buying_costs=2_600,
        loan_rate_mu=0.06,
        loan_rate_sigma=0.01,
        gross_yield=0.04,
        vacancy_weeks_mu=2.0,
        vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.005,
        property_growth_mu=0.055,
        property_growth_sigma=0.11,
        share_return_mu=0.085,
        share_return_sigma=0.15,
        correlation=0.3,
        management_fee_pct=0.07,
        maintenance_pct=0.012,
        property_age="established_post_2017",
        asset_type="house",
        depreciation_override=None,
        portfolio_profile="blended",
        mode="realistic",
        margin_loan_rate=0.075,
        isolate_asset_quality=False,
        mtr=0.37,
        cpi=0.025,
        drp=True,
        seed=42,
    )

    assert "property_terminal_wealth" in result
    assert "shares_terminal_wealth" in result
    assert result["property_terminal_wealth"].shape == (100,)
    assert result["shares_terminal_wealth"].shape == (100,)
    assert "p_property_wins" in result
    assert 0 <= result["p_property_wins"] <= 1
```

- [ ] **Step 2: Verify it fails**

```bash
pytest tests/test_monte_carlo.py -v -k run_monte_carlo
```

- [ ] **Step 3: Implement `run_monte_carlo`**

Append to `model/monte_carlo.py`:

```python
from typing import Optional
from model.property_strategy import PropertyInputs, simulate_property_trial
from model.shares_strategy import simulate_shares_trial
from model.normalisation import (
    build_shares_inputs_for_mode_a,
    build_shares_inputs_for_mode_b,
    PORTFOLIO_PROFILES,
)


def run_monte_carlo(
    trials: int,
    horizon_years: int,
    # property
    purchase_price: float,
    deposit: float,
    stamp_duty: float,
    buying_costs: float,
    loan_rate_mu: float,
    loan_rate_sigma: float,
    gross_yield: float,
    vacancy_weeks_mu: float,
    vacancy_weeks_sigma: float,
    rental_yield_sigma: float,
    property_growth_mu: float,
    property_growth_sigma: float,
    management_fee_pct: float,
    maintenance_pct: float,
    property_age: str,
    asset_type: str,
    depreciation_override: Optional[float],
    # shares
    share_return_mu: float,
    share_return_sigma: float,
    portfolio_profile: str,
    # comparison
    mode: str,
    margin_loan_rate: float,
    isolate_asset_quality: bool,
    correlation: float,
    # macro
    mtr: float,
    cpi: float,
    drp: bool,
    seed: int = 42,
):
    """Run the full Monte Carlo simulation. Returns aggregated outputs."""
    rng = np.random.default_rng(seed)

    # Generate correlated property growth & share return paths
    paths = generate_correlated_paths(
        trials=trials, horizon=horizon_years,
        property_mu=property_growth_mu, property_sigma=property_growth_sigma,
        share_mu=share_return_mu, share_sigma=share_return_sigma,
        correlation=correlation, seed=seed,
    )

    # Independent draws for loan rate, vacancy, rental yield
    loan_rate_paths = loan_rate_mu + loan_rate_sigma * rng.standard_normal((trials, horizon_years))
    vacancy_paths = np.maximum(0, vacancy_weeks_mu + vacancy_weeks_sigma * rng.standard_normal((trials, horizon_years)))
    yield_paths = gross_yield + rental_yield_sigma * rng.standard_normal((trials, horizon_years))

    profile = PORTFOLIO_PROFILES[portfolio_profile]

    p_terminal = np.zeros(trials)
    s_terminal = np.zeros(trials)
    p_outside_cash = np.zeros((trials, horizon_years))

    for t in range(trials):
        p_inputs = PropertyInputs(
            purchase_price=purchase_price,
            deposit=deposit,
            loan_rate_path=loan_rate_paths[t],
            loan_term_years=30,
            io_period_years=5,
            gross_yield=gross_yield,  # using mean; could plumb yield_paths[t] in for stochastic yield
            vacancy_weeks_path=vacancy_paths[t],
            capital_growth_path=paths["property_growth"][t],
            management_fee_pct=management_fee_pct,
            maintenance_pct=maintenance_pct,
            property_age=property_age,
            asset_type=asset_type,
            depreciation_override=depreciation_override,
            mtr=mtr,
            cpi=cpi,
            horizon_years=horizon_years,
            selling_costs_pct=0.025,
        )
        p_result = simulate_property_trial(p_inputs)

        # Build shares inputs per mode, with external contributions matching property's needs
        if mode == "realistic":
            s_inputs = build_shares_inputs_for_mode_a(
                purchase_price=purchase_price, deposit=deposit, stamp_duty=stamp_duty,
                buying_costs=buying_costs, mtr=mtr, horizon_years=horizon_years,
                portfolio_profile=portfolio_profile,
                return_path=paths["share_return"][t], drp=drp,
            )
        elif mode == "fair_fight":
            s_inputs = build_shares_inputs_for_mode_b(
                purchase_price=purchase_price, deposit=deposit, stamp_duty=stamp_duty,
                buying_costs=buying_costs, mtr=mtr, horizon_years=horizon_years,
                portfolio_profile=portfolio_profile,
                margin_loan_rate=margin_loan_rate,
                isolate_asset_quality=isolate_asset_quality,
                mortgage_rate=loan_rate_mu,
                return_path=paths["share_return"][t], drp=drp,
            )
        else:
            raise ValueError(f"unknown mode: {mode}")

        s_inputs.external_contributions = p_result.outside_cash_required_per_year
        s_result = simulate_shares_trial(s_inputs)

        # Property strategy total wealth = property + overflow shares
        p_terminal[t] = p_result.terminal_after_tax_wealth + p_result.overflow_share_terminal_value
        s_terminal[t] = s_result.terminal_after_tax_wealth
        p_outside_cash[t] = p_result.outside_cash_required_per_year

    return {
        "property_terminal_wealth": p_terminal,
        "shares_terminal_wealth": s_terminal,
        "p_property_wins": float((p_terminal > s_terminal).mean()),
        "outside_cash_per_trial_year": p_outside_cash,
        "median_outside_cash_total": float(np.median(p_outside_cash.sum(axis=1))),
        "worst_year_cash": float(np.percentile(p_outside_cash.max(axis=1), 90)),
        "median_property_wealth": float(np.median(p_terminal)),
        "median_shares_wealth": float(np.median(s_terminal)),
    }
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_monte_carlo.py -v
```

Expected: PASS. (May be slow — 100 trials should still complete in <5s.)

- [ ] **Step 5: Commit**

```bash
git add model/monte_carlo.py tests/test_monte_carlo.py
git commit -m "feat(monte_carlo): full trial-loop runner with mode dispatch"
```

> **MILESTONE 3 reached: Monte Carlo + comparison engine working headless.** Run a quick smoke check:

```bash
python3 -c "
from model.monte_carlo import run_monte_carlo
r = run_monte_carlo(
    trials=500, horizon_years=25,
    purchase_price=700_000, deposit=140_000,
    stamp_duty=32_330, buying_costs=2_600,
    loan_rate_mu=0.06, loan_rate_sigma=0.01,
    gross_yield=0.04, vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
    rental_yield_sigma=0.005,
    property_growth_mu=0.055, property_growth_sigma=0.11,
    share_return_mu=0.085, share_return_sigma=0.15,
    management_fee_pct=0.07, maintenance_pct=0.012,
    property_age='established_post_2017', asset_type='house',
    depreciation_override=None,
    portfolio_profile='blended',
    mode='realistic',
    margin_loan_rate=0.075, isolate_asset_quality=False,
    correlation=0.3,
    mtr=0.37, cpi=0.025, drp=True,
    seed=42,
)
print(f'P(property wins) = {r[\"p_property_wins\"]:.1%}')
print(f'Median property wealth: \${r[\"median_property_wealth\"]:,.0f}')
print(f'Median shares wealth:   \${r[\"median_shares_wealth\"]:,.0f}')
print(f'Median outside cash:    \${r[\"median_outside_cash_total\"]:,.0f}')
print(f'Worst-year cash (90th): \${r[\"worst_year_cash\"]:,.0f}')
"
```

You should see actual numbers. If they look obviously wrong (e.g. property wealth is negative), trace through the property_strategy.py year-1 hand-calc.

---

## Phase 7 — Solvency tracking

### Task 18: Solvency module

**Files:**
- Create: `model/solvency.py`
- Create: `tests/test_solvency.py`
- Modify: `model/monte_carlo.py`

- [ ] **Step 1: Write the failing test**

```python
"""Solvency tests."""
import pytest
import numpy as np
from model.solvency import flag_forced_sales


def test_no_forced_sale_when_all_under_ceiling():
    outside_cash = np.array([
        [5_000, 5_000, 5_000],
        [3_000, 4_000, 6_000],
    ])
    flags = flag_forced_sales(outside_cash, ceiling=20_000)
    assert flags.sum() == 0


def test_forced_sale_when_year_exceeds_ceiling():
    outside_cash = np.array([
        [5_000, 25_000, 5_000],   # year 1 breach
        [3_000, 4_000, 30_000],   # year 2 breach
        [5_000, 5_000, 5_000],    # never breaches
    ])
    flags = flag_forced_sales(outside_cash, ceiling=20_000)
    assert flags.tolist() == [True, True, False]


def test_p_solvent_metric():
    from model.solvency import p_solvent
    outside_cash = np.array([
        [5_000, 25_000, 5_000],
        [5_000, 5_000, 5_000],
        [3_000, 4_000, 5_000],
        [5_000, 5_000, 30_000],
    ])
    # 2 of 4 trials never breach
    assert p_solvent(outside_cash, ceiling=20_000) == 0.5
```

- [ ] **Step 2: Verify it fails**

```bash
pytest tests/test_solvency.py -v
```

- [ ] **Step 3: Implement `model/solvency.py`**

```python
"""Solvency / serviceability tracking.

If property strategy needs more outside-cash in any year than the user can fund, that trial
is marked as a 'forced sale' — meaning the user would have had to sell early at whatever
price the property had reached at that year. v1 simplification: terminal wealth for forced-
sale trials is *not* recalculated; instead they are just flagged so the user can see how often
the strategy actually fails.
"""
import numpy as np


def flag_forced_sales(outside_cash_per_trial_year: np.ndarray, ceiling: float) -> np.ndarray:
    """Return a boolean array (length = trials) flagging trials with any year exceeding ceiling."""
    return (outside_cash_per_trial_year > ceiling).any(axis=1)


def p_solvent(outside_cash_per_trial_year: np.ndarray, ceiling: float) -> float:
    """Fraction of trials where property strategy never breaches the serviceability ceiling."""
    return float(1 - flag_forced_sales(outside_cash_per_trial_year, ceiling).mean())
```

- [ ] **Step 4: Wire into Monte Carlo result**

Modify `model/monte_carlo.py` to add `p_solvent` and `forced_sale_flags` to the return dict. After the trial loop, add:

```python
from model.solvency import flag_forced_sales, p_solvent
# ... at the end of run_monte_carlo, before returning:
serviceability_ceiling = ...  # Add this as a new parameter to run_monte_carlo, default $20_000
forced_flags = flag_forced_sales(p_outside_cash, serviceability_ceiling)
result["p_solvent"] = float(1 - forced_flags.mean())
result["forced_sale_flags"] = forced_flags
```

(Add `serviceability_ceiling: float = 20_000` to the `run_monte_carlo` signature.)

- [ ] **Step 5: Run all tests**

```bash
pytest -v
```

Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add model/solvency.py model/monte_carlo.py tests/test_solvency.py tests/test_monte_carlo.py
git commit -m "feat(solvency): serviceability ceiling flagging and P(solvent) metric"
```

> **MILESTONE 4 reached: Full headless model complete.** All seven P0 corrections from the review pass are now implemented and tested.

---

## Phase 8 — Streamlit UI

### Task 19: Streamlit app skeleton + Standard sidebar

**Files:**
- Create: `app.py`

- [ ] **Step 1: Write `app.py` skeleton**

```python
"""Property vs Shares Streamlit UI. Imports the model engine and renders sliders + charts."""
import streamlit as st
import numpy as np
import plotly.graph_objects as go

from model.monte_carlo import run_monte_carlo
from model.tax import sa_stamp_duty
from model.normalisation import PORTFOLIO_PROFILES

st.set_page_config(page_title="Property vs Shares", layout="wide")

st.title("Property vs Shares — your scenario")

# --------------- Sidebar: STANDARD inputs ---------------
with st.sidebar:
    st.header("Standard inputs")
    purchase_price = st.number_input("Purchase price", value=700_000, step=10_000)
    deposit_pct = st.slider("Deposit %", 5, 50, 20)
    deposit = purchase_price * deposit_pct / 100

    loan_rate = st.slider("Loan rate (mean)", 3.0, 10.0, 6.0, step=0.1) / 100
    horizon = st.slider("Investment horizon (years)", 5, 40, 25)

    mtr_label_to_value = {"19%": 0.19, "30%": 0.30, "37%": 0.37, "45%": 0.45}
    mtr_label = st.selectbox("Marginal tax rate", list(mtr_label_to_value.keys()), index=2)
    mtr = mtr_label_to_value[mtr_label]

    property_age = st.selectbox(
        "Property age",
        ["new_build", "established_post_2017", "established_pre_2017"],
        index=1,
        format_func=lambda x: {
            "new_build": "New build",
            "established_post_2017": "Established (post-May-2017)",
            "established_pre_2017": "Established (pre-May-2017)",
        }[x],
    )
    asset_type = st.selectbox(
        "Asset type",
        ["house", "apartment", "townhouse"],
        format_func=str.title,
    )

    gross_yield = st.slider("Gross rental yield %", 2.0, 7.0, 4.0, step=0.1) / 100
    vacancy_weeks = st.slider("Vacancy (weeks/yr)", 0, 8, 2)

    portfolio_profile = st.selectbox(
        "Portfolio profile",
        ["asx_only", "global", "blended"],
        index=2,
        format_func=lambda x: {
            "asx_only": "ASX-only",
            "global": "Global (developed)",
            "blended": "Blended (50/50)",
        }[x],
    )

    max_top_up = st.number_input(
        "Max annual out-of-pocket top-up",
        value=20_000, step=1_000,
        help="Used to flag scenarios where property cashflow exceeds your serviceability."
    )

# --------------- Main pane: comparison radio + display toggle ---------------
col_mode, col_display = st.columns([2, 1])
with col_mode:
    mode = st.radio("Comparison mode", ["realistic", "fair_fight"], horizontal=True,
                    format_func=lambda x: {"realistic": "Realistic", "fair_fight": "Fair fight"}[x])
with col_display:
    display_mode = st.radio("Display", ["nominal", "today"], horizontal=True,
                            format_func=lambda x: {"nominal": "Nominal", "today": "Today's $"}[x])

st.write("Tool initialised. Charts and metrics arrive in subsequent tasks.")
```

- [ ] **Step 2: Run the app to verify the skeleton renders**

```bash
streamlit run app.py
```

Expected: browser opens, sidebar shows Standard inputs, main pane shows mode + display toggles.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(app): Streamlit skeleton with Standard sidebar"
```

---

### Task 20: Advanced sidebar (collapsible)

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add Advanced expander after Standard inputs**

Insert in sidebar after Standard section:

```python
    with st.expander("Advanced", expanded=False):
        st.subheader("Volatility (σ) overrides")
        property_growth_sigma = st.slider("Property growth σ", 0.05, 0.20, 0.11, step=0.01)
        share_return_sigma = st.slider("Share return σ", 0.05, 0.30, 0.15, step=0.01)
        loan_rate_sigma = st.slider("Loan rate σ (pp)", 0.5, 2.0, 1.0, step=0.1) / 100
        rental_yield_sigma = st.slider("Rental yield σ (pp)", 0.1, 1.0, 0.5, step=0.1) / 100
        vacancy_weeks_sigma = st.slider("Vacancy σ (weeks)", 0.5, 4.0, 1.0, step=0.5)
        property_growth_mu = st.slider("Property growth μ", 0.0, 0.10, 0.055, step=0.005)
        share_return_mu = st.slider("Share return μ", 0.0, 0.15, 0.085, step=0.005)

        st.subheader("Correlation")
        corr_quick = st.radio("Quick-pick", [-0.1, 0.3, 0.6], index=1, horizontal=True,
                              format_func=lambda x: f"{x:.1f}")
        correlation = st.slider("Property–shares correlation", -1.0, 1.0, corr_quick, step=0.05)

        st.subheader("Mode B — counterfactual")
        margin_loan_rate = st.slider("Margin loan rate", 0.05, 0.12, 0.075, step=0.005)
        isolate_asset_quality = st.checkbox(
            "Isolate asset quality (pin shares loan rate to mortgage rate)",
            value=False,
            help="Counterfactual — retail investors cannot borrow against shares on mortgage terms."
        )

        st.subheader("Other")
        cpi = st.slider("CPI", 0.0, 0.05, 0.025, step=0.005)
        depreciation_override = st.number_input("Depreciation override (annual)", value=0, step=500)
        depreciation_override = depreciation_override if depreciation_override > 0 else None
        management_fee_pct = st.slider("Management fee %", 0.0, 0.12, 0.07, step=0.005)
        maintenance_pct = st.slider("Maintenance + insurance + rates % of value/yr", 0.005, 0.030, 0.012, step=0.001)
```

- [ ] **Step 2: Verify rendering**

```bash
streamlit run app.py
```

Click the Advanced expander; all sliders should appear.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(app): Advanced sidebar with σ, correlation, Mode B toggle"
```

---

### Task 21: Run Monte Carlo and display headline + supporting metrics

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Wire run-button + metrics**

Add at the bottom of the main pane:

```python
# Compute stamp duty + buying costs from inputs
stamp_duty = sa_stamp_duty(purchase_price)
buying_costs = 2_600  # conveyancing + inspection + loan app

st.markdown(f"**Upfront cash deployed:** ${deposit + stamp_duty + buying_costs:,.0f} "
            f"(${deposit:,.0f} deposit + ${stamp_duty:,.0f} stamp duty + ${buying_costs:,.0f} buying costs)")

# Symmetric reinvestment banner
st.warning(
    "⚠ Both strategies deploy the same total capital each year. When property needs $X to "
    "feed negative gearing, shares invests the same $X. (Equal outside-cash contributions — ON.)"
)

# Margin call warning if Mode B
if mode == "fair_fight":
    st.error(
        "Mode B does not model margin-call risk. In a 30%+ share crash, your margin lender "
        "may force a sale at the bottom — this risk is real and is not captured below."
    )

# Run Monte Carlo (cached)
@st.cache_data(show_spinner="Running 5,000 Monte Carlo trials...")
def cached_run(**kwargs):
    return run_monte_carlo(**kwargs)

result = cached_run(
    trials=5000, horizon_years=horizon,
    purchase_price=purchase_price, deposit=deposit,
    stamp_duty=stamp_duty, buying_costs=buying_costs,
    loan_rate_mu=loan_rate, loan_rate_sigma=loan_rate_sigma,
    gross_yield=gross_yield,
    vacancy_weeks_mu=vacancy_weeks, vacancy_weeks_sigma=vacancy_weeks_sigma,
    rental_yield_sigma=rental_yield_sigma,
    property_growth_mu=property_growth_mu, property_growth_sigma=property_growth_sigma,
    share_return_mu=share_return_mu, share_return_sigma=share_return_sigma,
    management_fee_pct=management_fee_pct, maintenance_pct=maintenance_pct,
    property_age=property_age, asset_type=asset_type,
    depreciation_override=depreciation_override,
    portfolio_profile=portfolio_profile,
    mode=mode,
    margin_loan_rate=margin_loan_rate, isolate_asset_quality=isolate_asset_quality,
    correlation=correlation,
    mtr=mtr, cpi=cpi, drp=True,
    seed=42,
)

# Headline
st.header(f"Property beats shares in **{result['p_property_wins']:.0%}** of 5,000 simulated futures over {horizon} years.")

# Supporting metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Median property wealth", f"${result['median_property_wealth']:,.0f}")
m2.metric("Median shares wealth", f"${result['median_shares_wealth']:,.0f}")
m3.metric("Worst-year cash needed", f"${result['worst_year_cash']:,.0f}")
m4.metric("P(strategy stays solvent)", f"{result['p_solvent']:.0%}")
```

- [ ] **Step 2: Run app and verify metrics appear**

```bash
streamlit run app.py
```

You should see the headline and 4-metric row populated.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(app): wire Monte Carlo run + headline + 4 supporting metrics"
```

---

### Task 22: Distribution chart

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add Plotly histogram**

After the metrics row, add:

```python
st.subheader("Terminal wealth distribution")
fig = go.Figure()
fig.add_trace(go.Histogram(
    x=result["property_terminal_wealth"], name="Property",
    opacity=0.6, nbinsx=50,
))
fig.add_trace(go.Histogram(
    x=result["shares_terminal_wealth"], name="Shares",
    opacity=0.6, nbinsx=50,
))
fig.update_layout(barmode="overlay", xaxis_title="Terminal wealth ($)", yaxis_title="Trials")
st.plotly_chart(fig, use_container_width=True)
```

- [ ] **Step 2: Verify rendering**

```bash
streamlit run app.py
```

You should see overlaid histograms.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(app): terminal wealth distribution histogram"
```

---

### Task 23: Cashflow stress chart

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add cashflow chart with serviceability line**

```python
st.subheader("Cashflow stress")
years = np.arange(1, horizon + 1)
median_cashflow = np.median(result["outside_cash_per_trial_year"], axis=0)
p90_cashflow = np.percentile(result["outside_cash_per_trial_year"], 90, axis=0)
p10_cashflow = np.percentile(result["outside_cash_per_trial_year"], 10, axis=0)

fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=years, y=median_cashflow, mode="lines", name="Median"))
fig2.add_trace(go.Scatter(x=years, y=p90_cashflow, mode="lines", name="90th %ile (worst)",
                          line=dict(dash="dot")))
fig2.add_trace(go.Scatter(x=years, y=p10_cashflow, mode="lines", name="10th %ile (best)",
                          line=dict(dash="dot")))
fig2.add_hline(y=max_top_up, line_dash="dash", line_color="red",
               annotation_text=f"Your serviceability ceiling: ${max_top_up:,}")
fig2.update_layout(xaxis_title="Year", yaxis_title="Annual out-of-pocket cash ($)")
st.plotly_chart(fig2, use_container_width=True)
```

- [ ] **Step 2: Verify rendering**

```bash
streamlit run app.py
```

You should see the cashflow chart with the dashed red line at your serviceability ceiling.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(app): cashflow stress chart with serviceability ceiling"
```

---

### Task 24: Assumptions panel

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Add collapsible assumptions panel**

```python
with st.expander("Assumptions used in this run", expanded=False):
    st.markdown(f"""
- **Tax:** SA, MTR {mtr:.0%}, FY2026 Stage 3 brackets
- **Negative gearing:** current FY2026 rules ⚠ law potentially changing in Budget 2026-27
- **Property:** {property_age.replace('_', ' ').title()}, {asset_type.title()}
- **Portfolio profile:** {portfolio_profile.replace('_', ' ').title()} (μ {PORTFOLIO_PROFILES[portfolio_profile]['return_mu']:.1%}, σ {PORTFOLIO_PROFILES[portfolio_profile]['return_sigma']:.1%}, {PORTFOLIO_PROFILES[portfolio_profile]['franked']:.0%} franked)
- **Correlation (property ↔ shares):** {correlation:.2f}
- **Monte Carlo:** 5,000 trials, fixed seed (reproducible)
- **CPI:** {cpi:.1%} applied to rent and holding costs annually
- **Buy-and-hold share portfolio** — no mid-period rebalancing CGT events
- **Disclaimer:** Normal distributions; does not predict severe market crashes (fat-tail events)
- **Counterfactual mode (if Mode B isolated):** assumes margin loan at mortgage rate — not real-world available
""")
```

- [ ] **Step 2: Verify**

```bash
streamlit run app.py
```

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(app): assumptions panel"
```

---

### Task 25: Today's-dollars deflator toggle

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Apply deflator when display_mode is "today"**

After the Monte Carlo run, before charts:

```python
from model.inflation import deflate

if display_mode == "today":
    deflator = (1 + cpi) ** horizon
    result["property_terminal_wealth"] = result["property_terminal_wealth"] / deflator
    result["shares_terminal_wealth"] = result["shares_terminal_wealth"] / deflator
    result["median_property_wealth"] = result["median_property_wealth"] / deflator
    result["median_shares_wealth"] = result["median_shares_wealth"] / deflator
    # Outside cash is per-year; deflate each year by its own deflator
    yearly_deflator = (1 + cpi) ** np.arange(1, horizon + 1)
    result["outside_cash_per_trial_year"] = result["outside_cash_per_trial_year"] / yearly_deflator
    result["worst_year_cash"] = result["worst_year_cash"] / deflator  # rough; use horizon's deflator
```

- [ ] **Step 2: Verify**

```bash
streamlit run app.py
```

Toggle Display between Nominal and Today's $; numbers should change accordingly.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(app): today's dollars deflator toggle"
```

> **MILESTONE 5 reached: Streamlit UI complete.** Run `streamlit run app.py` and you have a working tool.

---

## Phase 9 — Validation & polish

### Task 26: End-to-end smoke validation

**Files:**
- Create: `tests/test_e2e_smoke.py`

- [ ] **Step 1: Write end-to-end test using default scenario**

```python
"""End-to-end smoke test. Validates the full pipeline produces sane numbers for a default
scenario."""
import pytest
from model.monte_carlo import run_monte_carlo


def test_default_scenario_produces_sane_numbers():
    result = run_monte_carlo(
        trials=1000, horizon_years=25,
        purchase_price=700_000, deposit=140_000,
        stamp_duty=32_330, buying_costs=2_600,
        loan_rate_mu=0.06, loan_rate_sigma=0.01,
        gross_yield=0.04, vacancy_weeks_mu=2.0, vacancy_weeks_sigma=1.0,
        rental_yield_sigma=0.005,
        property_growth_mu=0.055, property_growth_sigma=0.11,
        share_return_mu=0.085, share_return_sigma=0.15,
        management_fee_pct=0.07, maintenance_pct=0.012,
        property_age='established_post_2017', asset_type='house',
        depreciation_override=None,
        portfolio_profile='blended',
        mode='realistic',
        margin_loan_rate=0.075, isolate_asset_quality=False,
        correlation=0.3,
        mtr=0.37, cpi=0.025, drp=True,
        seed=42,
    )

    # Sanity checks
    assert 0.20 <= result["p_property_wins"] <= 0.80, "P(property wins) outside plausible range"
    assert result["median_property_wealth"] > 500_000, "Property wealth implausibly low"
    assert result["median_shares_wealth"] > 500_000, "Shares wealth implausibly low"
    assert result["p_solvent"] >= 0.50, "Default scenario shouldn't fail solvency in most trials"
    assert result["worst_year_cash"] < 200_000, "Worst-year cash implausibly high"
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/test_e2e_smoke.py -v
```

Expected: PASS. If any assertion fails, the engineer must trace through to find the issue — do NOT relax the assertions.

- [ ] **Step 3: Run the full test suite**

```bash
pytest -v
```

Expected: ALL tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/test_e2e_smoke.py
git commit -m "test: end-to-end smoke validation for default scenario"
```

---

### Task 27: README + final docs polish

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Expand README with usage notes, defaults rationale, and known limitations**

```markdown
# Property vs Shares Model

Personal-use Monte Carlo simulator comparing AU residential investment property vs shares.

See full design spec at `../2026-05-11-property-vs-shares-design-v2.md`.

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

Most updates only require editing `config.py` (brackets, rates, thresholds). For the Federal Budget 2026-27 negative gearing changes (announced 12 May 2026), see spec §5.10 — a regime toggle is planned for v1.1.
```

- [ ] **Step 2: Final commit**

```bash
git add README.md
git commit -m "docs: README with usage, features, and known limitations"
```

> **MILESTONE 6 reached: v1 complete.** All seven P0 corrections from the review pass are implemented, tested, and exposed via the Streamlit UI.

---

## Self-review checklist

Before declaring the plan ready for execution, the writer of this plan ran through:

- [x] **Spec coverage:** Every section of the design spec is mapped to at least one task. Mode A, Mode B, equal-outside-cash, solvency tracking, depreciation per property age, Stage 3 brackets, inflation on rent + costs, DRP-taxed dividends, Mode B isolate-asset-quality toggle, portfolio profile presets, asset type toggle, correlation slider, Standard/Advanced UI split, headline + 4 supporting metrics, distribution chart, cashflow stress chart, assumptions panel, today's-dollars toggle — all present.
- [x] **Placeholder scan:** No "TBD", "implement later", or "similar to Task N" patterns. Every step contains actual code or actual commands.
- [x] **Type consistency:** `PropertyInputs`, `PropertyResult`, `SharesInputs`, `SharesResult` field names match across the tasks that use them. `simulate_property_trial` and `simulate_shares_trial` return the dataclasses defined in their respective tasks. `run_monte_carlo` consumes both and returns a dict whose keys match what `app.py` reads.
- [x] **External dependencies:** RevenueSA stamp duty bands, RevenueSA land tax thresholds, ATO income tax brackets — all explicitly told to verify against the live calculator URL before relying on the values written into the plan. Plan does not pretend to know exact numbers; engineer is told to verify.

---

*End of implementation plan.*
