"""FUS-06 provenance / duplicate evidence · FUS-07 stale, contradictory, missing, malformed remote observations."""
import math
import numpy as np, pytest
from hypothesis import given, settings, strategies as st
from fusion.fuser import CooperativeFuser
from fusion.identity import AUTHENTICATED, ALLOWLIST_ONLY, _UnsafeTestOnlyAcceptAllVerifier, UnauthenticatedVerifier
from fusion.types import REASONS, Estimate
from tests.fusion.helpers import est, loc, P4

pytestmark = pytest.mark.fus


# ------------------------------------------------------------------ FUS-06
def test_fus06_the_same_observation_arriving_directly_and_via_relay_contributes_once():
    direct = est("k", 1, x=(10, 0, 1, 0), seq=7, hops=0)
    relayed = Estimate("k", 2, 1.0, (10.02, 0.0, 1, 0), P4(0.25), "pedestrian", 0.9, "remote", (("k", 7, 1),), 1, ("rsu",))     # same evidence id (k, 7, 1) re-labelled with another track id
    w = CooperativeFuser("B3_info").step(1.0, [loc(1), direct, relayed])
    assert len(w.tracks) == 1
    ev = w.tracks[0].evidence
    assert len(ev) == len(set(ev)) and ev.count(("k", 7, 1)) == 1
    p_one = CooperativeFuser("B3_info").step(1.0, [loc(1), direct]).tracks[0].P
    assert np.allclose(w.tracks[0].P, p_one)                                                          # the duplicate added NO information


def test_fus06_relayed_evidence_is_flagged_and_provenance_is_preserved():
    r = Estimate("k", 1, 1.0, (10, 0, 1, 0), P4(), "pedestrian", 0.9, "remote", (("k", 3, 1),), 2, ("rsu1", "rsu2"))
    t = CooperativeFuser("B4_ci").step(1.0, [loc(1), r]).tracks[0]
    assert "relayed" in t.flags and ("k", 1) in t.members and ("k", 3, 1) in t.evidence
    assert t.assurance == ALLOWLIST_ONLY                                                              # never claims authentication


def test_fus06_distinct_observations_from_distinct_sources_are_both_used():
    t = CooperativeFuser("B3_info").step(1.0, [loc(1), est("k", 1, seq=1), est("v", 4, seq=1, x=(10.05, 0.0, 1, 0))]).tracks
    assert len(t) == 1 and len(set(t[0].evidence)) == 3


def test_fus06_duplicate_source_ref_keeps_only_the_newest_and_is_counted():
    f = CooperativeFuser("B1_remote")
    w = f.step(1.0, [est("k", 1, t=0.9, seq=1), est("k", 1, t=1.0, seq=2)])
    assert len(w.tracks) == 1 and w.diagnostics["rejected"] == {"duplicate_ref": 1} and w.tracks[0].evidence == (("k", 2, 1),)


def test_fus06_echo_through_a_different_source_label_is_NOT_detectable_by_the_ledger():
    """Honest limit: evidence ids are only as good as the source claims. A relay re-labelling someone's data as its own evidence defeats the ledger;
    this is why B4 (CI, unknown correlation) exists. Documented, not hidden."""
    a = est("k", 1, seq=1); b = est("rsu", 9, seq=1, x=(10.0, 0.0, 1.0, 0.0))
    t = CooperativeFuser("B3_info").step(1.0, [loc(1), a, b]).tracks[0]
    assert len(set(t.evidence)) == 3


# ------------------------------------------------------------------ FUS-07
BAD = {
    "nonfinite": lambda: est(x=(float("nan"), 0, 0, 0)),
    "bad_covariance": lambda: est(P=tuple(-np.eye(4).reshape(-1))),
    "frame_mismatch": lambda: est(frame="cctv-local"),
    "future": lambda: est(t=5.0),
    "stale": lambda: est(t=0.2),
    "bad_class": lambda: est(cls=""),
}


@pytest.mark.parametrize("reason", sorted(BAD))
def test_fus07_each_invalid_input_is_refused_with_its_own_reason_and_the_local_track_survives(reason):
    for m in ("B2_naive", "B3_info", "B4_ci"):
        w = CooperativeFuser(m).step(1.0, [loc(1), BAD[reason]()])
        assert w.diagnostics["rejected"] == {reason: 1}
        assert len(w.tracks) == 1 and w.tracks[0].members == (("ego", 1),)


def test_fus07_horizon_duplicate_ref_and_unauthenticated_reasons():
    assert CooperativeFuser("B0_local").step(3.0, [loc(1, t=1.0)]).diagnostics["rejected"] == {"horizon": 1}
    w = CooperativeFuser("B4_ci", {"require_assurance": AUTHENTICATED}).step(1.0, [loc(1), est("k", 1, seq=1)])
    assert w.diagnostics["rejected"] == {"unauthenticated_source": 1} and w.tracks[0].members == (("ego", 1),)
    assert set(REASONS) == {"nonfinite", "bad_covariance", "frame_mismatch", "future", "stale", "horizon", "bad_class", "duplicate_ref", "unauthenticated_source", "self_track"}


