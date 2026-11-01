#!/usr/bin/env python3
"""WP3 benchmark against comm/thresholds.json (declared BEFORE any benchmark ran; its SHA-256 is checked and the file is never edited here).
Writes docs/phase2/wp-reports/evidence/wp3/{benchmark.json, benchmark_table.md}. Statuses: PASS / FAIL (invariant|provisional_design) or REPORTED (report_only). Nothing is tuned."""
import hashlib, json, math, pathlib, sys, time
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from comm.channel import LinkConfig
from comm.metrics import dist, summarize
from comm.telemetry import accounting
from comm.trackmsg import deserialize
from integration.comm_rig import run_rig_comm

TH_PATH = ROOT / "comm" / "thresholds.json"
DECLARED_SHA = "47096a4ea5957f8e1f7f9a180ef379fdd003af3426b8d3a6090f7d7c2d758760"
sha = hashlib.sha256(TH_PATH.read_bytes()).hexdigest()
assert sha == DECLARED_SHA, f"thresholds.json changed after declaration: {sha}"
TH = json.loads(TH_PATH.read_text())
SEEDS = list(range(20261101, 20261151))
COND = {
    "B0_nominal": LinkConfig("L", base_delay_s=0.030, jitter_s=0.010, loss_p=0.01),
    "B1_degraded": LinkConfig("L", base_delay_s=0.080, jitter_s=0.040, ge=(0.05, 0.30, 0.02, 0.60), dup_p=0.02, reorder_p=0.05, reorder_extra_delay_s=(0.05, 0.15)),
    "B2_severe": LinkConfig("L", base_delay_s=0.200, jitter_s=0.100, loss_p=0.30, dup_p=0.10, reorder_p=0.15, reorder_extra_delay_s=(0.10, 0.40), corrupt_p=0.02, blackouts=((5.0, 6.0),)),
}
TRUTH_IDS = {"ped1", "truck", "ego"}


def one(seed, link):
    w, rig, net, store, adm, pub = run_rig_comm(seed, link, keep_wire=True)
    ev = net.tel.events
    s = summarize(ev, net.eval_aoi, w.t, 0.01, w.t)
    acc = accounting(ev)
    sched = {(e["link"], e["msg_id"], e["copy"]): e for e in ev if e["type"] == "sched"}
    send = {(e["link"], e["msg_id"]): e for e in ev if e["type"] == "send"}
    admits = [e for e in ev if e["type"] == "proc" and e["verdict"] == "admit"]
    corrupted_adm = sum(1 for e in admits if "corrupted" in sched[(e["link"], e["msg_id"], e["copy"])]["flags"])
    keys = [(send[(e["link"], e["msg_id"])]["origin"], send[(e["link"], e["msg_id"])]["orig_seq"]) for e in admits]
    dup_adm = len(keys) - len(set(keys))
    strings = []
    def walk(o):
        if isinstance(o, dict):
            [walk(v) for v in o.values()]
        elif isinstance(o, list):
            [walk(v) for v in o]
        elif isinstance(o, str): strings.append(o)
    for b in net.wire: walk(json.loads(b))
    truth_in_wire = sum(1 for x in strings if x in TRUTH_IDS)
    # INV-7: independent brute-force AoI (freshest admitted observation so far) vs the meter, on the 10 ms grid
    mism = 0
    for (dst, src), m in net.eval_aoi.items():
        pts = sorted((e["t"], e["eval"]["obs_sim"]) for e in admits if e["eval"]["obs_sim"] is not None)
        got = m.samples(0.01, w.t)
        t0 = pts[0][0]
        for i, a in enumerate(got):
            t = t0 + i * 0.01
            fresh = max(o for tp, o in pts if tp <= t + 1e-12)
            mism += abs(a - (t - fresh)) > 1e-9
    wire_len = len(net.wire)
    return dict(summary=s, acc=acc, hash=net.tel.hexdigest(), corrupted_adm=corrupted_adm, dup_adm=dup_adm, truth_in_wire=truth_in_wire, aoi_mism=int(mism), t_end=w.t,
                aoi_samples=[x for m in net.eval_aoi.values() for x in m.samples(0.01, w.t)],
                net_lat=[e["t"] - send[(e["link"], e["msg_id"])]["t"] for e in ev if e["type"] == "recv"],
                obs_use=[e["t"] - e["eval"]["obs_sim"] for e in admits if e["eval"]["obs_sim"] is not None], wire_len=wire_len)


