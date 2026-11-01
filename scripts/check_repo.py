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

# --- physics gates (map test files -> PHY ids; PHY-07/08 have no tests yet)
junit = "results/junit_phy.xml"; os.makedirs("results", exist_ok=True)
sh(PY, "-m", "pytest", "-m", "phy", f"--junitxml={junit}", "-q", "-p", "no:cacheprovider")
per = {}
for tc in ET.parse(junit).getroot().iter("testcase"):
    m = re.search(r"test_phy0(\d)_", tc.get("classname", "") + tc.get("file", ""))
    if not m: continue
    pid = f"PHY-0{m.group(1)}"; d = per.setdefault(pid, {"pass": 0, "fail": 0, "skip": 0})
    d["fail" if tc.find("failure") is not None or tc.find("error") is not None else "skip" if tc.find("skipped") is not None else "pass"] += 1
names = {1: "determinism / wall-clock independence", 2: "linear kinematics", 3: "braking distance + friction", 4: "steering / turning",
         5: "accel / jerk / steer limits", 6: "collision + pedestrian", 7: "sensors FOV/occlusion/uncertainty", 8: "communication / freshness"}
for i in range(1, 9):
    pid = f"PHY-0{i}"; d = per.get(pid)
    if not d: add(f"{pid} {names[i]}", "NOT_CHECKED", "no test exists yet (later WP)"); continue
    st = "FAIL" if d["fail"] else "PASS"
    add(f"{pid} {names[i]}", st, f"{d['pass']} passed, {d['fail']} failed, {d['skip']} skipped" + ("  (skip = golden hash from another environment, never counted as pass)" if d["skip"] else ""))
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
