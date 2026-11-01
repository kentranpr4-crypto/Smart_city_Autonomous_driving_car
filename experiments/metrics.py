"""Evaluator (TRUTH SIDE). Per-run statistics from a harness record, and pooling over seeds. Definitions: docs/phase2/09 §5."""
from __future__ import annotations
import hashlib, json, math
import numpy as np
from perception.hungarian import linear_sum_assignment
from . import conditions as K

SRC_EGO = "ego_cam"


def match(tracks_xy, truth: dict, gate: float = K.EVAL_GATE_M):
    """Optimal 1-1 association of tracks [(key, x, y)] to truth {id: (x, y, ...)}; returns {truth_id: key}."""
    ids = sorted(truth)
    if not tracks_xy or not ids:
        return {}
    cost = [[math.hypot(x - truth[i][0], y - truth[i][1]) for i in ids] for _, x, y in tracks_xy]
    return {ids[j]: tracks_xy[i][0] for i, j in linear_sum_assignment(cost) if cost[i][j] <= gate}


def _walk(obj, seen=None, depth=0):
    seen = set() if seen is None else seen
    if id(obj) in seen or depth > 10: return
    seen.add(id(obj)); yield obj
    if isinstance(obj, dict):
        for k, v in obj.items(): yield from _walk(k, seen, depth + 1); yield from _walk(v, seen, depth + 1)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj: yield from _walk(v, seen, depth + 1)
    elif hasattr(obj, "__dict__"):
        yield from _walk(vars(obj), seen, depth + 1)


def truth_objects_reachable(fuser) -> int:
    return sum(1 for o in _walk(fuser) if type(o).__module__.startswith(("backend", "experiments", "comm", "integration")) and type(o).__module__ != "backend.observation")


def run_hash(rec: dict) -> str:
    h = hashlib.sha256()
    for c in rec["cycles"]:
        for m, v in sorted(c["methods"].items()):
            h.update(json.dumps([m, c["t"], [(a[0], a[1], a[2]) for a in v["tracks"]], v["rej"]], sort_keys=True, default=float).encode())
    return h.hexdigest()


def per_run(rec: dict, method: str) -> dict:
    cyc = rec["cycles"]; tg = rec["targets"]; dt = K.DT * K.FUSION_EVERY_STEPS
    S = dict(n_opp=0, n_hit=0, occ_opp=0, occ_hit=0, m=0, pos_sq=0.0, vel_sq=0.0, nees_sum=0.0, nees_n=0, cov_hit=0, ov_n=0, ov_pos_sq=0.0,
             pairs=0, pairs_ok=0, potential=0, switches=0, minutes=0.0, false=0, false_b0=0, cycles=len(cyc), bad_out=0, dup_use=0, max_age=0.0, runtime=[], ttfv=[], recovery=None,
             nis_sum=0.0, nis_n=0, fused_with_remote=0, failures=0)
    last, first_obs, first_hit = {}, {}, {}
    rem_after = None
    for c in cyc:
        t = c["t"]; truth = c["truth"]; M = c["methods"][method]
        fused = [(a[0], a[1][0], a[1][1]) for a in M["tracks"]]
        mt = match(fused, truth)
        all_t = c["truth_all"]
        matched_all = set(match(fused, all_t).values())      # tracks of real non-target actors (e.g. another vehicle) are not 'false'
        b0 = match([(a[0], a[1][0], a[1][1]) for a in c["methods"]["B0_local"]["tracks"]], truth) if "B0_local" in c["methods"] else {}
        matched_fids = set(mt.values())
        S["false"] += sum(1 for f in fused if f[0] not in matched_all)
        b0t = c["methods"].get("B0_local", {"tracks": []})["tracks"]; b0all = set(match([(a[0], a[1][0], a[1][1]) for a in b0t], all_t).values()); S["false_b0"] += sum(1 for a in b0t if a[0] not in b0all)
        S["runtime"].append(M["runtime_s"])
        for a in M["tracks"]:
            P = np.array(a[2]).reshape(4, 4); x = np.array(a[1])
            if not (np.all(np.isfinite(x)) and np.all(np.isfinite(P)) and np.allclose(P, P.T, atol=1e-8 * max(1, np.abs(P).max())) and np.linalg.eigvalsh(0.5 * (P + P.T)).min() > -1e-9 * max(1, np.abs(P).max())): S["bad_out"] += 1
            if len(a[5]) != len(set(a[5])): S["dup_use"] += 1
            S["max_age"] = max(S["max_age"], a[6])
        for tid in tg:
            if tid in truth:
                ego_v, rem_v = tid in c["vis"]["ego_cam"], tid in c["vis"]["cctv_k1"]
                if tid not in first_obs and (tid in c["det"]["ego_cam"] or tid in c["det"]["cctv_k1"]): first_obs[tid] = t
                hit = tid in mt
                S["n_opp"] += 1; S["n_hit"] += int(hit)
                if rem_v and not ego_v: S["occ_opp"] += 1; S["occ_hit"] += int(hit)
                if hit and tid not in first_hit: first_hit[tid] = t
                if hit and t >= K.WARMUP_S:
                    fid = mt[tid]; a = next(q for q in M["tracks"] if q[0] == fid)
                    e = np.array(a[1]) - np.array(truth[tid]); P = np.array(a[2]).reshape(4, 4)
                    S["m"] += 1; S["pos_sq"] += float(e[0] ** 2 + e[1] ** 2); S["vel_sq"] += float(e[2] ** 2 + e[3] ** 2)
                    n = float(e @ np.linalg.solve(P, e)); S["nees_sum"] += n; S["nees_n"] += 1; S["cov_hit"] += int(n <= K.CHI2_95_4DOF)
                    if rem_v and ego_v: S["ov_n"] += 1; S["ov_pos_sq"] += float(e[0] ** 2 + e[1] ** 2)
                    if tid in last and last[tid] != fid: S["switches"] += 1
                if hit: last[tid] = mt[tid]
        if mt: S["minutes"] += dt / 60.0
        for d in M["pair_d2"]:
            S["nis_sum"] += d; S["nis_n"] += 1
        # association precision / recall from cluster membership (fused tracks with a local AND a remote member)
        loc_map = match([(r[1], r[2][0], r[2][1]) for r in c["local"]], truth)
        rem_map = match([(r[1], r[2][0] + r[2][2] * (t - r[3]), r[2][1] + r[2][3] * (t - r[3])) for r in c["remote"]], truth)
        if method in ("B2_naive", "B3_info", "B4_ci", "B4q_ci_quarantine"):
            inv_l = {v: k for k, v in loc_map.items()}; inv_r = {v: k for k, v in rem_map.items()}
            for a in M["tracks"]:
                ml = [r[1] for r in a[3] if r[0] == SRC_EGO]; mr = [r[1] for r in a[3] if r[0] != SRC_EGO]
                if ml and mr:
                    S["pairs"] += 1; S["pairs_ok"] += int(inv_l.get(ml[0]) is not None and inv_l.get(ml[0]) == inv_r.get(mr[0]))
                    S["fused_with_remote"] += 1
            S["potential"] += len(set(loc_map) & set(rem_map))
        if rec["blackout"] and t >= rec["blackout"][1] and rem_after is None and any(r[0] != SRC_EGO for a in M["tracks"] for r in a[3]):
            rem_after = t - rec["blackout"][1]
    for tid, to in first_obs.items():
        S["ttfv"].append((first_hit.get(tid, cyc[-1]["t"] + dt) - to))
    if rec["blackout"]:
        S["recovery"] = rem_after if rem_after is not None else cyc[-1]["t"] - rec["blackout"][1]
    S["avail"] = S["n_hit"] / max(1, S["n_opp"])
    S["failures"] = int(S["avail"] < 0.5)
    mon = rec["monitor"].get(method, {})
    S["flag_3s"] = int(mon.get("first_flag_t") is not None and mon.get("first_pair_t") is not None and mon["first_flag_t"] - mon["first_pair_t"] <= 3.0)
    S["flag_any"] = int(mon.get("first_flag_t") is not None)
    return S


