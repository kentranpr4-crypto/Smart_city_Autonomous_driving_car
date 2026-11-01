#!/usr/bin/env python3
"""Mutation 'bites' (physics + WP2 sensors/tracker/isolation): inject a fault into a COPY of the code and run the TARGETED tests that are
supposed to protect that behaviour; they MUST fail. A surviving mutant means the tests do not protect it. Never touches the working tree.
Targets are listed per mutant to keep the run fast; --full runs the whole suite per mutant."""
import pathlib, shutil, subprocess, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[1]
PHY = ["tests/physics"]
M = [  # name, file, old, new[, test targets]
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
 ("standstill_event_removed",      "backend/world.py",   "if info.stop_jerk_equiv > j_lim + 1e-9:", "if False:", ["tests/physics/test_phy05_standstill.py", "tests/physics/test_phy05_limits.py"]),
 ("standstill_jerk_magnitude_wrong","backend/dynamics.py","stop_jerk = abs(a0) / dt if v0 > 0.0 else 0.0", "stop_jerk = abs(a0) if v0 > 0.0 else 0.0", ["tests/physics/test_phy05_standstill.py"]),
 ("occlusion_ignores_height",      "backend/sensors.py", "    return min(z0, z1) < ho\n", "    return True\n", ["tests/perception/test_phy07_sensor_geometry.py"]),
 ("shadow_polygon_scale_wrong",    "backend/sensors.py", "k = hs / (hs - ho)\n    return convex_hull", "k = 1.01 * hs / (hs - ho)\n    return convex_hull", ["tests/perception/test_phy07_sensor_geometry.py"]),
 ("fov_too_wide",                  "backend/sensors.py", "<= spec.fov / 2 + 1e-12", "<= spec.fov / 2 + 0.01", ["tests/perception/test_phy07_sensor_statistics.py"]),
 ("range_too_long",                "backend/sensors.py", "r <= spec.range_m + 1e-12", "r <= spec.range_m * 1.01", ["tests/perception/test_phy07_sensor_statistics.py"]),
 ("noise_scale_wrong",             "backend/sensors.py", "a.x + spec.bias[0] + sg * nx", "a.x + spec.bias[0] + 1.2 * sg * nx", ["tests/perception/test_phy07_sensor_statistics.py"]),
 ("pd_curve_wrong",                "backend/sensor_spec.py", "math.exp((r - self.r50) / self.pd_slope)", "math.exp((r - self.r50) / (1.2 * self.pd_slope))", ["tests/perception/test_phy07_sensor_statistics.py"]),
 ("rng_consumption_depends_on_visibility","backend/sensors.py", "det_l.append(a.id)\n", "det_l.append(a.id); rng.random()\n", ["tests/perception/test_phy07_sensor_statistics.py"]),
 ("t_proc_ignored",               "backend/sensors.py", "t, t + spec.t_proc, (sx, sy, yaw, hs)", "t, t, (sx, sy, yaw, hs)", ["tests/perception/test_phy07_sensor_statistics.py"]),
 ("detections_not_shuffled",       "backend/sensors.py", "order = sorted(range(len(raw)), key=lambda i: raw[i][6])", "order = list(range(len(raw)))", ["tests/perception/test_phy07_sensor_statistics.py"]),
 ("tracker_gate_disabled",         "perception/tracker.py", "row.append(d2 if d2 <= c.gate_chi2 else big)", "row.append(d2)", ["tests/perception/test_trk_association.py"]),
 ("tracker_process_noise_too_small","perception/tracker.py", "    q = sa * sa\n    return q", "    q = sa * sa * 0.01\n    return q", ["tests/perception/test_trk_consistency.py"]),
 ("tracker_stale_expiry_after_association","perception/tracker.py", "        self._tracks = [tr for tr in self._tracks if (t - tr.t_upd) <= c.max_coast_s]\n", "", ["tests/perception/test_trk_stale_and_validation.py"]),
 ("tracker_replay_check_removed",  "perception/tracker.py", "        if f.seq <= self._last_seq: return \"seq_replay\"\n", "", ["tests/perception/test_trk_stale_and_validation.py"]),
 ("tracker_future_check_removed",  "perception/tracker.py", "if f.t_meas > t_now + c.max_future_s: return \"future\"", "pass", ["tests/perception/test_trk_stale_and_validation.py"]),
 ("tracker_duplicate_suppression_off","perception/tracker.py", "        n_merged = self._suppress_duplicates()", "        n_merged = 0", ["tests/perception/test_trk_association.py", "tests/perception/test_trk_consistency.py"]),
 ("tracker_confirms_on_first_hit", "perception/tracker.py", "sum(tr.hist) >= c.confirm_m: tr.confirmed = True", "sum(tr.hist) >= 1: tr.confirmed = True", ["tests/perception/test_trk_association.py"]),
 ("tracker_health_monitor_blind",  "perception/tracker.py", "flag = sum(self._nis) > thr", "flag = False", ["tests/perception/test_trk_occlusion_and_failure_modes.py"]),
 ("hungarian_potentials_broken",   "perception/hungarian.py", "if used[j]: u[p[j]] += delta; v[j] -= delta", "if used[j]: u[p[j]] += 0.5 * delta; v[j] -= delta", ["tests/perception/test_trk_association.py"]),
 ("tracker_imports_truth_side",    "perception/tracker.py", "import numpy as np\n", "import numpy as np\nimport backend.world\n", ["tests/perception/test_iso_ground_truth_separation.py"]),
 ("tracker_reads_frame_labels",    "perception/tracker.py", "from .stats import chi2_ppf", "from .stats import chi2_ppf\nfrom backend.sensors import FrameLabels", ["tests/perception/test_iso_ground_truth_separation.py"]),
 ("rig_leaks_labels_to_tracker",   "backend/rig.py",     "rep = tr.update(frame, t_now=world.t)", "rep = tr.update(frame, t_now=world.t); tr._leak = self.labels", ["tests/perception/test_iso_ground_truth_separation.py"]),
]
def main():
    survivors = []
    full = '--full' in sys.argv
    for item in M:
        name, rel, old, new = item[:4]
        targets = item[4] if len(item) > 4 else PHY

        tmp = pathlib.Path(tempfile.mkdtemp())
        for d in ("backend", "perception", "tests", "schemas", "scenarios"):
            shutil.copytree(ROOT / d, tmp / d, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy(ROOT / "pytest.ini", tmp / "pytest.ini")
        f = tmp / rel; s = f.read_text(encoding="utf-8")
        if s.count(old) != 1:
            print(f"{name:34} SELFTEST BROKEN (pattern count={s.count(old)})"); survivors.append(name); continue
        f.write_text(s.replace(old, new), encoding="utf-8")
        r = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "pytest", *(["tests"] if full else targets), "-k", "not golden_hash", "-x", "-q", "-p", "no:cacheprovider"], cwd=tmp, capture_output=True, text=True)
        caught = r.returncode != 0
        first = next((l for l in r.stdout.splitlines() if l.startswith("FAILED")), "")[:90]
        print(f"{name:34} {'BITES' if caught else 'SURVIVED!!'}  {first}")
        if not caught: survivors.append(name)
        shutil.rmtree(tmp, ignore_errors=True)
    print("MUTATION BITES:", "ALL CAUGHT" if not survivors else f"SURVIVORS {survivors}")
    return 1 if survivors else 0
sys.exit(main())
