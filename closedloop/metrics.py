"""Closed-loop SAFETY metrics (TRUTH SIDE). Independent of any estimation-RMSE metric. Definitions: docs/phase2/10 section 6."""
from __future__ import annotations
import math
import numpy as np
from . import conditions as K

BASE = {"hazard": "H_E0N", "control": "C_E0N", "ghost": "G_E0N"}
ABOVE = 1e-9


def wilson(k, n, z=1.96):
    if n == 0: return [None, None]
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, c - h), min(1.0, c + h)]


def walk(obj, seen=None, depth=0):
    seen = set() if seen is None else seen
    if id(obj) in seen or depth > 12: return
    seen.add(id(obj)); yield obj
    if isinstance(obj, dict):
        for k, v in obj.items(): yield from walk(k, seen, depth + 1); yield from walk(v, seen, depth + 1)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj: yield from walk(v, seen, depth + 1)
    elif hasattr(obj, "__dict__"):
        yield from walk(vars(obj), seen, depth + 1)


def truth_in_planning(stack) -> int:
    bad = ("backend", "closedloop", "experiments", "integration")
    return sum(1 for o in walk(stack) if type(o).__module__.startswith(bad) and type(o).__module__ != "backend.observation")


def per_run(r: dict) -> dict:
    ticks, a = r["ticks"], r["series"][:, 3]
    dt = K.DT
    out = dict(ego_col=r["ego_collision"], fol_col=r["follower_collision"], impact=r["impact_speed"],
               min_ttc=min([t["ttc"] for t in ticks] + [10.0]), near_miss=(not r["ego_collision"]) and r["min_clearance"] is not None and r["min_clearance"] < 1.0,
               unnecessary=any(cf >= 1.5 for _, cf in r["onsets"]), hard=float(-a.min()) > 3.5, max_decel=float(max(-a.min(), 0.0)),
               max_jerk=float(np.max(np.abs(np.diff(a))) / dt) if len(a) > 1 else 0.0, standstill=r["standstill_events"] > 0,
               completed=r["t_goal"] is not None, t_comp=(r["t_goal"] if r["t_goal"] is not None else K.DURATION),
               ages=[t["age"] for t in ticks if t["n_remote"] > 0], lat=[t["lat"] for t in ticks],
               pairs=[(t["p"], t["outcome"]) for t in ticks if not (t["n_remote"] == 0 and False)],
               stale=sum(1 for t in ticks if t["age"] > 0.5 + ABOVE), raised=sum(1 for t in ticks if t["a_cmd"] > t["a_local"] + ABOVE),
               cmd_viol=sum(1 for t in ticks if abs(t["a_cmd"]) > 6.0 + ABOVE or t["mode"] not in ("comfort", "emergency")), assur=sum(t["assur_bad"] for t in ticks),
               traj=r["traj_hash"], lead=None, f_ttc=None, f_req=None)
    if r["first_brake_t"] is not None and r["info"].get("t_edge") is not None:
        out["lead"] = r["info"]["t_edge"] - r["first_brake_t"]
    fs = r["fseries"]
    if len(fs):
        gap = fs[:, 3] - 0.9 - (fs[:, 1] + 3.6); clo = fs[:, 2] - fs[:, 4]
        with np.errstate(divide="ignore", invalid="ignore"):
            ttc = np.where(clo > 0.1, gap / clo, np.inf)
            req = np.where((clo > 0) & (gap > 0.05), clo * clo / (2 * gap), 0.0)
        out["f_ttc"] = float(min(np.min(ttc), 10.0)); out["f_req"] = float(np.max(req))
    return out


def ece_brier(pairs, bins=10):
    if not pairs: return None, None
    p = np.array([x[0] for x in pairs]); y = np.array([x[1] for x in pairs], float)
    idx = np.minimum((p * bins).astype(int), bins - 1); e = 0.0
    for b in range(bins):
        m = idx == b
        if m.any(): e += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(e), float(np.mean((p - y) ** 2))


def pool(runs: list, base_runs: dict | None = None, ref_traj: dict | None = None) -> dict:
    R = [per_run(r) for r in runs]; n = len(R)
    rate = lambda f: sum(1 for x in R if f(x)) / n
    pct = lambda v, q: float(np.percentile(v, q)) if len(v) else None
    ages = [a for x in R for a in x["ages"]]; lat = [l for x in R for l in x["lat"]]
    pairs = [q for x in R for q in x["pairs"]]
    ece, brier = ece_brier(pairs)
    k = sum(1 for x in R if x["ego_col"])
    out = dict(n=n, collision_rate=k / n, collision_ci95=wilson(k, n), follower_collision_rate=rate(lambda x: x["fol_col"]), ped_impact_speed_mean=float(np.mean([x["impact"] for x in R if x["impact"]] or [0.0])),
               min_ttc_median_s=float(np.median([x["min_ttc"] for x in R])), near_miss_rate=rate(lambda x: x["near_miss"]), unnecessary_intervention_rate=rate(lambda x: x["unnecessary"]),
               hard_brake_rate=rate(lambda x: x["hard"]), max_decel_p95=pct([x["max_decel"] for x in R], 95), max_jerk_p95=pct([x["max_jerk"] for x in R], 95),
               standstill_jerk_event_rate=rate(lambda x: x["standstill"]), completion_rate=rate(lambda x: x["completed"]), completion_time_mean_s=float(np.mean([x["t_comp"] for x in R])),
               warning_lead_median_s=(float(np.median([x["lead"] for x in R if x["lead"] is not None])) if any(x["lead"] is not None for x in R) else None),
               remote_age_p95_s=pct(ages, 95), remote_age_max_s=(max(ages) if ages else None), calibration_ece=ece, calibration_brier=brier,
               decision_latency_p95_ms=(1e3 * pct(lat, 95) if lat else None), decision_latency_p50_ms=(1e3 * pct(lat, 50) if lat else None),
               follower_min_ttc_median_s=(float(np.median([x["f_ttc"] for x in R if x["f_ttc"] is not None])) if any(x["f_ttc"] is not None for x in R) else None),
               follower_req_decel_p95=(pct([x["f_req"] for x in R if x["f_req"] is not None], 95) if any(x["f_req"] is not None for x in R) else None),
               stale_or_invalid_remote_used=sum(x["stale"] for x in R), remote_raised_speed_events=sum(x["raised"] for x in R), command_limit_violations=sum(x["cmd_viol"] for x in R),
               unauthenticated_treated_as_authenticated=sum(x["assur"] for x in R))
    if base_runs:
        pen = [x["t_comp"] - per_run(base_runs[r["seed"]])["t_comp"] for x, r in zip(R, runs) if r["seed"] in base_runs]
        out["travel_time_penalty_s"] = float(np.mean(pen)) if pen else None
    if ref_traj:
        out["fallback_identical_fraction"] = float(np.mean([x["traj"] == ref_traj.get(r["seed"]) for x, r in zip(R, runs)]))
    return out
