"""Constant-velocity Kalman multi-target tracker for ONE sensor stream (Mahalanobis gating, optimal assignment, M/N confirmation,
SPRT-style existence score, time-based coasting/expiry, frame validation, consistency monitor).

I9: input is SensorFrame only. This module has no access path to ground truth. The existence score is a HEURISTIC and is NOT a calibrated
probability (see docs/phase2/01 D04: calibration UNKNOWN).
"""
from __future__ import annotations
import math
from collections import deque
from dataclasses import dataclass, field
import numpy as np
from backend.observation import SensorFrame, SCHEMA_VERSION
from .hungarian import linear_sum_assignment
from .stats import chi2_ppf

GATE_CHI2_99_2DOF = 9.210340371976184
GATE_CHI2_999_2DOF = 13.815510557964274      # = -2 ln(0.001): chi2(2) 99.9% quantile


@dataclass(frozen=True)
class TrackerConfig:
    sigma_a: float = 1.0                 # process noise (white-noise acceleration) std [m/s^2]
    init_speed_sigma: float = 2.0
    gate_chi2: float = GATE_CHI2_999_2DOF   # 99.9%: a 99% gate rejects ~1% of true detections (the informative ones) and makes the filter over-confident (AC-VS-03 failed at 99%)
    confirm_m: int = 2
    confirm_n: int = 3
    hit_llr: float = 1.2
    miss_llr: float = 0.8
    delete_score: float = -3.0
    max_score: float = 6.0
    max_coast_s: float = 1.5             # confirmed tracks expire if not updated for this long (stale data)
    max_frame_age_s: float = 1.0         # reject frames older than this at receipt (needs t_now)
    max_future_s: float = 1e-6           # reject frames stamped in the future
    meas_cov_inflation: float = 1.0
    max_abs_position: float = 1e5
    nis_window: int = 30
    merge_chi2: float = 18.466826  # duplicate suppression: 4-D state Mahalanobis (chi2(4) 99.9%) between two tracks => same target


@dataclass(frozen=True)
class Track:
    track_id: int
    t: float
    x: tuple                             # (x, y, vx, vy)
    P: tuple                             # 4x4 row-major
    confirmed: bool
    score: float
    existence: float                     # heuristic, uncalibrated
    cls: str
    hits: int
    misses: int
    age_s: float
    time_since_update_s: float
    cls_share: float = 1.0               # vote share of the majority class label (count based, NOT a calibrated probability)


@dataclass(frozen=True)
class UpdateReport:
    accepted: bool
    reason: str
    n_dets: int = 0
    n_matched: int = 0
    n_new: int = 0
    n_deleted: int = 0
    seq_gap: int = 0
    nis: tuple = ()                      # d^2 of each matched (track, detection) pair, for consistency monitoring
    n_merged: int = 0                    # duplicate tracks removed this frame


@dataclass
class _T:
    tid: int; x: np.ndarray; P: np.ndarray; t: float; t_birth: float; t_upd: float
    hist: deque = field(default_factory=deque); score: float = 0.0; confirmed: bool = False
    hits: int = 1; misses: int = 0; cls_counts: dict = field(default_factory=dict)


def _F(dt):
    F = np.eye(4); F[0, 2] = F[1, 3] = dt
    return F


def _Q(dt, sa):
    q = sa * sa
    return q * np.array([[dt**4 / 4, 0, dt**3 / 2, 0], [0, dt**4 / 4, 0, dt**3 / 2], [dt**3 / 2, 0, dt**2, 0], [0, dt**3 / 2, 0, dt**2]])


