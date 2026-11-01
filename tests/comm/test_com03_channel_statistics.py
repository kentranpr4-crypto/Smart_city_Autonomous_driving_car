"""COM-03 · channel statistics: Gilbert-Elliott, duplication, reordering, blackout, corruption, bandwidth/queue. One pre-registered seed; chi-square 95% / exact tolerances."""
import math
import numpy as np
import pytest
from comm.channel import Channel, LinkConfig, simulate
from perception.stats import chi2_ppf

pytestmark = pytest.mark.com
SEED = 20261101


def sends(n, dt=0.01, size=60):
    return [(i * dt, bytes([i % 256]) * size) for i in range(n)]


def test_gilbert_elliott_stationary_loss_rate_and_burst_length():
    p_gb, p_bg, lg, lb = 0.05, 0.30, 0.02, 0.60
    ch = Channel(LinkConfig("ge", ge=(p_gb, p_bg, lg, lb)), SEED)
    states, lost = [], []
    for i in range(300000):
        o = ch.send(i * 0.001, b"z"); states.append(ch.ge_bad); lost.append(o.dropped == "loss")
    pi_bad = p_gb / (p_gb + p_bg)
    expect_loss = (1 - pi_bad) * lg + pi_bad * lb
    assert abs(np.mean(lost) - expect_loss) <= 0.004                                    # analytic 0.10286
    assert abs(np.mean(states) - pi_bad) <= 0.004                                        # analytic 0.14286
    runs, cur = [], 0
    for s in states:
        if s: cur += 1
        elif cur: runs.append(cur); cur = 0
    assert abs(np.mean(runs) - 1 / p_bg) <= 0.1                                          # mean bad-state burst 3.33 packets


def test_duplication_rate_and_extra_delay_bounds():
    cfg = LinkConfig("d", base_delay_s=0.03, jitter_s=0.0, dup_p=0.2, dup_extra_delay_s=(0.01, 0.05))
    outs, _ = simulate(cfg, SEED, sends(20000))
    dups = [o for o in outs if len(o.copies) == 2]
    assert abs(len(dups) / 20000 - 0.2) <= 4 * math.sqrt(0.2 * 0.8 / 20000)
    for o in dups:
        extra = o.copies[1].t_deliver - o.copies[0].t_deliver
        assert 0.01 - 1e-12 <= extra <= 0.05 + 1e-12 and o.copies[1].flags[-1] == "dup" and o.copies[1].payload == o.copies[0].payload


def test_no_reordering_without_cause_and_every_inversion_involves_a_flagged_packet():
    s = sends(4000, dt=0.05)
    calm = LinkConfig("c", base_delay_s=0.03, jitter_s=0.02)                             # jitter < send gap: order must be preserved
    _, d = simulate(calm, SEED, s)
    t = [x.t_deliver for x in d]
    assert t == sorted(t) and all(not x.flags for x in d)
    wild = LinkConfig("w", base_delay_s=0.03, jitter_s=0.02, reorder_p=0.2, reorder_extra_delay_s=(0.1, 0.3))
    outs, d = simulate(wild, SEED, s)
    by_msg = {}
    for i, o in enumerate(outs):
        for c in o.copies: by_msg[i] = c
    inv = [(i, j) for i in range(len(s)) for j in range(i + 1, min(len(s), i + 12)) if i in by_msg and j in by_msg and by_msg[j].t_deliver < by_msg[i].t_deliver]
    assert len(inv) > 100                                                                 # reordering really happens
    assert all("reordered" in by_msg[i].flags for i, j in inv)                            # and only the delayed (flagged) packet is overtaken
    assert abs(sum("reordered" in c.flags for c in by_msg.values()) / len(by_msg) - 0.2) <= 0.02


def test_blackout_loses_exactly_the_packets_sent_in_the_half_open_window():
    cfg = LinkConfig("b", base_delay_s=0.01, blackouts=((1.0, 2.0), (5.0, 5.5)))
    outs, _ = simulate(cfg, SEED, sends(800, dt=0.01))
    for i, o in enumerate(outs):
        t = i * 0.01
        inside = (1.0 <= t < 2.0) or (5.0 <= t < 5.5)
        assert (o.dropped == "blackout") == inside, (i, t)


def test_corruption_flips_exactly_one_byte_and_at_the_configured_rate():
    cfg = LinkConfig("c", base_delay_s=0.01, corrupt_p=0.3)
    s = sends(5000, size=80)
    outs, _ = simulate(cfg, SEED, s)
    flipped = 0
    for (t, p), o in zip(s, outs):
        got = o.copies[0].payload
        diff = [i for i in range(len(p)) if p[i] != got[i]]
        assert len(got) == len(p) and len(diff) <= 1 and (bool(diff) == ("corrupted" in o.copies[0].flags))
        flipped += bool(diff)
    assert abs(flipped / len(s) - 0.3) <= 4 * math.sqrt(0.3 * 0.7 / len(s))


def test_jitter_is_uniform_chi2_95():
    cfg = LinkConfig("j", base_delay_s=0.03, jitter_s=0.02)
    outs, _ = simulate(cfg, SEED, sends(20000))
    d = np.array([o.copies[0].t_deliver - i * 0.01 - 0.03 for i, o in enumerate(outs)])
    assert d.min() >= 0 and d.max() <= 0.02
    obs, _ = np.histogram(d, bins=10, range=(0, 0.02)); exp = len(d) / 10
    assert float(((obs - exp) ** 2 / exp).sum()) <= chi2_ppf(0.95, 9)


def reference_queue(sends_, bps, limit, base):
    """Independent model of a FIFO serialization link with a byte-limited queue."""
    free, out = 0.0, []
    for t, p in sends_:
        backlog = max(0.0, free - t) * bps
        if limit is not None and backlog + len(p) > limit:
            out.append(("queue_overflow", None)); continue
        free = max(t, free) + len(p) / bps
        out.append((None, free + base))
    return out


@pytest.mark.parametrize("bps,limit", [(10000.0, None), (10000.0, 2500), (60000.0, 1500)])
def test_bandwidth_serialization_and_queue_overflow_match_an_independent_model(bps, limit):
    s = [(i * 0.05, bytes(1000)) for i in range(200)]                                    # 20 kB/s offered
    cfg = LinkConfig("q", base_delay_s=0.02, bandwidth_Bps=bps, queue_limit_bytes=limit)
    outs, _ = simulate(cfg, SEED, s)
    ref = reference_queue(s, bps, limit, 0.02)
    for o, (drop, t) in zip(outs, ref):
        assert o.dropped == drop
        if t is not None: assert o.copies[0].t_deliver == pytest.approx(t, abs=1e-9)
    if bps == 10000.0 and limit is None:
        gaps = np.diff([o.copies[0].t_deliver for o in outs]); assert gaps[10:].min() == pytest.approx(0.1) and gaps[10:].max() == pytest.approx(0.1)   # capacity-bound spacing
    if limit == 2500 and bps == 10000.0:
        assert sum(o.dropped == "queue_overflow" for o in outs) > 50                      # offered load is 2x capacity: the queue overflows
