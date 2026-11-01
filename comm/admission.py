"""Receiver-side admission control: FAIL-CLOSED, fixed check order, one reason per rejection.
A rejected message changes NO decision state (only counters). Nothing that fails a check can reach the store/fusion.
P1: admission only decides whether positive object information may be USED as advisory input; it never creates 'free space' information."""
from __future__ import annotations
import math
from collections import Counter
from dataclasses import dataclass
import numpy as np
from .clock import NodeClock
from .trackmsg import (MsgError, SCHEMA_VERSION, FRAME, UNITS, YAW_CONVENTION, TrackMsg, deserialize, content_key, track_ref)

REASONS = (
    "oversize", "malformed_bytes", "integrity", "unsupported_version", "schema", "non_finite", "bad_covariance", "out_of_range", "duplicate_track_id",
    "invalid_timestamps", "unknown_source", "unsupported_frame", "frame_mismatch", "units_mismatch", "yaw_convention_mismatch",
    "unsupported_confirmation", "too_many_hops", "relay_loop", "implausible_kinematics", "outside_roi",
    "duplicate", "replay_old", "future_obs", "expired_ttl", "stale",
)
SOURCE_TYPES = {"vehicle", "cctv", "aggregator"}


@dataclass(frozen=True)
class SourceRegistry:
    sources: dict                       # source_id -> source_type
    relays: frozenset = frozenset()     # node ids allowed to relay


@dataclass(frozen=True)
class AdmissionConfig:
    receiver_id: str
    origin_id: str                      # the map origin this receiver uses; no transforms are supported
    max_bytes: int = 65536
    max_age_s: float = 0.5              # receiver policy: maximum observation age at use (PROVISIONAL, no external source)
    clock_tolerance_s: float = 0.05     # PARAM: allowed 'future' observation / timestamp disorder (B04 UNKNOWN)
    max_ttl_s: float = 5.0
    reorder_window: int = 8
    max_hops: int = 2
    max_abs_pos: float = 1e5
    max_speed: tuple = (("pedestrian", 4.0), ("vehicle", 20.0), ("unknown", 20.0))
    roi: tuple | None = None            # (xmin, ymin, xmax, ymax) in the map frame
    max_track_info_age_s: float = 3.0
    accepted_confirmations: tuple = ("3of4",)
    cov_tol: float = 1e-9


@dataclass(frozen=True)
class AdmissionResult:
    admitted: bool
    reason: str                         # 'ok' or one of REASONS
    msg: TrackMsg | None
    t_recv: float
    t_proc: float
    age_recv_est: float | None          # receiver-visible ESTIMATE (assumes clocks agree), NOT the true age
    age_proc_est: float | None
    flags: tuple = ()


def _all_numbers(m: TrackMsg):
    yield from (m.t_meas, m.t_sent, m.ttl_s)
    for t in m.tracks:
        yield from (t.cls_prob, t.x, t.y, t.yaw, t.vx, t.vy, t.var_yaw, t.existence, t.t_upd, *t.cov)


