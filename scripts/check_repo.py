#!/usr/bin/env python3
"""`make check`: one gate table. Statuses: PASS / FAIL / BLOCKED / NOT_CHECKED. Exit 1 only on FAIL.
BLOCKED = cannot be evaluated for an external reason (e.g. no reference image). NOT_CHECKED = no test exists yet. Neither is PASS."""
import glob, json, os, pathlib, re, subprocess, sys, xml.etree.ElementTree as ET
ROOT = pathlib.Path(__file__).resolve().parents[1]; os.chdir(ROOT)
PY = str(ROOT / ".venv/bin/python"); REG = "data/refinery/domains/smartcity-v2x-landscape"
REGISTRY_BASELINE = "66f1a64"        # commit whose data/ and .claude/ must remain byte-identical
rows = []
def add(gid, status, note): rows.append((gid, status, note))
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")   # never let a gate rewrite tracked .pyc files in .claude/
def sh(*a, **k): return subprocess.run(a, capture_output=True, text=True, env=ENV, **k)

# --- evidence integrity (never modified to make a gate pass)
# bytecode caches are build artifacts (accidentally tracked since the kit install), not evidence: excluded from the byte-identity check
r = sh("git", "diff", "--stat", REGISTRY_BASELINE, "--", "data", ".claude", ":(exclude,glob)**/__pycache__/**")
add("REG-1 registry unchanged", "PASS" if r.returncode == 0 and not r.stdout.strip() else "FAIL",
    f"git diff {REGISTRY_BASELINE} -- data .claude (excl. __pycache__) " + ("is empty" if not r.stdout.strip() else "NOT empty: " + r.stdout.strip()[:80]) + (f" [git rc={r.returncode}: {r.stderr.strip()[:60]}]" if r.returncode else ""))
r = sh(PY, ".claude/skills/refinery/refinery.py", REG)
add("REG-2 refinery.py", "PASS" if "VALIDATION PASSED" in r.stdout else "FAIL", (re.findall(r"build digest = \w+", r.stdout) or [r.stdout[-80:]])[0])
r = sh(PY, ".claude/skills/refinery/bites.py", REG)
add("REG-3 bites.py", "PASS" if "TẤT CẢ RĂNG CẮN" in r.stdout else "FAIL", f"{r.stdout.count('(build dừng)')} applicable bites all bite; {r.stdout.count('N/A')} N/A (domain does not declare those gates)")
r = sh(PY, "scripts/check_phase2_docs.py")
add("DOC-1 ref/ID integrity", "PASS" if r.returncode == 0 else "FAIL", r.stdout.strip().splitlines()[-1][:90] if r.stdout.strip() else r.stderr[-90:])
r = sh(PY, "scripts/selftest_check_phase2_docs.py")
add("DOC-2 checker selftest", "PASS" if r.returncode == 0 else "FAIL", r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "")

# --- schemas and locks
import jsonschema
bad = []
for f in sorted(glob.glob("schemas/*.json")):
    try: jsonschema.Draft202012Validator.check_schema(json.load(open(f)))
    except Exception as e: bad.append(f"{f}: {e}")
add("SCHEMA valid", "FAIL" if bad else "PASS", f"{len(glob.glob('schemas/*.json'))} schemas" + (f"; {bad[0]}" if bad else ""))
lock = [l for l in open("requirements.lock") if l.strip() and not l.startswith("#")]
nohash = [l for l in lock if "--hash=sha256:" not in l]
pc = sh(PY, "-m", "pip", "check")
add("LOCK-PY hashed + consistent", "PASS" if not nohash and pc.returncode == 0 else "FAIL", f"{len(lock)} pinned with hashes; pip check: {pc.stdout.strip()[:40]}")
pkg = json.load(open("web/package.json")); deps = {**pkg["dependencies"], **pkg["devDependencies"]}
loose = [k for k, v in deps.items() if not re.fullmatch(r"\d+\.\d+\.\d+", v)]
nl = sh("npm", "ls", "--depth=0", cwd="web")
add("LOCK-WEB exact + installed", "PASS" if not loose and os.path.exists("web/package-lock.json") and nl.returncode == 0 else "FAIL",
    f"{len(deps)} exact deps, lockfile present, npm ls rc={nl.returncode}" + (f"; loose: {loose}" if loose else ""))

# --- physics + WP2 gates (map test files -> gate ids from the junit report)
junit = "results/junit_all.xml"; os.makedirs("results", exist_ok=True)
sh(PY, "-m", "pytest", "-m", "phy or trk or iso or com or fus or cls or known_failure", f"--junitxml={junit}", "-q", "-p", "no:cacheprovider")
per, extra, kf = {}, {}, {}
com, fus, cls = {}, {}, {}
def tally(d, key, tc):
    sk = tc.find("skipped")
    if sk is not None and "xfail" in (sk.get("type", "") + sk.get("message", "")):    # strict xfail = an EXPLICIT known failure that still fails as declared
        d = kf; key = tc.get("name", "?")
    s = d.setdefault(key, {"pass": 0, "fail": 0, "skip": 0})
    s["fail" if tc.find("failure") is not None or tc.find("error") is not None else "skip" if tc.find("skipped") is not None else "pass"] += 1
