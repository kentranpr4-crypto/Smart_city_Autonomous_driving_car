"""Stale / invalid / replayed data handling. Every rejection must (a) carry the right reason and (b) leave the tracker state untouched."""
import math
import numpy as np
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from backend.observation import Detection, SensorFrame, SCHEMA_VERSION
from perception.tracker import Tracker, TrackerConfig
from tests.perception.tracking_helpers import mk_frame

pytestmark = pytest.mark.trk


def warmed(n=6, cfg=None, sensor="s"):
    tr = Tracker(sensor, cfg or TrackerConfig())
    for k in range(n):
        t = k * 0.1
        tr.update(mk_frame(k, t, [(2.0 + 1.0 * t, 0.0, 0.04)], sensor=sensor), t_now=t)
    return tr


def fingerprint(tr):
    return [(t.track_id, t.x, t.P, t.score, t.hits, t.misses) for t in tr.tracks(confirmed_only=False)]


def bad_det(**kw):
    base = dict(det_id=0, x=1.0, y=1.0, cov=(0.04, 0.0, 0.04), cls="pedestrian", cls_prob=1.0, score=0.9)
    base.update(kw)
    return Detection(**base)


def frame(seq=6, t=0.6, dets=None, t_avail=None, sensor="s", version=SCHEMA_VERSION, fov=1.0, pose=(0, 0, 0, 1.5)):
    return SensorFrame(version, sensor, seq, t, t if t_avail is None else t_avail, pose, fov, 50.0, tuple(dets if dets is not None else [bad_det()]))


CASES = [
    ("seq_replay",            lambda: frame(seq=5, t=0.7),                              0.7),
    ("seq_replay",            lambda: frame(seq=2, t=0.9),                              0.9),
    ("out_of_order",          lambda: frame(seq=9, t=0.3),                              0.9),
    ("future",                lambda: frame(seq=7, t=5.0),                              0.7),
    ("stale",                 lambda: frame(seq=7, t=0.6),                              3.0),
    ("wrong_sensor",          lambda: frame(sensor="other"),                            0.6),
    ("schema_version",        lambda: frame(version="9.9.9"),                           0.6),
    ("non_finite",            lambda: frame(dets=[bad_det(x=float("nan"))]),            0.6),
    ("non_finite",            lambda: frame(dets=[bad_det(y=float("inf"))]),            0.6),
    ("non_finite",            lambda: frame(t=float("nan")),                            0.6),
    ("bad_covariance",        lambda: frame(dets=[bad_det(cov=(-0.04, 0.0, 0.04))]),    0.6),
    ("bad_covariance",        lambda: frame(dets=[bad_det(cov=(0.0, 0.0, 0.04))]),      0.6),
    ("bad_covariance",        lambda: frame(dets=[bad_det(cov=(0.04, 0.05, 0.04))]),    0.6),   # not positive definite
    ("duplicate_det_id",      lambda: frame(dets=[bad_det(det_id=3), bad_det(det_id=3, x=5.0)]), 0.6),
    ("t_avail_before_t_meas", lambda: frame(t=0.6, t_avail=0.5),                        0.6),
    ("position_out_of_range", lambda: frame(dets=[bad_det(x=1e7)]),                     0.6),
]


@pytest.mark.parametrize("reason,make,t_now", CASES)
def test_invalid_or_stale_frames_are_rejected_with_the_right_reason_and_change_nothing(reason, make, t_now):
    tr = warmed()
    before = fingerprint(tr); frames_ok = tr.frames_ok
    rep = tr.update(make(), t_now=t_now)
    assert (rep.accepted, rep.reason) == (False, reason)
    assert fingerprint(tr) == before and tr.frames_ok == frames_ok            # state untouched
    assert tr.health()["rejects"] == {reason: 1}


def test_sequence_gaps_are_counted_but_frames_are_still_accepted():
    tr = Tracker("s")
    tr.update(mk_frame(0, 0.0, [(0, 0, 0.04)]), t_now=0.0)
    rep = tr.update(mk_frame(4, 0.4, [(0.4, 0, 0.04)]), t_now=0.4)            # frames 1..3 never arrived
    assert rep.accepted and rep.seq_gap == 3 and tr.health()["seq_gaps"] == 3


def test_tracks_expire_with_time_even_without_new_frames_and_coasting_inflates_covariance():
    cfg = TrackerConfig(max_coast_s=1.5)
    tr = warmed(8, cfg)
    t_last = 0.7
    p_now = np.array(tr.tracks(t_last)[0].P).reshape(4, 4)
    traces = []
    for dt in (0.2, 0.5, 1.0, 1.4):
        trk = tr.tracks(t_last + dt)[0]
        traces.append(np.trace(np.array(trk.P).reshape(4, 4)))
        assert trk.time_since_update_s == pytest.approx(dt, abs=1e-9)
    assert traces == sorted(traces) and traces[0] > np.trace(p_now)            # uncertainty only grows while nothing is observed
    assert tr.tracks(t_last + 1.6) == []                                       # too stale to publish
    rep = tr.update(mk_frame(8, 3.0, [], t_avail=3.0), t_now=3.0)              # a later EMPTY frame also deletes it
    assert rep.accepted and rep.n_deleted == 1 and tr.tracks(3.0, confirmed_only=False) == []


def test_a_fresh_frame_after_a_long_gap_is_accepted_and_starts_a_new_track():
    tr = warmed()
    rep = tr.update(mk_frame(6, 10.0, [(50.0, 50.0, 0.04)]), t_now=10.0)
    assert rep.accepted and rep.n_new == 1


def test_empty_frames_are_valid_misses_not_errors():
    tr = warmed(6)
    rep = tr.update(mk_frame(6, 0.6, []), t_now=0.6)
    assert rep.accepted and rep.n_dets == 0 and rep.n_matched == 0
    assert tr.tracks(0.6)[0].misses == 1


finite = st.floats(allow_nan=True, allow_infinity=True, width=64)
det_st = st.builds(Detection, det_id=st.integers(0, 4), x=finite, y=finite, cov=st.tuples(finite, finite, finite),
                   cls=st.sampled_from(["pedestrian", "vehicle", "unknown"]), cls_prob=finite, score=finite)
frame_st = st.builds(SensorFrame, schema_version=st.sampled_from([SCHEMA_VERSION, "x"]), sensor_id=st.sampled_from(["s", "o"]), seq=st.integers(-5, 40),
                     t_meas=finite, t_avail=finite, sensor_pose=st.just((0.0, 0.0, 0.0, 1.5)), fov=st.just(1.0), range_m=st.just(50.0),
                     detections=st.lists(det_st, max_size=5).map(tuple))


@settings(max_examples=250, derandomize=True, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(frames=st.lists(frame_st, min_size=1, max_size=12))
def test_fuzz_arbitrary_frames_never_crash_and_never_corrupt_the_state(frames):
    tr = warmed()
    for f in frames:
        tr.update(f, t_now=None if math.isnan(f.t_meas) else f.t_meas)
        for t in tr.tracks(confirmed_only=False):
            P = np.array(t.P).reshape(4, 4)
            assert np.all(np.isfinite(P)) and np.all(np.isfinite(t.x))
            assert np.allclose(P, P.T, atol=1e-9) and np.linalg.eigvalsh(0.5 * (P + P.T)).min() > -1e-8
