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

# --- Legislated boundary discontinuities (NOT bugs; assert the jumps) ---

def test_vic_960k_step_up():
    below = stamp_duty("VIC", 960_000)
    at = stamp_duty("VIC", 960_001)
    assert below == pytest.approx(52_670, abs=1)
    assert at == pytest.approx(0.055 * 960_001, abs=1)   # ~52_800
    assert at > below                                     # legislated step UP

def test_vic_2m_continuous_into_top_band():
    assert stamp_duty("VIC", 2_000_000) == pytest.approx(0.055 * 2_000_000, abs=1)  # 110_000
    assert stamp_duty("VIC", 2_000_001) == pytest.approx(110_000 + 0.065 * 1, abs=1)

def test_nt_quadratic_and_flat_seam():
    v = 525_000 / 1000.0
    assert stamp_duty("NT", 525_000) == pytest.approx(0.06571441 * v * v + 15 * v, abs=1)
    assert stamp_duty("NT", 525_001) == pytest.approx(0.0495 * 525_001, abs=1)

def test_nt_3m_and_5m_jumps():
    assert stamp_duty("NT", 2_999_999) == pytest.approx(0.0495 * 2_999_999, abs=1)
    assert stamp_duty("NT", 3_000_000) == pytest.approx(0.0575 * 3_000_000, abs=1)  # +~24k
    assert stamp_duty("NT", 5_000_000) == pytest.approx(0.0595 * 5_000_000, abs=1)  # +~10k

def test_act_flat_top_band():
    assert stamp_duty("ACT", 1_455_000) == pytest.approx(36_950 + 0.064 * (1_455_000 - 1_000_000), abs=1)
    assert stamp_duty("ACT", 1_456_000) == pytest.approx(0.0454 * 1_456_000, abs=1)
