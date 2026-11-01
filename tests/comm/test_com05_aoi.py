"""COM-05 · observation-time AoI: exact sawtooth, never reduced by older/duplicate/relayed copies, per source and per track."""
import numpy as np
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from comm.aoi import AoIMeter
from comm.channel import LinkConfig
from tests.comm.harness import run_scripted

pytestmark = pytest.mark.com


def brute_age(updates, t):
    seen = [o for (u, o) in updates if u <= t]
    return None if not seen else t - max(seen)


def test_hand_computed_sawtooth_with_an_ignored_older_update():
    m = AoIMeter()
    assert [m.observe(1.0, 0.8), m.observe(2.0, 1.5), m.observe(2.5, 1.2), m.observe(4.0, 3.5)] == [True, True, False, True]
    assert m.age(0.9) is None and m.age(1.5) == pytest.approx(0.7) and m.age(3.0) == pytest.approx(1.5)
    assert m.peak(5.0) == pytest.approx(2.5) and m.time_average(5.0) == pytest.approx((0.7 + 3.0 + 1.0) / 4.0)   # 4.7 / 4 by hand
    assert (m.resets, m.ignored) == (3, 1)


updates = st.lists(st.tuples(st.floats(0, 100), st.floats(0, 100)), min_size=1, max_size=40).map(lambda l: sorted(l)).filter(lambda l: all(o <= u for u, o in l))


@settings(max_examples=200, derandomize=True, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(ups=updates)
def test_meter_equals_the_brute_force_definition(ups):
    m = AoIMeter()
    for u, o in ups: m.observe(u, o)
    t_end = ups[-1][0] + 1.0
    for t in np.linspace(ups[0][0], t_end, 57):
        assert m.age(float(t)) == pytest.approx(brute_age(ups, float(t)), abs=1e-9)
    grid = np.linspace(ups[0][0], t_end, 20001)
    ages = np.array([brute_age(ups, float(t)) for t in grid])
    assert m.peak(t_end) >= ages.max() - 1e-9 and m.peak(t_end) <= ages.max() + (grid[1] - grid[0]) + 1e-9
    assert m.time_average(t_end) == pytest.approx(float(np.trapezoid(ages, grid) / (t_end - ups[0][0])), abs=5e-3)


@settings(max_examples=100, derandomize=True, deadline=None)
@given(ups=updates)
def test_only_a_strictly_newer_observation_ever_resets_the_age(ups):
    m = AoIMeter(); obs = []
    for u, o in ups:
        before = m.age(u) if m.segments else None
        reset = m.observe(u, o)
        if reset: obs.append(m.fresh)
        if before is not None and not reset: assert m.age(u) == pytest.approx(before)        # an ignored update leaves AoI untouched
    assert all(b > a for a, b in zip(obs, obs[1:]))                                           # observation times of resets strictly increase


def test_network_aoi_with_duplicates_and_reordering_equals_the_brute_force_over_admitted_messages():
    link = LinkConfig("k>ego", base_delay_s=0.03, jitter_s=0.04, dup_p=0.3, reorder_p=0.2, reorder_extra_delay_s=(0.05, 0.4), loss_p=0.1)
    net, store, adm, _ = run_scripted(link, seed=5, duration=20.0, adm_kw={"max_age_s": 5.0, "reorder_window": 50})
    admitted = [(e["t"], e["eval"]["obs_sim"]) for e in net.tel.events if e["type"] == "proc" and e["verdict"] == "admit"]
    meter = net.eval_aoi[("ego", "k")]
    assert meter.ignored > 0 and meter.resets > 100                                          # reordering/duplication really exercised the ignore path
    for t in np.linspace(admitted[0][0], 20.0, 400):
        assert meter.age(float(t)) == pytest.approx(brute_age(admitted, float(t)), abs=1e-9)
    assert not any(e["reason"] == "duplicate" and e["verdict"] == "admit" for e in net.tel.events if e["type"] == "proc")


def test_estimated_aoi_at_the_receiver_equals_true_aoi_when_clocks_agree():
    net, store, *_ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03, jitter_s=0.02, loss_p=0.05), seed=4, duration=15.0)
    est, true = store.aoi_src["k"], net.eval_aoi[("ego", "k")]
    assert [round(a, 9) for _, a in est.segments] == [round(a, 9) for _, a in true.segments]


def test_track_level_aoi_grows_while_the_source_keeps_publishing_a_coasting_track():
    """After t=3 s the target stops being detected; the tracker coasts it (<=1.5 s) and keeps publishing, so source AoI stays small but the TRACK's information ages."""
    net, store, *_ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03), seed=1, duration=4.2, det_fn=lambda t: [(2.0 + t, 0.0, 0.04)] if t < 3.0 else [])
    src, trk = store.aoi_src["k"], next(iter(store.aoi_track.values()))
    t_end = 4.2
    assert src.age(t_end) < 0.2                                                               # fresh messages keep arriving
    assert trk.age(t_end) > 1.0                                                               # ...but the track's last real measurement is >1 s old
    assert trk.age(t_end) > src.age(t_end) + 0.9
