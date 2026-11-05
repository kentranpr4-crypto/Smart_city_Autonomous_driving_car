#!/usr/bin/env python3
"""WP5 closed-loop experiments. usage: run_wp5_closedloop.py tuning|eval [--out DIR].  `tuning` = debugging/tuning seeds (NOT claims); `eval` = preregistered final run (after the freeze).
Verifies preregistration hashes (and, for eval, the freeze record), runs 26 conditions, evaluates every preregistered threshold, writes JSON + markdown."""
import hashlib, json, pathlib, sys, time, traceback
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from closedloop import conditions as K
from closedloop.metrics import BASE, per_run, pool, truth_in_planning
from closedloop.runner import run

mode = sys.argv[1]; out = pathlib.Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else ROOT / "docs/phase2/wp-reports/evidence/wp5" / mode
PRE = json.loads((ROOT / "closedloop/preregistration.json").read_text())
DOC = (ROOT / "docs/phase2/10-wp5-closedloop-safety.md").read_text()
if mode == "eval":
    assert hashlib.sha256((ROOT / "closedloop/conditions.py").read_bytes()).hexdigest() == PRE["conditions_sha256"], "conditions.py differs from the pin in preregistration.json"
pre_sha = hashlib.sha256((ROOT / "closedloop/preregistration.json").read_bytes()).hexdigest()
if mode == "eval":
    assert pre_sha in DOC, "preregistration.json hash is not recorded in docs/phase2/10"
    from closedloop.freeze import tree_hashes
    fz = json.loads((ROOT / "closedloop/FREEZE.json").read_text())
    assert fz["tree_hashes"] == tree_hashes(), "frozen code/physics/protocol changed after the freeze record: refusing to run the final evaluation"
    assert not (ROOT / "docs/phase2/wp-reports/evidence/wp5/eval/results.json").exists(), "the final evaluation was already run; it is run ONCE (see docs/phase2/10 section 10 for any justified rerun)"
SEEDS = K.SEEDS_EVAL if mode == "eval" else K.SEEDS_TUNING
assert not (set(K.SEEDS_EVAL) & set(K.SEEDS_TUNING))
t0 = time.perf_counter(); runs, exc, reach, bad_replay, cfgs = {}, 0, 0, 0, set()
for cond in K.CONDITIONS:
    runs[cond] = []
    for s in SEEDS:
        try:
            r = run(cond, s); runs[cond].append(r); reach += truth_in_planning(r["stack"]); cfgs.add(r["config"])
        except Exception:
            exc += 1; traceback.print_exc()
    for s in K.REPLAY_SEEDS:
        a, b = run(cond, s, time_it=False), run(cond, s, time_it=False)
        bad_replay += (a["traj_hash"] != b["traj_hash"]) or (a["net_hash"] != b["net_hash"])
    print(cond, "done", round(time.perf_counter() - t0), "s", flush=True)
    for r in runs[cond]: r.pop("stack", None)
by = {c: {r["seed"]: r for r in rs} for c, rs in runs.items()}
table = {}
for c, rs in runs.items():
    if not rs: continue
    base = by.get(BASE[K.CONDITIONS[c]["scene"]])
    ref = {s: per_run(r)["traj"] for s, r in by["H_E0N"].items()} if c == "B_E3" else None
    table[c] = pool(rs, base, ref)
inv = dict(truth_in_planning=reach, replay_mismatches=int(bad_replay), run_exceptions=exc, physics_config_mismatch=len(cfgs) - 1,
           stale_or_invalid_remote_used=sum(t["stale_or_invalid_remote_used"] for t in table.values()), remote_raised_speed_events=sum(t["remote_raised_speed_events"] for t in table.values()),
           command_limit_violations=sum(t["command_limit_violations"] for t in table.values()), unauthenticated_treated_as_authenticated=sum(t["unauthenticated_treated_as_authenticated"] for t in table.values()))
def mv(th, cond, metric):
    if th["scope"] == "all": return inv[metric]
    return table[cond].get(metric)
def resolve(th):
    v = th["value"]
    if not isinstance(v, dict): return v
    vals = []
    for ref in v["of"]:
        c, m = ref.split(":"); x = table[c].get(m)
        if x is None: return None
        vals.append(x)
    b = min(vals)
    return v["factor"] * b if "factor" in v else (b - v["minus"] if "minus" in v else b + v["plus"])
ops = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, "<": lambda a, b: a < b, ">": lambda a, b: a > b, "==": lambda a, b: a == b}
verd = []
for th in PRE["thresholds"]:
    got = mv(th, th["scope"], th["metric"]); thr = resolve(th)
    if th["kind"] == "report":
        verd.append({**{k: th[k] for k in ("id", "kind", "scope", "metric")}, "op": "report", "threshold": None, "measured": got, "status": "REPORTED", "hypothesis": th.get("hypothesis")}); continue
    ok = None if got is None or thr is None else bool(ops[th["op"]](got, thr))
    st = "NOT_EVALUABLE" if ok is None else (("PASS" if ok else "FAIL") if th["kind"] == "invariant" else ("SUPPORTED" if ok else "REFUTED"))
    verd.append({**{k: th[k] for k in ("id", "kind", "scope", "metric", "op")}, "threshold": thr, "measured": got, "status": st, "hypothesis": th.get("hypothesis")})
out.mkdir(parents=True, exist_ok=True)
(out / "results.json").write_text(json.dumps({"mode": mode, "seeds": [SEEDS[0], SEEDS[-1]], "n_seeds": len(SEEDS), "preregistration_sha256": pre_sha, "invariant_counters": inv, "verdicts": verd, "table": table, "wall_s": time.perf_counter() - t0}, indent=1, sort_keys=True, default=float))
f = lambda x: "—" if x is None else (f"{x:.4g}" if isinstance(x, float) else str(x))
lines = ["| id | kind | scope | metric | op | threshold | measured | status |", "|---|---|---|---|---|---|---|---|"]
lines += [f"| {v['id']} | {v['kind']} | {v['scope']} | {v['metric']} | {v['op']} | {f(v['threshold'])} | {f(v['measured'])} | **{v['status']}** |" for v in verd]
(out / "verdicts.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines)); print("INVARIANT FAIL" if any(v["status"] == "FAIL" for v in verd) else "invariants hold", "| wall", round(time.perf_counter() - t0), "s")
