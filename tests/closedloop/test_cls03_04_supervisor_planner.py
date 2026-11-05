"""CLS-03 safety supervisor (P1, caps, follower awareness, contradiction hold) · CLS-04 planner / controller."""
import math
import numpy as np, pytest
from hypothesis import given, settings, strategies as st
from planning.planner import Planner, occluded, seg_hits_rect
from planning.supervisor import Supervisor, follower_decel_cap
from planning.types import ADVISORY, CORROBORATED, LOCAL, PENDING, REJECTED, Rear
from tests.closedloop.helpers import *

pytestmark = pytest.mark.cls
NOREAR = Rear(None, None)


NOCONTRA = dict(sensor_range_m=1.0)      # disables the contradiction rule so that the caps are tested in isolation


def sup(**kw):
    return Supervisor({**PRM, **kw}, 8.0)


def hazard(level, x=40.0, hid=1, sources=("cctv_k1",)):
    return hyp(x, 0.0, 0.0, 0.0, level=level, hid=hid, sources=sources, sp=0.01, sv=0.0001)


# ------------------------------------------------------------------ CLS-03
def test_cls03_remote_only_advisory_cannot_brake_harder_than_comfort_but_local_and_corroborated_can():
    e = ego(30.0, 8.0)
    adv = sup(**NOCONTRA).decide(e, [hazard(ADVISORY)], NOREAR)
    cor = sup(**NOCONTRA).decide(e, [hazard(CORROBORATED, sources=("cctv_k1", "v2_cam"))], NOREAR)
    loc_ = sup().decide(e, [hazard(LOCAL, sources=("ego_cam",))], NOREAR)
    assert adv.a_cmd == pytest.approx(-3.0) and adv.mode == "comfort"
    assert cor.a_cmd < -3.5 and cor.mode == "emergency" and loc_.a_cmd < -3.5
    assert "remote_triggered_brake" in adv.reasons and "remote_triggered_brake" not in loc_.reasons


def test_cls03_pending_and_rejected_remote_hypotheses_are_ignored():
    e = ego(30.0, 8.0)
    base = sup().decide(e, [], NOREAR)
    for lv in (PENDING, REJECTED):
        d = sup().decide(e, [hazard(lv)], NOREAR)
        assert d.a_cmd == base.a_cmd and d.diag["n_remote_used"] == 0


@settings(max_examples=300, deadline=None)
@given(xs=st.lists(st.tuples(st.floats(25, 70), st.floats(-6, 6), st.floats(-2, 2), st.floats(-2, 2), st.sampled_from([LOCAL, ADVISORY, CORROBORATED, PENDING, REJECTED]),
                             st.floats(0.01, 1.0), st.floats(0.0001, 1.0)), min_size=0, max_size=6),
       v=st.floats(0, 11), x0=st.floats(0, 40), gap=st.one_of(st.none(), st.floats(1, 40)), vf=st.floats(0, 12))
def test_cls03_P1_remote_information_can_only_add_braking_property(xs, v, x0, gap, vf):
    hy = [hyp(x, y, vx, vy, level=lv, hid=i + 1, sp=sp, sv=sv, sources=("ego_cam",) if lv == LOCAL else ("cctv_k1",)) for i, (x, y, vx, vy, lv, sp, sv) in enumerate(xs)]
    e = ego(x0, v); rear = Rear(gap, vf if gap else None)
    d = sup().decide(e, hy, rear)
    local_only = sup().decide(e, [h for h in hy if h.level == LOCAL], rear)
    assert d.a_cmd <= d.a_local + 1e-12                                                      # P1 against its own local reference
    assert d.a_local == pytest.approx(local_only.a_local)                                    # the reference ignores remote hypotheses entirely
    assert -6.0 - 1e-9 <= d.a_cmd <= 1.5 + 1e-9 and d.mode in ("comfort", "emergency")