for tc in ET.parse(junit).getroot().iter("testcase"):
    cn = tc.get("classname", "") + tc.get("file", "")
    m = re.search(r"test_phy0(\d)_", cn)
    if m: tally(per, f"PHY-0{m.group(1)}", tc)
    if "test_trk_consistency" in cn: tally(extra, "AC-VS-03 tracker consistency (NEES/NIS chi2)", tc)
    elif "test_trk_" in cn or "test_rig_integration" in cn: tally(extra, "WP2-TRK association/stale/occlusion/failure modes", tc)
    mc = re.search(r"test_com(\d\d)_", cn)
    if mc: tally(com, f"COM-{mc.group(1)}", tc)
    mcl = re.search(r"test_cls(\d\d)_", tc.get("name", ""))
    if mcl: tally(cls, f"CLS-{mcl.group(1)}", tc)
    mf = re.search(r"test_fus(\d\d)_", tc.get("name", ""))
    if mf: tally(fus, f"FUS-{mf.group(1)}", tc)
    if "test_known_failures" in cn: tally(kf, tc.get("name", "?"), tc)
    if "test_iso_" in cn: tally(extra, "AC-VS-06 ground-truth isolation (AST + blocked-import subprocess)", tc)
names = {1: "determinism / wall-clock independence", 2: "linear kinematics", 3: "braking distance + friction", 4: "steering / turning",
         5: "accel / jerk / steer limits (+standstill regression)", 6: "collision + pedestrian", 7: "sensors FOV/occlusion/uncertainty", 8: "communication / freshness"}
def row(label, d):
    st = "FAIL" if d["fail"] else "PASS"
    add(label, st, f"{d['pass']} passed, {d['fail']} failed, {d['skip']} skipped" + ("  (skip = golden hash from another environment, never counted as pass)" if d["skip"] else ""))
for i in range(1, 9):
    pid = f"PHY-0{i}"; d = per.get(pid)
    if not d: add(f"{pid} {names[i]}", "NOT_CHECKED", "no test exists yet (later WP)"); continue
    row(f"{pid} {names[i]}", d)
for k in sorted(extra): row(k, extra[k])
cnames = {1: "TrackMsg contract + (de)serialization", 2: "deterministic channel + replay", 3: "channel statistics", 4: "four timestamps + clock model", 5: "observation-time AoI",
          6: "fail-closed admission (+fuzz, fault injection)", 7: "source identity, provenance, frame", 8: "relay / retransmission", 9: "comm telemetry + accounting", 10: "isolation + P1 + publish policy"}
for i in range(1, 11):
    d = com.get(f"COM-{i:02d}")
    if not d: add(f"COM-{i:02d} {cnames[i]}", "NOT_CHECKED", "no test found"); continue
    row(f"COM-{i:02d} {cnames[i]}", d)
fnames = {1: "temporal alignment (original t_meas)", 2: "covariance propagation", 3: "SE(2) transform + covariance", 4: "cross-source association (no truth)", 5: "fusion B0-B4 (CI vs independence)",
          6: "provenance + duplicate evidence", 7: "stale/contradictory/missing/malformed handling", 8: "world state isolation + determinism", 9: "consistency monitor + identity interface (fail closed)", 10: "protocol integrity + evaluator"}
for i in range(1, 11):
    d = fus.get(f"FUS-{i:02d}")
    if not d: add(f"FUS-{i:02d} {fnames[i]}", "NOT_CHECKED", "no test found"); continue
    row(f"FUS-{i:02d} {fnames[i]}", d)
cnames = {1: "evidence/trust admission", 2: "risk prediction", 3: "safety supervisor (P1, caps, follower-aware)", 4: "planner/controller", 5: "physics + control-timestep integration", 6: "truth isolation of planning/",
          7: "local-only fallback", 8: "safety evaluator correctness", 9: "failure/attack taxonomy", 10: "protocol integrity + freeze"}
for i in range(1, 11):
    d = cls.get(f"CLS-{i:02d}")
    if not d: add(f"CLS-{i:02d} {cnames[i]}", "NOT_CHECKED", "no test found"); continue
    row(f"CLS-{i:02d} {cnames[i]}", d)
EXPECTED_KF = 11
kfn = len(kf)
add("KNOWN-FAILURES registry (xfail strict)", "PASS" if kfn == EXPECTED_KF else "FAIL",
    f"{kfn} explicit known failures still failing as declared (expected {EXPECTED_KF}): " + ", ".join(sorted(re.sub(r'^test_', '', k)[:4] for k in kf)) + "; an unexpected pass or a missing entry is FAIL")
img = [p for p in glob.glob("docs/references/*") if p.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
for i in range(1, 11):
    if i == 8: add("VIS-08 reference comparison", "BLOCKED" if not img else "NOT_CHECKED", "no image in docs/references/" if not img else f"{len(img)} reference image(s) present, rubric not yet run")
    else: add(f"VIS-{i:02d}", "NOT_CHECKED", "frontend city not built yet (WP6)")

w = max(len(r[0]) for r in rows)
print(f"{'GATE'.ljust(w)}  STATUS       NOTE"); print("-" * (w + 60))
for g, s, n in rows: print(f"{g.ljust(w)}  {s.ljust(11)}  {n}")
tot = {k: sum(1 for r in rows if r[1] == k) for k in ("PASS", "FAIL", "BLOCKED", "NOT_CHECKED")}
print("-" * (w + 60)); print("TOTAL", tot)
json.dump({"gates": [dict(gate=g, status=s, note=n) for g, s, n in rows], "totals": tot}, open("results/check_report.json", "w"), indent=1, ensure_ascii=False)
sys.exit(1 if tot["FAIL"] else 0)
