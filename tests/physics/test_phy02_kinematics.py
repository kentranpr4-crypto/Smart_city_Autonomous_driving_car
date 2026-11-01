"""PHY-02 · straight-line kinematics vs closed form (delay + jerk-limited ramp + constant accel). Tolerance 1e-6 m."""
import pytest
from backend.params import VehicleParams
from tests.physics.helpers import make, run, vframe
from tests.physics.reference import ramp_motion

pytestmark = pytest.mark.phy
P = VehicleParams()
CASES = [  # (v0, a_cmd, mode)
    (0.0, 1.5, "comfort"), (0.0, 2.0, "comfort"), (3.0, 2.0, "comfort"),
    (8.0, -2.0, "comfort"), (8.0, -3.0, "comfort"), (10.0, -6.0, "emergency"), (8.333333333333334, 0.0, "comfort"),
]


@pytest.mark.parametrize("v0,a_cmd,mode", CASES)
def test_trajectory_matches_closed_form(v0, a_cmd, mode):
    t_cmd = 1.0
    d = make(duration=4.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": v0},
                                       "script": [{"t": t_cmd, "a_cmd": a_cmd, "mode": mode}]}])
    _, frames, _ = run(d)
    jerk = P.j_emergency if mode == "emergency" else P.j_comfort
    a_t = min(max(a_cmd, -(P.a_brk_emergency if mode == "emergency" else P.a_brk_comfort)), P.a_acc)
    worst = 0.0
    for f in frames:
        t = f["t"]
        v = vframe(f)
        if t <= t_cmd:
            x_ref, v_ref, a_ref = v0 * t, v0, 0.0
        else:
            dx, vv, aa = ramp_motion(v0, a_t, jerk, P.t_act, t - t_cmd)
            x_ref, v_ref, a_ref = v0 * t_cmd + dx, vv, aa
        if v_ref < 0:                       # not reached in this grid; guard
            continue
        worst = max(worst, abs(v["x"] - x_ref))
        assert abs(v["x"] - x_ref) <= 1e-6, (t, v["x"], x_ref)
        assert abs(v["v"] - v_ref) <= 1e-9 and abs(v["a"] - a_ref) <= 1e-9
    assert worst <= 1e-6


def test_command_becomes_effective_exactly_after_t_act():
    d = make(duration=2.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": 5.0},
                                       "script": [{"t": 1.0, "a_cmd": -3.0}]}])
    _, frames, _ = run(d)
    a_by_step = {f["step"]: vframe(f)["a"] for f in frames}
    assert a_by_step[115] == 0.0                 # t=1.15: command just became effective, ramp starts
    assert a_by_step[116] < 0.0
    assert a_by_step[114] == 0.0
