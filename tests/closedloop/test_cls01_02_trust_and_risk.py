"""CLS-01 evidence/trust admission · CLS-02 risk prediction."""
import math
import numpy as np, pytest
from fusion.types import FusedTrack
from planning.risk import assess, lateral_p_inside, phi
from planning.trust import TrustAdmission
from planning.types import ADVISORY, CORROBORATED, LOCAL, PENDING, REJECTED
from tests.closedloop.helpers import *

pytestmark = pytest.mark.cls
PR = PRM


def ft(fid, members, flags=(), age=0.0, assurance="allowlist-only", x=(40.0, 0.0, 0.0, 0.0)):
    return FusedTrack(fid, 1.0, x, cov4(), "pedestrian", "B4_ci", tuple(members), tuple((m[0], 1, m[1]) for m in members), (), tuple(flags), age, assurance)


def test_cls01_levels_follow_the_declared_rules_and_persistence():
    t = TrustAdmission(PR)
    levels = []
    for k in range(4):
        levels.append(t.classify([ft(1, [("cctv_k1", 1)]), ft(2, [("cctv_k1", 2), ("v2_cam", 5)]), ft(3, [("ego_cam", 1), ("cctv_k1", 1)])]))
    assert [h.level for h in levels[0]] == [PENDING, PENDING, LOCAL]                          # first cycle: remote-only not yet persistent
    assert [h.level for h in levels[2]] == [ADVISORY, CORROBORATED, LOCAL]                    # >= 3 consecutive cycles
    assert all(h.assurance == "allowlist-only" for h in levels[3] if h.level != LOCAL)       # NEVER authenticated
    assert all(h.assurance != "authenticated" for L in levels for h in L)


def test_cls01_stale_flagged_quarantined_or_ambiguous_remote_is_rejected():
    for bad in (dict(age=0.6), dict(flags=("quarantined_source",)), dict(flags=("ambiguous_association",))):
        t = TrustAdmission(PR)
        for _ in range(4): out = t.classify([ft(1, [("cctv_k1", 1)], **bad)])
        assert out[0].level == REJECTED, bad
    t = TrustAdmission(PR)
    for _ in range(4): out = t.classify([ft(1, [("ego_cam", 1)], age=0.0, flags=("ambiguous_association",))])
    assert out[0].level == LOCAL                                                              # local evidence is never downgraded by remote-only rules


def test_cls01_a_claimed_authentication_is_counted_and_never_upgrades_trust():
    t = TrustAdmission(PR)
    for _ in range(4): out = t.classify([ft(1, [("cctv_k1", 1)], assurance="authenticated")])
    assert t.counts["claimed_authenticated"] == 4 and out[0].level == ADVISORY and out[0].assurance == "allowlist-only"


def test_cls01_naive_ablation_trusts_everything_as_local():
    t = TrustAdmission(PR, naive=True)
    assert t.classify([ft(1, [("cctv_k1", 1)], age=0.4)])[0].level == LOCAL


def test_cls01_stale_remote_never_reaches_the_decision_end_to_end():
    s = stack("guarded"); e = ego(30.0, 8.0)
    ped_local = [local_track(1, 60.0, 0.0)]
    base, _ = s.decide(e, ped_local, [], Rear(None, None))
    s2 = stack("guarded")
    d, hyps = s2.decide(e, ped_local, [stored("cctv_k1", 7, 36.0, 0.0, t_meas=0.2)], Rear(None, None))      # observation 0.8 s old
    assert d.a_cmd == base.a_cmd and d.diag["n_remote_used"] == 0 and d.diag["remote_age_s"] <= 0.5


# ------------------------------------------------------------------ CLS-02
def test_cls02_probability_is_one_for_a_pedestrian_in_the_path_and_zero_when_far_from_the_corridor():
    e = ego(30.0, 8.0)
    inpath = assess(hyp(40.0, 0.0, 0.0, 0.0, sp=0.01, sv=0.0001), e, PR)
    assert inpath.p_conflict > 0.99 and inpath.a_req == pytest.approx(64 / (2 * (40 - 33.6 - 1.0)), rel=1e-6)
    far = assess(hyp(40.0, -6.0, 0.0, 0.0, sp=0.01, sv=0.0001), e, PR)
    assert far.p_conflict < 1e-6
    behind = assess(hyp(20.0, 0.0), e, PR)
    assert behind.p_conflict == 0.0 or behind.a_req == 0.0 or behind.p_conflict < 0.01


