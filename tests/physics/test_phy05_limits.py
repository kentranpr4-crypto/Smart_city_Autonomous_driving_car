"""PHY-05 · acceleration / jerk / steering / friction-circle limits hold for ANY command sequence (property test, derandomised)."""
import math
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from backend.params import VehicleParams, G
from tests.physics.helpers import make, run, vframe

pytestmark = pytest.mark.phy
P = VehicleParams()
MUG = 0.8 * G
EPS = 1e-9

cmd = st.fixed_dictionaries({
    "t": st.integers(0, 500).map(lambda k: k * 0.01),
    "a_cmd": st.floats(-15.0, 15.0, allow_nan=False, allow_infinity=False),
    "delta_cmd": st.floats(-1.5, 1.5, allow_nan=False, allow_infinity=False),
    "mode": st.sampled_from(["comfort", "emergency"]),
})


def check_limits(frames, dt=0.01):
    prev = None
    for f in frames:
        s = vframe(f)
        assert s["v"] >= 0.0
        assert -P.a_brk_emergency - EPS <= s["a"] <= P.a_acc + EPS
        assert abs(s["a"]) <= MUG + EPS
        assert abs(s["delta"]) <= P.delta_max + EPS
        ay = None
        if prev is not None:
            jmax = P.j_emergency if s["cmd"]["mode"] == "emergency" else P.j_comfort
            stopped_now = s["v"] == 0.0 and prev["v"] > 0.0
            if not stopped_now:
                assert abs(s["a"] - prev["a"]) <= jmax * dt + EPS, (f["step"], s["a"], prev["a"])
            assert abs(s["delta"] - prev["delta"]) <= P.delta_rate_max * dt + EPS
            v_ref = max(s["v"], prev["v"])
            ay = v_ref ** 2 * abs(math.tan(s["delta_eff"])) / P.wheelbase
            assert math.hypot(s["a"], ay) <= MUG + 1e-7, (f["step"], s["a"], ay)    # friction circle
        prev = s


@settings(max_examples=150, derandomize=True, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(v0=st.floats(0.0, 11.0), d0=st.floats(-0.6, 0.6), script=st.lists(cmd, min_size=0, max_size=8))
def test_random_command_sequences_never_break_limits(v0, d0, script):
    d = make(duration=6.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": v0, "delta": d0}, "script": script}])
    _, frames, _ = run(d)
    check_limits(frames)


@pytest.mark.parametrize("a_cmd,delta_cmd,mode", [(-1e6, 1e6, "emergency"), (1e6, -1e6, "comfort"), (-1e6, 0.0, "comfort"), (-6.0, 0.61, "emergency")])
def test_extreme_commands_are_clipped(a_cmd, delta_cmd, mode):
    d = make(duration=6.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": 10.0},
                                       "script": [{"t": 0.0, "a_cmd": a_cmd, "delta_cmd": min(max(delta_cmd, -1.5), 1.5), "mode": mode}]}])
    _, frames, _ = run(d)
    check_limits(frames)


def test_comfort_jerk_is_lower_than_emergency():
    def peak_jerk(mode):
        d = make(duration=3.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": 8.0},
                                           "script": [{"t": 0.0, "a_cmd": -6.0, "mode": mode}]}])
        _, fr, _ = run(d)
        s = [vframe(f) for f in fr]
        # exclude the standstill transition: a snaps to 0 when v reaches 0 (documented limitation, see backend.params.LIMITATIONS)
        return max(abs(s[i + 1]["a"] - s[i]["a"]) / 0.01 for i in range(len(s) - 1) if s[i + 1]["v"] > 0.0)
    assert peak_jerk("comfort") == pytest.approx(P.j_comfort, rel=1e-9)
    assert peak_jerk("emergency") == pytest.approx(P.j_emergency, rel=1e-9)
