"""PHY-03 · braking distance and friction. Closed form (<=1 mm) and an independent fine-step integrator (<=5 mm)."""
import pytest
from backend.params import VehicleParams, G
from tests.physics.helpers import make, run, vframe
from tests.physics.reference import stop_distance, numeric_stop_distance

pytestmark = pytest.mark.phy
P = VehicleParams()
GRID = [(v0, mode, mu) for v0 in (5.0, 7.0, 9.0, 11.0) for mode in ("emergency", "comfort") for mu in (0.5, 0.8)]


def _sim_stop(v0, mode, mu, a_cmd=-100.0, t_cmd=0.5):
    d = make(duration=40.0, stop_when_all_stopped=True, road={"mu": mu},
             vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": v0},
                        "script": [{"t": t_cmd, "a_cmd": a_cmd, "mode": mode}]}])
    w, frames, _ = run(d)
    last = vframe(frames[-1])
    assert last["v"] == 0.0 and last["a"] == 0.0, "vehicle must come to rest"
    x_cmd = v0 * t_cmd
    return last["x"] - x_cmd, frames


@pytest.mark.parametrize("v0,mode,mu", GRID)
def test_stopping_distance_matches_closed_form_and_numeric(v0, mode, mu):
    a_brk, jerk = (P.a_brk_emergency, P.j_emergency) if mode == "emergency" else (P.a_brk_comfort, P.j_comfort)
    a_c = min(a_brk, mu * G)                                   # friction clips the achievable deceleration
    sim, _ = _sim_stop(v0, mode, mu)
    ref = stop_distance(v0, a_c, jerk, P.t_act)
    num = numeric_stop_distance(v0, a_c, jerk, P.t_act)
    assert abs(sim - ref) <= 1e-3, (sim, ref)
    assert abs(sim - num) <= 5e-3, (sim, num)


def test_headline_numbers_match_documentation():
    """07 §2 / 04 §3 state 9.45 m (emergency) and 17.64 m (comfort) at 30 km/h, mu=0.8."""
    v0 = 30 / 3.6
    assert round(_sim_stop(v0, "emergency", 0.8)[0], 2) == 9.45
    assert round(_sim_stop(v0, "comfort", 0.8)[0], 2) == 17.64


def test_friction_clips_deceleration_on_low_mu():
    _, frames = _sim_stop(9.0, "emergency", 0.5)
    amin = min(vframe(f)["a"] for f in frames)
    assert amin == pytest.approx(-0.5 * G, abs=1e-12)           # never exceeds mu*g
    assert any(vframe(f)["friction_limited"] for f in frames)


def test_stop_during_jerk_ramp_low_speed():
    v0 = 1.0                                                    # comfort ramp would take 1.2 s; speed is exhausted first
    sim, _ = _sim_stop(v0, "comfort", 0.8)
    assert abs(sim - stop_distance(v0, 3.0, 2.5, P.t_act)) <= 1e-3


def test_no_reverse_after_stop():
    _, frames = _sim_stop(5.0, "emergency", 0.8)
    assert all(vframe(f)["v"] >= 0.0 for f in frames)


ALIGNED = [(v0, mode, 0.8) for v0 in (5.0, 7.0, 9.0, 11.0) for mode in ("emergency", "comfort")]   # a_c/(j*dt) is an integer


@pytest.mark.parametrize("v0,mode,mu", ALIGNED)
def test_step_aligned_ramps_are_exact_to_float_precision(v0, mode, mu):
    """When the jerk ramp ends exactly on a step boundary the integration is exact; this also pins the in-step stop-time solve."""
    a_brk, jerk = (P.a_brk_emergency, P.j_emergency) if mode == "emergency" else (P.a_brk_comfort, P.j_comfort)
    sim, _ = _sim_stop(v0, mode, mu)
    assert abs(sim - stop_distance(v0, a_brk, jerk, P.t_act)) <= 1e-9


def test_unaligned_ramp_error_is_bounded_and_documented():
    """mu=0.5 -> a_c = 4.905 ends mid-step; the linear-within-step assumption costs < 0.1 mm (measured max ~4.7e-5 m)."""
    for v0 in (5.0, 7.0, 9.0, 11.0):
        sim, _ = _sim_stop(v0, "emergency", 0.5)
        assert abs(sim - stop_distance(v0, 0.5 * G, P.j_emergency, P.t_act)) <= 1e-4
