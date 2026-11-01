"""FUS-04 · cross-source association without ground truth."""
import itertools
import numpy as np, pytest
from fusion.associate import associate, d2, pair_cost_matrix, BIG
from fusion.fuser import CooperativeFuser
from tests.fusion.helpers import est, loc, P4

pytestmark = pytest.mark.fus
RNG = np.random.default_rng(11)


def rand_set(n, spread=10.0):
    return [(np.array([*RNG.uniform(0, spread, 2), *RNG.normal(0, 1, 2)]), np.diag(RNG.uniform(.02, .2, 4)), "pedestrian") for _ in range(n)]


def test_fus04_assignment_is_optimal_against_brute_force_on_random_problems():
    for _ in range(150):
        n, m = int(RNG.integers(1, 5)), int(RNG.integers(1, 5))
        A, B = rand_set(n, 3.0), rand_set(m, 3.0)
        gate = 1e6
        pairs, _ = associate(A, B, gate, class_gate=False)
        cost, raw = pair_cost_matrix(A, B, gate, False)
        k = min(n, m); best = min(sum(raw[r, c] for r, c in zip(rows, cols)) for rows in itertools.combinations(range(n), k) for cols in itertools.permutations(range(m), k))
        assert len(pairs) == k and sum(v for *_, v in pairs) == pytest.approx(best, rel=1e-9)


def test_fus04_gate_and_class_constraint():
    A = [(np.array([0, 0, 1, 0.0]), np.diag([.04] * 4), "pedestrian")]
    near = [(np.array([0.2, 0, 1, 0.0]), np.diag([.04] * 4), "pedestrian")]; far = [(np.array([5, 0, 1, 0.0]), np.diag([.04] * 4), "pedestrian")]
    veh = [(np.array([0.2, 0, 1, 0.0]), np.diag([.04] * 4), "vehicle")]; unk = [(np.array([0.2, 0, 1, 0.0]), np.diag([.04] * 4), "unknown")]
    assert len(associate(A, near, 18.47)[0]) == 1 and associate(A, far, 18.47)[0] == []
    assert associate(A, veh, 18.47)[0] == [] and len(associate(A, veh, 18.47, class_gate=False)[0]) == 1
    assert len(associate(A, unk, 18.47)[0]) == 1                                                       # 'unknown' never blocks


def test_fus04_ambiguity_is_flagged_for_close_competitors():
    A = [(np.array([0, 0, 0, 0.0]), np.diag([.1] * 4), "pedestrian"), (np.array([0.4, 0, 0, 0.0]), np.diag([.1] * 4), "pedestrian")]
    B = [(np.array([0.2, 0, 0, 0.0]), np.diag([.1] * 4), "pedestrian")]
    pairs, amb = associate(A, B, 18.47)
    assert len(pairs) == 1 and amb
    A2 = [(np.array([0, 0, 0, 0.0]), np.diag([.01] * 4), "pedestrian"), (np.array([30.0, 0, 0, 0.0]), np.diag([.01] * 4), "pedestrian")]
    assert associate(A2, [(np.array([0.05, 0, 0, 0.0]), np.diag([.01] * 4), "pedestrian")], 18.47)[1] == set()


def test_fus04_fuser_clusters_two_separated_targets_and_never_swaps_them():
    f = CooperativeFuser("B4_ci")
    ests = [loc(1, x=(10, 0, 1, 0)), loc(2, x=(10, 4, 1, 0)),
            est("k", 7, t=1.0, x=(10.05, 4.02, 1, 0), seq=1), est("k", 8, t=1.0, x=(10.02, 0.03, 1, 0), seq=1)]
    w = f.step(1.0, ests)
    assert len(w.tracks) == 2
    by_y = sorted(w.tracks, key=lambda t: t.x[1])
    assert set(by_y[0].members) == {("ego", 1), ("k", 8)} and set(by_y[1].members) == {("ego", 2), ("k", 7)}


def test_fus04_source_scoped_ids_do_not_collide():
    """Same numeric track_id from two sources, far apart: two separate fused tracks, refs keep the source."""
    w = CooperativeFuser("B4_ci").step(1.0, [est("a", 1, x=(0, 0, 0, 0), seq=1), est("b", 1, x=(50, 0, 0, 0), seq=1)])
    assert len(w.tracks) == 2 and {t.members for t in w.tracks} == {(("a", 1),), (("b", 1),)}


def test_fus04_contradictory_remote_far_from_local_stays_separate_and_is_not_fused():
    w = CooperativeFuser("B4_ci").step(1.0, [loc(1, x=(10, 0, 1, 0)), est("k", 1, x=(14, 3, 1, 0), seq=1)])
    assert len(w.tracks) == 2 and all("single_source" in t.flags for t in w.tracks)


def test_fus04_close_pedestrians_are_a_documented_association_limit():
    """KF-1 lives on: two real targets 0.4 m apart with sigma 0.2 m are inside the gate for BOTH pairings, so the ambiguity flag fires (the answer can be wrong)."""
    ests = [loc(1, x=(10, 0, 1, 0)), loc(2, x=(10, 0.4, 1, 0)), est("k", 1, x=(10, 0.0, 1, 0), seq=1), est("k", 2, x=(10, 0.4, 1, 0), seq=1)]
    w = CooperativeFuser("B4_ci").step(1.0, ests)
    assert any("ambiguous_association" in t.flags for t in w.tracks)


def test_fus04_association_is_deterministic():
    ests = [loc(1, x=(10, 0, 1, 0)), est("k", 1, x=(10.1, 0.1, 1, 0), seq=1)]
    a = CooperativeFuser("B4_ci").step(1.0, ests); b = CooperativeFuser("B4_ci").step(1.0, list(reversed(ests)))
    assert a == b                                                                                      # input order does not matter
