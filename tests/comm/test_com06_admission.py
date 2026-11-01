"""COM-06 · receiver admission control: fail-closed, one reason per rejection, every reason code exercised, no state change on reject, fuzz."""
import copy, json, math
import numpy as np
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from comm.admission import Admission, AdmissionConfig, REASONS, SourceRegistry
from comm.store import ReceiverStore
from comm.trackmsg import serialize, to_dict, deserialize, TrackEntry
from tests.comm.helpers import adm, mutated, msg, track, ORIGIN, with_crc, COV

pytestmark = pytest.mark.com
T_RECV, T_PROC = 1.03, 1.035          # observation at t_meas=1.0 -> age 0.035 s at use


def P(m=None, fn=None, **kw): return serialize(m or msg(**kw)) if fn is None else mutated(m or msg(**kw), fn)
def with_(fn, fix_crc=True, **kw): return mutated(msg(**kw), fn, fix_crc=fix_crc)


def _speed(d): d["tracks"][0].update(vx=100.0)


# reason -> (admission kwargs, registry relays, payload factory, optional warm-up factory)
CASES = {
    "oversize": (dict(max_bytes=100), (), lambda: P(), None),
    "malformed_bytes": ({}, (), lambda: b"{not json", None),
    "integrity": ({}, (), lambda: with_(lambda d: d["tracks"][0].update(x=10.5), fix_crc=False), None),
    "unsupported_version": ({}, (), lambda: with_(lambda d: d.update(schema_version="0.1.0")), None),
    "schema": ({}, (), lambda: with_(lambda d: d.pop("tracks")), None),
    "non_finite": ({}, (), lambda: with_(lambda d: d["tracks"][0].update(x=float("nan")), fix_crc=False), None),
    "bad_covariance": ({}, (), lambda: with_(lambda d: d["tracks"][0]["cov"].__setitem__(0, -1.0)), None),
    "out_of_range": ({}, (), lambda: with_(lambda d: d["tracks"][0].update(existence=1.5)), None),
    "duplicate_track_id": ({}, (), lambda: P(tracks=[track(1), track(1, x=3.0)]), None),
    "invalid_timestamps": ({}, (), lambda: P(t_meas=2.0, t_sent=1.01), None),
    "unknown_source": ({}, (), lambda: P(source="zzz"), None),
    "unsupported_frame": ({}, (), lambda: with_(lambda d: d.update(frame="wgs84")), None),
    "frame_mismatch": ({}, (), lambda: with_(lambda d: d.update(origin_frame_id="other-origin")), None),
    "units_mismatch": ({}, (), lambda: with_(lambda d: d["units"].update(length="ft")), None),
    "yaw_convention_mismatch": ({}, (), lambda: with_(lambda d: d.update(yaw_convention="cw_from_+y")), None),
    "unsupported_confirmation": ({}, (), lambda: P(confirmation="2of3-experimental"), None),
    "too_many_hops": ({}, ("r1", "r2", "r3"), lambda: P(hop=3, relay_path=("r1", "r2", "r3"), tx_node="r3"), None),
    "relay_loop": ({}, ("ego",), lambda: P(hop=1, relay_path=("ego",), tx_node="ego"), None),
    "implausible_kinematics": ({}, (), lambda: with_(_speed), None),
    "outside_roi": (dict(roi=(0.0, 0.0, 12.0, 5.0)), (), lambda: P(tracks=[track(1, x=40.0)]), None),
    "duplicate": ({}, (), lambda: P(seq=4), lambda: P(seq=4)),
    "replay_old": ({}, (), lambda: P(seq=2), lambda: P(seq=20)),
    "future_obs": ({}, (), lambda: P(t_meas=5.0, t_sent=5.01), None),
    "expired_ttl": ({}, (), lambda: P(ttl=0.01), None),
    "stale": ({}, (), lambda: P(t_meas=0.0, ttl=5.0), None),
}


def test_every_reason_code_has_exactly_one_case_and_fires_with_that_exact_reason():
    assert set(CASES) == set(REASONS), set(CASES) ^ set(REASONS)
    for reason, (kw, relays, make, warm) in CASES.items():
        a = adm(relays=relays, **kw)
        if warm: assert a.process(warm(), 1.0, 1.005).admitted
        r = a.process(make(), T_RECV, T_PROC)
        assert (r.admitted, r.reason, r.msg) == (False, reason, None), (reason, r.reason)
        assert a.stats[reason] == 1


