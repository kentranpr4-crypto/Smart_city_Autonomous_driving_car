"""PHY-07 (geometry part) · FOV and range boundaries, 2.5D occlusion vs the analytic shadow D = d*h_s/(h_s-h_o), shadow polygon, occluder semantics.
Analytic tolerance (PRD §12.2): <= 1 mm. See docs/phase2/wp-reports/PHY07-08-reconciliation.md for the clarification about which edge defines d."""
import math, random
import pytest
from backend.sensors import ray_blocked, target_visible, ground_shadow_polygon, signed_distance_to_convex, SensorProvider
from tests.perception.helpers import *

pytestmark = pytest.mark.phy


def _bisect_shadow_end(hs, prism, x_far, lo, hi):
    """Along +x from the sensor at the origin: smallest ground distance beyond the obstacle where the ground point becomes visible."""
    f = lambda x: ray_blocked((0.0, 0.0, hs), (x, 0.0, 0.0), prism)
    assert f(lo) and not f(hi)
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if f(mid) else (lo, mid)
    return 0.5 * (lo + hi)


@pytest.mark.parametrize("hs", [4.0, 6.0, 8.0])
@pytest.mark.parametrize("ho", [1.0, 3.0])
@pytest.mark.parametrize("d_near,depth", [(5.0, 0.0001), (10.0, 0.0001), (20.0, 0.0001), (10.0, 2.0), (6.0, 3.0)])
def test_ground_shadow_end_matches_analytic_within_1mm(hs, ho, d_near, depth):
    d_far = d_near + depth                                     # d in the formula = distance to the FAR top edge
    prism = (d_near + depth / 2, 0.0, 0.0, depth / 2, 5.0, ho)  # centre, yaw, half-length (along x), half-width, height
    D = d_far * hs / (hs - ho)
    D_sim = _bisect_shadow_end(hs, prism, d_far, d_far + 1e-6, D + 50.0)
    assert abs(D_sim - D) <= 1e-3, (D_sim, D)
    assert abs(D_sim - D) <= 1e-9                              # in practice exact to float precision


@pytest.mark.parametrize("hs,ho", [(3.0, 3.0), (2.0, 3.0), (1.5, 3.0), (1.0, 1.0)])
def test_sensor_not_above_obstacle_gives_unbounded_shadow(hs, ho):
    prism = (10.0, 0.0, 0.0, 1.0, 5.0, ho)
    assert ground_shadow_polygon(0.0, 0.0, hs, prism) is None
    for x in (12.0, 30.0, 100.0, 190.0):
        assert ray_blocked((0.0, 0.0, hs), (x, 0.0, 0.0), prism)
    assert ray_blocked((0.0, 0.0, hs), (30.0, 0.0, 0.0), prism)


def test_shadow_polygon_equals_ray_test_everywhere_outside_a_1mm_band():
    rnd = random.Random(20261101)
    mism = band = tested = 0
    for _ in range(40):
        hs, ho = rnd.uniform(3.0, 9.0), rnd.uniform(0.5, 2.8)
        prism = (rnd.uniform(5, 15), rnd.uniform(-8, 8), rnd.uniform(-math.pi, math.pi), rnd.uniform(0.5, 3.0), rnd.uniform(0.5, 3.0), ho)
        poly = ground_shadow_polygon(0.0, 0.0, hs, prism)
        for _ in range(200):
            p = (rnd.uniform(-5, 60), rnd.uniform(-30, 30))
            sd = signed_distance_to_convex(poly, p)
            hidden = ray_blocked((0.0, 0.0, hs), (p[0], p[1], 0.0), prism)
            if abs(sd) <= 1e-3:
                band += 1; continue
            tested += 1
            mism += hidden != (sd < 0)
    assert tested > 7000 and mism == 0, (tested, mism)
    assert band < 50                                           # the exempt 1 mm band is tiny, not a place to hide failures


def test_head_visible_over_low_wall_but_not_over_tall_wall():
    s = (0.0, 0.0, 1.5)                                       # vehicle-height sensor
    low = (10.0, 0.0, 0.0, 0.05, 5.0, 1.0)                    # 1.0 m wall
    tall = (10.0, 0.0, 0.0, 0.05, 5.0, 3.0)
    assert target_visible(s, 20.0, 0.0, 1.7, [low])           # head (1.7 m) clears the wall: visible
    assert not target_visible(s, 20.0, 0.0, 1.7, [tall])
    assert not target_visible(s, 20.0, 0.0, 0.5, [low])       # a 0.5 m object right behind a 1 m wall is hidden for this sensor


def test_ray_touching_exact_top_edge_is_not_blocked_but_just_below_is():
    prism = (10.0, 0.0, 0.0, 0.5, 5.0, 2.0)
    hs = 5.0
    D = 10.5 * hs / (hs - 2.0)
    assert not ray_blocked((0, 0, hs), (D, 0.0, 0.0), prism)  # grazing the far top edge: visible by definition (< is strict)
    assert ray_blocked((0, 0, hs), (D - 1e-6, 0.0, 0.0), prism)


def test_cctv_sees_behind_a_truck_that_hides_the_ground_from_a_vehicle_sensor():
    truck = wall("truck", cx=20.0, cy=0.0, length=8.0, width=2.5, h=3.0)
    target = ped("p", x=26.0, y=0.0)
    pv_v = SensorProvider([cctv("ego", pose=(0.0, 0.0, 0.0), height=1.5, **PERFECT)], 1, DT)
    pv_c = SensorProvider([cctv("cam", pose=(10.0, 12.0, -math.pi / 2), height=6.0, range_m=40.0, **PERFECT)], 1, DT)
    (fv, lv), = pv_v.sample(snap([target], [truck]), 0)
    (fc, lc), = pv_c.sample(snap([target], [truck]), 0)
    assert "p" in lv.candidates and "p" not in lv.visible and len(fv.detections) == 0      # ego-height sensor: occluded
    assert "p" in lc.candidates and "p" in lc.visible and len(fc.detections) == 1            # elevated CCTV: sees it


def test_vehicle_occluders_block_but_own_vehicle_and_target_do_not():
    spec = cctv("ego", pose=(0.0, 0.0, 0.0), height=1.5, **PERFECT)
    blocker = veh("blk", x=10.0, y=0.0, h=1.6)
    target = veh("tgt", x=20.0, y=0.0, h=1.5)
    pv = SensorProvider([spec], 1, DT)
    (f, lab), = pv.sample(snap([blocker, target]), 0)
    assert "blk" in lab.visible and "tgt" not in lab.visible                                 # blocker hides the target behind it, not itself
    (f, lab), = pv.sample(snap([target]), 10)
    assert "tgt" in lab.visible                                                              # a target never occludes itself


def test_vehicle_mounted_sensor_follows_vehicle_pose_and_excludes_own_body():
    from backend.sensor_spec import SensorSpec
    spec = SensorSpec(id="ego_cam", kind="vehicle", mount_vehicle="ego", height=1.5, fov=math.radians(90), range_m=50.0, rate_hz=10.0, mount_offset=(0.5, 0.0), **PERFECT)
    pv = SensorProvider([spec], 1, DT)
    ego = veh("ego", x=100.0, y=50.0, psi=math.pi / 2)         # heading +y; sensor 0.5 m ahead of centre
    t = ped("p", x=100.0, y=70.0)
    (f, lab), = pv.sample(snap([ego, t]), 0)
    assert f.sensor_pose[:3] == pytest.approx((100.0, 50.5, math.pi / 2), abs=1e-9)
    assert "p" in lab.visible and "ego" not in lab.candidates                                # sees the pedestrian ahead, not its own body