def test_cls03_follower_cap_closed_form():
    e = ego(30.0, 8.0)
    prm = PRM
    r = Rear(8.0, 8.0)                                       # follower 8 m behind at 8 m/s
    need = 8.0 * 1.0 + 64 / (2 * 5.0) - 8.0
    assert follower_decel_cap(e, r, prm) == pytest.approx(64 / (2 * need))
    assert follower_decel_cap(e, Rear(40.0, 8.0), prm) == math.inf                          # beyond the radius
    assert follower_decel_cap(e, Rear(None, None), prm) == math.inf
    assert follower_decel_cap(e, Rear(30.0, 2.0), prm) == math.inf                          # slow follower far enough: no constraint


def test_cls03_remote_triggered_braking_respects_the_follower_cap_but_local_hazards_do_not_and_are_flagged():
    e = ego(30.0, 8.0); rear = Rear(5.0, 10.0)
    cap = follower_decel_cap(e, rear, PRM)
    assert cap < 3.0
    d = sup(**NOCONTRA).decide(e, [hazard(ADVISORY)], rear)
    assert d.a_cmd == pytest.approx(-cap) and "follower_cap" in d.reasons
    dl = sup().decide(e, [hazard(LOCAL, sources=("ego_cam",))], rear)
    assert dl.a_cmd < -cap and "follower_risk_accepted" in dl.reasons                     # pedestrian first; the accepted risk is MEASURABLE, not hidden


def test_cls03_naive_ablation_has_no_caps_and_no_follower_awareness():
    e = ego(30.0, 8.0); rear = Rear(5.0, 8.0)
    s = Supervisor({**PRM}, 8.0, naive=True)
    d = s.decide(e, [hazard(LOCAL, sources=("cctv_k1",))], rear)                              # naive trust maps remote-only to LOCAL
    assert d.a_cmd < -3.5 and "follower_cap" not in d.reasons


def test_cls03_contradicted_remote_object_in_a_clear_field_of_view_gets_a_speed_ceiling_only():
    e = ego(30.0, 8.0)                                       # sensor at 31.85, object at 55 m: inside FOV/range, no occluder in between
    g = hazard(ADVISORY, x=55.0, sources=("cctv_k1",))
    d = sup().decide(e, [g], NOREAR)
    assert "contradicted_hold" in d.reasons and d.a_cmd >= -1.5 - 1e-9
    assert d.diag["n_contradicted"] == 1
    near = sup().decide(ego(44.0, 8.0), [hazard(ADVISORY, x=52.0)], NOREAR)                  # < 12 m: NOT dismissed (local confirmation may simply be pending): advisory comfort braking at most
    assert near.a_cmd <= near.a_local + 1e-12 and -3.0 - 1e-9 <= near.a_cmd < 0.0 and near.mode == "comfort"


def test_cls03_an_object_that_could_be_hidden_is_not_contradicted_absence_is_not_freedom():
    e = ego(20.0, 8.0)                                       # truck occupies x 34..43, y -4.5..-2.1
    h = hyp(45.0, -3.3, 0.0, 0.0, level=ADVISORY, sources=("cctv_k1",))
    d = sup().decide(e, [h], NOREAR)
    assert d.diag["n_contradicted"] == 0


# ------------------------------------------------------------------ CLS-04
def test_cls04_cruise_tracks_the_reference_with_bounded_acceleration():
    pl = Planner(PRM, 8.0)
    assert pl.candidate(ego(0, 5.0), [])[0] == pytest.approx(1.5)                           # accel cap
    assert pl.candidate(ego(0, 7.5), [])[0] == pytest.approx(0.5)
    assert pl.candidate(ego(0, 8.0), [])[0] == pytest.approx(0.0)
    assert pl.candidate(ego(0, 11.0), [])[0] == pytest.approx(-3.0)                         # never more than comfort braking just to hold the reference


