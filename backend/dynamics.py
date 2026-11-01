"""Vehicle dynamics for one fixed step.

Longitudinal motion is integrated EXACTLY for a piecewise-linear acceleration (the actuator produces linear
ramps), so straight-line results match closed forms to float precision. Path geometry is integrated in
arc length s with RK4 (exact for constant curvature to ~1e-12).  Friction is a friction-circle clip, NOT a tyre model.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, replace
from .params import VehicleParams, Friction


@dataclass(frozen=True)
class VehicleState:
    x: float
    y: float
    psi: float
    v: float
    a: float
    delta: float          # actuator (steering) angle
    delta_eff: float      # angle actually used after friction-circle limiting
    wheel_rot: float = 0.0


@dataclass(frozen=True)
class StepInfo:
    friction_limited: bool
    ay: float
    s: float


def mode_limits(mode: str, p: VehicleParams) -> tuple[float, float]:
    if mode == "emergency":
        return p.a_brk_emergency, p.j_emergency
    if mode == "comfort":
        return p.a_brk_comfort, p.j_comfort
    raise ValueError(f"unknown mode {mode!r}")


def effective_tan(delta: float, v_ref: float, a: float, p: VehicleParams, fr: Friction) -> tuple[float, bool]:
    """tan(delta) after friction-circle limiting: sqrt(a^2 + ay^2) <= mu*g with longitudinal priority."""
    t = math.tan(delta)
    ay_cap = math.sqrt(max(fr.mug * fr.mug - a * a, 0.0))
    if v_ref > 1e-9:
        t_lim = ay_cap * p.wheelbase / (v_ref * v_ref)
        if abs(t) > t_lim:
            return math.copysign(t_lim, t), True
    return t, False


def initial_state(x, y, psi, v, delta, p: VehicleParams, fr: Friction) -> VehicleState:
    t, _ = effective_tan(delta, v, 0.0, p, fr)
    return VehicleState(x, y, psi, v, 0.0, delta, math.atan(t), 0.0)


def _stop_time(v0: float, a0: float, jp: float, dt: float) -> float:
    """Smallest tau in [0, dt] with v0 + a0*tau + jp*tau^2/2 = 0 (stable quadratic)."""
    if v0 <= 0.0:
        return 0.0
    A, B, C = jp / 2.0, a0, v0
    if abs(A) < 1e-14:
        return min(-C / B, dt) if B < 0 else dt
    disc = B * B - 4.0 * A * C
    if disc < 0.0:
        return dt
    q = -0.5 * (B + math.copysign(math.sqrt(disc), B if B != 0 else 1.0))
    roots = [r for r in (q / A, (C / q) if q != 0 else None) if r is not None and 0.0 <= r <= dt * (1 + 1e-12)]
    return min(roots) if roots else dt


def _rk4_path(x, y, psi, S, k0, k1):
    """Integrate dx/ds=cos(psi), dy/ds=sin(psi), dpsi/ds=kappa(s) (linear from k0 to k1) over arc length S."""
    if S <= 0.0:
        return x, y, psi
    def f(s, st):
        px, py, pp = st
        k = k0 + (k1 - k0) * (s / S)
        return (math.cos(pp), math.sin(pp), k)
    s0 = (x, y, psi)
    k1_ = f(0.0, s0)
    k2_ = f(S / 2, tuple(a + S / 2 * b for a, b in zip(s0, k1_)))
    k3_ = f(S / 2, tuple(a + S / 2 * b for a, b in zip(s0, k2_)))
    k4_ = f(S, tuple(a + S * b for a, b in zip(s0, k3_)))
    return tuple(a + S / 6.0 * (b + 2 * c + 2 * d + e) for a, b, c, d, e in zip(s0, k1_, k2_, k3_, k4_))


def step_vehicle(st: VehicleState, a_cmd: float, delta_cmd: float, mode: str,
                 p: VehicleParams, fr: Friction, dt: float) -> tuple[VehicleState, StepInfo]:
    a_brk, jerk = mode_limits(mode, p)
    mug = fr.mug
    limited = False
    # --- longitudinal target (clamp -> friction -> no reverse), then jerk-limited approach
    tgt = min(max(a_cmd, -a_brk), p.a_acc)
    if abs(tgt) > mug:
        tgt = math.copysign(mug, tgt); limited = True
    if st.v <= 0.0 and tgt < 0.0:
        tgt = 0.0
    da, lim = tgt - st.a, jerk * dt
    a1 = tgt if abs(da) <= lim else st.a + math.copysign(lim, da)
    # --- steering actuator (angle and rate limits)
    d_tgt = min(max(delta_cmd, -p.delta_max), p.delta_max)
    dd, dlim = d_tgt - st.delta, p.delta_rate_max * dt
    d1 = d_tgt if abs(dd) <= dlim else st.delta + math.copysign(dlim, dd)
    # --- exact longitudinal integration for linear a(tau) on [0, dt]
    a0, v0 = st.a, st.v
    v1 = v0 + 0.5 * (a0 + a1) * dt
    if v1 <= 0.0:
        jp = (a1 - a0) / dt
        tau = _stop_time(v0, a0, jp, dt)
        s = v0 * tau + 0.5 * a0 * tau * tau + jp * tau ** 3 / 6.0
        v1, a1 = 0.0, 0.0
    else:
        s = v0 * dt + (2.0 * a0 + a1) / 6.0 * dt * dt
    # --- friction circle on lateral demand (uses end-of-step a1 and the larger speed)
    v_ref = max(v0, v1)
    t1, lat_lim = effective_tan(d1, v_ref, a1, p, fr)
    limited = limited or lat_lim
    t0 = math.tan(st.delta_eff)
    x, y, psi = _rk4_path(st.x, st.y, st.psi, s, t0 / p.wheelbase, t1 / p.wheelbase)
    ay = v_ref * v_ref * abs(t1) / p.wheelbase
    new = VehicleState(x, y, psi, v1, a1, d1, math.atan(t1), st.wheel_rot + s / p.wheel_radius)
    return new, StepInfo(limited, ay, s)
