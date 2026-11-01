"""COM-02 · deterministic discrete-event channel and replay: independent of wall clock, process, PYTHONHASHSEED and step/render granularity."""
import hashlib, json, os, pathlib, random, subprocess, sys, time
import pytest
from comm.channel import Channel, LinkConfig, N_DRAWS, simulate
from tests.comm.harness import run_scripted

pytestmark = pytest.mark.com
ROOT = pathlib.Path(__file__).resolve().parents[2]
CFG = LinkConfig("L", base_delay_s=0.03, jitter_s=0.02, loss_p=0.1, dup_p=0.1, reorder_p=0.1, corrupt_p=0.05, blackouts=((0.4, 0.5),), bandwidth_Bps=50000.0, queue_limit_bytes=3000)
SENDS = [(0.01 * i, bytes([i % 251]) * (50 + i % 40)) for i in range(300)]


def digest(outs, dels):
    h = hashlib.sha256()
    for o in outs: h.update(repr((o.dropped, o.t_tx_done, [(d.t_deliver, d.payload, d.copy, d.flags) for d in o.copies])).encode())
    return h.hexdigest()


def test_same_seed_same_outcomes_and_different_seed_differs():
    a, b, c = simulate(CFG, 5, SENDS), simulate(CFG, 5, SENDS), simulate(CFG, 6, SENDS)
    assert digest(*a) == digest(*b) and digest(*a) != digest(*c)


def test_wall_clock_jitter_between_sends_changes_nothing():
    rnd = random.Random(99)
    ch = Channel(CFG, 5); outs = []
    for t, p in SENDS:
        time.sleep(rnd.random() * 0.0004)                              # hostile wall-clock behaviour
        outs.append(ch.send(t, p))
    ref, _ = simulate(CFG, 5, SENDS)
    assert [(o.dropped, o.t_tx_done, o.copies) for o in outs] == [(o.dropped, o.t_tx_done, o.copies) for o in ref]


@pytest.mark.parametrize("hashseed", ["0", "4242"])
def test_other_process_and_pythonhashseed_give_the_same_digest(hashseed):
    code = ("import hashlib, sys\nfrom comm.channel import LinkConfig, simulate\n"
            "CFG = LinkConfig('L', base_delay_s=0.03, jitter_s=0.02, loss_p=0.1, dup_p=0.1, reorder_p=0.1, corrupt_p=0.05, blackouts=((0.4, 0.5),), bandwidth_Bps=50000.0, queue_limit_bytes=3000)\n"
            "S = [(0.01 * i, bytes([i % 251]) * (50 + i % 40)) for i in range(300)]\nouts, dels = simulate(CFG, 5, S)\nh = hashlib.sha256()\n"
            "for o in outs: h.update(repr((o.dropped, o.t_tx_done, [(d.t_deliver, d.payload, d.copy, d.flags) for d in o.copies])).encode())\nprint(h.hexdigest())\n")
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, env={"PYTHONHASHSEED": hashseed, "PYTHONPATH": str(ROOT), "PATH": "/usr/bin"})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == digest(*simulate(CFG, 5, SENDS))


def test_random_draws_per_packet_are_fixed_so_parameters_never_shift_other_packets():
    """Paired-seed discipline: a lossless link and a lossy link share jitter/dup/reorder draws packet by packet."""
    clean = LinkConfig("L", base_delay_s=0.03, jitter_s=0.02, dup_p=0.2, reorder_p=0.2)
    lossy = LinkConfig("L", base_delay_s=0.03, jitter_s=0.02, loss_p=0.5, dup_p=0.2, reorder_p=0.2)
    s = [(0.01 * i, b"x" * 40) for i in range(500)]
    oc, _ = simulate(clean, 11, s); ol, _ = simulate(lossy, 11, s)
    survivors = [(a, b) for a, b in zip(oc, ol) if b.dropped is None]
    assert 150 < len(survivors) < 350 and N_DRAWS == 10
    assert all(a.copies == b.copies for a, b in survivors)               # identical delays, duplicates, flags for every surviving packet


def test_links_have_independent_streams():
    a = LinkConfig("A", jitter_s=0.02, loss_p=0.3); b = LinkConfig("B", jitter_s=0.02, loss_p=0.3)
    s = [(0.01 * i, b"y" * 30) for i in range(200)]
    only_b, _ = simulate(b, 3, s)
    ca, cb = Channel(a, 3), Channel(b, 3)
    mixed = []
    for t, p in s:
        ca.send(t, p); mixed.append(cb.send(t, p))                        # traffic on A must not perturb B
    assert [(o.dropped, o.copies) for o in only_b] == [(o.dropped, o.copies) for o in mixed]


def _digest_net(net):
    return net.tel.hexdigest()


LINK = LinkConfig("k>ego", base_delay_s=0.03, jitter_s=0.02, loss_p=0.1, dup_p=0.1, reorder_p=0.1, reorder_extra_delay_s=(0.05, 0.2))


def test_full_network_replay_is_identical_and_independent_of_call_frequency_and_wall_clock():
    base = _digest_net(run_scripted(LINK, seed=7, step_dt=0.01)[0])
    assert base == _digest_net(run_scripted(LINK, seed=7, step_dt=0.01)[0])
    assert base == _digest_net(run_scripted(LINK, seed=7, step_dt=0.05)[0])            # 5x fewer step() calls ("lower render rate"): same events
    rnd = random.Random(1)
    assert base == _digest_net(run_scripted(LINK, seed=7, step_dt=0.01, on_step=lambda n, t: time.sleep(rnd.random() * 0.0002), duration=10.0)[0])
    assert base != _digest_net(run_scripted(LINK, seed=8, step_dt=0.01)[0])


def test_equal_time_events_are_ordered_deliveries_before_processing():
    link = LinkConfig("k>ego", base_delay_s=0.03)
    net, *_ = run_scripted(link, seed=1, duration=2.0, proc_delay=0.0)               # recv and proc happen at the SAME instant
    ev = [e for e in net.tel.events if e["type"] in ("recv", "proc")]
    for r, p in zip(ev[0::2], ev[1::2]):
        assert r["type"] == "recv" and p["type"] == "proc" and r["t"] == p["t"] and r["msg_id"] == p["msg_id"]


def test_blackout_and_queue_overflow_consume_the_same_draws_as_delivered_packets():
    """Found by mutation: if a blacked-out packet consumed fewer draws, every later packet would shift. Outcomes outside the outage must be identical."""
    base = dict(base_delay_s=0.03, jitter_s=0.02, dup_p=0.2, reorder_p=0.2)
    clean = LinkConfig("L", **base)
    outage = LinkConfig("L", **base, blackouts=((1.0, 2.0),))
    s = [(0.01 * i, b"x" * 40) for i in range(500)]
    oc, _ = simulate(clean, 11, s); oo, _ = simulate(outage, 11, s)
    outside = [(a, b, t) for (t, _), a, b in zip(s, oc, oo) if not (1.0 <= t < 2.0)]
    assert len(outside) == 400 and all(a.copies == b.copies for a, b, _ in outside)
    assert all(b.dropped == "blackout" for (t, _), b in zip(s, oo) if 1.0 <= t < 2.0)
