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


def test_marginal_tax_custom_brackets():
    """Verify the brackets= parameter is actually plumbed through."""
    simple = [(10_000, 0.0), (float("inf"), 0.50)]
    assert marginal_tax(15_000, brackets=simple) == pytest.approx(2_500)


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


def test_unfranked_dividend_taxed_at_mtr():
    """Purely unfranked dividend: no credit, full MTR applies to cash dividend."""
    # $700 unfranked dividend at MTR 30% → no credit, no gross-up.
    # Tax = $700 * 30% = $210. Net (positive = owed) = $210.
    assert franking_credit_refund(700, mtr=0.30, franked_portion=0.0) == pytest.approx(210)


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


def test_cgt_at_exactly_12_months_no_discount():
    """Boundary: exactly 12 months held does NOT qualify for 50% discount."""
    # $100k gain at MTR 37%, no discount = $37,000
    assert cgt_payable(gain=100_000, holding_years=1.0, mtr=0.37) == pytest.approx(37_000)


from model.tax import sa_stamp_duty


# Expected values computed from the SA_DUTY_BANDS encoded in tax.py.
# Verify against the official RevenueSA calculator before relying:
# https://www.revenuesa.sa.gov.au/stamp-duty/transfer-of-property
def test_stamp_duty_zero_price():
    assert sa_stamp_duty(0) == 0


def test_stamp_duty_400k():
    # Band walk: $11,330 base at $300k + ($400k - $300k) * 5.0% = $16,330; + $181 fee
    assert sa_stamp_duty(400_000) == pytest.approx(16_511, abs=1)


def test_stamp_duty_700k():
    # Band walk: $21,330 base at $500k + ($700k - $500k) * 5.5% = $32,330; + $181 fee
    assert sa_stamp_duty(700_000) == pytest.approx(32_511, abs=1)


def test_stamp_duty_1_2m():
    # Band walk: $21,330 base at $500k + ($1,200k - $500k) * 5.5% = $59,830; + $181 fee
    assert sa_stamp_duty(1_200_000) == pytest.approx(60_011, abs=1)


def test_stamp_duty_at_band_boundary_500k():
    # Exactly at $500k boundary: $11,330 base + ($500k - $300k) * 5.0% = $21,330; + $181 fee
    # (price <= upper, so $500k uses the $300k-$500k band's 5.0% rate)
    assert sa_stamp_duty(500_000) == pytest.approx(21_511, abs=1)


from model.tax import sa_land_tax


# Expected values derived from SA_LAND_TAX_BANDS encoded in tax.py.
# Verify against RevenueSA before relying on production:
# https://revenuesa.sa.gov.au/landtax/rates-and-thresholds
def test_land_tax_zero():
    assert sa_land_tax(0) == 0


def test_land_tax_below_threshold():
    assert sa_land_tax(500_000) == 0


def test_land_tax_at_threshold_boundary():
    # $833k uses the 0% band (<= boundary semantics)
    assert sa_land_tax(833_000) == 0


def test_land_tax_900k_in_first_taxable_band():
    # ($900k - $833k) * 0.5% = $335
    assert sa_land_tax(900_000) == pytest.approx(335, abs=1)


def test_land_tax_1_5m_in_middle_band():
    # $1,895 + ($1.5m - $1.212m) * 1.0% = $1,895 + $2,880 = $4,775
    assert sa_land_tax(1_500_000) == pytest.approx(4_775, abs=1)


def test_land_tax_2m_in_top_band():
    # $7,335 + ($2m - $1.756m) * 2.4% = $7,335 + $5,856 = $13,191
    assert sa_land_tax(2_000_000) == pytest.approx(13_191, abs=1)


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
