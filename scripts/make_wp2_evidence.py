#!/usr/bin/env python3
"""Regenerate WP2 evidence under docs/phase2/wp-reports/evidence/wp2/ from real runs (no hand-typed numbers)."""
import json, math, pathlib, sys, time
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from backend.scenario import load_scenario
from backend.rig import run_with_rig
from backend.sensors import ray_blocked, ground_shadow_polygon, signed_distance_to_convex, SensorProvider
from perception.stats import chi2_ppf
from perception.tracker import Tracker, TrackerConfig, GATE_CHI2_99_2DOF
import tests.perception.test_trk_consistency as C
from tests.perception.helpers import *
from tests.perception.tracking_helpers import simulate_scene, associate, id_switches
from tests.perception.test_trk_association import two_peds, CAM, _false_confirmed_per_frame
OUT = ROOT / "docs/phase2/wp-reports/evidence/wp2"; OUT.mkdir(parents=True, exist_ok=True)
SEED = 20261101
M = {}

# ---------------- PHY-07
sh = []
for hs in (4.0, 6.0, 8.0):
    for ho in (1.0, 3.0):
        for d_near, depth in ((5.0, 1e-4), (10.0, 1e-4), (20.0, 1e-4), (10.0, 2.0), (6.0, 3.0)):
            d_far = d_near + depth; prism = (d_near + depth / 2, 0.0, 0.0, depth / 2, 5.0, ho); D = d_far * hs / (hs - ho)
            f = lambda x: ray_blocked((0, 0, hs), (x, 0, 0), prism); lo, hi = d_far + 1e-6, D + 50
            for _ in range(80):
                mid = (lo + hi) / 2; lo, hi = (mid, hi) if f(mid) else (lo, mid)
            sh.append(abs((lo + hi) / 2 - D))
M["phy07_shadow_end_error_m"] = {"cases": len(sh), "max": max(sh), "criterion": 1e-3}
spec = cctv(pose=(0, 0, 0), sigma0=0.1, sigma1=0.01, bias=(0.3, -0.2), fov_deg=120.0, range_m=60.0, **PERFECT)
noise = []
for r in (5.0, 20.0, 45.0):
    sg = 0.1 + 0.01 * r; n = 2000; fr = stream(spec, snap([ped("p", r, 0.0)]), n, seed=SEED)
    ex = np.array([(f.detections[0].x - r - 0.3) / sg for f, _ in fr]); ey = np.array([(f.detections[0].y + 0.2) / sg for f, _ in fr])
    noise.append({"range_m": r, "N": n, "chi2_stat": float((ex**2 + ey**2).sum()), "lo95": chi2_ppf(0.025, 2 * n), "hi95": chi2_ppf(0.975, 2 * n),
                  "mean_x": float(ex.mean()), "mean_y": float(ey.mean()), "corr_xy": float(np.corrcoef(ex, ey)[0, 1])})
M["phy07_noise"] = noise
sp = cctv(pose=(0, 0, 0), fov_deg=120.0, range_m=80.0, pd0=0.95, r50=35.0, pd_slope=8.0)
rows, stat = [], 0.0
for r in (10, 20, 30, 40, 50, 60):
    n = 3000; fr = stream(sp, snap([ped("p", float(r), 0.0)]), n, seed=SEED); k = sum(len(f.detections) for f, _ in fr)
    p = 0.95 / (1 + math.exp((r - 35.0) / 8.0)); z = (k - n * p) ** 2 / (n * p * (1 - p)); stat += z
    rows.append({"range_m": r, "p_model": p, "p_observed": k / n, "z2": z})
M["phy07_pd"] = {"bins": rows, "chi2_stat": stat, "chi2_95_df6": chi2_ppf(0.95, 6)}

