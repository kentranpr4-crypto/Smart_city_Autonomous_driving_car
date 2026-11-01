import numpy as np
from fusion.types import Estimate

def P4(sp=0.2, sv=0.5):
    return tuple(np.diag([sp * sp, sp * sp, sv * sv, sv * sv]).reshape(-1))

def est(src="k", tid=1, t=1.0, x=(10.0, 0.0, 1.0, 0.0), P=None, cls="pedestrian", kind="remote", seq=0, hops=0, path=(), prob=0.9, frame="map"):
    ev = ((src, seq, tid),) if kind == "remote" else ((f"local:{src}", tid),)
    return Estimate(src, tid, t, tuple(x), P or P4(), cls, prob, kind, ev, hops, tuple(path), frame)

def loc(tid=1, t=1.0, x=(10.0, 0.0, 1.0, 0.0), P=None, cls="pedestrian"):
    return est("ego", tid, t, x, P, cls, "local")
