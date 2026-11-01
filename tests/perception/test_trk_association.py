"""Association, confirmation and clutter behaviour. Thresholds are pre-registered in the comments of each test (no re-tuning after seeing results)."""
import itertools, math, random
import pytest
from perception.hungarian import linear_sum_assignment
from perception.tracker import Tracker, TrackerConfig
from tests.perception.helpers import *
from tests.perception.tracking_helpers import mk_frame, simulate_scene, associate, id_switches

pytestmark = pytest.mark.trk
SEED = 20261101


# ------------------------------------------------------------------ Hungarian (optimal assignment) vs brute force
def _brute(cost):
    n, m = len(cost), len(cost[0])
    best = math.inf
    k = min(n, m)
    for rows in itertools.combinations(range(n), k):
        for cols in itertools.permutations(range(m), k):
            best = min(best, sum(cost[r][c] for r, c in zip(rows, cols)))
    return best


def test_hungarian_matches_brute_force_on_random_rectangular_matrices():
    rnd = random.Random(SEED)
    for _ in range(300):
        n, m = rnd.randint(1, 6), rnd.randint(1, 6)
        cost = [[rnd.uniform(0, 100) for _ in range(m)] for _ in range(n)]
        pairs = linear_sum_assignment(cost)
        assert len(pairs) == min(n, m) and len({r for r, _ in pairs}) == len(pairs) and len({c for _, c in pairs}) == len(pairs)
        assert sum(cost[r][c] for r, c in pairs) == pytest.approx(_brute(cost), abs=1e-9)


def test_hungarian_is_deterministic_on_ties_and_handles_empty_inputs():
    cost = [[1, 1, 1], [1, 1, 1], [1, 1, 1]]
    assert linear_sum_assignment(cost) == linear_sum_assignment([r[:] for r in cost])
    assert linear_sum_assignment([]) == [] and linear_sum_assignment([[]]) == []


# ------------------------------------------------------------------ scenes
def two_peds(a0, av, b0, bv):
    return lambda t: [ped("a", a0[0] + av[0] * t, a0[1] + av[1] * t), ped("b", b0[0] + bv[0] * t, b0[1] + bv[1] * t)]


CAM = dict(pose=(10.0, -25.0, math.pi / 2), height=6.0, fov_deg=120.0, range_m=70.0)


def min_separation(fn, ts):
    return min(math.dist((fn(t)[0].x, fn(t)[0].y), (fn(t)[1].x, fn(t)[1].y)) for t in ts)


def test_perpendicular_crossing_with_1p7m_miss_has_no_id_switch_in_20_seeds():
    """pre-registered: miss distance >= 1.2 m (here 1.77 m), sigma ~0.2-0.3 m  ->  0 ID switches in each of 20 seeds, exactly 2 distinct confirmed ids."""
    fn = two_peds((0.0, 0.0), (1.4, 0.0), (16.5, -14.0), (0.0, 1.4))      # analytic minimum separation = 1.77 m (xb=16.5)
    ts = [i * 0.05 for i in range(0, 400)]
    assert min_separation(fn, ts) >= 1.2
    for s in range(20):
        tr, rec = simulate_scene(cctv(id="k", **CAM, **PERFECT), fn, 200, SEED + s)
        ids = {t.track_id for r in rec for t in r["tracks"]}
        assert id_switches(rec) == 0, s
        assert len(ids) == 2, (s, ids)


def test_parallel_walkers_2m_apart_have_no_id_switch_in_20_seeds():
    fn = two_peds((0.0, 0.0), (1.4, 0.0), (0.0, 2.0), (1.4, 0.0))
    for s in range(20):
        tr, rec = simulate_scene(cctv(id="k", pose=(10.0, -20.0, math.pi / 2), height=6.0, fov_deg=120.0, range_m=70.0, **PERFECT), fn, 150, SEED + s)
        assert id_switches(rec) == 0 and len({t.track_id for r in rec for t in r["tracks"]}) == 2, s