# ---------------- tracker consistency (AC-VS-03)
cfgs = {"default (gate 99.9%, dedup)": C.MATCHED, "gate 99%, NO dedup (first draft)": TrackerConfig(sigma_a=C.SA, init_speed_sigma=C.SIGV0, gate_chi2=GATE_CHI2_99_2DOF, merge_chi2=0.0),
        "gate 99%, dedup": TrackerConfig(sigma_a=C.SA, init_speed_sigma=C.SIGV0, gate_chi2=GATE_CHI2_99_2DOF),
        "no gate": TrackerConfig(sigma_a=C.SA, init_speed_sigma=C.SIGV0, gate_chi2=1e12),
        "sigma_a 10x too small (must FAIL)": TrackerConfig(sigma_a=C.SA / 10, init_speed_sigma=C.SIGV0)}
cons = {}
for name, cfg in cfgs.items():
    v = C.verdict(*C.monte_carlo(cfg)); cons[name] = {k: (float(x) if not isinstance(x, tuple) else [float(y) for y in x]) if k != "ok" else bool(x) for k, x in v.items()}
v = C.verdict(*C.monte_carlo(C.MATCHED, declared_scale=0.5)); cons["declared sigma 0.5x (must FAIL)"] = {k: (float(x) if not isinstance(x, tuple) else [float(y) for y in x]) if k != "ok" else bool(x) for k, x in v.items()}
M["ac_vs_03"] = {"M": C.M, "K": C.K, "criteria": "inside_frac>=0.90 and 3.6<=ANEES<=4.4 and |NIS-2|<=4SE", "configs": cons}

# ---------------- association / confirmation / clutter (reported metrics; thresholds only where pre-registered in tests)
def sweep(fn, n_seeds, frames, camspec, cfg=None):
    sw, ids = [], []
    for s in range(n_seeds):
        tr, rec = simulate_scene(camspec, fn, frames, SEED + s, cfg=cfg)
        sw.append(id_switches(rec)); ids.append(len({t.track_id for r in rec for t in r["tracks"]}))
    return {"seeds": n_seeds, "runs_with_id_switch": int(sum(1 for x in sw if x)), "total_switches": int(sum(sw)), "mean_distinct_ids": float(np.mean(ids))}
spec_c = cctv(id="k", **CAM, **PERFECT)
M["association"] = {
    "crossing_miss_1.77m (pre-registered 0 in 20)": sweep(two_peds((0, 0), (1.4, 0), (16.5, -14), (0, 1.4)), 100, 200, spec_c),
    "crossing_miss_0.71m (reported only)": sweep(two_peds((0, 0), (1.4, 0), (15.0, -14), (0, 1.4)), 100, 200, spec_c),
    "crossing_miss_0.00m (reported only, collision course)": sweep(two_peds((0, 0), (1.4, 0), (14.0, -14), (0, 1.4)), 100, 200, spec_c),
    "parallel_2m_apart": sweep(two_peds((0, 0), (1.4, 0), (0, 2), (1.4, 0)), 100, 150, cctv(id="k", pose=(10.0, -20.0, math.pi / 2), height=6.0, fov_deg=120.0, range_m=70.0, **PERFECT)),
    "parallel_0.4m_apart (reported only)": sweep(two_peds((0, 0), (1.4, 0), (0, 0.4), (1.4, 0)), 100, 150, cctv(id="k", pose=(10.0, -20.0, math.pi / 2), height=6.0, fov_deg=120.0, range_m=70.0, **PERFECT)),
}
lam, r, fov = 2.0, 50.0, math.radians(120); p = lam * (math.pi * 13.8155 * 0.22) / (0.5 * r * r * fov)
M["false_tracks_per_frame"] = {"lambda": lam, "frames": 4000,
    "confirm_2of3_measured": _false_confirmed_per_frame(TrackerConfig(confirm_m=2, confirm_n=3), 4000), "confirm_2of3_analytic_estimate": lam * (1 - (1 - p) ** 2),
    "confirm_3of4_measured": _false_confirmed_per_frame(TrackerConfig(confirm_m=3, confirm_n=4), 4000)}
