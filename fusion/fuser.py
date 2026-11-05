"""CooperativeFuser: ego-centric, decentralised track-to-track fusion producing a CooperativeWorldState.
Inputs are `Estimate`s only (no truth, no planner, no comm internals). No wall clock, no randomness: deterministic.
Each source contributes its LATEST estimate only (no accumulation over time) so temporal correlation cannot be double counted."""
from __future__ import annotations
import math
from collections import Counter
import numpy as np
from perception.stats import chi2_ppf
from . import combine
from .associate import associate
from .identity import ALLOWLIST_ONLY, AUTHENTICATED, LOCAL, UnauthenticatedVerifier
from .model import predict
from .monitor import ConsistencyMonitor
from .types import REASONS, Estimate, FusedTrack, WorldState

METHODS = ("B0_local", "B1_remote", "B2_naive", "B3_info", "B4_ci", "B4q_ci_quarantine")
DEFAULTS = dict(sigma_a=1.0, gate_chi2_4dof=18.466826, max_horizon_s=1.0, max_remote_age_s=0.5, time_sigma_s=0.0, ci_criterion="trace",
                monitor_window=10, monitor_chi2_conf=0.999, monitor_warmup_s=0.0, class_gate=True, quarantine_on_flag=False, self_radius_m=0.0, require_assurance=None, supported_frame="map")


