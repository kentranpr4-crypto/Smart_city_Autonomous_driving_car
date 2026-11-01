#!/usr/bin/env python3
"""Regenerate WP1 evidence under docs/phase2/wp-reports/evidence/wp1/ from a real run (no hand-edited numbers)."""
import json, pathlib, sys, time, platform
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from backend.run import run_scenario
from backend.params import VehicleParams, G
from tests.physics.reference import stop_distance, ramp_motion, numeric_stop_distance
from tests.physics.helpers import make, run, vframe
OUT = ROOT / "docs/phase2/wp-reports/evidence/wp1"; OUT.mkdir(parents=True, exist_ok=True)
P = VehicleParams()

# 1) sandbox runs -> manifests + head/tail of telemetry
for name, f in (("s00a", "s00a_physics_sandbox_brake_early.yaml"), ("s00b", "s00b_physics_sandbox_brake_late.yaml")):
    m, _ = run_scenario(ROOT / "scenarios" / f, 7, OUT / name)
    lines = (OUT / name / "telemetry.jsonl").read_text().splitlines()
    (OUT / name / "telemetry.jsonl").write_text("\n".join(lines[:4] + ["... (%d lines total; full file regenerable: python -m backend.run scenarios/%s --seed 7)" % (len(lines), f)] + lines[-3:]) + "\n")

# 2) PHY-03 error table across the whole grid vs closed form and vs independent numeric integrator
rows = []
for v0 in (5.0, 7.0, 9.0, 11.0):
    for mode in ("emergency", "comfort"):
        for mu in (0.5, 0.8):
            a_brk, j = (P.a_brk_emergency, P.j_emergency) if mode == "emergency" else (P.a_brk_comfort, P.j_comfort)
            a_c = min(a_brk, mu * G)
            d = make(duration=40.0, stop_when_all_stopped=True, road={"mu": mu},
                     vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": v0}, "script": [{"t": 0.5, "a_cmd": -100.0, "mode": mode}]}])
            _, fr, _ = run(d); sim = vframe(fr[-1])["x"] - v0 * 0.5
            rows.append({"v0": v0, "mode": mode, "mu": mu, "a_c": a_c, "sim_m": sim, "closed_form_m": stop_distance(v0, a_c, j, P.t_act),
                         "numeric_ref_m": numeric_stop_distance(v0, a_c, j, P.t_act)})
for r in rows:
    r["err_closed_m"] = abs(r["sim_m"] - r["closed_form_m"]); r["err_numeric_m"] = abs(r["sim_m"] - r["numeric_ref_m"])
(OUT / "phy03_error_table.json").write_text(json.dumps(rows, indent=1) + "\n")
mx = lambda k: max(r[k] for r in rows)
summary = {"cases": len(rows), "max_err_vs_closed_form_m": mx("err_closed_m"), "max_err_vs_numeric_m": mx("err_numeric_m"),
           "criteria_m": {"closed_form": 1e-3, "numeric": 5e-3}}

# 3) SVG: braking profile (sim vs closed form) at 30 km/h, emergency, mu=0.8
v0 = 30 / 3.6
d = make(duration=3.0, road={"mu": 0.8}, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": v0}, "script": [{"t": 0.0, "a_cmd": -6.0, "mode": "emergency"}]}])
_, fr, _ = run(d)
ts = [f["t"] for f in fr]; vs = [vframe(f)["v"] for f in fr]; as_ = [vframe(f)["a"] for f in fr]
ref = [ramp_motion(v0, -6.0, P.j_emergency, P.t_act, t) for t in ts]
ref_v = [max(r[1], 0.0) for r in ref]; ref_a = [r[2] if r[1] > 0 else 0.0 for r in ref]      # reference clamped at standstill
W, PH, ml, mr, mt, gap = 760, 230, 70, 30, 75, 60
def pth(xs, ys, ymin, ymax, top):
    pts = [(ml + x / 3.0 * (W - ml - mr), top + (1 - (y - ymin) / (ymax - ymin)) * PH) for x, y in zip(xs, ys)]
    return " ".join(f"{'M' if k == 0 else 'L'}{x:.1f},{y:.1f}" for k, (x, y) in enumerate(pts))
Ht = mt + 2 * (PH + gap) + 20
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{Ht}" font-family="sans-serif" font-size="12" style="background:#fff">',
       f'<text x="{ml}" y="20" font-weight="bold">WP1 evidence: emergency braking from 30 km/h (mu=0.8, cmd at t=0, t_act=0.15 s, jerk 10 m/s³, a=6 m/s²)</text>',
       f'<text x="{ml}" y="38" fill="#444">blue = simulation (100 Hz) · thick orange = closed-form reference (independent code, clamped at standstill)</text>']
for panel, (lab, sim, rf, lo, hi, ticks) in enumerate((("speed v [m/s]", vs, ref_v, 0, 9, (0, 3, 6, 9)), ("acceleration a [m/s²]", as_, ref_a, -7, 1, (-6, -4, -2, 0)))):
    top = mt + panel * (PH + gap)
    svg.append(f'<rect x="{ml}" y="{top}" width="{W-ml-mr}" height="{PH}" fill="none" stroke="#999"/>')
    svg.append(f'<text x="{ml}" y="{top-6}" font-weight="bold">{lab}</text>')
    for tk in ticks:
        y = top + (1 - (tk - lo) / (hi - lo)) * PH
        svg.append(f'<line x1="{ml}" x2="{W-mr}" y1="{y:.1f}" y2="{y:.1f}" stroke="#eee"/><text x="{ml-6}" y="{y+4:.1f}" text-anchor="end">{tk}</text>')
    for xs_ in (0, 0.5, 1, 1.5, 2, 2.5, 3):
        x = ml + xs_ / 3.0 * (W - ml - mr)
        svg.append(f'<text x="{x:.1f}" y="{top+PH+16}" text-anchor="middle">{xs_}</text>')
    svg.append(f'<text x="{W//2}" y="{top+PH+32}" text-anchor="middle" fill="#444">time [s]</text>')
    svg.append(f'<path d="{pth(ts, rf, lo, hi, top)}" stroke="#e67e22" stroke-width="6" fill="none" opacity="0.55"/>')
    svg.append(f'<path d="{pth(ts, sim, lo, hi, top)}" stroke="#1f4e9e" stroke-width="1.5" fill="none"/>')
svg.append("</svg>")
(OUT / "braking_profile_vs_closed_form.svg").write_text("\n".join(svg) + "\n")

# 4) throughput (informational, NOT a gate): wall time of a 10 s sandbox scenario
t0 = time.perf_counter(); _, _, _ = run(make(duration=10.0, vehicles=[{"id": "ego", "init": {"x": 0.0, "y": 0.0, "psi": 0.0, "v": 8.0}, "script": [{"t": 1.0, "a_cmd": -2.0}]}])); dt = time.perf_counter() - t0
summary["throughput"] = {"sim_seconds": 10.0, "wall_seconds": round(dt, 3), "real_time_factor": round(10.0 / dt, 1), "note": "informational; one vehicle; includes telemetry capture in memory"}
summary["environment"] = {"python": platform.python_version(), "platform": platform.platform()}
(OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n"); print(json.dumps(summary, indent=1))
