"""CLS-08 · the SAFETY evaluator is correct on synthetic records with known answers (TTC, near-miss, counterfactual, severity, jerk, calibration, pairing)."""
import math
import numpy as np, pytest
from closedloop import conditions as K
from closedloop.metrics import ece_brier, per_run, pool, wilson
from closedloop.runner import _rect_circle_dist

pytestmark = pytest.mark.cls


def rec(a=None, ticks=None, **kw):
    a = np.zeros(300) if a is None else np.asarray(a, float)
    series = np.stack([np.arange(len(a)) * 0.01, np.arange(len(a)) * 0.1, np.full(len(a), 8.0), a], axis=1)
    base = dict(seed=1, ego_collision=False, follower_collision=False, impact_speed=None, min_clearance=5.0, standstill_events=0, t_goal=9.0, traj_hash="h", onsets=[], first_brake_t=None,
                info={"t_edge": 5.0}, ticks=ticks or [], series=series, fseries=np.zeros((0, 5)))
    base.update(kw); return base


def tick(t=0.0, a=0.0, a_local=0.0, ttc=10.0, p=0.0, outcome=0, age=0.0, n_remote=0, mode="comfort"):
    return dict(t=t, a_cmd=a, a_local=a_local, mode=mode, p=p, age=age, n_remote=n_remote, lat=0.001, outcome=outcome, ttc=ttc, assur_bad=0, reasons=(), binding=None, hyps=[], ego_x=0.0)


def test_cls08_rect_circle_distance_geometry():
    assert _rect_circle_dist(0, 4, -1, 1, 2, 0) == 0.0                                      # centre inside
    assert _rect_circle_dist(0, 4, -1, 1, 6, 0) == pytest.approx(2.0)                       # side
    assert _rect_circle_dist(0, 4, -1, 1, 5, 2) == pytest.approx(math.hypot(1, 1))          # corner


def test_cls08_collision_near_miss_ttc_and_hard_brake_flags():
    r = per_run(rec(ticks=[tick(ttc=3.0), tick(ttc=1.2), tick(ttc=2.0)], min_clearance=0.8, a=np.r_[np.zeros(100), -4.0 * np.ones(50), np.zeros(150)]))
    assert r["min_ttc"] == 1.2 and r["near_miss"] and r["hard"] and r["max_decel"] == pytest.approx(4.0)
    c = per_run(rec(ego_collision=True, impact_speed=5.0, min_clearance=0.0))
    assert c["ego_col"] and not c["near_miss"] and c["impact"] == 5.0                        # a collision is not also counted as a near miss
    assert per_run(rec(min_clearance=1.5))["near_miss"] is False


def test_cls08_jerk_includes_the_standstill_discontinuity_and_is_reported_as_an_event():
    a = np.r_[np.zeros(10), -6.0 * np.ones(20), np.zeros(10)]                               # acceleration snaps from -6 to 0 within one step
    r = per_run(rec(a=a, standstill_events=1))
    assert r["max_jerk"] == pytest.approx(6.0 / K.DT) and r["standstill"] is True


def test_cls08_unnecessary_intervention_uses_the_counterfactual_clearance():
    assert per_run(rec(onsets=[(2.0, 0.4)]))["unnecessary"] is False                         # without braking the ego would have come within 0.4 m: needed
    assert per_run(rec(onsets=[(2.0, 3.0)]))["unnecessary"] is True                          # would have cleared by 3 m: unnecessary
    assert per_run(rec(onsets=[]))["unnecessary"] is False
    assert per_run(rec(onsets=[(2.0, math.inf)]))["unnecessary"] is True                      # no pedestrian at all (ghost)


def test_cls08_warning_lead_completion_censoring_and_travel_penalty_pairing():
    r = per_run(rec(first_brake_t=3.5, info={"t_edge": 5.0}))
    assert r["lead"] == pytest.approx(1.5)
    assert per_run(rec(t_goal=None))["t_comp"] == K.DURATION and per_run(rec(t_goal=None))["completed"] is False
    base = {1: rec(t_goal=9.0), 2: rec(t_goal=10.0, seed=2)}
    runs = [rec(t_goal=11.0), rec(t_goal=None, seed=2)]
    p = pool(runs, base)
    assert p["travel_time_penalty_s"] == pytest.approx(((11.0 - 9.0) + (K.DURATION - 10.0)) / 2)


def test_cls08_calibration_ece_brier_and_wilson_on_hand_cases():
    perfect = [(0.0, 0)] * 50 + [(1.0, 1)] * 50
    assert ece_brier(perfect) == (0.0, 0.0)
    wrong = [(0.9, 0)] * 100
    e, b = ece_brier(wrong)
    assert e == pytest.approx(0.9) and b == pytest.approx(0.81)
    calib = [(0.5, 1)] * 50 + [(0.5, 0)] * 50
    assert ece_brier(calib)[0] == pytest.approx(0.0)
    lo, hi = wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=2e-3) and hi == pytest.approx(0.7634, abs=2e-3)


def test_cls08_rear_end_metrics_from_the_follower_series():
    f = np.array([[0.0, 0.0, 10.0, 12.0, 6.0], [0.1, 1.0, 10.0, 12.5, 5.0]])               # t, f.x, f.v, ego.x, ego.v ; gap = ego.x - 0.9 - (f.x + 3.6)
    r = per_run(rec(fseries=f))
    gap0, clo0 = 12.0 - 0.9 - 3.6, 4.0; gap1, clo1 = 12.5 - 0.9 - 4.6, 5.0
    assert r["f_ttc"] == pytest.approx(min(gap0 / clo0, gap1 / clo1)) and r["f_req"] == pytest.approx(max(clo0 ** 2 / (2 * gap0), clo1 ** 2 / (2 * gap1)))


def test_cls08_invariant_counters_detect_planted_violations():
    bad = rec(ticks=[tick(a=-0.5, a_local=-1.0), tick(a=7.0, a_local=8.0), tick(age=0.6, n_remote=1), tick(mode="weird")])
    r = per_run(bad)
    assert r["raised"] == 1 and r["cmd_viol"] == 2 and r["stale"] == 1


def test_cls08_pooled_rates_and_fallback_fraction():
    runs = [rec(ego_collision=True, seed=1), rec(seed=2), rec(seed=3), rec(ego_collision=True, seed=4)]
    p = pool(runs, ref_traj={1: "h", 2: "x", 3: "h", 4: "h"})
    assert p["collision_rate"] == 0.5 and p["fallback_identical_fraction"] == 0.75 and p["n"] == 4


def test_cls08_unnecessary_intervention_boundary_and_ece_weighting():
    """Found by mutation: boundary counterfactual 1.0 m is NOT unnecessary; 1.5 m is; ECE weights bins by their share."""
    assert per_run(rec(onsets=[(2.0, 1.0)]))["unnecessary"] is False
    assert per_run(rec(onsets=[(2.0, 1.5)]))["unnecessary"] is True
    two_bins = [(0.2, 0)] * 50 + [(0.8, 0)] * 50
    assert ece_brier(two_bins)[0] == pytest.approx(0.5 * 0.2 + 0.5 * 0.8)