def test_fus07_missing_remote_degrades_to_local_and_missing_everything_is_no_information_not_free():
    ego = [loc(1)]
    assert CooperativeFuser("B4_ci").step(1.0, ego).tracks[0].members == (("ego", 1),)
    empty = CooperativeFuser("B4_ci").step(1.0, [])
    assert empty.tracks == () and not hasattr(empty, "free_space") and not hasattr(empty, "is_free")


def test_fus07_all_remote_stale_gives_exactly_the_local_only_result():
    stale = [est("k", i, t=0.1, seq=i) for i in range(3)]
    a = CooperativeFuser("B4_ci").step(1.0, [loc(1)] + stale).tracks; b = CooperativeFuser("B0_local").step(1.0, [loc(1)]).tracks
    assert [(t.x, t.P) for t in a] == [(t.x, t.P) for t in b]


def test_fus07_class_conflict_prevents_fusion():
    w = CooperativeFuser("B4_ci").step(1.0, [loc(1, cls="vehicle"), est("k", 1, cls="pedestrian", seq=1)])
    assert len(w.tracks) == 2


finite = st.floats(-1e3, 1e3, allow_nan=False, allow_infinity=False)
anyf = st.one_of(finite, st.sampled_from([float("nan"), float("inf"), -float("inf"), 1e300, -1e300, 0.0]))


@settings(max_examples=250, deadline=None)
@given(xs=st.lists(anyf, min_size=4, max_size=4), ps=st.lists(anyf, min_size=16, max_size=16), t=anyf, kind=st.sampled_from(["local", "remote"]))
def test_fus07_fuzz_outputs_are_always_finite_and_psd(xs, ps, t, kind):
    for m in ("B2_naive", "B3_info", "B4_ci"):
        w = CooperativeFuser(m).step(1.0, [loc(1), Estimate("z", 1, t, tuple(xs), tuple(ps), "pedestrian", .9, kind, (("z", 1, 1),))])
        for tr in w.tracks:
            P = np.array(tr.P).reshape(4, 4)
            assert np.all(np.isfinite(tr.x)) and np.all(np.isfinite(P)) and np.allclose(P, P.T, atol=1e-8 * max(1, np.abs(P).max())) and np.linalg.eigvalsh(P).min() > -1e-9 * max(1, np.abs(P).max())


def test_fus07_remote_track_of_the_ego_vehicle_itself_is_suppressed_using_the_egos_own_localisation():
    f = CooperativeFuser("B4_ci")
    me = est("k", 9, x=(50.0, 20.0, 0, 0), seq=3, cls="vehicle")
    other = est("k", 10, x=(52.0, 20.0, 0, 0), seq=3, cls="vehicle")
    w = f.step(1.0, [me, other], ego_pose=(50.05, 19.95, 0.1))
    assert w.diagnostics["rejected"] == {"self_track": 1} and [t.members for t in w.tracks] == [(("k", 10),)]
    assert len(CooperativeFuser("B4_ci").step(1.0, [me, other]).tracks) == 2                            # without the ego pose nothing is suppressed
    local_same_place = CooperativeFuser("B4_ci").step(1.0, [loc(1, x=(50.0, 20.0, 0, 0)), est("k", 1, x=(50.0, 20.0, 0, 0), seq=1)], ego_pose=(50.0, 20.0, 0.1))
    assert local_same_place.diagnostics["rejected"] == {"self_track": 1}                                # only REMOTE tracks are suppressed (the ego keeps its own local tracks)


def test_fus07_self_track_uses_the_ego_pose_at_the_remote_observation_time():
    """Found in WP5: a remote constant-velocity estimate of a BRAKING ego lags; comparing at decision time missed it. A callable pose is evaluated at the observation time."""
    me = est("k", 9, t=0.8, x=(40.0, 0.0, 6.0, 0.0), seq=3, cls="vehicle")                 # the remote saw the ego at x=40 at t=0.8
    pose_then = lambda t: (40.05 if abs(t - 0.8) < 1e-9 else 99.0, 0.0, 0.1)
    w = CooperativeFuser("B4_ci").step(1.0, [me], ego_pose=pose_then)
    assert w.diagnostics["rejected"] == {"self_track": 1} and w.tracks == ()
    far = lambda t: (47.0, 0.0, 0.1)
    assert CooperativeFuser("B4_ci").step(1.0, [me], ego_pose=far).tracks                     # a different place at that time => not the ego


def test_fus07_self_radius_catches_a_lagging_constant_velocity_track_of_a_braking_ego():
    me = est("k", 9, t=0.8, x=(41.2, 0.0, 6.0, 0.0), seq=3, cls="vehicle")                 # remote CV track lags the ego centre by 1.3 m
    pose = lambda t: (42.5, 0.0, 0.1)
    assert CooperativeFuser("B4_ci").step(1.0, [me], ego_pose=pose).tracks != ()           # default: Mahalanobis gate only (WP4 behaviour) misses it
    w = CooperativeFuser("B4_ci", {"self_radius_m": 3.0}).step(1.0, [me], ego_pose=pose)
    assert w.diagnostics["rejected"] == {"self_track": 1} and w.tracks == ()
    other = est("k", 10, t=0.8, x=(47.0, 0.0, 6.0, 0.0), seq=4, cls="vehicle")             # a different vehicle 4.5 m ahead is NOT suppressed
    assert CooperativeFuser("B4_ci", {"self_radius_m": 3.0}).step(1.0, [other], ego_pose=pose).tracks