def test_a_rejected_message_changes_no_decision_state():
    for reason, (kw, relays, make, warm) in CASES.items():
        a = adm(relays=relays, **kw)
        if reason != "oversize":                                   # (with max_bytes=100 not even the warm-up message fits)
            assert a.process(P(seq=5, t_meas=1.0, tracks=[track(1, x=10.0, t_upd=1.0)]), 1.0, 1.005).admitted
        if warm: a.process(warm(), 1.0, 1.005)
        before = (copy.deepcopy(a._max_seq), copy.deepcopy(a._seen))
        a.process(make(), T_RECV, T_PROC)
        assert (a._max_seq, a._seen) == before, reason


def test_valid_message_is_admitted_with_estimated_ages_and_no_flags():
    r = adm().process(P(seq=0), T_RECV, T_PROC)
    assert r.admitted and r.reason == "ok" and r.flags == () and r.age_recv_est == pytest.approx(0.03) and r.age_proc_est == pytest.approx(0.035)


def test_late_in_window_is_admitted_once_flagged_and_the_window_boundary_is_exact():
    a = adm(reorder_window=8)
    assert a.process(P(seq=20), 1.03, 1.035).admitted
    r = a.process(P(seq=12), 1.03, 1.035)                                      # max - W = 12: still inside the window
    assert r.admitted and "late" in r.flags
    assert a.process(P(seq=12), 1.03, 1.035).reason == "duplicate"             # ...and only once
    assert a.process(P(seq=11), 1.03, 1.035).reason == "replay_old"            # one below the window
    assert a.process(P(seq=21), 1.03, 1.035).admitted                          # newer seq moves the window


def test_fail_closed_one_bad_track_rejects_the_whole_message():
    bad = TrackEntry(2, "pedestrian", 0.9, float("inf"), 0.0, 0.0, 1.0, 0.0, COV, 0.1, 0.9, 1.0)
    from dataclasses import replace
    m = replace(msg(), tracks=(track(1), track(3, x=11.0)))
    d = to_dict(m); d["tracks"].append(to_dict(replace(msg(), tracks=(bad,)))["tracks"][0] | {"x": 1e999})
    payload = json.dumps(with_crc({**d, "tracks": d["tracks"][:2] + [{**d["tracks"][2], "x": 1.0, "existence": -0.5}]}), allow_nan=True).encode()
    r = adm().process(payload, T_RECV, T_PROC)
    assert (r.admitted, r.reason) == (False, "out_of_range")


def test_store_accepts_only_admitted_results():
    a = adm(); st_ = ReceiverStore(0.5)
    with pytest.raises(AssertionError):
        st_.ingest(a.process(b"garbage", T_RECV, T_PROC))
    st_.ingest(a.process(P(), T_RECV, T_PROC))
    assert [s.ref for s in st_.tracks(1.04)] == [("k", 1)]


def test_class_conflict_with_a_confirmed_local_track_is_flagged_not_rejected():
    from perception.tracker import Track
    lt = Track(1, 1.0, (10.0, 2.0, 1.0, 0.0), tuple([0.0] * 16), True, 3.0, 0.9, "vehicle", 5, 0, 1.0, 0.0)
    r = adm().process(P(), T_RECV, T_PROC, local_tracks=(lt,))
    assert r.admitted and "class_conflict" in r.flags
    r2 = adm().process(P(), T_RECV, T_PROC, local_tracks=())
    assert "class_conflict" not in r2.flags


# ------------------------------------------------------------------ fuzz: nothing invalid may be admitted
def independent_is_valid(m, cfg):
    nums = [m.t_meas, m.t_sent, m.ttl_s] + [v for t in m.tracks for v in (t.cls_prob, t.x, t.y, t.yaw, t.vx, t.vy, t.var_yaw, t.existence, t.t_upd, *t.cov)]
    if not all(math.isfinite(v) for v in nums): return False
    for t in m.tracks:
        Pm = np.array(t.cov).reshape(4, 4)
        if not (np.allclose(Pm, Pm.T, atol=1e-6) and np.linalg.eigvalsh((Pm + Pm.T) / 2).min() > -1e-6 and t.var_yaw > 0): return False
        if not (0 <= t.existence <= 1 and 0 <= t.cls_prob <= 1): return False
    return (m.frame == "map" and m.origin_frame_id == cfg.origin_id and m.units == {"length": "m", "time": "s", "angle": "rad", "speed": "m/s"} and m.yaw_convention == "ccw_from_+x"
            and len({t.track_id for t in m.tracks}) == len(m.tracks) and m.hop_count <= cfg.max_hops and m.ttl_s > 0)


