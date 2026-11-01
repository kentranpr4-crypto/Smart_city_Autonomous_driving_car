#!/usr/bin/env python3
"""Mutation 'bites' for the physics gates: inject a fault into a COPY of backend/, run `pytest -m phy`; the suite MUST fail.
A surviving mutant means the tests do not protect that behaviour. Never touches the working tree."""
import pathlib, shutil, subprocess, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[1]
M = [  # name, file, old, new
 ("integrator_wrong_cubic_term",   "backend/dynamics.py", "s = v0 * dt + (2.0 * a0 + a1) / 6.0 * dt * dt", "s = v0 * dt + (a0 + a1) / 4.0 * dt * dt"),
 ("jerk_limit_removed",            "backend/dynamics.py", "a1 = tgt if abs(da) <= lim else st.a + math.copysign(lim, da)", "a1 = tgt"),
 ("friction_clip_removed",         "backend/dynamics.py", "    if abs(tgt) > mug:\n        tgt = math.copysign(mug, tgt); limited = True\n", ""),
 ("wheelbase_error_in_curvature",  "backend/dynamics.py", "t0 / p.wheelbase, t1 / p.wheelbase", "t0 / (p.wheelbase * 1.01), t1 / (p.wheelbase * 1.01)"),
 ("lateral_friction_circle_off",   "backend/dynamics.py", "    if v_ref > 1e-9:\n        t_lim", "    if False:\n        t_lim"),
 ("steer_rate_limit_removed",      "backend/dynamics.py", "d1 = d_tgt if abs(dd) <= dlim else st.delta + math.copysign(dlim, dd)", "d1 = d_tgt"),
 ("actuator_delay_ignored",        "backend/world.py",   "if issue + self.n_act <= self.n:", "if issue <= self.n:"),
 ("sat_missing_second_box_axes",   "backend/collision.py", "for ax in _axes(a) + _axes(b):", "for ax in _axes(a):"),
 ("segment_distance_endpoints_only","backend/collision.py", "    if _seg_hits_aabb(l0, l1, o[3], o[4]):\n        return 0.0\n", ""),
 ("stop_on_collision_ignored",     "backend/world.py",   "and self.scn.stop_on_collision:", "and False:"),
 ("wall_clock_noise_in_world",     "backend/world.py",   "self.t_start = _draw(spec.start_time, rng)", "self.t_start = _draw(spec.start_time, rng) + __import__('random').random() * 1e-9"),
 ("stop_snap_exact_removed",       "backend/dynamics.py", "tau = _stop_time(v0, a0, jp, dt)", "tau = dt"),
]
def main():
    survivors = []
    for name, rel, old, new in M:
        tmp = pathlib.Path(tempfile.mkdtemp())
        for d in ("backend", "tests", "schemas", "scenarios"):
            shutil.copytree(ROOT / d, tmp / d, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(ROOT / "pytest.ini", tmp / "pytest.ini")
        f = tmp / rel; s = f.read_text(encoding="utf-8")
        if s.count(old) != 1:
            print(f"{name:34} SELFTEST BROKEN (pattern count={s.count(old)})"); survivors.append(name); continue
        f.write_text(s.replace(old, new), encoding="utf-8")
        r = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "pytest", "-m", "phy", "-k", "not golden_hash", "-x", "-q", "-p", "no:cacheprovider"], cwd=tmp, capture_output=True, text=True)
        caught = r.returncode != 0
        first = next((l for l in r.stdout.splitlines() if l.startswith("FAILED")), "")[:90]
        print(f"{name:34} {'BITES' if caught else 'SURVIVED!!'}  {first}")
        if not caught: survivors.append(name)
        shutil.rmtree(tmp, ignore_errors=True)
    print("PHYSICS BITES:", "ALL CAUGHT" if not survivors else f"SURVIVORS {survivors}")
    return 1 if survivors else 0
sys.exit(main())
