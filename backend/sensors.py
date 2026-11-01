"""TRUTH-SIDE sensor models: ground truth -> SensorFrame (+ FrameLabels for metrics only).

2.5D visibility: sensors have a height h_s, obstacles are prisms (OBB footprint x height h_o). A ray (sensor -> target sample point)
is blocked iff it passes through a prism, i.e. its height at the prism's entry/exit is below h_o.  Ground shadow of a prism seen from
height h_s > h_o is the convex hull of its footprint corners and its top corners projected from the sensor (scale h_s/(h_s-h_o)).
Random-number consumption per frame is independent of visibility, so adding an occluder never shifts other targets' noise (paired seeds).
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from .collision import obb_corners
from .observation import Detection, SensorFrame, SCHEMA_VERSION
from .rng import rng_stream
from .sensor_spec import SensorSpec
from .truth import TruthSnapshot

SAMPLES = 3            # target sample heights: foot, middle, head


# ------------------------------------------------------------------ geometry
def ray_blocked(s, t, prism) -> bool:
    """s,t = (x, y, z); prism = (cx, cy, yaw, half_len, half_wid, height). Blocked iff min(z at entry, z at exit) < height."""
    cx, cy, yaw, hl, hw, ho = prism
    c, sn = math.cos(yaw), math.sin(yaw)
    p0 = ((s[0] - cx) * c + (s[1] - cy) * sn, -(s[0] - cx) * sn + (s[1] - cy) * c)
    p1 = ((t[0] - cx) * c + (t[1] - cy) * sn, -(t[0] - cx) * sn + (t[1] - cy) * c)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    t0, t1 = 0.0, 1.0
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
    z0 = s[2] + (t[2] - s[2]) * t0
    z1 = s[2] + (t[2] - s[2]) * t1
    return min(z0, z1) < ho


def target_visible(s, tx, ty, th, prisms) -> bool:
    """Visible iff at least one of SAMPLES points (foot, middle, head) is unblocked by every prism (binary, no partial-occlusion scaling)."""
    for k in range(SAMPLES):
        z = th * k / (SAMPLES - 1)
        if not any(ray_blocked(s, (tx, ty, z), pr) for pr in prisms):
            return True
    return False


def convex_hull(pts):
    pts = sorted(set(pts))
    if len(pts) <= 2:
        return pts
    def cross(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def ground_shadow_polygon(sx, sy, hs, prism):
    """Convex ground region hidden from a sensor at (sx, sy, hs) by the prism; None if hs <= prism height (shadow unbounded)."""
    cx, cy, yaw, hl, hw, ho = prism
    if hs <= ho:
        return None
    base = obb_corners((cx, cy, yaw, hl, hw))
    k = hs / (hs - ho)
    return convex_hull(base + [(sx + (x - sx) * k, sy + (y - sy) * k) for x, y in base])


def signed_distance_to_convex(poly, p) -> float:
    """Negative inside, positive outside (distance to boundary), for a CCW convex polygon."""
    n = len(poly)
    inside = all((poly[(i + 1) % n][0] - poly[i][0]) * (p[1] - poly[i][1]) - (poly[(i + 1) % n][1] - poly[i][1]) * (p[0] - poly[i][0]) >= 0 for i in range(n))
    d = math.inf
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ex, ey = b[0] - a[0], b[1] - a[1]
        L2 = ex * ex + ey * ey
        t = 0.0 if L2 == 0 else min(max(((p[0] - a[0]) * ex + (p[1] - a[1]) * ey) / L2, 0.0), 1.0)
        d = min(d, math.hypot(p[0] - (a[0] + t * ex), p[1] - (a[1] + t * ey)))
    return -d if inside else d


def wrap(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


# ------------------------------------------------------------------ labels (metrics only; never given to perception)
@dataclass(frozen=True)
class FrameLabels:
    truth_of: dict            # det_id -> truth actor id, or None for clutter
    candidates: tuple         # targets inside FOV/range (before occlusion)
    visible: tuple            # candidates not occluded
    detected: tuple           # visible targets that were actually detected
    pd: dict                  # target id -> p_d(r) used


class SensorProvider:
    def __init__(self, specs, seed: int, dt: float):
        self.dt, self.seed = dt, seed
        self.specs = {s.id: s for s in specs}
        self.rng = {s.id: rng_stream(seed, f"sensor:{s.id}") for s in specs}
        self.seq = {s.id: 0 for s in specs}
        self.outage = {s.id: False for s in specs}
        self.period, self.phase = {}, {}
        for s in specs:
            per = round(1.0 / (s.rate_hz * dt))
            if per < 1 or abs(per * dt * s.rate_hz - 1.0) > 1e-9:
                raise ValueError(f"sensor {s.id}: 1/(rate*dt) must be an integer number of steps")
            for what, val in (("phase", s.phase), ("t_proc", s.t_proc)):
                if abs(round(val / dt) * dt - val) > 1e-9:
                    raise ValueError(f"sensor {s.id}: {what}={val} is not a multiple of dt={dt}")
            self.period[s.id], self.phase[s.id] = per, round(s.phase / dt)

    def due(self, step: int):
        return [s for s in self.specs.values() if step >= self.phase[s.id] and (step - self.phase[s.id]) % self.period[s.id] == 0]

    def sensor_pose(self, spec: SensorSpec, snap: TruthSnapshot):
        if spec.kind == "cctv":
            x, y, yaw = spec.pose
            return x, y, yaw
        veh = next((a for a in snap.actors if a.id == spec.mount_vehicle), None)
        if veh is None:
            raise KeyError(f"sensor {spec.id}: mount vehicle {spec.mount_vehicle!r} not in snapshot")
        # truth vehicle x,y is the OBB centre; rear-axle based offsets are handled by the caller via mount_offset relative to the centre
        c, s = math.cos(veh.psi), math.sin(veh.psi)
        dx, dy = spec.mount_offset
        return veh.x + c * dx - s * dy, veh.y + s * dx + c * dy, veh.psi + spec.yaw_offset

    def sample(self, snap: TruthSnapshot, step: int):
        out = []
        for spec in self.due(step):
            out.append(self._sample_one(spec, snap, step))
        return [o for o in out if o is not None]

    def _sample_one(self, spec: SensorSpec, snap: TruthSnapshot, step: int):
        rng = self.rng[spec.id]
        seq = self.seq[spec.id]; self.seq[spec.id] += 1
        # frame-level outage chain (one draw per scheduled frame, always)
        u_drop = rng.random()
        if spec.dropout is not None:
            p_enter, p_exit = spec.dropout
            self.outage[spec.id] = (u_drop < p_enter) if not self.outage[spec.id] else not (u_drop < p_exit)
        sx, sy, yaw = self.sensor_pose(spec, snap)
        hs = spec.height
        own = spec.mount_vehicle
        targets = sorted((a for a in snap.actors if a.id != own), key=lambda a: a.id)
        obst = [(o.cx, o.cy, o.yaw, o.length / 2, o.width / 2, o.height) for o in snap.obstacles]
        veh_prisms = {a.id: (a.x, a.y, a.psi, a.length / 2, a.width / 2, a.height) for a in snap.actors if a.kind == "vehicle" and a.id != own}
        raw = []                                   # (truth_id|None, x, y, sigma_true, cls, cls_prob, shuffle_key)
        cand, vis_l, det_l, pds = [], [], [], {}
        for a in targets:
            u_det = rng.random(); nx, ny = rng.normal(size=2); u_cls = rng.random(); u_key = rng.random()   # fixed consumption per target (u_key: shuffle key)
            r = math.hypot(a.x - sx, a.y - sy)
            in_fov = r <= spec.range_m + 1e-12 and abs(wrap(math.atan2(a.y - sy, a.x - sx) - yaw)) <= spec.fov / 2 + 1e-12
            if not in_fov:
                continue
            cand.append(a.id)
            prisms = obst + [p for k, p in veh_prisms.items() if k != a.id]
            visible = target_visible((sx, sy, hs), a.x, a.y, a.height, prisms)
            pd = spec.pd(r); pds[a.id] = pd
            if visible:
                vis_l.append(a.id)
            if visible and u_det < pd:
                det_l.append(a.id)
                sg = spec.sigma(r)
                cls = ("pedestrian" if a.kind == "pedestrian" else "vehicle") if u_cls < spec.class_accuracy else "unknown"
                raw.append((a.id, a.x + spec.bias[0] + sg * nx, a.y + spec.bias[1] + sg * ny, sg, cls, spec.class_accuracy, u_key))
        # clutter (count draw always, positions after targets so target draws never shift)
        k = int(rng.poisson(spec.clutter_rate)) if spec.clutter_rate > 0 else 0
        for _ in range(k):
            ur, ua, uk = rng.random(), rng.random(), rng.random()
            r = spec.range_m * math.sqrt(ur)
            ang = yaw + (ua - 0.5) * spec.fov
            sg = spec.sigma(r)
            raw.append((None, sx + r * math.cos(ang), sy + r * math.sin(ang), sg, "unknown", 0.5, uk))
        # shuffle by per-detection keys drawn above (NOT rng.permutation: its consumption would depend on how many targets are visible)
        order = sorted(range(len(raw)), key=lambda i: raw[i][6])
        dets, truth_of = [], {}
        for new_id, idx in enumerate(order):
            tid, x, y, sg, cls, cp, _ = raw[idx]
            ds = (spec.declared_sigma_scale * sg) ** 2
            dets.append(Detection(new_id, x, y, (ds, 0.0, ds), cls, cp, 0.9 if tid else 0.3))
            truth_of[new_id] = tid
        if self.outage[spec.id]:
            return None                                              # frame never delivered; seq gap is observable
        t = snap.t
        frame = SensorFrame(SCHEMA_VERSION, spec.id, seq, t, t + spec.t_proc, (sx, sy, yaw, hs), spec.fov, spec.range_m, tuple(dets))
        return frame, FrameLabels(truth_of, tuple(cand), tuple(vis_l), tuple(det_l), pds)