class Admission:
    def __init__(self, cfg: AdmissionConfig, registry: SourceRegistry, clock: NodeClock | None = None):
        self.cfg, self.registry = cfg, registry
        self.clock = clock or NodeClock("rx")
        self.stats = Counter()
        self._max_seq: dict = {}
        self._seen: dict = {}

    # ------------------------------------------------------------------ pure (stateless) checks
    def _static_checks(self, m: TrackMsg, from_bytes_len: int):
        c = self.cfg
        if not all(math.isfinite(v) for v in _all_numbers(m)):
            return "non_finite"
        for t in m.tracks:
            P = np.array(t.cov, dtype=float).reshape(4, 4)
            if not (np.allclose(P, P.T, atol=1e-9 + 1e-9 * np.abs(P).max()) and np.all(np.diag(P) > 0)
                    and np.linalg.eigvalsh(0.5 * (P + P.T)).min() > -c.cov_tol) or not t.var_yaw > 0:
                return "bad_covariance"
        if any(not (0.0 <= t.existence <= 1.0 and 0.0 <= t.cls_prob <= 1.0 and abs(t.x) <= c.max_abs_pos and abs(t.y) <= c.max_abs_pos) for t in m.tracks) \
                or not (0.0 < m.ttl_s <= c.max_ttl_s) or m.t_meas < 0 or m.t_sent < 0:
            return "out_of_range"
        ids = [t.track_id for t in m.tracks]
        if len(ids) != len(set(ids)):
            return "duplicate_track_id"
        if m.t_meas > m.t_sent + c.clock_tolerance_s or any(t.t_upd > m.t_meas + c.clock_tolerance_s or m.t_meas - t.t_upd > c.max_track_info_age_s for t in m.tracks):
            return "invalid_timestamps"
        o = m.origin
        if self.registry.sources.get(o.source_id) != o.source_type or (m.tx.node_id != o.source_id and m.tx.node_id not in self.registry.relays) \
                or (m.hop_count == 0 and m.tx.node_id != o.source_id):
            return "unknown_source"
        if m.frame != FRAME:
            return "unsupported_frame"
        if m.origin_frame_id != c.origin_id:
            return "frame_mismatch"
        if m.units != UNITS:
            return "units_mismatch"
        if m.yaw_convention != YAW_CONVENTION:
            return "yaw_convention_mismatch"
        if o.provenance.get("confirmation") not in c.accepted_confirmations:
            return "unsupported_confirmation"
        if m.hop_count > c.max_hops or len(m.relay_path) != m.hop_count:
            return "too_many_hops"
        if c.receiver_id in m.relay_path or len(set(m.relay_path)) != len(m.relay_path) or (m.relay_path and m.tx.node_id != m.relay_path[-1]) \
                or o.source_id in m.relay_path:
            return "relay_loop"
        vmax = dict(c.max_speed)
        if any(math.hypot(t.vx, t.vy) > vmax[t.cls] for t in m.tracks):
            return "implausible_kinematics"
        if c.roi is not None and any(not (c.roi[0] <= t.x <= c.roi[2] and c.roi[1] <= t.y <= c.roi[3]) for t in m.tracks):
            return "outside_roi"
        return None

    # ------------------------------------------------------------------ main entry
    def process(self, payload: bytes, t_recv_sim: float, t_proc_sim: float, local_tracks=()) -> AdmissionResult:
        c = self.cfg
        t_recv, t_proc = self.clock.local(t_recv_sim), self.clock.local(t_proc_sim)

        def rej(reason, m=None, age_r=None, age_p=None):
            self.stats[reason] += 1
            return AdmissionResult(False, reason, None, t_recv, t_proc, age_r, age_p)
        if len(payload) > c.max_bytes:
            return rej("oversize")
        try:
            m = deserialize(payload)
        except MsgError as e:
            return rej(e.reason)
        why = self._static_checks(m, len(payload))
        age_r, age_p = t_recv - m.t_meas, t_proc - m.t_meas
        if why:
            return rej(why, m, age_r, age_p)
        # ---- stateful checks (read-only until the message is admitted)
        src = m.origin.source_id
        key = content_key(m)
        seen, mx = self._seen.get(src, set()), self._max_seq.get(src, -1)
        if key[1] in seen:
            return rej("duplicate", m, age_r, age_p)
        if mx >= 0 and key[1] < mx - c.reorder_window:
            return rej("replay_old", m, age_r, age_p)
        if age_p < -c.clock_tolerance_s:
            return rej("future_obs", m, age_r, age_p)
        if age_p > m.ttl_s:
            return rej("expired_ttl", m, age_r, age_p)
        if age_p > c.max_age_s:
            return rej("stale", m, age_r, age_p)
        # ---- admit: only now does decision state change
        flags = []
        if key[1] < mx:
            flags.append("late")
        if m.hop_count > 0:
            flags.append("relayed")
        if any(lt.confirmed and any(math.hypot(lt.x[0] - t.x, lt.x[1] - t.y) < 1.0 and lt.cls != t.cls and "unknown" not in (lt.cls, t.cls) for t in m.tracks)
               for lt in local_tracks):
            flags.append("class_conflict")                       # flagged for fusion (WP4); not a rejection
        seen.add(key[1]); self._seen[src] = {s for s in seen if s >= max(mx, key[1]) - c.reorder_window}
        self._max_seq[src] = max(mx, key[1])
        self.stats["admitted"] += 1
        return AdmissionResult(True, "ok", m, t_recv, t_proc, age_r, age_p, tuple(flags))
