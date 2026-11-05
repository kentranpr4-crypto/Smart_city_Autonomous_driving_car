"""Local longitudinal motion planner (stop-only: no steering avoidance - documented limitation).
Pure function of (ego state, hypotheses with trust levels, parameters). No truth, no wall clock, no randomness."""
from __future__ import annotations
import math
from .risk import assess
from .types import ADVISORY, CORROBORATED, LOCAL, Hypothesis

INF = float("inf")


def seg_hits_rect(p0, p1, rect) -> bool:
    """2-D segment vs axis-aligned rectangle (cx, cy, length_x, width_y) - Liang-Barsky."""
    cx, cy, lx, wy = rect
    xmin, xmax, ymin, ymax = cx - lx / 2, cx + lx / 2, cy - wy / 2, cy + wy / 2
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, p0[0] - xmin), (dx, xmax - p0[0]), (-dy, p0[1] - ymin), (dy, ymax - p0[1])):
        if p == 0:
            if q < 0: return False
        else:
            r = q / p
            if p < 0:
                if r > t1: return False
                t0 = max(t0, r)
            else:
                if r < t0: return False
                t1 = min(t1, r)
    return True


def occluded(sensor_xy, point_xy, occluders) -> bool:
    return any(seg_hits_rect(sensor_xy, point_xy, r) for r in occluders)


class Planner:
    def __init__(self, prm: dict, v_ref: float, conservative: bool = False):
        self.prm, self.v_ref, self.conservative = prm, v_ref, conservative

    def phantoms(self, ego) -> list:
        """E0-C: a pedestrian MAY be waiting at each map crosswalk spot whenever the ego sensor cannot see that spot. Precaution only (stationary, never a hazard trigger)."""
        if not self.conservative:
            return []
        out = []
        sx = ego.x + self.prm["sensor_offset_x"]
        for k, (px, py) in enumerate(self.prm.get("crosswalk_spots", ())):
            if px > ego.x + ego.front_offset - 0.3 and occluded((sx, 0.0), (px, py), self.prm.get("occluders", ())):
                P = tuple(0.01 if i % 5 == 0 else 0.0 for i in range(16))
                out.append(Hypothesis(-1 - k, px, py, 0.0, 0.0, P, "pedestrian", LOCAL, ("map",), phantom=True))
        return out

    def candidate(self, ego, items) -> tuple:
        """items: list of (Hypothesis, cap_decel, hazard_allowed, v_cap_override). Returns (a_des, info)."""
        prm = self.prm
        a = max(-prm["a_comf"], min(prm["a_accel"], self.v_ref - ego.v))
        info = {"p_max": 0.0, "binding": None, "n_items": len(items)}
        for h, cap, hazard_ok, vcap_ovr in items:
            r = assess(h, ego, prm)
            info["p_max"] = max(info["p_max"], r.p_conflict)
            if hazard_ok and r.p_conflict >= prm["p_thr"] and r.a_req >= 0.3 and not h.phantom:
                ah = -min(max(r.a_req * 1.15, 0.5), cap)
                if ah < a: a, info["binding"] = ah, ("hazard", h.hid, h.level)
            if r.precaution:
                vc = min(r.v_cap, vcap_ovr) if vcap_ovr is not None else r.v_cap
                ap = max(-min(cap, prm["a_comf"]), min(0.0, vc - ego.v))
                if ap < a: a, info["binding"] = ap, ("precaution", h.hid, h.level)
        return a, info
