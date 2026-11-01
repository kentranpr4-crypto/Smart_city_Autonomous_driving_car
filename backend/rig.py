"""Perception rig (truth side): World truth -> SensorProvider -> (t_avail queue) -> per-sensor Tracker.
The Tracker receives SensorFrame objects ONLY. FrameLabels (truth ids) are kept on the rig for METRICS and never passed to a tracker (I9)."""
from __future__ import annotations
import heapq, json, hashlib
from .observation import frame_to_dict
from .scenario import Scenario
from .sensors import SensorProvider
from .world import World
from .telemetry import TelemetryWriter, canonical_line
from perception.tracker import Tracker, TrackerConfig


class PerceptionRig:
    def __init__(self, scn: Scenario, seed: int, trackers: dict | None = None, cfg: TrackerConfig | None = None):
        self.provider = SensorProvider(scn.sensors, seed, scn.dt)
        self.trackers = trackers if trackers is not None else {s.id: Tracker(s.id, cfg) for s in scn.sensors}
        self._q, self._n = [], 0
        self.labels = {s.id: {} for s in scn.sensors}      # sensor -> seq -> FrameLabels (metrics only)
        self.log = []                                       # one entry per released frame
        self._h = hashlib.sha256()

    def __call__(self, world: World):
        snap = world.truth_snapshot()
        step = world.n
        for frame, lab in self.provider.sample(snap, step):
            self.labels[frame.sensor_id][frame.seq] = lab
            heapq.heappush(self._q, (frame.t_avail, self._n, frame)); self._n += 1
        while self._q and self._q[0][0] <= world.t + 1e-12:
            _, _, frame = heapq.heappop(self._q)
            tr = self.trackers[frame.sensor_id]
            rep = tr.update(frame, t_now=world.t)             # frame ONLY (no labels, no truth)
            tracks = tr.tracks(world.t)
            entry = {"t": world.t, "frame": frame_to_dict(frame),
                     "report": {"accepted": rep.accepted, "reason": rep.reason, "n_matched": rep.n_matched, "n_new": rep.n_new, "n_deleted": rep.n_deleted, "seq_gap": rep.seq_gap},
                     "tracks": [{"id": t.track_id, "x": list(t.x), "P": list(t.P), "existence": t.existence, "cls": t.cls, "since": t.time_since_update_s} for t in tracks]}
            self.log.append(entry); self._h.update(canonical_line(entry))

    def hexdigest(self) -> str:
        return self._h.hexdigest()


def run_with_rig(scn: Scenario, seed: int, trackers=None, cfg=None):
    w = World(scn, seed, TelemetryWriter(keep=False))
    rig = PerceptionRig(scn, seed, trackers, cfg)
    rig(w)                                                    # step 0
    w.run(on_step=rig)
    return w, rig
