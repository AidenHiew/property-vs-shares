import pytest
from model.duty import stamp_duty, DUTY_SCHEDULES

def test_all_states_present():
    assert set(DUTY_SCHEDULES) == {"NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"}

def test_nsw_marginal_700k():
    # $700k sits in the $372k–$1.24M band: base $11,152 + 4.5% over $372k.
    assert stamp_duty("NSW", 700_000) == pytest.approx(11_152 + 0.045 * (700_000 - 372_000), abs=1)

def test_schedules_contiguous_no_gaps():
    # Every marginal/flat schedule must tile [0, INF) with no gaps/overlaps —
    # guards against a dropped or mis-bounded band (each lower == previous upper).
    for state, segs in DUTY_SCHEDULES.items():
        if not segs:  # NT uses a formula, not segments
            continue
        assert segs[0][0] == 0, f"{state} first band must start at 0"
        for prev, cur in zip(segs, segs[1:]):
            assert cur[0] == prev[1], f"{state} gap/overlap at {cur[0]} vs {prev[1]}"
        assert segs[-1][1] == float("inf"), f"{state} last band must end at INF"

def test_sa_700k_no_transfer_fee():
    assert stamp_duty("SA", 700_000) == pytest.approx(21_330 + 0.055 * (700_000 - 500_000), abs=1)

def test_qld_700k():
    assert stamp_duty("QLD", 700_000) == pytest.approx(17_325 + 0.045 * (700_000 - 540_000), abs=1)

def test_tas_min_50_under_3k():
    assert stamp_duty("TAS", 2_000) == pytest.approx(50, abs=0.5)
    assert stamp_duty("TAS", 3_000) == pytest.approx(50, abs=0.5)

def test_zero_or_negative_price():
    assert stamp_duty("NSW", 0) == 0.0
    assert stamp_duty("VIC", -5) == 0.0
