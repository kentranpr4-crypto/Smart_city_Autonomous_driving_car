"""PHY-06 · geometric collision detection and pedestrian interaction, checked against analytic first-contact times."""
import math
import pytest
from backend.collision import sat_obb_obb, dist_point_obb, dist_segment_obb, capsule_hits_obb, obb_corners
from backend.scenario import ScenarioError, scenario_from_dict
from tests.physics.helpers import make, run, vframe

pytestmark = pytest.mark.phy

# ------------------------------------------------------------------ SAT / distance tables (hand-derived cases)
A = (0.0, 0.0, 0.0, 2.0, 1.0)      # 4 x 2 box at origin
SAT_CASES = [
    ((5.0, 0.0, 0.0, 2.0, 1.0), False),                # clear gap
    ((4.0, 0.0, 0.0, 2.0, 1.0), True),                 # edges exactly touching (counts as contact)
    ((3.9, 0.0, 0.0, 2.0, 1.0), True),                 # overlap
    ((0.0, 2.5, 0.0, 2.0, 1.0), False),
    ((0.0, 2.0, 0.0, 2.0, 1.0), True),                 # touching on the long side
    ((3.5, 2.5, math.pi / 4, 2.0, 1.0), False),        # rotated, diagonal gap
    ((0.0, 0.0, math.pi / 2, 2.0, 1.0), True),         # same centre, rotated 90 deg
    ((2.0 + math.sqrt(2) * 1.0 + 0.001, 0.0, math.pi / 4, 1.0, 1.0), False),   # rotated square just clear
    ((2.0 + math.sqrt(2) * 1.0 - 0.001, 0.0, math.pi / 4, 1.0, 1.0), True),    # rotated square just overlapping
]


@pytest.mark.parametrize("b,expect", SAT_CASES)
def test_sat_table(b, expect):
    assert sat_obb_obb(A, b) is expect
    assert sat_obb_obb(b, A) is expect                  # symmetric


def test_point_and_segment_distance():
    assert dist_point_obb(A, 3.0, 0.0) == pytest.approx(1.0)
    assert dist_point_obb(A, 3.0, 2.0) == pytest.approx(math.sqrt(2.0))      # corner region
    assert dist_point_obb(A, 0.5, 0.5) == 0.0
    assert dist_segment_obb(A, (3.0, -5.0), (3.0, 5.0)) == pytest.approx(1.0)  # passes beside the box
    assert dist_segment_obb(A, (-5.0, 0.0), (5.0, 0.0)) == 0.0                # through the box
    assert capsule_hits_obb(A, (3.0, -5.0), (3.0, 5.0), 1.0) and not capsule_hits_obb(A, (3.0, -5.0), (3.0, 5.0), 0.99)


# ------------------------------------------------------------------ first-contact time vs analytic (static pedestrian)
P_FRONT = 3.6   # rear axle -> front bumper (wheelbase 2.7 + front overhang 0.9)
HALF_W = 0.9
R = 0.3


def analytic_contact_time(v, x_ped, y_off):
    """Pedestrian at (x_ped, y_off), ego along +x at speed v from x=0 (rear axle). Returns first-contact time."""
    gap = abs(y_off) - HALF_W
    if gap > R:
        return None
    lateral = R if gap <= 0 else math.sqrt(R * R - gap * gap)   # pedestrian centre inside the hull width -> nearest point is R ahead
    front_needed = x_ped - lateral
    return (front_needed - P_FRONT) / v


@pytest.mark.parametrize("v", [3.0, 8.0, 11.0])
@pytest.mark.parametrize("y_off", [0.0, 0.5, 0.9, 1.0, 1.1, 1.19, 1.21, -1.0])
def test_first_contact_time_matches_analytic_within_one_step(v, y_off):
    x_ped = 30.0
    d = make(duration=14.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": v}}],
             pedestrians=[{"id": "p", "radius": R, "path": [[x_ped, y_off], [x_ped, y_off + 1e-9]], "speed": 0.0}])
    w, frames, _ = run(d)
    t_ref = analytic_contact_time(v, x_ped, y_off)
    cols = [e for f in frames for e in f["events"] if e["type"] == "collision"]
    if t_ref is None:
        assert not cols
        return
    assert len(cols) == 1
    # first step whose pose overlaps: detection time lies in [t_ref, t_ref + dt]
    assert t_ref - 1e-9 <= cols[0]["t"] <= t_ref + 0.01 + 1e-9, (cols[0]["t"], t_ref)
    assert cols[0]["impact_speed"] == pytest.approx(v, abs=1e-9)


def test_moving_pedestrian_collision_matches_brute_force_and_impact_speed():
    v, vp, x0 = 8.0, 1.4, 24.0
    d = make(duration=6.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": v}}],
             pedestrians=[{"id": "p", "radius": R, "path": [[x0, -4.0], [x0, 4.0]], "speed": vp, "start_time": 0.0}])
    w, frames, _ = run(d)
    ev = [e for f in frames for e in f["events"] if e["type"] == "collision"]
    assert len(ev) == 1
    # independent brute force at 1e-5 s: first time the exact geometry overlaps
    t = 0.0
    while t < 6.0:
        xe_front = v * t + P_FRONT
        yp = -4.0 + vp * t
        lat = max(abs(yp) - HALF_W, 0.0)
        hit = lat <= R and (x0 - xe_front) <= math.sqrt(max(R * R - lat * lat, 0.0)) and x0 >= v * t - 0.9 - 1e-12
        if hit: break
        t += 1e-5
    assert t - 1e-4 <= ev[0]["t"] - 0.01 <= t + 0.01 + 1e-4 or abs(ev[0]["t"] - t) <= 0.0101
    assert ev[0]["impact_speed"] == pytest.approx(math.hypot(v, vp), abs=1e-9)   # perpendicular velocities
    assert w.finished and frames[-1]["events"]                                    # run ends at contact


def test_obstacle_collision_and_stop_on_collision():
    d = make(duration=6.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": 5.0}}],
             obstacles=[{"id": "truck", "center": [20.0, 0.0], "size": [10.0, 2.5]}])
    w, frames, _ = run(d)
    ev = [e for f in frames for e in f["events"] if e["type"] == "collision"]
    assert len(ev) == 1 and ev[0]["actors"] == ["ego", "truck"]
    # front bumper reaches the truck's rear face at x=15 when rear axle x = 15 - 3.6
    assert ev[0]["t"] == pytest.approx((15.0 - P_FRONT) / 5.0, abs=0.0101)
    assert w.finished


def test_no_tunnelling_at_maximum_speed_over_dense_offsets():
    v = 40 / 3.6
    for k in range(0, 41):
        y_off = -1.3 + k * 0.065
        d = make(duration=4.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": v}}],
                 pedestrians=[{"id": "p", "radius": R, "path": [[20.0, y_off], [20.0, y_off + 1e-9]], "speed": 0.0}])
        _, frames, _ = run(d)
        hit = any(e["type"] == "collision" for f in frames for e in f["events"])
        assert hit == (abs(y_off) <= HALF_W + R + 1e-12), y_off


def test_tunnelling_guard_rejects_too_coarse_dt():
    with pytest.raises(ScenarioError, match="tunnelling guard"):
        scenario_from_dict(make(dt=0.05, duration=1.0,
                                pedestrians=[{"id": "p", "radius": 0.3, "path": [[10, 0], [10, 1]], "speed": 1.5}]))
