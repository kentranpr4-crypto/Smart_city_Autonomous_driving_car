"""KNOWN FAILURES (owner decision, WP3 #2): these two behaviours are real, measured limitations of the WP2 tracker and are kept as EXPLICIT failures.
Each test states the DESIRED behaviour and is xfail(strict=True): it must keep failing until the limitation is genuinely fixed; an unexpected pass
(XPASS) turns the suite red so the registry cannot silently go stale. Nothing here was loosened to pass; numbers: WP2 report (17/100 and 70/100 seeds)."""
import math
import pytest
from backend.sensors import SensorProvider
from tests.perception.helpers import *
from tests.perception.tracking_helpers import simulate_scene, id_switches

pytestmark = [pytest.mark.trk, pytest.mark.known_failure]
SEED = 20261101


def two_peds(a0, av, b0, bv):
    return lambda t: [ped("a", a0[0] + av[0] * t, a0[1] + av[1] * t), ped("b", b0[0] + bv[0] * t, b0[1] + bv[1] * t)]


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="KF-1: duplicate suppression merges two REAL pedestrians 0.4 m apart (WP2: 17/100 seeds ID switch, mean 1.19 tracks). Not fixed in WP3.")
def test_KF1_two_pedestrians_0p4m_apart_are_kept_as_two_tracks():
    spec = cctv(id="k", pose=(10.0, -20.0, math.pi / 2), height=6.0, fov_deg=120.0, range_m=70.0, **PERFECT)
    for s in range(60):
        tr, rec = simulate_scene(spec, two_peds((0, 0), (1.4, 0), (0, 0.4), (1.4, 0)), 150, SEED + s)
        ids = {t.track_id for r in rec for t in r["tracks"]}
        assert len(ids) == 2 and id_switches(rec) == 0, (s, ids)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="KF-2: collision-course crossing (0.00 m miss distance) causes ID switches (WP2: 70/100 seeds). Not fixed in WP3.")
def test_KF2_collision_course_crossing_keeps_identities():
    spec = cctv(id="k", pose=(10.0, -25.0, math.pi / 2), height=6.0, fov_deg=120.0, range_m=70.0, **PERFECT)
    for s in range(20):
        tr, rec = simulate_scene(spec, two_peds((0, 0), (1.4, 0), (14.0, -14), (0, 1.4)), 200, SEED + s)
        assert id_switches(rec) == 0, s
