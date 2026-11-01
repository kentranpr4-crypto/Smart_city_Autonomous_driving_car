"""Metrics from a comm telemetry event list (+ evaluation AoI meters). Definitions are declared in comm/thresholds.json before any benchmark."""
from __future__ import annotations
from collections import Counter
import numpy as np


def pct(a, q):
    return float(np.percentile(np.asarray(a, dtype=float), q, method="linear")) if len(a) else None


def dist(a):
    return {"n": len(a), "p50": pct(a, 50), "p95": pct(a, 95), "p99": pct(a, 99), "max": float(max(a)) if len(a) else None, "mean": float(np.mean(a)) if len(a) else None}


def summarize(events, aoi_meters=None, duration: float = 0.0, aoi_dt: float = 0.01, t_end: float | None = None) -> dict:
    ev = [e for e in events if e["type"] != "header"]
    sends = [e for e in ev if e["type"] == "send"]
    sent_t = {(e["link"], e["msg_id"]): e["t"] for e in sends}
    drops = Counter(e["reason"] for e in ev if e["type"] == "drop")
    recv = [e for e in ev if e["type"] == "recv"]
    proc = [e for e in ev if e["type"] == "proc"]
    admit = [e for e in proc if e["verdict"] == "admit"]
    rej = Counter(e["reason"] for e in proc if e["verdict"] == "reject")
    net_lat = [e["t"] - sent_t[(e["link"], e["msg_id"])] for e in recv]
    obs_use = [e["t"] - e["eval"]["obs_sim"] for e in admit if e["eval"]["obs_sim"] is not None]
    by_src = Counter()
    for e in sends:
        by_src[e["node"]] += e["bytes"]
    aoi = []
    for m in (aoi_meters or {}).values():
        aoi += m.samples(aoi_dt, t_end if t_end is not None else duration)
    return {
        "sent": len(sends), "dropped_by_reason": dict(drops), "copies_delivered": len(recv), "processed": len(proc), "admitted": len(admit),
        "rejected_by_reason": dict(rej), "delivery_ratio": (len(admit) / len(sends)) if sends else None,
        "duplicates_rejected": rej.get("duplicate", 0), "late_admitted": sum(1 for e in admit if "late" in e["flags"]),
        "replay_old_rejected": rej.get("replay_old", 0),
        "network_latency_s": dist(net_lat), "obs_to_use_latency_s": dist(obs_use), "aoi_s": dist(aoi),
        "max_observation_age_accepted_est_s": max((e["age_proc_est"] for e in admit), default=None),
        "max_observation_age_accepted_true_s": max((e["eval"]["age_true_proc"] for e in admit if e["eval"]["age_true_proc"] is not None), default=None),
        "bandwidth_Bps_per_source": {k: v / duration for k, v in by_src.items()} if duration else {},
        "bytes_sent_total": int(sum(by_src.values())),
    }