def test_missed_detections_do_not_break_tracks():
    """pre-registered: p_d = 0.7 flat -> after confirmation >= 98% of frames have a confirmed track on the target and 0 ID switches (20 seeds)."""
    for s in range(20):
        spec = cctv(id="k", pose=(0.0, -20.0, math.pi / 2), height=6.0, pd0=0.7, r50=1e4, pd_slope=1.0)
        tr, rec = simulate_scene(spec, lambda t: [ped("a", 0.0 + 1.0 * t, 0.0)], 200, SEED + s)
        first = next(i for i, r in enumerate(rec) if r["tracks"])
        covered = sum(bool(associate(r["tracks"], r["truth"])) for r in rec[first:]) / len(rec[first:])
        assert covered >= 0.98 and id_switches(rec) == 0, (s, covered)


@pytest.mark.parametrize("m,n,frames", [(2, 3, 2), (3, 4, 3)])
def test_confirmation_latency_is_exactly_m_frames_with_perfect_detection(m, n, frames):
    spec = cctv(id="k", pose=(0.0, -20.0, math.pi / 2), height=6.0, **PERFECT)
    tr, rec = simulate_scene(spec, lambda t: [ped("a", 5.0 + 1.0 * t, 0.0)], 30, SEED, cfg=TrackerConfig(confirm_m=m, confirm_n=n))
    first = next(i for i, r in enumerate(rec) if r["tracks"])
    assert first + 1 == frames                                              # frame index (1-based) at which the first track is published


def test_far_detection_outside_the_gate_is_not_associated_and_spawns_a_new_track():
    tr = Tracker("s", TrackerConfig())
    for k in range(5):
        tr.update(mk_frame(k, k * 0.1, [(0.0, 0.0, 0.04)]), t_now=k * 0.1)
    rep = tr.update(mk_frame(5, 0.5, [(30.0, 30.0, 0.04)]), t_now=0.5)
    assert rep.n_matched == 0 and rep.n_new == 1


def _false_confirmed_per_frame(cfg, frames, lam=2.0, seed=SEED):
    spec = cctv(id="k", pose=(0.0, 0.0, 0.0), height=6.0, fov_deg=120.0, range_m=50.0, clutter_rate=lam, **PERFECT)
    tr, rec = simulate_scene(spec, lambda t: [], frames, seed, cfg=cfg)
    ever = {t.track_id for r in rec for t in r["tracks"]}                    # no truth targets exist: every published track is false
    return len(ever) / frames


def test_false_confirmed_track_rate_is_close_to_the_analytic_estimate_for_2_of_3():
    """pre-registered estimate (see docstring): births ~ lam per frame; P(confirm) ~ 1-(1-p)^2 with p = lam*A_gate/A_sector.
    A_gate = pi*gamma*s2 (s2 = predicted position var + R ~ 0.22 m^2, gamma = 13.8155), A_sector = 0.5*r^2*fov.  Measured/estimate must lie in [0.3, 3]."""
    lam, r, fov = 2.0, 50.0, math.radians(120)
    s2 = 0.22
    p = lam * (math.pi * 13.8155 * s2) / (0.5 * r * r * fov)
    est = lam * (1 - (1 - p) ** 2)
    meas = _false_confirmed_per_frame(TrackerConfig(confirm_m=2, confirm_n=3), 2000)
    assert 0.3 <= meas / est <= 3.0, (meas, est)


def test_stricter_confirmation_reduces_false_tracks():
    f23 = _false_confirmed_per_frame(TrackerConfig(confirm_m=2, confirm_n=3), 2000)
    f34 = _false_confirmed_per_frame(TrackerConfig(confirm_m=3, confirm_n=4), 2000)
    assert f34 < f23 and f34 * 2000 <= 5                                    # pre-registered: <= 5 false confirmed tracks in 2000 frames at 3-of-4
