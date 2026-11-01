"""PHY-05 (extension) · moving -> stopping -> stationary regression, with an explicit statement of what the model can and cannot guarantee.

CANNOT guarantee: if braking is commanded all the way to v=0, acceleration snaps to 0 within one step (jerk = |a|/dt >> limit).
The model REPORTS this as a `standstill_jerk_discontinuity` event.  CAN guarantee: when the command eases the brake to ~0 as v->0
(soft stop) the jerk bound holds at EVERY step including the last one.
"""
import pytest
from backend.params import VehicleParams
from tests.physics.helpers import make, run, vframe
from tests.physics.reference import ramp_motion

pytestmark = pytest.mark.phy
P = VehicleParams()


def _stop_events(frames):
    return [e for f in frames for e in f["events"] if e["type"] == "standstill_jerk_discontinuity"]


def _abrupt(v0=5.0, mode="emergency", extra=3.0):
    d = make(duration=15.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": v0},
                                        "script": [{"t": 0.5, "a_cmd": -100.0, "mode": mode}]}])
    return run(d)


@pytest.mark.parametrize("mode,a_c,j", [("emergency", 6.0, 10.0), ("comfort", 3.0, 2.5)])
def test_abrupt_stop_exceeds_jerk_limit_and_is_reported(mode, a_c, j):
    w, frames, _ = _abrupt(5.0, mode)
    ev = _stop_events(frames)
    assert len(ev) == 1, "exactly one standstill transition"
    assert ev[0]["a_before"] == pytest.approx(-a_c) and ev[0]["limit"] == j
    assert ev[0]["jerk_equiv"] == pytest.approx(a_c / 0.01, rel=1e-9)          # 600 / 300 m/s^3  >>  limit
    assert ev[0]["jerk_equiv"] > 10 * j
    assert w.counts["standstill_jerk_discontinuities"] == 1


def test_stationary_state_is_frozen_after_stop():
    w, frames, _ = _abrupt(5.0)
    k = next(i for i, f in enumerate(frames) if vframe(f)["v"] == 0.0)
    ref = vframe(frames[k])
    assert len(frames) - k > 300                                                # many steps at rest are actually checked
    for f in frames[k:]:
        s = vframe(f)
        assert s["v"] == 0.0 and s["a"] == 0.0
        assert (s["x"], s["y"], s["psi"], s["wheel_rot"]) == (ref["x"], ref["y"], ref["psi"], ref["wheel_rot"])
        if f is not frames[k]:
            assert f["events"] == []                                            # nothing spurious after the transition


def test_velocity_is_monotone_non_increasing_to_zero_and_never_negative():
    _, frames, _ = _abrupt(9.0)
    v = [vframe(f)["v"] for f in frames]
    k = v.index(0.0)
    assert all(v[i + 1] <= v[i] + 1e-12 for i in range(0, k))
    assert min(v) == 0.0


def test_soft_stop_keeps_jerk_bound_at_every_step_including_standstill():
    """Command law: emergency brake, then ease to 0 so that a reaches 0 exactly when v does (v_ease = a^2/(2 j) = 1.8 m/s)."""
    v0, a_c, j, td = 9.6, 6.0, 10.0, P.t_act
    t_issue2 = 1.6                                   # second command effective at 1.75 s (t_act = 0.15 s)
    d = make(duration=4.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": v0},
             "script": [{"t": 0.0, "a_cmd": -a_c, "mode": "emergency"}, {"t": t_issue2, "a_cmd": 0.0, "mode": "emergency"}]}])
    w, frames, _ = run(d)
    # analytic expectation from independent code
    t_c = t_issue2 + td
    x_c, v_c, a_cc = ramp_motion(v0, -a_c, j, td, t_c)
    assert v_c == pytest.approx(a_c ** 2 / (2 * j), abs=1e-12)                    # 1.8 m/s: ramp-down will end exactly at rest
    tau = a_c / j
    x_expected = x_c + v_c * tau - a_c * tau ** 2 / 2 + j * tau ** 3 / 6
    # 1) jerk bound at EVERY step (no exemption)
    a = [vframe(f)["a"] for f in frames]
    assert max(abs(a[i + 1] - a[i]) for i in range(len(a) - 1)) / 0.01 <= j + 1e-9
    # 2) no standstill discontinuity was needed
    assert _stop_events(frames) == []
    # 3) the vehicle really did stop, where the closed form says
    last = vframe(frames[-1])
    assert abs(last["v"]) <= 1e-9 and abs(last["a"]) <= 1e-9
    assert last["x"] == pytest.approx(x_expected, abs=1e-6)
    assert min(vframe(f)["v"] for f in frames) >= 0.0


def test_restart_from_standstill_respects_jerk_and_moves():
    d = make(duration=12.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": 5.0},
             "script": [{"t": 0.5, "a_cmd": -100.0, "mode": "emergency"}, {"t": 6.0, "a_cmd": 2.0, "mode": "comfort"}]}])
    _, frames, _ = run(d)
    k = next(i for i, f in enumerate(frames) if vframe(f)["v"] == 0.0)
    x_rest = vframe(frames[k])["x"]
    a = [vframe(f)["a"] for f in frames]
    # after the (reported) stop, every step respects the comfort jerk bound
    assert max(abs(a[i + 1] - a[i]) for i in range(k + 1, len(a) - 1)) / 0.01 <= P.j_comfort + 1e-9
    assert vframe(frames[-1])["v"] > 1.0 and vframe(frames[-1])["x"] > x_rest + 5.0
    assert len(_stop_events(frames)) == 1                                        # only the original abrupt stop