class Tracker:
    def __init__(self, sensor_id: str, cfg: TrackerConfig | None = None):
        self.sensor_id, self.cfg = sensor_id, cfg or TrackerConfig()
        self._tracks: list[_T] = []
        self._next_id = 1
        self._last_seq = -1
        self._last_t = -math.inf
        self.rejects: dict = {}
        self.frames_ok = 0
        self.seq_gaps = 0
        self._nis = deque(maxlen=self.cfg.nis_window)

    @property
    def last_frame_time(self) -> float:
        """Measurement time of the newest ACCEPTED frame (-inf before the first)."""
        return self._last_t

    # ------------------------------------------------------------ validation
    def _validate(self, f: SensorFrame, t_now):
        c = self.cfg
        if f.schema_version != SCHEMA_VERSION: return "schema_version"
        if f.sensor_id != self.sensor_id: return "wrong_sensor"
        nums = [f.t_meas, f.t_avail, f.fov, f.range_m, *f.sensor_pose]
        for d in f.detections:
            nums += [d.x, d.y, d.cls_prob, d.score, *d.cov]
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in nums): return "non_finite"
        if f.t_avail < f.t_meas: return "t_avail_before_t_meas"
        ids = [d.det_id for d in f.detections]
        if len(set(ids)) != len(ids): return "duplicate_det_id"
        for d in f.detections:
            xx, xy, yy = d.cov
            if not (xx > 0 and yy > 0 and xx * yy - xy * xy > 0): return "bad_covariance"
            if abs(d.x) > c.max_abs_position or abs(d.y) > c.max_abs_position: return "position_out_of_range"
        if f.seq <= self._last_seq: return "seq_replay"
        if f.t_meas <= self._last_t: return "out_of_order"
        if t_now is not None:
            if f.t_meas > t_now + c.max_future_s: return "future"
            if t_now - f.t_meas > c.max_frame_age_s: return "stale"
        return None

    # ------------------------------------------------------------ update
    def update(self, f: SensorFrame, t_now: float | None = None) -> UpdateReport:
        c = self.cfg
        why = self._validate(f, t_now)
        if why:
            self.rejects[why] = self.rejects.get(why, 0) + 1
            return UpdateReport(False, why, len(f.detections))
        gap = max(0, f.seq - self._last_seq - 1) if self._last_seq >= 0 else 0
        self.seq_gaps += gap
        self._last_seq, self._last_t = f.seq, f.t_meas
        self.frames_ok += 1
        t = f.t_meas
        # Stale tracks must be expired BEFORE association: otherwise a track that has not been updated for > max_coast_s could 'come back to life'
        # and absorb an unrelated detection through its huge predicted covariance.
        n_expired = sum(1 for tr in self._tracks if (t - tr.t_upd) > c.max_coast_s)
        self._tracks = [tr for tr in self._tracks if (t - tr.t_upd) <= c.max_coast_s]
        for tr in self._tracks:                                       # predict everything to the measurement time
            dt = t - tr.t
            F = _F(dt); tr.x = F @ tr.x; tr.P = F @ tr.P @ F.T + _Q(dt, c.sigma_a); tr.t = t
        dets = f.detections
        Rs = [c.meas_cov_inflation * np.array([[d.cov[0], d.cov[1]], [d.cov[1], d.cov[2]]]) for d in dets]
        zs = [np.array([d.x, d.y]) for d in dets]
        big = 1e12
        cost, S_inv = [], {}
        for i, tr in enumerate(self._tracks):
            row = []
            for j in range(len(dets)):
                S = tr.P[:2, :2] + Rs[j]; Si = np.linalg.inv(S)
                nu = zs[j] - tr.x[:2]; d2 = float(nu @ Si @ nu)
                S_inv[(i, j)] = (Si, S, nu, d2)
                row.append(d2 if d2 <= c.gate_chi2 else big)
            cost.append(row)
        pairs = [(i, j) for i, j in linear_sum_assignment(cost) if cost[i][j] < big] if cost and dets else []
        matched_t = {i for i, _ in pairs}; matched_d = {j for _, j in pairs}
        for i, j in pairs:
            tr = self._tracks[i]; Si, S, nu, d2 = S_inv[(i, j)]
            K = tr.P[:, :2] @ Si
            tr.x = tr.x + K @ nu
            IKH = np.eye(4) - np.hstack([K, np.zeros((4, 2))])
            tr.P = IKH @ tr.P @ IKH.T + K @ Rs[j] @ K.T
            tr.P = 0.5 * (tr.P + tr.P.T)
            tr.t_upd = t; tr.hits += 1; tr.score = min(c.max_score, tr.score + c.hit_llr)
            tr.hist.append(1); self._nis.append(d2)
            tr.cls_counts[dets[j].cls] = tr.cls_counts.get(dets[j].cls, 0) + 1
        for i, tr in enumerate(self._tracks):
            if i not in matched_t:
                tr.misses += 1; tr.score -= c.miss_llr; tr.hist.append(0)
            while len(tr.hist) > c.confirm_n: tr.hist.popleft()
            if not tr.confirmed and sum(tr.hist) >= c.confirm_m: tr.confirmed = True
        n_new = 0
        for j, d in enumerate(dets):                                  # births from unassociated detections (clutter included)
            if j in matched_d: continue
            P0 = np.zeros((4, 4)); P0[:2, :2] = Rs[j]; P0[2, 2] = P0[3, 3] = c.init_speed_sigma ** 2
            tr = _T(self._next_id, np.array([d.x, d.y, 0.0, 0.0]), P0, t, t, t, hist=deque([1]), score=c.hit_llr, cls_counts={d.cls: 1})
            self._next_id += 1; n_new += 1; self._tracks.append(tr)
        keep, n_del = [], n_expired
        for tr in self._tracks:
            dead = False
            if tr.confirmed:
                dead = tr.score < c.delete_score or (t - tr.t_upd) > c.max_coast_s
            else:
                dead = len(tr.hist) >= c.confirm_n and sum(tr.hist) < c.confirm_m
                dead = dead or (t - tr.t_upd) > c.max_coast_s
            if dead: n_del += 1
            else: keep.append(tr)
        self._tracks = keep
        n_merged = self._suppress_duplicates()
        n_del += n_merged
        return UpdateReport(True, "ok", len(dets), len(pairs), n_new, n_del, gap, tuple(S_inv[(i, j)][3] for i, j in pairs), n_merged)

    def _suppress_duplicates(self) -> int:
        """Two tracks whose 4-D states are statistically indistinguishable describe the same target (typically after a true detection was
        gated out and spawned a newborn). Keep the more established one (confirmed > hits > older), drop the other.
        LIMITATION: two genuinely distinct targets walking together within ~the combined uncertainty are merged."""
        c, removed = self.cfg, set()
        rank = lambda tr: (tr.confirmed, tr.hits, -tr.t_birth, -tr.tid)
        for i in range(len(self._tracks)):
            for j in range(i + 1, len(self._tracks)):
                a, b = self._tracks[i], self._tracks[j]
                if a.tid in removed or b.tid in removed: continue
                dx = a.x - b.x
                if float(dx @ np.linalg.solve(a.P + b.P, dx)) <= c.merge_chi2:
                    removed.add((b if rank(a) >= rank(b) else a).tid)
        self._tracks = [t for t in self._tracks if t.tid not in removed]
        return len(removed)

    # ------------------------------------------------------------ outputs
    def tracks(self, t: float | None = None, confirmed_only: bool = True) -> list[Track]:
        c = self.cfg
        t = self._last_t if t is None else t
        out = []
        for tr in self._tracks:
            if confirmed_only and not tr.confirmed: continue
            dt = t - tr.t
            F = _F(dt); x = F @ tr.x; P = F @ tr.P @ F.T + (_Q(dt, c.sigma_a) if dt > 0 else 0.0)
            since = t - tr.t_upd
            if since > c.max_coast_s: continue                          # too stale to publish
            cls = max(tr.cls_counts.items(), key=lambda kv: (kv[1], kv[0]))[0]
            out.append(Track(tr.tid, t, tuple(float(v) for v in x), tuple(float(v) for v in P.reshape(-1)), tr.confirmed, tr.score,
                             1.0 / (1.0 + math.exp(-tr.score)), cls, tr.hits, tr.misses, t - tr.t_birth, since,
                             tr.cls_counts[cls] / sum(tr.cls_counts.values())))
        return out

    def health(self) -> dict:
        """Consistency monitor: windowed NIS vs chi2. Flags a sensor whose measurements are inconsistent with the tracker's model
        (bias, over-confident declared covariance, wrong dynamics)."""
        w = len(self._nis)
        flag, thr = False, None
        if w >= 10:
            thr = chi2_ppf(0.999, 2 * w); flag = sum(self._nis) > thr
        return {"frames_ok": self.frames_ok, "rejects": dict(self.rejects), "seq_gaps": self.seq_gaps, "n_tracks": len(self._tracks),
                "nis_window": w, "nis_mean": (sum(self._nis) / w) if w else None, "nis_inconsistent": flag, "nis_threshold_sum": thr}
