from __future__ import annotations
import math
import numpy as np
from backend.observation import Detection, SensorFrame, SCHEMA_VERSION
from backend.sensors import SensorProvider
from perception.tracker import Tracker, TrackerConfig
from tests.perception.helpers import DT, snap


def mk_frame(seq, t, dets, sensor="s", t_avail=None, pose=(0.0, 0.0, 0.0, 1.5)):
    """dets: list of (x, y, var) -> SensorFrame with isotropic declared covariance."""
    ds = tuple(Detection(i, x, y, (v, 0.0, v), "pedestrian", 1.0, 0.9) for i, (x, y, v) in enumerate(dets))
    return SensorFrame(SCHEMA_VERSION, sensor, seq, t, t if t_avail is None else t_avail, pose, math.radians(120), 60.0, ds)


def simulate_scene(spec, actors_at, n_frames, seed, cfg=None, tracker=None):
    """Drive SensorProvider + Tracker over scripted truth. actors_at(t) -> list[TruthActor]; obstacles via actors_at returning (actors, obstacles).
    Returns per-frame records for METRICS (labels/truth are test-side only; the tracker only ever sees frames)."""
    pv = SensorProvider([spec], seed, DT)
    tr = tracker or Tracker(spec.id, cfg)
    per = pv.period[spec.id]; rec = []
    for k in range(n_frames):
        step = pv.phase[spec.id] + k * per
        t = step * DT
        sc = actors_at(t)
        actors, obst = sc if isinstance(sc, tuple) else (sc, [])
        s = snap(actors, obst, t=t)
        for f, lab in pv.sample(s, step):
            rep = tr.update(f, t_now=f.t_avail)
            rec.append({"t": f.t_avail, "frame": f, "labels": lab, "report": rep, "tracks": tr.tracks(f.t_avail), "truth": {a.id: (a.x, a.y) for a in actors}})
    return tr, rec


def associate(tracks, truth, gate=2.0):
    """Evaluation-side association (uses truth; never given to the tracker): optimal 1-1 by distance."""
    from perception.hungarian import linear_sum_assignment
    if not tracks or not truth: return {}
    ids = sorted(truth)
    cost = [[math.hypot(t.x[0] - truth[i][0], t.x[1] - truth[i][1]) for i in ids] for t in tracks]
    return {ids[j]: tracks[i].track_id for i, j in linear_sum_assignment(cost) if cost[i][j] <= gate}


def id_switches(rec):
    last, sw = {}, 0
    for r in rec:
        for tid, trk in associate(r["tracks"], r["truth"]).items():
            if tid in last and last[tid] != trk: sw += 1
            last[tid] = trk
    return sw
