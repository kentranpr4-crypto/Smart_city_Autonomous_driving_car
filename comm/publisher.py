"""Builds TrackMsg from a single-source Tracker. Observation time is the time of the newest accepted FRAME, never 'now': republishing an old
state does not manufacture a newer observation.  Only confirmed tracks are published, and only under the 3-of-4 policy unless explicitly experimental."""
from __future__ import annotations
import math
from .clock import NodeClock
from .trackmsg import (SCHEMA_VERSION, FRAME, UNITS, YAW_CONVENTION, Origin, Tx, TrackEntry, TrackMsg, serialize)
from perception.presets import confirmation_label

PI2 = math.pi ** 2


class PublishPolicyError(RuntimeError):
    pass


class Publisher:
    def __init__(self, source_id: str, source_type: str, clock: NodeClock, origin_id: str, rate_hz: float = 10.0, ttl_s: float = 1.0,
                 sensor_model: str = "stat-sim-2.5d", algo_version: str = "cvkf-0.1.0", calib_id: str = "none", clock_sync: str = "synced",
                 experimental: bool = False):
        self.source_id, self.source_type, self.clock, self.origin_id = source_id, source_type, clock, origin_id
        self.period = 1.0 / rate_hz
        self.ttl_s, self.sensor_model, self.algo_version, self.calib_id, self.clock_sync = ttl_s, sensor_model, algo_version, calib_id, clock_sync
        self.experimental = experimental
        self.seq = 0
        self._tick = 0
        self._last_obs = -math.inf
        self.suppressed_no_new_obs = 0

    def due(self, t_sim: float) -> bool:
        return t_sim >= self._tick * self.period - 1e-9

    def maybe_publish(self, t_sim: float, tracker):
        """Returns (TrackMsg, bytes, obs_sim) or None. obs_sim is a simulation-time ANNOTATION for evaluation; it is not part of the message."""
        if not self.due(t_sim):
            return None
        self._tick = int(t_sim / self.period + 1e-9) + 1
        label = confirmation_label(tracker.cfg)
        if label != "3of4" and not self.experimental:
            raise PublishPolicyError(f"tracker confirmation {label}: publishing to V2X requires 3-of-4 (2-of-3 is an experimental baseline; pass experimental=True)")
        obs = tracker.last_frame_time
        if not math.isfinite(obs) or not obs > self._last_obs:
            self.suppressed_no_new_obs += 1
            return None                                          # no new observation since the last message
        self._last_obs = obs
        tracks = []
        for t in tracker.tracks(obs, confirmed_only=True):
            P = t.P
            vx, vy = t.x[2], t.x[3]
            sp = math.hypot(vx, vy)
            if sp >= 0.3:
                yaw = math.atan2(vy, vx)
                var_yaw = max((vx * vx * P[15] + vy * vy * P[10] - 2 * vx * vy * P[11]) / sp ** 4, 1e-6)
            else:
                yaw, var_yaw = 0.0, PI2                         # direction unknown: maximal uncertainty
            tracks.append(TrackEntry(t.track_id, t.cls, t.cls_share, t.x[0], t.x[1], yaw, vx, vy, tuple(P), var_yaw, t.existence,
                                     self.clock.local(t.t - t.time_since_update_s)))
        seq = self.seq; self.seq += 1
        prov = {"sensor_model": self.sensor_model, "algo_version": self.algo_version, "calib_id": self.calib_id, "privacy_level": "object_only", "confirmation": label}
        msg = TrackMsg(SCHEMA_VERSION, f"{self.source_id}:{seq}", Tx(self.source_id, seq, self.clock.clock_id),
                       Origin(self.source_id, self.source_type, seq, f"{self.source_id}:{seq}", self.clock.clock_id, self.clock_sync, prov),
                       self.clock.local(obs), self.clock.local(t_sim), FRAME, self.origin_id, dict(UNITS), YAW_CONVENTION, self.ttl_s, 0, (), tuple(tracks))
        return msg, serialize(msg), obs
