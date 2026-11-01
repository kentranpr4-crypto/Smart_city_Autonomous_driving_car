from __future__ import annotations
import copy
from backend.scenario import scenario_from_dict
from backend.telemetry import TelemetryWriter
from backend.world import World

BASE = {"schema_version": "0.1.0", "id": "t", "dt": 0.01, "duration": 10.0,
        "road": {"mu": 0.8},
        "vehicles": [{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": 8.0}}]}


def make(**over):
    d = copy.deepcopy(BASE)
    for k, v in over.items():
        d[k] = v
    return d


def run(d, seed=1, on_step=None):
    scn = scenario_from_dict(d)
    tw = TelemetryWriter(keep=True)
    w = World(scn, seed, tw)
    w.run(on_step)
    frames = [r for r in tw.lines if r["type"] == "frame"]
    return w, frames, tw


def vframe(frame, vid="ego"):
    return next(v for v in frame["vehicles"] if v["id"] == vid)
