"""INDEPENDENT analytic / numeric references for the physics gates. Deliberately shares no code with backend/*."""
from __future__ import annotations
import math


def stop_distance(v0: float, a_c: float, jerk: float, td: float) -> float:
    """Distance travelled from brake command to standstill. Delay td (no decel), then linear ramp at `jerk` to a_c, then constant a_c."""
    tr = a_c / jerk
    v_after_ramp = v0 - jerk * tr * tr / 2.0
    if v_after_ramp >= 0.0:      # reaches full deceleration before stopping
        return v0 * td + v0 * tr - jerk * tr ** 3 / 6.0 + v_after_ramp ** 2 / (2.0 * a_c)
    ts = math.sqrt(2.0 * v0 / jerk)  # stops during the ramp
    return v0 * td + v0 * ts - jerk * ts ** 3 / 6.0


def ramp_motion(v0: float, a_target: float, jerk: float, td: float, t: float):
    """(x, v, a) at time t after a command at t=0 with pure delay td then jerk-limited ramp to a_target (signed)."""
    sgn = 1.0 if a_target >= 0 else -1.0
    if t <= td:
        return v0 * t, v0, 0.0
    tau = t - td
    tr = abs(a_target) / jerk
    x0 = v0 * td
    if tau <= tr:
        return x0 + v0 * tau + sgn * jerk * tau ** 3 / 6.0, v0 + sgn * jerk * tau ** 2 / 2.0, sgn * jerk * tau
    xr = x0 + v0 * tr + sgn * jerk * tr ** 3 / 6.0
    vr = v0 + sgn * jerk * tr ** 2 / 2.0
    d = tau - tr
    return xr + vr * d + a_target * d * d / 2.0, vr + a_target * d, a_target


def numeric_stop_distance(v0: float, a_c: float, jerk: float, td: float, h: float = 2e-5) -> float:
    """Independent midpoint integrator of the same command law at a much smaller step (no shared code with backend)."""
    t = x = 0.0; v = v0
    a = lambda tt: 0.0 if tt <= td else min(a_c, jerk * (tt - td))
    while True:
        am = a(t + h / 2.0)
        vn = v - am * h
        if vn <= 0.0:
            return x + v * v / (2.0 * max(am, 1e-12))
        x += (v + vn) / 2.0 * h
        v = vn; t += h


def circumradius(p1, p2, p3) -> float:
    (x1, y1), (x2, y2), (x3, y3) = p1, p2, p3
    a, b, c = math.dist(p2, p3), math.dist(p1, p3), math.dist(p1, p2)
    area2 = abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1))
    return a * b * c / (2.0 * area2)