vals = st.one_of(st.floats(allow_nan=True, allow_infinity=True), st.integers(-10**12, 10**12), st.text(max_size=8), st.none(), st.booleans(), st.lists(st.floats(), max_size=3))
paths = st.sampled_from([("t_meas",), ("t_sent",), ("ttl_s",), ("hop_count",), ("frame",), ("origin_frame_id",), ("units", "length"), ("yaw_convention",), ("tx", "tx_seq"),
                         ("origin", "orig_seq"), ("origin", "source_id"), ("origin", "provenance", "confirmation"), ("tracks", 0, "x"), ("tracks", 0, "vx"),
                         ("tracks", 0, "existence"), ("tracks", 0, "cov"), ("tracks", 0, "var_yaw"), ("tracks", 0, "track_id"), ("tracks", 0, "t_upd"), ("relay_path",)])


def setpath(d, path, v):
    for k in path[:-1]: d = d[k]
    d[path[-1]] = v


@settings(max_examples=500, derandomize=True, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(muts=st.lists(st.tuples(paths, vals), min_size=1, max_size=3), recrc=st.booleans())
def test_fuzz_structured_mutations_never_admit_invalid_data(muts, recrc):
    a = adm()
    d = to_dict(msg(seq=3))
    for path, v in muts:
        try: setpath(d, path, v)
        except (KeyError, IndexError, TypeError): pass
    try:
        d = with_crc(d) if recrc else {**d, "crc32": 123}
    except (ValueError, TypeError):
        d["crc32"] = 123
    try:
        payload = json.dumps(d, allow_nan=True).encode()
    except (TypeError, ValueError):
        return
    r = a.process(payload, T_RECV, T_PROC)
    if r.admitted:
        assert independent_is_valid(r.msg, a.cfg) and r.msg == deserialize(serialize(r.msg))


@settings(max_examples=400, derandomize=True, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(raw=st.binary(max_size=600))
def test_fuzz_arbitrary_bytes_never_crash_and_are_rejected(raw):
    r = adm().process(raw, T_RECV, T_PROC)
    assert (not r.admitted) and r.reason in REASONS


@settings(max_examples=300, derandomize=True, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(pos=st.integers(0, 10**6), xor=st.integers(1, 255), cut=st.integers(0, 10**6))
def test_fuzz_byte_flips_and_truncations_of_a_valid_message_are_never_admitted(pos, xor, cut):
    good = serialize(msg(seq=1, tracks=[track(1), track(2, x=20.0)]))
    bad = bytearray(good); bad[pos % len(good)] ^= xor
    assert not adm().process(bytes(bad), T_RECV, T_PROC).admitted
    assert not adm().process(good[: cut % len(good)], T_RECV, T_PROC).admitted


def test_staleness_is_judged_at_processing_time_not_at_reception_time():
    """Found by mutation: age at reception 0.499 s (fresh) but 0.504 s at processing -> stale (max_age 0.5 s)."""
    a = adm(); m = msg(t_meas=1.0, ttl=2.0)
    r = a.process(serialize(m), 1.499, 1.504)
    assert not r.admitted and r.reason == "stale" and r.age_recv_est == pytest.approx(0.499) and r.age_proc_est == pytest.approx(0.504)
    a2 = adm(); ok = a2.process(serialize(msg(t_meas=1.0, ttl=2.0)), 1.495, 1.499)
    assert ok.admitted


def test_static_non_finite_guard_catches_values_that_bypass_the_parser():
    """Defence in depth: dataclass instances built in-process (never parsed) with NaN/Inf are refused by the stateless check on its own."""
    from dataclasses import replace
    a = adm()
    for bad in (float("nan"), float("inf"), -float("inf")):
        m = msg(tracks=[replace(track(), x=bad)])
        assert a._static_checks(m, 100) == "non_finite"
    assert a._static_checks(msg(), 100) is None
