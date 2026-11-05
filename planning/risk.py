"""Risk prediction for one hypothesis against the ego's longitudinal path. Closed form; no random numbers; no truth.
p_conflict : probability that the object is inside the ego swept corridor while the ego body passes its x-position, ego keeping its CURRENT speed.
precaution : the object is slow/stationary near the corridor and COULD (worst case, intent unknown) enter it before the ego passes.
Absence of an object is never evidence of freedom: this module only evaluates objects that exist as hypotheses."""
from __future__ import annotations
import math
from .types import EgoState, Hypothesis, Risk

INF = float("inf")


def phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def lateral_p_inside(mu: float, sigma: float, half: float) -> float:
    s = max(sigma, 1e-6)
    return phi((half - mu) / s) - phi((-half - mu) / s)


def assess(h: Hypothesis, ego: EgoState, prm: dict) -> Risk:
    w, so, H = prm["corridor_half_m"], prm["standoff_m"], prm["horizon_s"]
    xf = ego.x + ego.front_offset
    P = h.P
    pyy, pyv, pvv = P[5], P[7], P[15]
    v = max(ego.v, 0.0)
    best_p, t_best = 0.0, INF
    beside = h.x <= xf - 0.3                       # already level with / behind the front bumper: only what is inside the corridor NOW matters
    n = 0 if beside else int(H / 0.1)
    for k in range(n + 1):
        t = 0.1 * k
        xp = h.x + h.vx * t
        front, rear = xf + v * t, xf + v * t - ego.length
        if not beside and not (rear - 0.3 <= xp <= front + 0.3):
            continue
        if beside and not (rear - 0.3 <= xp <= front + 0.3):
            continue
        mu = h.y + h.vy * t
        sd = math.sqrt(max(pyy + 2.0 * t * pyv + t * t * pvv, 1e-9))
        p = lateral_p_inside(mu, sd, w)
        if p > best_p:
            best_p, t_best = p, t
    d = h.x - xf - so
    if d < 0.0:
        d_stop, a_req = 0.0, (INF if best_p > 0 else 0.0)
    else:
        d_stop = d
        a_req = (v * v) / (2.0 * max(d, 0.1)) if v > 0 else 0.0
    # worst case: slow object near the corridor may start toward it at the worst speed
    spd = math.hypot(h.vx, h.vy)
    lat_gap = abs(h.y) - w
    precaution, v_cap = False, INF
    if spd < 0.4 and lat_gap <= prm["near_lane_m"] and h.x > xf - 0.3 and h.cls in ("pedestrian", "unknown"):
        t_edge = max(lat_gap, 0.0) / prm["ped_worst_speed"]
        t_ego = (h.x - xf) / v if v > 0.1 else INF
        t_clear = t_edge + 2.0 * w / prm["ped_worst_speed"]
        if t_ego + prm["margin_s"] >= t_edge and t_ego - prm["margin_s"] <= t_clear + ego.length / max(v, 1.0):
            precaution = True
            t_rd = 0.4
            dd = max(h.x - xf - so, 0.0)
            ac = prm["a_comf"]
            v_cap = max(ac * (-t_rd + math.sqrt(t_rd * t_rd + 2.0 * dd / ac)), prm.get("creep_speed", 0.0))   # creep floor: never freeze in front of a waiting pedestrian
    return Risk(float(best_p), float(d_stop), float(a_req), precaution, float(v_cap), float(t_best))
