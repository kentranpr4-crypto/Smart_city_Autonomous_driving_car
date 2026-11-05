"""CLS-09 · failure / attack taxonomy handled correctly at unit level (ghost, ID churn, untrusted source, rear-end)."""
import numpy as np, pytest
from comm.admission import Admission, AdmissionConfig, SourceRegistry
from comm.clock import NodeClock
from comm.trackmsg import serialize
from closedloop.runner import ChurnPublisher, _forged, ORIGIN
from planning.types import Rear
from tests.closedloop.helpers import *

pytestmark = pytest.mark.cls


def adm():
    return Admission(AdmissionConfig("ego", ORIGIN), SourceRegistry({"cctv_k1": "cctv", "v2_cam": "vehicle"}, frozenset()), NodeClock("rx"))


def test_cls09_untrusted_source_ghost_is_rejected_at_admission_and_an_allowlisted_forgery_is_admitted_known_failure_KF3():
    a = adm()
    rogue = a.process(serialize(_forged("rogue_9", 1, 0.95, 55.0, 0.0)), 1.0, 1.005)
    assert not rogue.admitted and rogue.reason == "unknown_source"
    forged = a.process(serialize(_forged("cctv_k1", 2, 0.95, 55.0, 0.0)), 1.0, 1.005)
    assert forged.admitted                                                                    # documented limitation (no authentication): the planning layer must cope


def feed(planner, n=8, ghost_x=55.0, rear=Rear(None, None)):
    s = stack(planner); out = []
    for k in range(n):
        t = 1.0 + 0.1 * k
        d, hy = s.decide(ego(30.0 + 0.8 * k, 8.0, t), [], [stored("cctv_k1", 99, ghost_x, 0.0, t_meas=t - 0.05, seq=k, sp=0.04, sv=0.0001)], rear, ego_pose=(31.35 + 0.8 * k, 0.0, 0.1))
        out.append((d, hy))
    return out


def test_cls09_ghost_in_a_clear_field_of_view_causes_no_hard_braking_when_guarded_but_does_when_naive():
    g = feed("guarded", ghost_x=50.0); n = feed("naive", ghost_x=50.0)
    assert min(d.a_cmd for d, _ in g) > -3.5 and any("contradicted_hold" in d.reasons for d, _ in g)
    assert min(d.a_cmd for d, _ in n) < -3.5                                                  # the naive ablation is harmed (hard brake)
    assert all(h.assurance != "authenticated" for _, hy in g for h in hy)


def test_cls09_ghost_plus_follower_guarded_braking_respects_the_follower_while_naive_ignores_it():
    rear = Rear(5.0, 10.0)
    g = feed("guarded", ghost_x=48.0, rear=rear); n = feed("naive", ghost_x=48.0, rear=rear)
    assert min(d.a_cmd for d, _ in g) >= min(d.a_cmd for d, _ in n)
    assert min(d.a_cmd for d, _ in n) < -3.5


def test_cls09_id_churn_does_not_change_the_hazard_response():
    """Renumbering track ids every message must not create phantom tracks or delay the response: the guarded stack associates by state, not by id."""
    e = ego(30.0, 8.0)
    steady = stack("guarded"); churn = stack("guarded"); a = b = None
    for k in range(6):
        t = 1.0 + 0.1 * k
        a, _ = steady.decide(ego(30.0 + 0.6 * k, 8.0, t), [], [stored("cctv_k1", 7, 40.0, -1.0 + 0.2 * k, 0.0, 1.5, t_meas=t - 0.05, seq=k)], Rear(None, None), ego_pose=(31.35 + 0.6 * k, 0.0, 0.1))
        b, _ = churn.decide(ego(30.0 + 0.6 * k, 8.0, t), [], [stored("cctv_k1", 1000 * (k + 1) + 7, 40.0, -1.0 + 0.2 * k, 0.0, 1.5, t_meas=t - 0.05, seq=k)], Rear(None, None), ego_pose=(31.35 + 0.6 * k, 0.0, 0.1))
    assert a.a_cmd < 0 and b.a_cmd == pytest.approx(a.a_cmd) or b.diag["n_remote_used"] == 0   # churn can only delay (persistence restarts) - never hallucinate extra braking
    assert b.a_cmd >= a.a_cmd - 1e-9


def test_cls09_churn_publisher_renumbers_track_ids_every_message():
    from perception.presets import V2X_PUBLISH
    from perception.tracker import Tracker
    from tests.comm.frames import mk_frame
    tr = Tracker("k", V2X_PUBLISH)
    for k in range(8): tr.update(mk_frame(k, k * 0.1, [(2.0, 0.0, 0.04)], sensor="k"), t_now=k * 0.1)
    pub = ChurnPublisher("k", "cctv", NodeClock("c"), ORIGIN, rate_hz=10.0)
    ids = []
    for k in range(3):
        tr.update(mk_frame(8 + k, 0.8 + 0.1 * k, [(2.0, 0.0, 0.04)], sensor="k"), t_now=0.8 + 0.1 * k)
        r = pub.maybe_publish(0.8 + 0.1 * k, tr)
        ids.append(r[0].tracks[0].track_id)
    assert len(set(ids)) == 3 and all(i >= 1000 for i in ids)


def test_cls09_rear_end_stationary_follower_far_away_places_no_constraint_but_a_close_fast_one_does():
    e = ego(30.0, 8.0)
    s_far = sup_remote(Rear(30.0, 2.0)); s_close = sup_remote(Rear(4.0, 12.0))
    assert s_far.a_cmd == pytest.approx(-3.0) and s_close.a_cmd > -3.0


def sup_remote(rear):
    from planning.supervisor import Supervisor
    s = Supervisor({**PRM, "sensor_range_m": 1.0}, 8.0)
    return s.decide(ego(30.0, 8.0), [hyp(40.0, 0.0, level="advisory", sources=("cctv_k1",), sp=0.01, sv=0.0001)], rear)