def pool(runs: list, method: str, boot_seed: int = 20261101) -> dict:
    R = [per_run(r, method) for r in runs]
    s = lambda k: sum(x[k] for x in R)
    div = lambda a, b: (a / b) if b else None
    out = {
        "availability": div(s("n_hit"), s("n_opp")), "availability_occluded": div(s("occ_hit"), s("occ_opp")), "occluded_opportunities": s("occ_opp"),
        "pos_rmse": math.sqrt(s("pos_sq") / s("m")) if s("m") else None, "vel_rmse": math.sqrt(s("vel_sq") / s("m")) if s("m") else None,
        "pos_rmse_overlap": math.sqrt(s("ov_pos_sq") / s("ov_n")) if s("ov_n") else None, "overlap_n": s("ov_n"),
        "coverage95": div(s("cov_hit"), s("nees_n")), "anees": div(s("nees_sum"), s("nees_n")), "nees_n": s("nees_n"), "nis_mean": div(s("nis_sum"), s("nis_n")),
        "assoc_precision": div(s("pairs_ok"), s("pairs")), "assoc_recall": div(s("pairs_ok"), s("potential")), "assoc_pairs": s("pairs"),
        "id_switch_rate_per_min": div(s("switches"), s("minutes")), "id_switch_seed_fraction": np.mean([x["switches"] > 0 for x in R]),
        "false_tracks_per_cycle": div(s("false"), s("cycles")), "false_tracks_per_cycle_excess_vs_B0": div(s("false") - s("false_b0"), s("cycles")),
        "ttfv_median_s": float(np.median([v for x in R for v in x["ttfv"]])) if any(x["ttfv"] for x in R) else None,
        "fuse_runtime_p95_ms": 1e3 * float(np.percentile([v for x in R for v in x["runtime"]], 95)), "fuse_runtime_mean_ms": 1e3 * float(np.mean([v for x in R for v in x["runtime"]])),
        "nonfinite_or_non_psd_outputs": s("bad_out"), "duplicate_evidence_double_use": s("dup_use"), "max_remote_age_used_s": max(x["max_age"] for x in R),
        "monitor_flag_seed_fraction": float(np.mean([x["flag_3s"] for x in R])), "monitor_flag_any_seed_fraction": float(np.mean([x["flag_any"] for x in R])),
        "recovery_p95_s": float(np.percentile([x["recovery"] for x in R if x["recovery"] is not None], 95)) if any(x["recovery"] is not None for x in R) else None,
        "failure_rate": float(np.mean([x["failures"] for x in R])), "seeds": len(R),
    }
    # bootstrap 95% CI over seeds for the headline error metrics
    rng = np.random.default_rng(boot_seed)
    def ci(fn):
        vals = []
        for _ in range(300):
            idx = rng.integers(0, len(R), len(R)); sub = [R[i] for i in idx]
            vals.append(fn(sub))
        return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]
    ss = lambda sub, k: sum(x[k] for x in sub)
    if s("m"):
        out["pos_rmse_ci95"] = ci(lambda sub: math.sqrt(ss(sub, "pos_sq") / max(1, ss(sub, "m"))))
        out["coverage95_ci95"] = ci(lambda sub: ss(sub, "cov_hit") / max(1, ss(sub, "nees_n")))
    out["availability_ci95"] = ci(lambda sub: ss(sub, "n_hit") / max(1, ss(sub, "n_opp")))
    return out