# ---------------- rig scenario
scn = load_scenario(ROOT / "scenarios/s01w2_occlusion_rig.yaml"); t0 = time.perf_counter(); w, rig = run_with_rig(scn, 7); wall = time.perf_counter() - t0
info = {}
for sid in ("ego_cam", "cctv_k1"):
    rows_ = {e["frame"]["seq"]: e for e in rig.log if e["frame"]["sensor_id"] == sid}; labs = rig.labels[sid]
    vis = min(s for s, l in labs.items() if "ped1" in l.visible); pub = min(s for s, e in rows_.items() if e["tracks"])
    info[sid] = {"frames": len(labs), "first_visible_t": rows_[vis]["frame"]["t_meas"], "first_visible_sensor_x": rows_[vis]["frame"]["sensor_pose"][0],
                 "previous_frame_sensor_x": rows_[vis - 1]["frame"]["sensor_pose"][0] if vis else None, "first_track_published_t": rows_[pub]["t"]}
info["analytic_first_visibility_sensor_x"] = 39.5; info["perception_log_sha256"] = rig.hexdigest(); info["wall_seconds_for_11s_sim"] = round(wall, 3)
M["rig_s01w2"] = info
(OUT / "metrics.json").write_text(json.dumps(M, indent=1) + "\n")

# ---------------- top-down SVG from the rig log (two instants)
def panel(t_want, ox, title):
    S, X0, X1, Y0, Y1 = 11.0, 22.0, 66.0, -11.0, 11.0
    px = lambda x: ox + (x - X0) * S; py = lambda y: 40 + (Y1 - y) * S
    e_e = min((e for e in rig.log if e["frame"]["sensor_id"] == "ego_cam"), key=lambda e: abs(e["t"] - t_want)); e_c = min((e for e in rig.log if e["frame"]["sensor_id"] == "cctv_k1"), key=lambda e: abs(e["t"] - t_want))
    t = e_e["t"]; ego_x = 6.0 * t; ped_y = -3.3 + 1.4 * max(0.0, t - 8.0)
    cid = f"clip{int(ox)}"
    out = [f'<clipPath id="{cid}"><rect x="{px(X0)}" y="{py(Y1)}" width="{(X1-X0)*S}" height="{(Y1-Y0)*S}"/></clipPath>',
           f'<text x="{ox}" y="18" font-weight="bold">{title} (t≈{t:.1f} s)</text>',
           f'<rect x="{px(X0)}" y="{py(Y1)}" width="{(X1-X0)*S}" height="{(Y1-Y0)*S}" fill="#f4f4f4" stroke="#999"/>',
           f'<rect x="{px(X0)}" y="{py(1.75)}" width="{(X1-X0)*S}" height="{3.5*S}" fill="#d9d9d9"/>',
           f'<rect x="{px(34)}" y="{py(-2.1)}" width="{9*S}" height="{2.4*S}" fill="#8c6d46"/><text x="{px(35)}" y="{py(-3.0)+4}" fill="#fff" font-size="10">truck 3 m</text>']
    for sid, e, col in (("ego_cam", e_e, "#2a7fff"), ("cctv_k1", e_c, "#e67e22")):
        f = e["frame"]; sx, sy, yaw, hs = f["sensor_pose"]; half = f["fov"] / 2; R = min(f["range_m"], 45)
        pts = [(sx, sy)] + [(sx + R * math.cos(yaw + a), sy + R * math.sin(yaw + a)) for a in np.linspace(-half, half, 20)]
        out.append(f'<polygon points="{" ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in pts)}" fill="{col}" opacity="0.10" stroke="{col}" stroke-width="0.6" clip-path="url(#{cid})"/>')
    out.append(f'<rect x="{px(ego_x-0.9)}" y="{py(0.9)}" width="{4.5*S}" height="{1.8*S}" fill="#2a7fff" opacity="0.8"/><text x="{px(ego_x-0.9)}" y="{py(0.9)-3}" font-size="10">ego</text>')
    out.append(f'<circle cx="{px(45)}" cy="{py(ped_y)}" r="{0.3*S:.1f}" fill="#c0392b" stroke="#000"/><text x="{px(45)+8}" y="{py(ped_y)+4}" font-size="10">pedestrian (truth)</text>')
    out.append(f'<rect x="{px(45)-4}" y="{py(8)-4}" width="8" height="8" fill="#e67e22"/><text x="{px(45)+8}" y="{py(8)+4}" font-size="10">CCTV (6 m)</text>')
    for sid, e, col in (("ego_cam", e_e, "#2a7fff"), ("cctv_k1", e_c, "#e67e22")):
        f = e["frame"]
        for d in f["detections"]: out.append(f'<circle cx="{px(d["x"]):.1f}" cy="{py(d["y"]):.1f}" r="3.5" fill="{col}" stroke="#fff" stroke-width="1" clip-path="url(#{cid})"/>')
        for tr in e["tracks"]:
            P = np.array(tr["P"]).reshape(4, 4)[:2, :2]; w_, v_ = np.linalg.eigh(P); ang = math.degrees(math.atan2(v_[1, 1], v_[0, 1]))
            out.append(f'<ellipse cx="{px(tr["x"][0]):.1f}" cy="{py(tr["x"][1]):.1f}" rx="{5*2*math.sqrt(max(w_[1],1e-6))*S:.1f}" ry="{5*2*math.sqrt(max(w_[0],1e-6))*S:.1f}" transform="rotate({-ang:.1f} {px(tr["x"][0]):.1f} {py(tr["x"][1]):.1f})" fill="none" stroke="{col}" stroke-width="1.5"/>')
    return "\n".join(out)
svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="320" font-family="sans-serif" font-size="12" style="background:#fff">',
       panel(5.0, 10, "ego far from the truck: pedestrian hidden from ego, tracked by CCTV"), panel(6.6, 560, "line of sight opens: ego now sees it"),
       '<text x="10" y="305" fill="#444">Top-down evidence from the real rig log (blue = ego sensor, orange = CCTV; dots = detections, ellipses = 2σ track covariance drawn at 5× scale for visibility). Not a VIS deliverable.</text></svg>']
(OUT / "occlusion_rig_topdown.svg").write_text("\n".join(svg) + "\n")
print(json.dumps({k: M[k] for k in ("phy07_shadow_end_error_m", "phy07_pd", "rig_s01w2", "false_tracks_per_frame")}, indent=1)[:2500])

# ---------------- test calibration (REPORT ONLY; the gate uses the single pre-registered seed): how often does each statistical test pass across seeds?
from perception.stats import chi2_cdf
spec = cctv(pose=(0, 0, 0), sigma0=0.1, sigma1=0.01, bias=(0.3, -0.2), fov_deg=120.0, range_m=60.0, **PERFECT)
n = 2000; sg = 0.1 + 0.01 * 20.0
stats = []
for s in range(60):
    fr = stream(spec, snap([ped("p", 20.0, 0.0)]), n, seed=SEED + s)
    ex = np.array([(f.detections[0].x - 20.0 - 0.3) / sg for f, _ in fr]); ey = np.array([(f.detections[0].y + 0.2) / sg for f, _ in fr])
    stats.append(float((ex**2 + ey**2).sum()))
lo, hi = chi2_ppf(0.025, 2 * n), chi2_ppf(0.975, 2 * n)
pre = stats[0]
M2 = {"noise_chi2_registered_seed": {"stat": pre, "percentile": chi2_cdf(pre, 2 * n), "interval95": [lo, hi]},
      "noise_chi2_60_seeds": {"fraction_inside_95": float(np.mean([lo <= x <= hi for x in stats])), "expected": 0.95, "mean_stat": float(np.mean(stats)), "df": 2 * n},
      "note": "the three range-parametrised noise tests share ONE seed, hence identical z-scores; they verify sigma(r) scaling, not three independent samples"}
M["calibration"] = M2
(OUT / "metrics.json").write_text(json.dumps(M, indent=1) + "\n")
print(json.dumps(M2, indent=1))
