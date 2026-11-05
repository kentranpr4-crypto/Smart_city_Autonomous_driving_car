"""SafetyStack: Local perception + cooperative tracks -> fusion -> trust -> risk -> supervisor -> planner -> command.
Inputs are plain objects (tracks, estimates, ego state, rear measurement). No truth, no backend, no clock."""
from __future__ import annotations
from fusion.adapters import from_local_track, from_stored
from fusion.fuser import CooperativeFuser
from .supervisor import Supervisor
from .trust import TrustAdmission
from .types import EGO_SOURCE, EgoState, Rear

DEFAULTS = dict(sensor_offset_x=1.85, crosswalk_spots=(), occluders=(), self_radius_m=3.0)


class SafetyStack:
    """policy: planner in {'nominal','conservative','guarded','naive'}.  nominal/conservative never read remote data."""
    def __init__(self, planner: str, prm: dict, fusion_prm: dict, v_ref: float):
        self.planner = planner
        self.prm = {**DEFAULTS, **prm}
        naive = planner == "naive"
        method = "B3_info" if naive else ("B4_ci" if planner == "guarded" else "B0_local")
        self.fuser = CooperativeFuser(method, {**fusion_prm, "self_radius_m": self.prm["self_radius_m"]})
        self.trust = TrustAdmission(self.prm, naive=naive)
        self.sup = Supervisor(self.prm, v_ref, conservative=(planner == "conservative"), naive=naive)
        self._pose_hist: list = []                        # (t, x_center, y_center, sigma): the ego's OWN localisation history (not truth)

    def decide(self, ego: EgoState, local_tracks, remote_stored, rear: Rear | None, ego_pose=None):
        if ego_pose is not None:
            self._pose_hist.append((ego.t, ego_pose[0], ego_pose[1], ego_pose[2]))
            self._pose_hist = [q for q in self._pose_hist if q[0] >= ego.t - 2.0]
        hist = list(self._pose_hist)
        def pose_at(t):
            if len(hist) == 0: return ego_pose
            if t <= hist[0][0]: return hist[0][1:]
            for a, b in zip(hist, hist[1:]):
                if a[0] <= t <= b[0]:
                    u = (t - a[0]) / max(b[0] - a[0], 1e-9)
                    return (a[1] + u * (b[1] - a[1]), a[2] + u * (b[2] - a[2]), max(a[3], b[3]))
            return hist[-1][1:]                           # t newer than the last pose: hold (the remote observation cannot be newer than now)
        ests = [from_local_track(EGO_SOURCE, t) for t in local_tracks]
        if self.planner in ("guarded", "naive"):
            ests += [from_stored(s) for s in remote_stored]
        world = self.fuser.step(ego.t, ests, ego_pose=(pose_at if ego_pose is not None else None))
        hyps = self.trust.classify(world.tracks)
        d = self.sup.decide(ego, hyps, rear)
        return d, hyps
