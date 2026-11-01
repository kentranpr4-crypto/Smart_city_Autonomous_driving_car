"""PHY-08 (definition from PRD §12.2, implemented as written): 'Lịch giao thông điệp biết trước → AoI răng cưa tính tay; thống kê trễ/mất/jitter khớp tham số'.
Tolerances: AoI exact; statistics chi-square 95% with one pre-registered seed."""
import math
import numpy as np
import pytest
from comm.aoi import AoIMeter
from comm.channel import LinkConfig, simulate
from perception.stats import chi2_ppf

pytestmark = pytest.mark.phy
SEED = 20261101
BASE, PROC, OBS_LEAD = 0.030, 0.005, 0.020           # link delay, receiver processing, observation made 20 ms before sending


def run_schedule(n=40, dropped=()):
    """Known schedule: message k sent at 0.1*k, observed at 0.1*k - OBS_LEAD, link delay BASE, processing PROC; messages in `dropped` never arrive."""
    sends = [(round(0.1 * k, 9), b"x") for k in range(n)]
    cfg = LinkConfig("s", base_delay_s=BASE, blackouts=tuple((0.1 * k - 1e-6, 0.1 * k + 1e-6) for k in dropped))
    outs, _ = simulate(cfg, SEED, sends)
    m = AoIMeter()
    for k, o in enumerate(outs):
        if o.dropped is None:
            m.observe(o.copies[0].t_deliver + PROC, 0.1 * k - OBS_LEAD)
    return m, outs


def test_saw_tooth_without_loss_matches_the_hand_computation_exactly():
    m, _ = run_schedule(40)
    t_end = 0.1 * 39 + BASE + PROC                          # end exactly at the last update
    low = BASE + PROC + OBS_LEAD                            # age right after each update: 0.055 s (by hand)
    assert all(a == pytest.approx(low, abs=1e-12) for _, a in m.segments)
    assert m.peak(t_end) == pytest.approx(low + 0.1, abs=1e-12)               # 0.155 s just before the next update
    assert m.time_average(t_end) == pytest.approx(low + 0.05, abs=1e-12)      # 0.105 s: low + period/2
    assert m.age(0.1 * 20 + BASE + PROC - 1e-9) == pytest.approx(low + 0.1, abs=1e-6)


def test_saw_tooth_with_scheduled_losses_matches_the_hand_computation_exactly():
    m, outs = run_schedule(40, dropped=(3, 4, 5))           # three consecutive messages never arrive
    low = BASE + PROC + OBS_LEAD
    assert [o.dropped for o in outs[3:6]] == ["blackout"] * 3
    t_end = 0.1 * 39 + BASE + PROC
    assert m.peak(t_end) == pytest.approx(low + 0.4, abs=1e-12)               # gap between updates k=2 and k=6 is 0.4 s -> tooth of height low+0.4
    # exact time-average by hand: 36 updates of period 0.1 (n teeth) plus the long tooth
    n_short = 40 - 3 - 1 - 1                                # intervals of 0.1 s between consecutive received messages (excluding the long one)
    integral = n_short * (low * 0.1 + 0.5 * 0.1 ** 2) + (low * 0.4 + 0.5 * 0.4 ** 2)
    assert m.time_average(t_end) == pytest.approx(integral / (0.1 * 39 + 0.0 - 0.0 + 0.0 - 0.0 + 0.0 + 0.0 + 0.0 + 0.0), abs=0.0) if False else True
    span = (0.1 * 39 + BASE + PROC) - (0.0 + BASE + PROC)
    assert m.time_average(t_end) == pytest.approx(integral / span, abs=1e-12)


def test_delay_and_jitter_statistics_match_the_parameters():
    cfg = LinkConfig("d", base_delay_s=0.03, jitter_s=0.02)
    outs, _ = simulate(cfg, SEED, [(0.01 * i, b"x") for i in range(20000)])
    d = np.array([o.copies[0].t_deliver - 0.01 * i for i, o in enumerate(outs)])
    assert d.min() >= 0.03 and d.max() <= 0.05                                  # exact support [base, base+jitter]
    assert abs(d.mean() - 0.04) <= 4 * (0.02 / math.sqrt(12)) / math.sqrt(len(d))
    obs, _ = np.histogram(d, bins=10, range=(0.03, 0.05)); exp = len(d) / 10
    assert float(((obs - exp) ** 2 / exp).sum()) <= chi2_ppf(0.95, 9)           # uniform jitter, chi-square 95%


def test_loss_rate_matches_the_parameter_and_is_independent_of_delay():
    cfg = LinkConfig("l", base_delay_s=0.03, jitter_s=0.02, loss_p=0.1)
    n = 30000
    outs, _ = simulate(cfg, SEED, [(0.01 * i, b"x") for i in range(n)])
    lost = np.array([o.dropped == "loss" for o in outs], dtype=float)
    assert abs(lost.mean() - 0.1) <= 4 * math.sqrt(0.1 * 0.9 / n)
    assert abs(float(np.corrcoef(lost[:-1], lost[1:])[0, 1])) <= 4 / math.sqrt(n)   # Bernoulli: no serial correlation
    surv = np.array([o.copies[0].t_deliver - 0.01 * i for i, o in enumerate(outs) if o.dropped is None])
    assert abs(surv.mean() - 0.04) <= 4 * (0.02 / math.sqrt(12)) / math.sqrt(len(surv))   # survivors' delay unaffected by loss
