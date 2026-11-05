import numpy as np
from comm.store import StoredTrack
from comm.trackmsg import TrackEntry
from perception.tracker import Track
from planning.stack import SafetyStack, DEFAULTS
from planning.types import EgoState, Rear, Hypothesis, LOCAL
from closedloop import conditions as K
from experiments.conditions import FUSION_PARAMS

OCC = ((38.5, -3.3, 9.0, 2.4),)
PRM = {**DEFAULTS, **K.STACK, "crosswalk_spots": ((45.0, -3.3),), "occluders": OCC}


def cov4(sp=0.04, sv=0.09):
    return tuple(np.diag([sp, sp, sv, sv]).reshape(-1))


def local_track(tid, x, y, vx=0.0, vy=0.0, t=1.0, cls="pedestrian", sp=0.04, sv=0.09):
    return Track(tid, t, (x, y, vx, vy), cov4(sp, sv), True, 3.0, 0.95, cls, 5, 0, 1.0, 0.0)


def stored(src, tid, x, y, vx=0.0, vy=0.0, t_meas=0.95, seq=1, hops=0, cls="pedestrian", sp=0.04, sv=0.09):
    cv = tuple(cov4(sp, sv))
    e = TrackEntry(tid, cls, 0.9, x, y, 0.0, vx, vy, cv, 0.1, 0.9, t_meas)
    return StoredTrack((src, tid), e, t_meas, 0.05, 0.9, hops, (), seq, ())


def stack(planner="guarded", v_ref=8.0, **over):
    return SafetyStack(planner, {**PRM, **over}, FUSION_PARAMS, v_ref)


def ego(x=30.0, v=8.0, t=1.0):
    return EgoState(t, x, v)


def hyp(x, y, vx=0.0, vy=0.0, level=LOCAL, cls="pedestrian", hid=1, age=0.0, sp=0.04, sv=0.09, sources=("ego_cam",), flags=()):
    return Hypothesis(hid, x, y, vx, vy, cov4(sp, sv), cls, level, sources, age, flags)
