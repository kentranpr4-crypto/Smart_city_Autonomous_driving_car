"""PHY-04 · steering and turning: R = L/tan(delta), heading law, steering-rate limit, friction clamp on curvature."""
import math
import pytest
from backend.params import VehicleParams, G
from tests.physics.helpers import make, run, vframe
from tests.physics.reference import circumradius

pytestmark = pytest.mark.phy
P = VehicleParams()


def _circle(v, delta, duration=4.0, mu=0.8):
    d = make(duration=duration, road={"mu": mu},
             vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": v, "delta": delta}}])
    return run(d)


@pytest.mark.parametrize("v,delta", [(3.0, 0.1), (3.0, 0.2), (3.0, 0.4), (2.0, -0.3), (4.0, 0.25)])
def test_steady_turn_radius_and_heading(v, delta):
    _, frames, _ = _circle(v, delta)
    R = P.wheelbase / math.tan(abs(delta))
    sgn = 1.0 if delta > 0 else -1.0
    cx, cy = 0.0 - sgn * R * 0.0, sgn * R                      # centre for psi0 = 0: (0, +/-R)
    worst_r = worst_psi = 0.0
    for f in frames:
        s = vframe(f)
        worst_r = max(worst_r, abs(math.hypot(s["x"] - cx, s["y"] - cy) - R))
        worst_psi = max(worst_psi, abs(s["psi"] - v * math.tan(delta) / P.wheelbase * f["t"]))
    assert worst_r <= 1e-3 and worst_psi <= 1e-3                # criterion; actual errors are far smaller (recorded in WP report)
    assert worst_r <= 1e-9 and worst_psi <= 1e-9


def test_friction_limits_curvature_to_mu_g_over_v2():
    v, delta, mu = 30 / 3.6, math.radians(35.0), 0.8             # demanded a_y = 18 m/s^2 >> mu*g
    w, frames, _ = _circle(v, delta, duration=3.0, mu=mu)
    pts = [(vframe(f)["x"], vframe(f)["y"]) for f in (frames[10], frames[150], frames[290])]
    R_expect = v * v / (mu * G)
    assert abs(circumradius(*pts) - R_expect) <= 1e-3
    assert all(vframe(f)["friction_limited"] for f in frames[1:])
    assert w.counts["outside_model_validity_steps"] > 0         # a_y = mu*g > 0.5*mu*g : flagged, never silently trusted


def test_steering_rate_limit_and_delay():
    d = make(duration=2.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": 2.0},
                                       "script": [{"t": 0.0, "a_cmd": 0.0, "delta_cmd": 0.3}]}])
    _, frames, _ = run(d)
    for f in frames:
        t = f["t"]
        expect = 0.0 if t <= P.t_steer else min(0.3, P.delta_rate_max * (t - P.t_steer))
        assert abs(vframe(f)["delta"] - expect) <= 1e-9, (t, vframe(f)["delta"], expect)


def test_steering_angle_clipped_to_delta_max():
    d = make(duration=3.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": 1.0},
                                       "script": [{"t": 0.0, "a_cmd": 0.0, "delta_cmd": 1.4}]}])
    _, frames, _ = run(d)
    assert max(abs(vframe(f)["delta"]) for f in frames) == pytest.approx(P.delta_max, abs=1e-12)


def test_minimum_turning_radius_at_low_speed():
    _, frames, _ = _circle(1.0, P.delta_max, duration=6.0)
    R = P.wheelbase / math.tan(P.delta_max)
    assert R == pytest.approx(3.856, abs=1e-3)
    s = vframe(frames[-1])
    assert abs(math.hypot(s["x"], s["y"] - R) - R) <= 1e-9
