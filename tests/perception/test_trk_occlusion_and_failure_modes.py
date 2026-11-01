"""Occlusion -> coast -> reacquire, and deliberate failure modes (outage bursts, clutter bursts, over-confident sensors, bias, class confusion)."""
import math
import numpy as np
import pytest
from backend.sensors import SensorProvider
from perception.tracker import Tracker, TrackerConfig
from tests.perception.helpers import *
from tests.perception.tracking_helpers import mk_frame, simulate_scene, associate, id_switches

pytestmark = pytest.mark.trk
SEED = 20261101


def crossing_behind_wall(wall_width):
    """Ego-height sensor at the origin; a pedestrian crosses laterally at x=30 behind a 3 m wall at x=20. Shadow half-width at x=30 = (w/2)*30/20."""
    spec = cctv(id="e", pose=(0.0, 0.0, 0.0), height=1.5, fov_deg=120.0, range_m=80.0, **PERFECT)
    w = wall("w", cx=20.0, cy=0.0, length=0.2, width=wall_width, h=3.0)
    fn = lambda t: ([ped("p", 30.0, -8.0 + 1.4 * t)], [w])
    return spec, fn


def hidden_frames(rec):
    return [i for i, r in enumerate(rec) if "p" not in r["labels"].visible and "p" in r["labels"].candidates]


def test_short_occlusion_is_bridged_by_coasting_and_the_track_keeps_its_id():
    spec, fn = crossing_behind_wall(0.9)               # shadow half-width 0.675 m -> hidden for ~0.96 s < max_coast 1.5 s
    tr, rec = simulate_scene(spec, fn, 130, SEED)
    hid = hidden_frames(rec)
    assert 8 <= len(hid) <= 12 and hid == list(range(hid[0], hid[-1] + 1))
    ids = {t.track_id for r in rec for t in r["tracks"]}
    assert len(ids) == 1 and id_switches(rec) == 0
    # during the occlusion the track is coasting: uncertainty grows monotonically, staleness grows, existence score falls
    traj = [next(t for t in rec[i]["tracks"]) for i in hid]
    traces = [sum(t.P[k * 5] for k in range(4)) for t in traj]
    assert traces == sorted(traces) and traces[-1] > 2 * traces[0]
    assert [t.time_since_update_s for t in traj] == sorted(t.time_since_update_s for t in traj)
    assert [t.score for t in traj] == sorted((t.score for t in traj), reverse=True) and traj[-1].score < traj[0].score
    # after the occlusion the same track is reacquired with a position consistent with the truth
    after = rec[hid[-1] + 3]
    assert associate(after["tracks"], after["truth"], gate=1.0)


def test_long_occlusion_exceeds_the_coast_limit_so_the_track_is_dropped_and_a_new_id_appears():
    spec, fn = crossing_behind_wall(4.0)               # shadow half-width 3 m -> hidden ~4.3 s > max_coast 1.5 s
    tr, rec = simulate_scene(spec, fn, 130, SEED)
    hid = hidden_frames(rec)
    assert len(hid) > 40
    assert all(not r["tracks"] for r in rec[hid[0] + 20: hid[-1] + 1])         # nothing published once the coast limit passed (stale data not shown)
    ids = sorted({t.track_id for r in rec for t in r["tracks"]})
    assert len(ids) == 2                               # DOCUMENTED LIMITATION: identity is lost across a long occlusion (no re-identification)


def test_outage_bursts_are_visible_as_sequence_gaps_and_tracking_survives_short_ones():
    spec = cctv(id="o", pose=(0.0, -20.0, math.pi / 2), height=6.0, dropout=(0.05, 0.4), **PERFECT)
    tr, rec = simulate_scene(spec, lambda t: [ped("p", 0.0 + 1.0 * t, 0.0)], 400, SEED)
    last_seq = rec[-1]["frame"].seq
    assert tr.health()["seq_gaps"] == last_seq + 1 - tr.frames_ok              # every missing frame accounted for, exactly
    assert tr.health()["seq_gaps"] > 10
    first = next(i for i, r in enumerate(rec) if r["tracks"])
    # coverage is evaluated ONLY on frames where the target is inside the sensor's FOV/range (labels.candidates); after it leaves the FOV the track
    # correctly expires. (First draft of this test used all frames as the denominator: a metric-definition bug, fixed; the 0.95 threshold is unchanged.)
    obs = [r for r in rec[first:] if "p" in r["labels"].candidates]
    cov = sum(bool(associate(r["tracks"], r["truth"])) for r in obs) / len(obs)
    assert len(obs) > 250 and cov >= 0.95, (len(obs), cov)                      # pre-registered: bursts (mean 2.5 frames) << max_coast