class CooperativeFuser:
    def __init__(self, method: str, params: dict | None = None, verifier=None):
        if method not in METHODS:
            raise ValueError(f"unknown method {method}")
        self.method = method
        self.p = {**DEFAULTS, **(params or {})}
        if method == "B4q_ci_quarantine":
            self.p["quarantine_on_flag"] = True
        self.verifier = verifier or UnauthenticatedVerifier()
        self.monitor = ConsistencyMonitor(self.p["monitor_window"], self.p["monitor_chi2_conf"], self.p["monitor_warmup_s"])
        self._next_fid = 1
        self._ref_fid: dict = {}
        self.rejected = Counter()
        self._self_gate = chi2_ppf(0.999, 2)

    # ------------------------------------------------------------------ validation (defence in depth, after WP3 admission)
    def _validate(self, e: Estimate, t_now: float):
        p = self.p
        try:
            x = np.array(e.x, dtype=float); P = np.array(e.P, dtype=float).reshape(4, 4)
        except (TypeError, ValueError):
            return "nonfinite", None
        if x.shape != (4,) or not (np.all(np.isfinite(x)) and np.all(np.isfinite(P)) and math.isfinite(e.t)):
            return "nonfinite", None
        scale = max(1e-12, float(np.abs(P).max()))
        if not (np.allclose(P, P.T, atol=1e-9 * scale + 1e-12) and np.all(np.diag(P) > 0) and np.linalg.eigvalsh(0.5 * (P + P.T)).min() > -1e-9 * scale):
            return "bad_covariance", None
        if e.frame != p["supported_frame"]:
            return "frame_mismatch", None                                    # no silent transform: use fusion.transform.Transform2D explicitly BEFORE fusing
        if e.t > t_now + 1e-6:
            return "future", None
        age = t_now - e.t
        if e.kind == "remote" and age > p["max_remote_age_s"] + 1e-9:
            return "stale", None
        if age > p["max_horizon_s"] + 1e-9:
            return "horizon", None
        if not isinstance(e.cls, str) or not e.cls:
            return "bad_class", None
        if e.kind == "remote" and p["require_assurance"] == AUTHENTICATED and self.verifier.assurance(e.source_id, e.evidence) != AUTHENTICATED:
            return "unauthenticated_source", None
        return None, (x, 0.5 * (P + P.T), age)

    # ------------------------------------------------------------------ main
    def step(self, t_now: float, estimates, ego_pose=None) -> WorldState:
        """ego_pose = (x, y, sigma_m): the ego's OWN localisation (inference-time information the ego legitimately has). Remote tracks that are the ego vehicle itself are dropped."""
        p = self.p; rej = Counter()
        use_local = self.method != "B1_remote"; use_remote = self.method != "B0_local"
        seen_ref: dict = {}
        for e in estimates:                                                 # duplicate source-scoped refs: keep the newest
            if (e.kind == "local" and not use_local) or (e.kind == "remote" and not use_remote):
                continue
            old = seen_ref.get(e.ref)
            if old is not None:
                rej["duplicate_ref"] += 1
                if e.t <= old.t: continue
            seen_ref[e.ref] = e
        items = []                                                          # (est, x_pred, P_pred, age)
        for e in sorted(seen_ref.values(), key=lambda q: (q.kind != "local", q.source_id, q.track_id)):
            why, v = self._validate(e, t_now)
            if why:
                rej[why] += 1; continue
            x, P, age = v
            xp, Pp = predict(x, P, t_now - e.t, p["sigma_a"], p["time_sigma_s"]) if abs(t_now - e.t) > 0 else (x, P)
            if ego_pose is not None and e.kind == "remote":
                if callable(ego_pose):                          # ego pose AT THE REMOTE OBSERVATION TIME (no constant-velocity lag when the ego brakes)
                    ep = ego_pose(e.t); S = P[:2, :2] + np.eye(2) * ep[2] ** 2; r = x[:2] - np.array(ep[:2], dtype=float)
                else:
                    S = Pp[:2, :2] + np.eye(2) * ego_pose[2] ** 2; r = xp[:2] - np.array(ego_pose[:2], dtype=float)
                if float(r @ np.linalg.solve(S, r)) <= self._self_gate or float(np.hypot(r[0], r[1])) <= p["self_radius_m"]:
                    rej["self_track"] += 1; continue
            items.append((e, xp, Pp, age))
        # evidence ledger (input level): one observation (origin source, origin seq) may enter the fusion once, whatever path/track id it arrived under
        used_ev: set = set(); kept = []; dup_ev = 0
        for it in sorted(items, key=lambda q: (np.trace(q[2]), q[0].kind != "local", q[0].ref)):
            if any(ev in used_ev for ev in it[0].evidence):
                dup_ev += 1; continue
            used_ev.update(it[0].evidence); kept.append(it)
        items = sorted(kept, key=lambda q: (q[0].kind != "local", q[0].source_id, q[0].track_id))
        clusters, amb_flags, pair_d2, class_blocked = self._cluster(items)
        tracks = []
        for cl in clusters:
            tr = self._combine(cl, t_now, amb_flags)
            if tr is not None: tracks.append(tr)
        tracks = self._assign_ids(tracks)
        for k, v in rej.items(): self.rejected[k] += v
        return WorldState(t_now, self.method, tuple(tracks), {"rejected": dict(rej), "pair_d2": tuple(pair_d2), "monitor_flagged": sorted(s for s, f in self.monitor.flagged.items() if f),
                                                              "n_inputs": len(items), "duplicate_evidence_dropped": dup_ev})

    # ------------------------------------------------------------------ clustering across sources (no truth)
    def _cluster(self, items):
        p = self.p; clusters: list = []; amb_clusters: set = set(); pair_d2 = []
        by_src: dict = {}
        for it in items:
            by_src.setdefault((it[0].kind != "local", it[0].source_id), []).append(it)
        for key in sorted(by_src):
            grp = by_src[key]; src = key[1]
            quarantined = p["quarantine_on_flag"] and key[0] and self.monitor.is_flagged(src)
            if not clusters or quarantined:
                for it in grp: clusters.append({"m": [it], "q": bool(quarantined), "amb": False})
                continue
            reps = [min(c["m"], key=lambda m: np.trace(m[2])) for c in clusters if not c["q"]]
            idx = [i for i, c in enumerate(clusters) if not c["q"]]
            A = [(r[1], r[2], r[0].cls) for r in reps]; B = [(g[1], g[2], g[0].cls) for g in grp]
            pairs, amb = associate(A, B, p["gate_chi2_4dof"], p["class_gate"])
            taken = set()
            for i, j, v in pairs:
                ci = idx[i]
                clusters[ci]["m"].append(grp[j]); taken.add(j)
                if (i, j) in amb: clusters[ci]["amb"] = True
                a, b = reps[i], grp[j]
                if a[0].kind == "local" and b[0].kind == "remote":
                    S = a[2][:2, :2] + b[2][:2, :2]; r = a[1][:2] - b[1][:2]
                    d2pos = float(r @ np.linalg.solve(S, r))
                    self.monitor.push(src, d2pos, a[0].t if a[0].kind == "local" else b[0].t)
                    pair_d2.append(v)
            for j, it in enumerate(grp):
                if j not in taken: clusters.append({"m": [it], "q": False, "amb": False})
        return clusters, None, pair_d2, 0

    # ------------------------------------------------------------------ per-cluster combination
    def _combine(self, cl, t_now, _amb):
        p = self.p; mem = list(cl["m"])
        # evidence ledger: a given evidence id may contribute once; the member with the smaller trace wins
        used: dict = {}
        for m in sorted(mem, key=lambda q: (np.trace(q[2]), q[0].ref)):
            if any(ev in used for ev in m[0].evidence):
                continue
            for ev in m[0].evidence: used[ev] = m
        mem = [m for m in mem if any(used.get(ev) is m for ev in m[0].evidence)] or mem[:1]
        mem.sort(key=lambda q: (q[0].kind != "local", q[0].source_id, q[0].track_id))
        flags = []
        if cl["amb"]: flags.append("ambiguous_association")
        if cl["q"]: flags.append("quarantined_source")
        if len(mem) == 1: flags.append("single_source")
        m = self.method
        if m == "B0_local":
            sel = [q for q in mem if q[0].kind == "local"]
            if not sel: return None
            mem = [min(sel, key=lambda q: np.trace(q[2]))]
        elif m == "B1_remote":
            sel = [q for q in mem if q[0].kind == "remote"]
            if not sel: return None
            mem = [min(sel, key=lambda q: np.trace(q[2]))]
        pairs = [(q[1], q[2]) for q in mem]
        omega: tuple = ()
        if len(mem) == 1:
            x, P = pairs[0]
        elif m == "B2_naive":
            x, P, omega = combine.naive(pairs)
        elif m == "B3_info":
            x, P, omega = combine.information(pairs)
        else:
            x, P, omega = combine.covariance_intersection(pairs, p["ci_criterion"])
        if not (np.all(np.isfinite(x)) and np.all(np.isfinite(P))):
            self.rejected["fused_nonfinite"] += 1
            return None
        remote_ages = [q[3] for q in mem if q[0].kind == "remote"]
        if any(q[0].hops > 0 for q in mem): flags.append("relayed")
        assur = LOCAL
        for q in mem:
            if q[0].kind == "remote":
                a = self.verifier.assurance(q[0].source_id, q[0].evidence)
                assur = AUTHENTICATED if (assur in (LOCAL, AUTHENTICATED) and a == AUTHENTICATED) else ALLOWLIST_ONLY
        cls = max(((q[0].cls_prob, q[0].cls) for q in mem))[1]
        return FusedTrack(0, t_now, tuple(float(v) for v in x), tuple(float(v) for v in np.asarray(P).reshape(-1)), cls, m, tuple(q[0].ref for q in mem),
                          tuple(ev for q in mem for ev in q[0].evidence), tuple(float(w) for w in omega), tuple(flags), max(remote_ages, default=0.0), assur)

    # ------------------------------------------------------------------ identity persistence (fusion-local; refs are source-scoped)
    def _assign_ids(self, tracks):
        order = sorted(range(len(tracks)), key=lambda i: tracks[i].members)
        taken: set = set(); out = [None] * len(tracks)
        cand = []
        for i in order:
            cnt = Counter(self._ref_fid[r] for r in tracks[i].members if r in self._ref_fid)
            for fid, c in cnt.items(): cand.append((-c, fid, i))
        for _, fid, i in sorted(cand):
            if out[i] is None and fid not in taken:
                out[i] = fid; taken.add(fid)
        for i in order:
            if out[i] is None:
                out[i] = self._next_fid; self._next_fid += 1
        new_map = {}
        from dataclasses import replace
        res = []
        for i, tr in enumerate(tracks):
            for r in tr.members: new_map[r] = out[i]
            res.append(replace(tr, fid=out[i]))
        self._ref_fid = new_map
        return sorted(res, key=lambda t: t.fid)