def test_cls02_crossing_pedestrian_arriving_with_the_ego_has_high_probability_and_one_that_clears_early_does_not():
    e = ego(30.0, 8.0)                                       # front at 33.6 -> reaches x=40 in ~0.8 s
    hit = assess(hyp(40.0, -1.5, 0.0, 1.5, sp=0.01, sv=0.01), e, PR)
    miss = assess(hyp(40.0, 4.0, 0.0, 1.5, sp=0.01, sv=0.01), e, PR)                      # already beyond the corridor, moving away
    assert hit.p_conflict > 0.5 and miss.p_conflict < 0.01


def test_cls02_monte_carlo_matches_the_closed_form_probability():
    rng = np.random.default_rng(3)
    e = ego(30.0, 8.0); h = hyp(36.0, -2.4, 0.0, 0.8, sp=0.01, sv=0.2 ** 2)
    r = assess(h, e, PR)
    t = r.t_arrive; sd = math.sqrt(h.P[5] + 2 * t * h.P[7] + t * t * h.P[15])
    y = rng.normal(h.y + h.vy * t, sd, 200000)
    assert np.mean(np.abs(y) <= PR["corridor_half_m"]) == pytest.approx(r.p_conflict, abs=0.01)


def test_cls02_a_pedestrian_already_beside_the_ego_does_not_inherit_horizon_long_uncertainty():
    """Found in WP5 tuning: a stopped ego beside a waiting pedestrian got p~0.2 from velocity uncertainty over 6 s and froze."""
    e = ego(43.0, 0.0)                                        # stopped, front at 46.6, pedestrian at x=45 is beside the body
    r = assess(hyp(45.0, -3.3, 0.0, 0.0, sp=0.04, sv=0.25), e, PR)
    assert r.p_conflict < 0.01


def test_cls02_precaution_flag_worst_case_cap_formula_creep_floor_and_far_pedestrians():
    e = ego(30.0, 8.0)
    near = assess(hyp(45.0, -3.3), e, PR)
    assert near.precaution
    dd = 45.0 - 33.6 - PR["standoff_m"]
    expect = max(PR["a_comf"] * (-0.4 + math.sqrt(0.16 + 2 * dd / PR["a_comf"])), PR["creep_speed"])
    assert near.v_cap == pytest.approx(expect, rel=1e-9)
    close = assess(hyp(45.0, -3.3), ego(41.0, 6.0), PR)
    assert close.v_cap >= PR["creep_speed"] - 1e-12                                          # never freezes below the creep speed
    assert not assess(hyp(45.0, -12.0), e, PR).precaution                                    # 10 m from the lane: no worst-case assumption
    assert not assess(hyp(45.0, -3.3, 0.0, 1.5), e, PR).precaution                           # observed moving: handled by the hazard branch, not the intent prior


def test_cls02_calibration_on_a_synthetic_world_where_the_truth_distribution_is_known():
    """Reliability of p_conflict: draw lateral velocity from the hypothesis's own covariance; the observed outcome frequency per probability bin matches the stated probability."""
    from closedloop.metrics import ece_brier
    rng = np.random.default_rng(11); pairs = []
    for _ in range(4000):
        vy = rng.uniform(0.0, 1.2); sv = rng.uniform(0.05, 0.4)
        h = hyp(38.0, -2.5, 0.0, vy, sp=0.02, sv=sv * sv); e = ego(30.0, 8.0)
        r = assess(h, e, PR); t = r.t_arrive
        if not math.isfinite(t): continue
        sd = math.sqrt(h.P[5] + 2 * t * h.P[7] + t * t * h.P[15])
        y = rng.normal(h.y + h.vy * t, sd)
        pairs.append((r.p_conflict, int(abs(y) <= PR["corridor_half_m"])))
    ece, brier = ece_brier(pairs)
    assert ece < 0.05
    shifted = [(min(1.0, p * 0.5 + 0.0), y) for p, y in pairs]                               # test of the test: a mis-scaled risk model is detected
    assert ece_brier(shifted)[0] > 0.1


def test_cls02_phi_and_inside_probability_closed_forms():
    assert phi(0.0) == 0.5 and phi(1.96) == pytest.approx(0.975, abs=1e-3)
    assert lateral_p_inside(0.0, 1.0, 1.0) == pytest.approx(0.6827, abs=1e-3)


def test_cls02_creep_floor_applies_when_the_worst_case_cap_would_otherwise_fall_below_it():
    """Found by mutation: the earlier creep-floor test used a state where the precaution did not even trigger."""
    r = assess(hyp(45.0, -3.3), ego(39.0, 5.0), PR)
    assert r.precaution
    raw = PR["a_comf"] * (-0.4 + math.sqrt(0.16 + 2 * (45.0 - 42.6 - PR["standoff_m"]) / PR["a_comf"]))
    assert raw < PR["creep_speed"] and r.v_cap == pytest.approx(PR["creep_speed"])
