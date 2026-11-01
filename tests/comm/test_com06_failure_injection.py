"""COM-06 (end-to-end) · failure injection through the full publisher -> channel -> admission -> store path. Every run must satisfy the same invariants."""
import collections, json
import numpy as np
import pytest
from comm.channel import LinkConfig
from comm.telemetry import accounting
from tests.comm.harness import run_scripted
from tests.comm.test_com06_admission import independent_is_valid

pytestmark = pytest.mark.com


def invariants(net, store, adm):
    ev = net.tel.events
    acc = accounting(ev)
    assert acc["ok_sent"] and acc["ok_recv"] and acc["ok_proc"] and acc["ok_verdict"], acc                # INV-4
    sched = {(e["msg_id"], e["copy"]): e["flags"] for e in ev if e["type"] == "sched"}
    send = {e["msg_id"]: e for e in ev if e["type"] == "send"}
    admitted = [e for e in ev if e["type"] == "proc" and e["verdict"] == "admit"]
    assert not any("corrupted" in sched[(e["msg_id"], e["copy"])] or "injected" in sched[(e["msg_id"], e["copy"])] for e in admitted)    # INV-1
    keys = [(send[e["msg_id"]]["origin"], send[e["msg_id"]]["orig_seq"]) for e in admitted]
    assert len(keys) == len(set(keys))                                                                      # INV-2: no content admitted twice
    assert all(e["age_proc_est"] <= adm.cfg.max_age_s + 1e-12 for e in admitted)                            # INV-3
    for s in store.tracks(net.tel.events[-1]["t"] if net.tel.events else 0.0):
        assert np.isfinite([s.entry.x, s.entry.y, s.age_est]).all()
    return acc, admitted, send, sched


def reasons(net):
    return collections.Counter(e["reason"] for e in net.tel.events if e["type"] == "proc" and e["verdict"] == "reject")


def test_heavy_loss():
    net, st, adm, _ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03, loss_p=0.5), seed=1, duration=30.0, step_dt=0.1)
    acc, admitted, *_ = invariants(net, st, adm)
    assert 0.35 < len(admitted) / acc["sent"] < 0.65 and not reasons(net)                                   # losses are silent: nothing is "rejected"


def test_duplicate_storm_is_absorbed_exactly():
    net, st, adm, _ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03, dup_p=0.5, dup_extra_delay_s=(0.01, 0.2)), seed=1, duration=30.0, step_dt=0.1)
    acc, admitted, send, sched = invariants(net, st, adm)
    dup_copies = sum("dup" in f for f in sched.values())
    assert dup_copies > 50 and reasons(net) == {"duplicate": dup_copies} and len(admitted) == acc["sent"]


def test_heavy_reordering_is_admitted_as_late_without_regressing_the_store():
    net, st, adm, _ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03, reorder_p=0.5, reorder_extra_delay_s=(0.1, 0.35)), seed=1, duration=30.0, step_dt=0.1)
    acc, admitted, *_ = invariants(net, st, adm)
    assert sum("late" in e["flags"] for e in admitted) > 20 and not reasons(net)
    assert st.ignored_older > 0                                                                           # older observations arrived after newer ones and were ignored


def test_corruption_storm_never_admits_a_corrupted_packet():
    net, st, adm, _ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03, corrupt_p=0.5), seed=3, duration=60.0, step_dt=0.1)
    acc, admitted, send, sched = invariants(net, st, adm)
    corrupted = sum("corrupted" in f for f in sched.values())
    assert corrupted > 200 and sum(reasons(net).values()) == corrupted                                    # every corrupted copy rejected (previously 5/320 slipped through)
    assert set(reasons(net)) <= {"malformed_bytes", "integrity", "schema", "unsupported_version", "non_finite"}


def test_blackout_leaves_no_phantom_information_and_the_store_goes_empty_without_claiming_free_space():
    snap = {}
    def capture(net, t):
        if abs(t - 4.9) < 1e-9: snap["during"] = net.rx["ego"][1].tracks(4.9)            # snapshot INSIDE the blackout, as a consumer would see it
        if abs(t - 2.9) < 1e-9: snap["before"] = net.rx["ego"][1].tracks(2.9)
    net, st, adm, _ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03, blackouts=((3.0, 5.0),)), seed=1, duration=8.0, step_dt=0.1, on_step=capture)
    acc, admitted, send, sched = invariants(net, st, adm)
    assert not any(3.0 <= send[e["msg_id"]]["t"] < 5.0 for e in admitted)
    assert len(snap["before"]) == 1 and snap["during"] == []                           # fresh before; empty during = "no information" (the API has no way to say "free")
    assert st.aoi_src["k"].peak(8.0) >= 2.0                                            # AoI shows the ~2 s gap


def test_delay_beyond_the_receiver_policy_makes_every_message_stale_exactly():
    net, st, adm, _ = run_scripted(LinkConfig("k>ego", base_delay_s=0.7), seed=1, duration=6.0, step_dt=0.1)
    invariants(net, st, adm)
    assert set(reasons(net)) == {"stale"} and not [e for e in net.tel.events if e["type"] == "proc" and e["verdict"] == "admit"]


def test_replayed_valid_message_is_rejected_as_duplicate_then_as_replay_old():
    """A RECENT delivered message replayed inside the reorder window is a duplicate; an OLD one (beyond the window) is replay_old. Never admitted twice."""
    def attack(net, t):
        if abs(t - 3.0) < 1e-9: net.inject(t, "k", "ego", net.wire[-2])                  # previous message (already delivered and admitted)
        if abs(t - 8.0) < 1e-9: net.inject(t, "k", "ego", net.wire[5])                   # seq 5, far behind the window
    net, st, adm, _ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03), seed=1, duration=9.0, step_dt=0.1, keep_wire=True, on_step=attack)
    invariants(net, st, adm)
    assert [e["reason"] for e in net.tel.events if e["type"] == "proc" and e["verdict"] == "reject"] == ["duplicate", "replay_old"]


def test_garbage_storm_is_rejected_and_leaves_the_store_unchanged():
    rnd = np.random.default_rng(7)
    def storm(net, t):
        if abs(t - 2.0) < 1e-9:
            for i in range(500):
                net.inject(t, "k", "ego", bytes(rnd.integers(0, 256, int(rnd.integers(0, 300)), dtype=np.uint8)), delay_s=0.001 * i)
    net, st, adm, _ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03), seed=1, duration=4.0, step_dt=0.1, on_step=storm)
    acc, admitted, *_ = invariants(net, st, adm)
    inj = [e for e in net.tel.events if e["type"] == "proc" and e["msg_id"].startswith("inject:")]
    assert len(inj) == 500 and all(e["verdict"] == "reject" for e in inj)
    assert len(admitted) == acc["sent"] - 500


def test_oversize_payload_is_cut_off_before_any_parsing():
    net, st, adm, _ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03), seed=1, duration=3.0, step_dt=0.1,
                                   on_step=lambda n, t: n.inject(t, "k", "ego", b"[" * 1_000_000) if abs(t - 1.0) < 1e-9 else None)
    assert reasons(net) == {"oversize": 1}


def test_combined_faults_keep_every_invariant():
    link = LinkConfig("k>ego", base_delay_s=0.05, jitter_s=0.05, ge=(0.05, 0.3, 0.02, 0.6), dup_p=0.1, reorder_p=0.1, corrupt_p=0.1, blackouts=((10.0, 11.0),))
    for seed in range(5):
        net, st, adm, _ = run_scripted(link, seed=seed, duration=30.0, step_dt=0.1)
        invariants(net, st, adm)
