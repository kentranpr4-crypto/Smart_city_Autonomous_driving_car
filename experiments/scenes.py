"""Scene builders (TRUTH SIDE: evaluator and simulator only; nothing here is importable by fusion/comm/perception)."""
from __future__ import annotations
import math
from dataclasses import dataclass
from backend.sensor_spec import SensorSpec
from backend.truth import TruthActor, TruthObstacle, TruthSnapshot

EGO_ID, REMOTE_ID = "ego_cam", "cctv_k1"
DURATION = 11.0


@dataclass
class Scene:
    targets: tuple                 # truth ids of the targets that are evaluated
    sensors: list
    snapshot: callable            # t -> TruthSnapshot
    duration: float = DURATION


def _ped(i, x, y, vx, vy):
    return TruthActor(i, "pedestrian", x, y, vx, vy, 0.0, 0.6, 0.6, 1.7)


def build_scene(cond: dict, remote_bias=(0.0, 0.0)) -> Scene:
    kind = cond["scene"]
    if kind == "occ":
        ego = SensorSpec(id=EGO_ID, kind="vehicle", height=1.5, fov=math.radians(100), range_m=80, rate_hz=10, mount_vehicle="ego", mount_offset=(0.5, 0.0),
                         pd0=0.95, r50=60, pd_slope=8, sigma0=0.05, sigma1=0.01, t_proc=0.05)
        rem = SensorSpec(id=REMOTE_ID, kind="cctv", height=6.0, fov=math.radians(120), range_m=40, rate_hz=10, pose=(45.0, 8.0, -math.pi / 2), pd0=0.95, r50=40, pd_slope=6,
                         sigma0=0.05, sigma1=0.01, phase=0.03, t_proc=0.05, bias=remote_bias)
        truck = TruthObstacle("truck", 38.5, -3.3, 0.0, 9.0, 2.4, 3.0)

        def snap(t):
            return TruthSnapshot(t, (TruthActor("ego", "vehicle", 5.0 * t, 3.0, 5.0, 0.0, 0.0, 4.5, 1.8, 1.5), _ped("ped1", 45.0, -4.4 + 0.4 * t, 0.0, 0.4)), (truck,))
        return Scene(("ped1",), [ego, rem], snap)
    ego = SensorSpec(id=EGO_ID, kind="vehicle", height=1.5, fov=math.radians(100), range_m=70, rate_hz=10, mount_vehicle="ego", mount_offset=(0.5, 0.0),
                     pd0=0.95, r50=60, pd_slope=8, sigma0=0.05, sigma1=0.01, t_proc=0.05)
    rem = SensorSpec(id=REMOTE_ID, kind="cctv", height=6.0, fov=math.radians(120), range_m=70, rate_hz=10, pose=(10.0, -25.0, math.pi / 2), pd0=0.95, r50=60, pd_slope=8,
                     sigma0=0.05, sigma1=0.01, phase=0.03, t_proc=0.05, bias=remote_bias)
    egoa = TruthActor("ego", "vehicle", 10.0, 25.0, 0.0, 0.0, -math.pi / 2, 4.5, 1.8, 1.5)
    if kind == "solo":
        f = lambda t: [_ped("p1", 1.4 * t, 0.0, 1.4, 0.0)]; tg = ("p1",)
    elif kind == "close":
        d = cond["d"]; f = lambda t: [_ped("p1", 1.4 * t, 0.0, 1.4, 0.0), _ped("p2", 1.4 * t, d, 1.4, 0.0)]; tg = ("p1", "p2")
    elif kind == "cross":
        x0 = 14.0 + cond["miss"] * math.sqrt(2.0)
        f = lambda t: [_ped("p1", 1.4 * t, 0.0, 1.4, 0.0), _ped("p2", x0, -14.0 + 1.4 * t, 0.0, 1.4)]; tg = ("p1", "p2")
    else:
        raise ValueError(kind)
    return Scene(tg, [ego, rem], lambda t: TruthSnapshot(t, (egoa, *f(t)), ()))
