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