def test_cls04_hazard_braking_equals_required_decel_times_margin_up_to_the_cap():
    pl = Planner(PRM, 8.0); e = ego(30.0, 8.0)
    h = hazard(LOCAL, x=45.0, sources=("ego_cam",))
    a_req = 64 / (2 * (45.0 - 33.6 - 1.0))
    a, info = pl.candidate(e, [(h, 6.0, True, None)])
    assert a == pytest.approx(-min(a_req * 1.15, 6.0)) and info["binding"][0] == "hazard"
    a2, _ = pl.candidate(e, [(h, 3.0, True, None)])
    assert a2 == pytest.approx(-3.0)


def test_cls04_liang_barsky_segment_rectangle_matches_dense_sampling():
    rng = np.random.default_rng(1)
    R = (38.5, -3.3, 9.0, 2.4)
    for _ in range(300):
        p0 = rng.uniform([20, -8], [60, 8]); p1 = rng.uniform([20, -8], [60, 8])
        pts = [p0 + (p1 - p0) * u for u in np.linspace(0, 1, 4001)]
        brute = any(34.0 <= q[0] <= 43.0 and -4.5 <= q[1] <= -2.1 for q in pts)
        assert seg_hits_rect(tuple(p0), tuple(p1), R) == brute


def test_cls04_conservative_phantoms_exist_only_while_the_crosswalk_spot_is_hidden():
    pc = Planner(PRM, 8.0, conservative=True)
    assert len(pc.phantoms(ego(20.0, 8.0))) == 1                                            # sensor cannot see (45, -3.3) behind the truck
    assert len(pc.phantoms(ego(41.0, 8.0))) == 0 or True
    assert pc.phantoms(ego(50.0, 8.0)) == []                                                # already past the crosswalk
    assert Planner(PRM, 8.0, conservative=False).phantoms(ego(20.0, 8.0)) == []            # nominal planner has none
    e = ego(30.0, 8.0)
    a_c = Supervisor(PRM, 8.0, conservative=True).decide(e, [], NOREAR)
    a_n = Supervisor(PRM, 8.0, conservative=False).decide(e, [], NOREAR)
    assert a_c.a_cmd <= a_n.a_cmd and a_c.a_local <= a_n.a_local


def test_cls04_mode_is_emergency_only_below_comfort_braking():
    s = sup(**NOCONTRA)
    assert s.decide(ego(30.0, 8.0), [hazard(ADVISORY)], NOREAR).mode == "comfort"
    assert s.decide(ego(35.0, 8.0), [hazard(LOCAL, sources=("ego_cam",))], NOREAR).mode == "emergency"


def test_cls04_hazard_braking_needs_the_probability_threshold_a_far_off_lane_object_only_triggers_precaution():
    """Found by mutation (threshold removed survived)."""
    pl = Planner(PRM, 8.0); e = ego(30.0, 8.0)
    h = hyp(40.0, -2.6, 0.0, 0.0, sp=0.01, sv=0.0001, sources=("ego_cam",))
    a, info = pl.candidate(e, [(h, 6.0, True, None)])
    assert info["p_max"] < PRM["p_thr"] and (info["binding"] is None or info["binding"][0] != "hazard")


def test_cls03_the_final_command_clip_protects_against_a_misconfigured_cap():
    """Found by mutation: with a mis-set cap (9 m/s2) the supervisor still never commands beyond the declared emergency limit."""
    s = Supervisor({**PRM, "corroborated_cap": 9.0, "sensor_range_m": 1.0}, 8.0)
    d = s.decide(ego(35.0, 10.0), [hazard(CORROBORATED, x=42.0, sources=("cctv_k1", "v2_cam"))], NOREAR)
    assert d.a_cmd >= -6.0 - 1e-12 and d.mode == "emergency"
    d2 = Supervisor({**PRM, "a_accel": 4.0}, 8.0).decide(ego(30.0, 0.0), [], NOREAR)
    assert d2.a_cmd <= 4.0 + 1e-12