def main():
    t0 = time.perf_counter(); R = {}
    for cname, link in COND.items():
        runs, replay_bad = [], 0
        for sd in SEEDS:
            r = one(sd, link); runs.append(r)
            if one(sd, link)["hash"] != r["hash"]: replay_bad += 1
        sent = sum(r["summary"]["sent"] for r in runs); adm = sum(r["summary"]["admitted"] for r in runs)
        rej, drp = {}, {}
        for r in runs:
            for k, v in r["summary"]["rejected_by_reason"].items(): rej[k] = rej.get(k, 0) + v
            for k, v in r["summary"]["dropped_by_reason"].items(): drp[k] = drp.get(k, 0) + v
        aoi = [x for r in runs for x in r["aoi_samples"]]; nl = [x for r in runs for x in r["net_lat"]]; ou = [x for r in runs for x in r["obs_use"]]
        R[cname] = {
            "seeds": len(SEEDS), "sent": sent, "admitted": adm, "delivery_ratio": adm / sent, "dropped_by_reason": drp, "rejected_by_reason": rej,
            "duplicates_rejected": rej.get("duplicate", 0), "late_admitted": sum(r["summary"]["late_admitted"] for r in runs), "replay_old_rejected": rej.get("replay_old", 0),
            "copies_delivered": sum(r["summary"]["copies_delivered"] for r in runs),
            "network_latency_s": dist(nl), "obs_to_use_latency_s": dist(ou), "aoi_s": dist(aoi),
            "bandwidth_Bps_per_source_mean": float(np.mean([sum(r["summary"]["bandwidth_Bps_per_source"].values()) for r in runs])),
            "bytes_per_message_mean": float(np.mean([r["summary"]["bytes_sent_total"] / max(r["summary"]["sent"], 1) for r in runs])),
            "max_observation_age_accepted_true_s": max(r["summary"]["max_observation_age_accepted_true_s"] for r in runs),
            "max_observation_age_accepted_s": max(r["summary"]["max_observation_age_accepted_true_s"] for r in runs),   # INV-3 metric = TRUE age (simulation clock)
            "max_observation_age_accepted_est_s": max(r["summary"]["max_observation_age_accepted_est_s"] for r in runs),
            "invalid_messages_admitted": sum(r["corrupted_adm"] for r in runs), "duplicate_content_admitted": sum(r["dup_adm"] for r in runs),
            "accounting_identity_violations": sum(0 if all((r["acc"]["ok_sent"], r["acc"]["ok_recv"], r["acc"]["ok_proc"], r["acc"]["ok_verdict"], r["acc"]["recv"] == r["acc"]["proc"])) else 1 for r in runs),
            "replay_hash_mismatches": replay_bad, "truth_identifiers_in_wire_bytes": sum(r["truth_in_wire"] for r in runs),
            "aoi_decreases_caused_by_older_or_duplicate_or_relayed_copies": sum(r["aoi_mism"] for r in runs),
            "network_latency_max_s": float(max(nl)), "obs_to_use_latency_p99_s": dist(ou)["p99"], "aoi_p95_s": dist(aoi)["p95"], "aoi_p99_s": dist(aoi)["p99"],
            "run_hash_first_seed": runs[0]["hash"],
        }
        print(cname, "done", round(time.perf_counter() - t0, 1), "s", flush=True)
    ops = {"==": lambda a, b: a == b, "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b}
    verdicts = []
    for t in TH["thresholds"]:
        scopes = [t["scope"]] if t["scope"] != "all" else list(COND)
        vals = []
        for sc in scopes:
            v = R[sc][t["metric"]]; vals.append(v)
        worst = max(vals) if t["op"] in ("<=", "==") else min(vals)
        ok = all(ops[t["op"]](v, t["value"]) for v in vals)
        st = "REPORTED" if t["kind"] == "report_only" else ("PASS" if ok else "FAIL")
        verdicts.append({"id": t["id"], "kind": t["kind"], "scope": t["scope"], "metric": t["metric"], "op": t["op"], "threshold": t["value"], "measured": worst if t["scope"] == "all" else vals[0], "status": st})
    out = ROOT / "docs/phase2/wp-reports/evidence/wp3"; out.mkdir(parents=True, exist_ok=True)
    (out / "benchmark.json").write_text(json.dumps({"thresholds_sha256": sha, "seeds": [SEEDS[0], SEEDS[-1]], "results": R, "verdicts": verdicts}, indent=1, sort_keys=True))
    lines = ["| id | kind | scope | metric | op | threshold | measured | status |", "|---|---|---|---|---|---|---|---|"]
    f = lambda x: f"{x:.4g}" if isinstance(x, float) else str(x)
    lines += [f"| {v['id']} | {v['kind']} | {v['scope']} | {v['metric']} | {v['op']} | {f(v['threshold'])} | {f(v['measured'])} | {v['status']} |" for v in verdicts]
    (out / "benchmark_table.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines)); print("FAIL" if any(v["status"] == "FAIL" for v in verdicts) else "no FAIL")
    return 0


sys.exit(main())
