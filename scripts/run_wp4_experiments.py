#!/usr/bin/env python3
"""WP4 experiments. usage: run_wp4_experiments.py tuning|eval [--out DIR].  `tuning` = sanity/debug seeds (results are NOT claims); `eval` = preregistered final benchmark.
Checks the preregistration hashes, runs 21 conditions x 6 methods, evaluates every preregistered threshold, writes JSON + markdown."""
import hashlib, json, pathlib, sys, time, traceback
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from experiments import conditions as K
from experiments.harness import run
from experiments.metrics import pool, run_hash, truth_objects_reachable

mode = sys.argv[1]; out = pathlib.Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else ROOT / "docs/phase2/wp-reports/evidence/wp4" / mode
PRE = json.loads((ROOT / "fusion/preregistration.json").read_text())
DOC = (ROOT / "docs/phase2/09-wp4-fusion-requirements.md").read_text()
assert hashlib.sha256((ROOT / "experiments/conditions.py").read_bytes()).hexdigest() == PRE["conditions_sha256"], "conditions.py changed after preregistration"
pre_sha = hashlib.sha256((ROOT / "fusion/preregistration.json").read_bytes()).hexdigest()
assert pre_sha in DOC, "preregistration.json hash is not the one recorded in docs/phase2/09 §8b"
SEEDS = K.SEEDS_EVAL if mode == "eval" else K.SEEDS_TUNING
assert not (set(K.SEEDS_EVAL) & set(K.SEEDS_TUNING))
t0 = time.perf_counter(); runs = {}; exc = 0; reach = 0; replay_bad = 0
for cond in K.CONDITIONS:
    runs[cond] = []
    for s in SEEDS:
        try:
            r = run(cond, s); runs[cond].append(r); reach += sum(truth_objects_reachable(f) for f in r["fusers"].values())
        except Exception:
            exc += 1; traceback.print_exc()
    for s in K.REPLAY_SEEDS:                                                    # deterministic replay: bit-identical fused output
        if mode == "eval" or s in SEEDS or True:
            a = run(cond, s, time_it=False); b = run(cond, s, time_it=False)
            replay_bad += run_hash(a) != run_hash(b)
    print(cond, "done", round(time.perf_counter() - t0), "s", flush=True)
    for r in runs[cond]: r.pop("fusers", None)
table = {c: {m: pool(rs, m) for m in K.METHODS} for c, rs in runs.items() if rs}
for c, rs in runs.items():
    sent = sum(r["comm"]["sent"] for r in rs); adm = sum(r["comm"]["admitted_ego"] for r in rs); dist = sum(r["comm"]["distinct_obs_admitted"] for r in rs)
    for m in K.METHODS:
        table[c][m]["remote_admitted_fraction"] = adm / sent; table[c][m]["distinct_obs_admitted_ratio"] = dist / sent
        table[c][m]["bandwidth_Bps"] = sum(r["comm"]["bandwidth_Bps"] for r in rs) / len(rs)
# supplementary (NOT a preregistered verdict): monitor with a 1 s warm-up chosen on TUNING seeds only (docs/phase2/09 section 9, change 3)
supp = {}
for cond in ("C0_solo_control", "C5a_bias_undeclared"):
    rs = [run(cond, s, methods=("B4_ci",), params={"monitor_warmup_s": 1.0}, time_it=False) for s in SEEDS]
    supp[cond] = {"flag_within_3s": pool(rs, "B4_ci")["monitor_flag_seed_fraction"], "flag_any": pool(rs, "B4_ci")["monitor_flag_any_seed_fraction"]}
    for r in rs: r.pop("fusers", None)
allruns = [r for rs in runs.values() for r in rs]
pooled_all = {m: pool(allruns, m) for m in K.METHODS}
inv = {"nonfinite_or_non_psd_outputs": sum(table[c][m]["nonfinite_or_non_psd_outputs"] for c in table for m in K.METHODS),
       "duplicate_evidence_double_use": sum(table[c][m]["duplicate_evidence_double_use"] for c in table for m in K.METHODS),
       "max_remote_age_used_s": max(table[c][m]["max_remote_age_used_s"] for c in table for m in K.METHODS),
       "replay_mismatches": int(replay_bad), "run_exceptions": exc, "truth_objects_reachable_from_fuser": reach}

def metric_value(th, cond=None, method=None):
    cond = cond or th["scope"]; method = method or th["method"]
    if th["scope"] == "all":
        if th["metric"] in inv: return inv[th["metric"]]
        return pooled_all[method][th["metric"]]
    return table[cond][method].get(th["metric"])

def resolve(th):
    v = th["value"]
    if not isinstance(v, dict): return v
    vals = []
    for ref in v["of"]:
        c, m = ref.split(":") if ":" in ref else (th["scope"], ref)
        x = metric_value(th, c, m)
        if x is None: return None
        vals.append(x)
    base = (min(vals) if v.get("agg", "min") == "min" else max(vals))
    if "factor" in v: return v["factor"] * base
    if "minus" in v: return base - v["minus"]
    return base + v["plus"]

ops = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, "<": lambda a, b: a < b, ">": lambda a, b: a > b, "==": lambda a, b: a == b}
verd = []
for th in PRE["thresholds"]:
    methods = K.METHODS if th["method"] == "all_methods" else [th["method"]]
    if th["method"] == "all_methods":
        got = metric_value(th, method="B4_ci"); thr = resolve(th)
    else:
        got = metric_value(th); thr = resolve(th)
    ok = None if got is None or thr is None else bool(ops[th["op"]](got, thr))
    status = "NOT_EVALUABLE" if ok is None else (("PASS" if ok else "FAIL") if th["kind"] == "invariant" else ("SUPPORTED" if ok else "REFUTED"))
    verd.append({"id": th["id"], "kind": th["kind"], "scope": th["scope"], "metric": th["metric"], "method": th["method"], "op": th["op"], "threshold": thr, "measured": got, "status": status, "hypothesis": th.get("hypothesis")})
out.mkdir(parents=True, exist_ok=True)
(out / "results.json").write_text(json.dumps({"mode": mode, "seeds": [SEEDS[0], SEEDS[-1]], "n_seeds": len(SEEDS), "preregistration_sha256": pre_sha, "invariant_counters": inv, "supplementary_monitor_warmup_1s": supp, "verdicts": verd, "table": table,
                                              "pooled_all_conditions": {m: {k: v for k, v in d.items() if not k.endswith("ci95")} for m, d in pooled_all.items()}, "wall_s": time.perf_counter() - t0}, indent=1, sort_keys=True, default=float))
f = lambda x: "—" if x is None else (f"{x:.4g}" if isinstance(x, float) else str(x))
lines = ["| id | kind | scope | method | metric | op | threshold | measured | status |", "|---|---|---|---|---|---|---|---|---|"]
lines += [f"| {v['id']} | {v['kind']} | {v['scope']} | {v['method']} | {v['metric']} | {v['op']} | {f(v['threshold'])} | {f(v['measured'])} | **{v['status']}** |" for v in verd]
(out / "verdicts.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines)); print("INVARIANT FAIL" if any(v["status"] == "FAIL" for v in verd) else "invariants hold", "| wall", round(time.perf_counter() - t0), "s")
