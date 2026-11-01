from __future__ import annotations
import math
from backend.sensor_spec import SensorSpec
from backend.sensors import SensorProvider
from backend.truth import TruthActor, TruthObstacle, TruthSnapshot

DT = 0.01


def ped(id="p", x=0.0, y=0.0, vx=0.0, vy=0.0, h=1.7):
    return TruthActor(id, "pedestrian", x, y, vx, vy, 0.0, 0.6, 0.6, h)


def veh(id="v", x=0.0, y=0.0, psi=0.0, h=1.5, vx=0.0, vy=0.0, length=4.5, width=1.8):
    return TruthActor(id, "vehicle", x, y, vx, vy, psi, length, width, h)


def wall(id="w", cx=0.0, cy=0.0, yaw=0.0, length=0.01, width=10.0, h=3.0):
    return TruthObstacle(id, cx, cy, yaw, length, width, h)


def snap(actors=(), obstacles=(), t=0.0):
    return TruthSnapshot(t, tuple(actors), tuple(obstacles))


def cctv(id="k", pose=(0.0, 0.0, 0.0), height=6.0, fov_deg=120.0, range_m=60.0, rate_hz=10.0, **kw):
    return SensorSpec(id=id, kind="cctv", height=height, fov=math.radians(fov_deg), range_m=range_m, rate_hz=rate_hz, pose=pose, **kw)


PERFECT = dict(pd0=1.0, r50=1e4, pd_slope=1.0)     # p_d == 1 over any realistic range


def frames_at(provider, snapshots_by_step):
    out = []
    for step, s in snapshots_by_step:
        out += provider.sample(s, step)
    return out


def stream(spec, snapshot, n_frames, seed=1):
    """n_frames consecutive frames of a static snapshot: returns [(frame, labels)]."""
    pv = SensorProvider([spec], seed, DT)
    per = pv.period[spec.id]
    out = []
    for k in range(n_frames):
        out += pv.sample(snapshot, k * per + pv.phase[spec.id])
    return out
