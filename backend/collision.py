"""Geometric collision tests (2D). Touching counts as contact. OBB = (cx, cy, psi, half_length, half_width)."""
from __future__ import annotations
import math

OBB = tuple  # (cx, cy, psi, hl, hw)


def obb_corners(o: OBB):
    cx, cy, psi, hl, hw = o
    c, s = math.cos(psi), math.sin(psi)
    return [(cx + sx * hl * c - sy * hw * s, cy + sx * hl * s + sy * hw * c) for sx, sy in ((1, 1), (1, -1), (-1, -1), (-1, 1))]


def _axes(o: OBB):
    psi = o[2]
    return [(math.cos(psi), math.sin(psi)), (-math.sin(psi), math.cos(psi))]


def _project(pts, ax):
    d = [px * ax[0] + py * ax[1] for px, py in pts]
    return min(d), max(d)


def sat_obb_obb(a: OBB, b: OBB) -> bool:
    ca, cb = obb_corners(a), obb_corners(b)
    for ax in _axes(a) + _axes(b):
        a0, a1 = _project(ca, ax)
        b0, b1 = _project(cb, ax)
        if a1 < b0 or b1 < a0:
            return False
    return True


def to_local(o: OBB, px: float, py: float):
    cx, cy, psi, _, _ = o
    c, s = math.cos(psi), math.sin(psi)
    dx, dy = px - cx, py - cy
    return dx * c + dy * s, -dx * s + dy * c


def dist_point_obb(o: OBB, px: float, py: float) -> float:
    lx, ly = to_local(o, px, py)
    return math.hypot(max(abs(lx) - o[3], 0.0), max(abs(ly) - o[4], 0.0))


def closest_point_obb(o: OBB, px: float, py: float):
    lx, ly = to_local(o, px, py)
    qx, qy = min(max(lx, -o[3]), o[3]), min(max(ly, -o[4]), o[4])
    c, s = math.cos(o[2]), math.sin(o[2])
    return o[0] + qx * c - qy * s, o[1] + qx * s + qy * c


def _seg_hits_aabb(p0, p1, hl, hw) -> bool:
    """Liang-Barsky: does segment p0->p1 intersect [-hl,hl]x[-hw,hw]?"""
    t0, t1 = 0.0, 1.0
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    for p, q in ((-dx, p0[0] + hl), (dx, hl - p0[0]), (-dy, p0[1] + hw), (dy, hw - p0[1])):
        if p == 0.0:
            if q < 0.0:
                return False
        else:
            r = q / p
            if p < 0.0:
                if r > t1: return False
                t0 = max(t0, r)
            else:
                if r < t0: return False
                t1 = min(t1, r)
    return True


def _dist_pt_seg(px, py, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0.0 else min(max(((px - a[0]) * dx + (py - a[1]) * dy) / L2, 0.0), 1.0)
    return math.hypot(px - (a[0] + t * dx), py - (a[1] + t * dy))


def dist_segment_obb(o: OBB, p0, p1) -> float:
    l0, l1 = to_local(o, *p0), to_local(o, *p1)
    if _seg_hits_aabb(l0, l1, o[3], o[4]):
        return 0.0
    hl, hw = o[3], o[4]
    cands = [dist_point_obb(o, *p0), dist_point_obb(o, *p1)]
    cands += [_dist_pt_seg(cx, cy, l0, l1) for cx, cy in ((hl, hw), (hl, -hw), (-hl, -hw), (-hl, hw))]
    return min(cands)


def capsule_hits_obb(o: OBB, p0, p1, radius: float) -> bool:
    """Swept pedestrian (segment p0->p1 inflated by radius) vs OBB."""
    return dist_segment_obb(o, p0, p1) <= radius
