"""Truth-free frame builder for comm tests (imports only backend.observation, so it works where truth-side modules are blocked)."""
from __future__ import annotations
import math
from backend.observation import Detection, SensorFrame, SCHEMA_VERSION


def mk_frame(seq, t, dets, sensor="s", t_avail=None, pose=(0.0, 0.0, 0.0, 1.5)):
    ds = tuple(Detection(i, x, y, (v, 0.0, v), "pedestrian", 1.0, 0.9) for i, (x, y, v) in enumerate(dets))
    return SensorFrame(SCHEMA_VERSION, sensor, seq, t, t if t_avail is None else t_avail, pose, math.radians(120), 60.0, ds)