def test_clutter_burst_keeps_the_target_track():
    """pre-registered: lambda = 10 false alarms/frame, 10 seeds -> mean target coverage >= 0.95 (clutter is gated out, it does not steal the track)."""
    covs = []
    for s in range(10):
        spec = cctv(id="c", pose=(0.0, -20.0, math.pi / 2), height=6.0, fov_deg=120.0, range_m=50.0, clutter_rate=10.0, **PERFECT)
        tr, rec = simulate_scene(spec, lambda t: [ped("p", 2.0 + 1.0 * t, 0.0)], 150, SEED + s)
        first = next(i for i, r in enumerate(rec) if associate(r["tracks"], r["truth"]))
        covs.append(sum(bool(associate(r["tracks"], r["truth"])) for r in rec[first:]) / len(rec[first:]))
    assert float(np.mean(covs)) >= 0.95, covs


def _health_after(spec, frames=120, seed=SEED):
    tr, rec = simulate_scene(spec, lambda t: [ped("p", 2.0 + 1.0 * t, 0.0)], frames, seed)
    return tr.health()


def test_consistency_monitor_flags_an_overconfident_sensor_and_stays_quiet_otherwise():
    base = dict(pose=(0.0, -20.0, math.pi / 2), height=6.0, fov_deg=120.0, range_m=60.0, sigma0=0.3, sigma1=0.0, **PERFECT)
    quiet = [_health_after(cctv(id="q", **base), seed=SEED + s)["nis_inconsistent"] for s in range(20)]
    loud = [_health_after(cctv(id="q", declared_sigma_scale=0.3, **base), seed=SEED + s)["nis_inconsistent"] for s in range(20)]
    assert not any(quiet)                    # pre-registered: 0/20 false alarms (0.1% per window by construction)
    assert all(loud)                         # sensor declaring 30% of its true sigma is flagged in 20/20 runs


def test_DOCUMENTED_LIMITATION_constant_bias_is_invisible_to_the_single_source_consistency_monitor():
    """A constant extrinsic/localisation offset shifts every measurement identically; a single-source tracker just tracks the shifted target.
    The tracker therefore reports healthy NIS while its tracks are wrong by exactly the bias. Detecting this needs a SECOND source (WP3/WP4)."""
    base = dict(pose=(0.0, -20.0, math.pi / 2), height=6.0, fov_deg=120.0, range_m=60.0, sigma0=0.2, sigma1=0.0, **PERFECT)
    errs = []
    for s in range(10):
        tr, rec = simulate_scene(cctv(id="b", bias=(1.5, -0.7), **base), lambda t: [ped("p", 2.0 + 1.0 * t, 0.0)], 120, SEED + s)
        assert not tr.health()["nis_inconsistent"]                                     # monitor stays quiet ...
        t = rec[-1]["tracks"][0]; tx, ty = rec[-1]["truth"]["p"]
        errs.append((t.x[0] - tx, t.x[1] - ty))
    e = np.mean(errs, axis=0)
    assert e[0] == pytest.approx(1.5, abs=0.15) and e[1] == pytest.approx(-0.7, abs=0.15)   # ... while the track is off by the bias


def test_class_label_is_the_majority_vote_under_label_noise():
    ok = 0
    for s in range(10):
        spec = cctv(id="k", pose=(0.0, -20.0, math.pi / 2), height=6.0, class_accuracy=0.7, **PERFECT)
        tr, rec = simulate_scene(spec, lambda t: [ped("p", 2.0 + 1.0 * t, 0.0)], 80, SEED + s)
        ok += rec[-1]["tracks"][0].cls == "pedestrian"
    assert ok >= 9                                                                      # pre-registered: >= 9/10 runs end with the correct label


def test_tracker_output_is_deterministic():
    spec, fn = crossing_behind_wall(0.9)
    a = [[(t.track_id, t.x) for t in r["tracks"]] for r in simulate_scene(spec, fn, 60, SEED)[1]]
    b = [[(t.track_id, t.x) for t in r["tracks"]] for r in simulate_scene(spec, fn, 60, SEED)[1]]
    assert a == b
