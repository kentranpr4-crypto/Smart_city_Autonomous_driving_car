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
 # ---- WP3 communication mutants (targets: tests/comm unless stated)
 ("com_crc_check_removed",         "comm/trackmsg.py", "            ok = crc_of(d) == c", "            ok = True", ["tests/comm"]),
 ("com_dedup_removed",             "comm/admission.py", "        if key[1] in seen:\n            return rej(\"duplicate\", m, age_r, age_p)\n", "", ["tests/comm"]),
 ("com_replay_window_removed",     "comm/admission.py", "        if mx >= 0 and key[1] < mx - c.reorder_window:\n            return rej(\"replay_old\", m, age_r, age_p)\n", "", ["tests/comm"]),
 ("com_future_check_removed",      "comm/admission.py", "        if age_p < -c.clock_tolerance_s:\n            return rej(\"future_obs\", m, age_r, age_p)\n", "", ["tests/comm"]),
 ("com_ttl_check_removed",         "comm/admission.py", "        if age_p > m.ttl_s:\n            return rej(\"expired_ttl\", m, age_r, age_p)\n", "", ["tests/comm"]),
 ("com_stale_check_removed",       "comm/admission.py", "        if age_p > c.max_age_s:\n            return rej(\"stale\", m, age_r, age_p)\n", "", ["tests/comm"]),
 ("com_stale_uses_recv_not_proc",  "comm/admission.py", "        if age_p > c.max_age_s:", "        if age_r > c.max_age_s:", ["tests/comm"]),
 ("com_nonfinite_check_removed",   "comm/admission.py", "        if not all(math.isfinite(v) for v in _all_numbers(m)):\n            return \"non_finite\"\n", "", ["tests/comm"]),
 ("com_covariance_not_checked",    "comm/admission.py", "                return \"bad_covariance\"", "                pass", ["tests/comm"]),
 ("com_frame_check_removed",       "comm/admission.py", "        if m.frame != FRAME:\n            return \"unsupported_frame\"\n", "", ["tests/comm"]),
 ("com_origin_check_removed",      "comm/admission.py", "        if m.origin_frame_id != c.origin_id:\n            return \"frame_mismatch\"\n", "", ["tests/comm"]),
 ("com_units_check_removed",       "comm/admission.py", "        if m.units != UNITS:\n            return \"units_mismatch\"\n", "", ["tests/comm"]),
 ("com_allowlist_removed",         "comm/admission.py", "        if self.registry.sources.get(o.source_id) != o.source_type or", "        if False and self.registry.sources.get(o.source_id) != o.source_type or", ["tests/comm"]),
 ("com_confirmation_policy_off",   "comm/admission.py", "        if o.provenance.get(\"confirmation\") not in c.accepted_confirmations:\n            return \"unsupported_confirmation\"\n", "", ["tests/comm"]),
 ("com_hop_limit_removed",         "comm/admission.py", "        if m.hop_count > c.max_hops or", "        if False and m.hop_count > c.max_hops or", ["tests/comm"]),
 ("com_loop_check_removed",        "comm/admission.py", "        if c.receiver_id in m.relay_path or", "        if False and c.receiver_id in m.relay_path or", ["tests/comm"]),
 ("com_reject_changes_state",      "comm/admission.py", "        def rej(reason, m=None, age_r=None, age_p=None):\n            self.stats[reason] += 1\n", "        def rej(reason, m=None, age_r=None, age_p=None):\n            self.stats[reason] += 1\n            if m is not None: self._max_seq[m.origin.source_id] = max(self._max_seq.get(m.origin.source_id, -1), m.origin.orig_seq)\n", ["tests/comm"]),
 ("com_aoi_resets_on_older",       "comm/aoi.py", "if self.fresh is not None and not (t_obs > self.fresh):", "if self.fresh is not None and not (t_obs > self.fresh - 1e9):", ["tests/comm"]),
 ("com_aoi_average_wrong",         "comm/aoi.py", "total += a0 * dt + 0.5 * dt * dt", "total += a0 * dt + dt * dt", ["tests/comm"]),
 ("com_store_overwrites_with_older","comm/store.py", "if cur is not None and not (m.t_meas > cur[1]):", "if False:", ["tests/comm"]),
 ("com_store_purge_ignores_age",   "comm/store.py", "if t_local - tm > self.max_age_s or t_local > exp]", "if False]", ["tests/comm"]),
 ("com_store_key_not_source_scoped","comm/trackmsg.py", "    return (m.origin.source_id, t.track_id)", "    return (\"*\", t.track_id)", ["tests/comm"]),
 ("com_channel_rng_conditional",   "comm/channel.py", "        u = self.rng.random(N_DRAWS)\n", "        u = self.rng.random(N_DRAWS) if not any(t0 <= t_now < t1 for t0, t1 in c.blackouts) else self.rng.random(1).repeat(N_DRAWS)\n", ["tests/comm"]),
 ("com_channel_ge_wrong_recovery",   "comm/channel.py", "else not (u[1] < p_bg)", "else not (u[1] < p_gb)", ["tests/comm"]),
 ("com_channel_delay_ignores_jitter","comm/channel.py", "delay = c.base_delay_s + u[2] * c.jitter_s", "delay = c.base_delay_s + 0.5 * c.jitter_s", ["tests/comm"]),
 ("com_channel_dup_never",         "comm/channel.py", "if u[3] < c.dup_p:", "if False:", ["tests/comm"]),
 ("com_pump_after_publish",        "comm/network.py", "        self.pump(t_sim)\n        for pub, key, dsts in self.pubs:", "        for pub, key, dsts in self.pubs:", ["tests/comm"]),
 ("com_relay_resets_observation_time","comm/trackmsg.py", "replace(m, msg_id=f\"{node_id}:{tx_seq}\", tx=Tx(node_id, tx_seq, clock_id), t_sent=t_sent_local,", "replace(m, msg_id=f\"{node_id}:{tx_seq}\", tx=Tx(node_id, tx_seq, clock_id), t_sent=t_sent_local, t_meas=t_sent_local,", ["tests/comm"]),
 ("com_relay_hop_not_incremented", "comm/trackmsg.py", "hop_count=m.hop_count + 1, relay_path", "hop_count=m.hop_count, relay_path", ["tests/comm"]),
 ("com_publisher_uses_publish_time","comm/publisher.py", "        obs = tracker.last_frame_time\n", "        obs = t_sim\n", ["tests/comm"]),
 ("com_publisher_republishes_old", "comm/publisher.py", "if not math.isfinite(obs) or not obs > self._last_obs:", "if not math.isfinite(obs):", ["tests/comm"]),
 ("com_publisher_policy_off",      "comm/publisher.py", "if label != \"3of4\" and not self.experimental:", "if False:", ["tests/comm"]),
 ("com_publisher_tentative_tracks","comm/publisher.py", "tracker.tracks(obs, confirmed_only=True)", "tracker.tracks(obs, confirmed_only=False)", ["tests/comm"]),
 ("com_comm_imports_truth_side",   "comm/network.py", "import heapq", "import heapq\nimport backend.world", ["tests/comm"]),
 ("com_comm_reads_wall_clock",     "comm/clock.py", "        return t_sim * (1.0 + self.drift_ppm * 1e-6) + self.offset_s", "        import time\n        return t_sim * (1.0 + self.drift_ppm * 1e-6) + self.offset_s + time.time() * 0.0", ["tests/comm"]),
 ("com_telemetry_drops_events",    "comm/telemetry.py", "        self._h.update(b); self.events.append(rec)", "        self._h.update(b); self.events.append(rec) if rec[\"type\"] != \"drop\" else None", ["tests/comm"]),
 # ---- WP4 fusion mutants (targets: tests/fusion)
 ("fus_q_scale_wrong",             "fusion/model.py", "    q = sigma_a * sigma_a\n", "    q = 0.5 * sigma_a * sigma_a\n", ["tests/fusion"]),
 ("fus_no_covariance_growth",      "fusion/model.py", "    Pn = Fm @ P @ Fm.T + Q(abs(dt), sigma_a)", "    Pn = Fm @ P @ Fm.T", ["tests/fusion"]),
 ("fus_time_sigma_ignored",        "fusion/model.py", "    if time_sigma_s > 0.0:", "    if False:", ["tests/fusion"]),
 ("fus_predicts_from_arrival_not_obs","fusion/fuser.py", "if abs(t_now - e.t) > 0 else (x, P)", "if False else (x, P)", ["tests/fusion"]),
 ("fus_transform_jacobian_sign",   "fusion/transform.py", "dR = np.array([[-s, -c], [c, -s]])                           # dR/dtheta", "dR = np.array([[s, c], [c, -s]])", ["tests/fusion"]),
 ("fus_transform_ignores_uncertainty","fusion/transform.py", "Pn = Jx @ P @ Jx.T + Ju @ Sig @ Ju.T", "Pn = Jx @ P @ Jx.T", ["tests/fusion"]),
 ("fus_transform_accepts_wrong_frame","fusion/transform.py", "if est.frame != self.src_frame:", "if False:", ["tests/fusion"]),
 ("fus_association_gate_removed",  "fusion/associate.py", "if v <= gate and not conflict:", "if not conflict:", ["tests/fusion"]),
 ("fus_class_constraint_removed",  "fusion/associate.py", "conflict = class_gate and ca != cb and \"unknown\" not in (ca, cb)", "conflict = False", ["tests/fusion"]),
 ("fus_association_not_optimal",   "fusion/associate.py", "pairs = [(i, j, float(raw[i, j])) for i, j in linear_sum_assignment(cost.tolist()) if cost[i, j] < BIG]", "pairs = [(i, int(np.argmin(cost[i])), float(raw[i, int(np.argmin(cost[i]))])) for i in range(len(A)) if cost[i].min() < BIG]", ["tests/fusion"]),
 ("fus_ambiguity_never_flagged",   "fusion/associate.py", "if any(c < BIG and c <= v + ambiguity_margin for c in others):", "if False:", ["tests/fusion"]),
 ("fus_info_fusion_averages_P",    "fusion/combine.py", "    Y = sum(_spd_inv(P) for _, P in items)\n    P = _spd_inv(Y)", "    Y = sum(_spd_inv(P) for _, P in items) / len(items)\n    P = _spd_inv(Y)", ["tests/fusion"]),
 ("fus_ci_omega_fixed_half",       "fusion/combine.py", "    w = min(cands, key=lambda c: (at(c)[0], c))", "    w = 0.5", ["tests/fusion"]),
 ("fus_ci_is_information_fusion",  "fusion/combine.py", "        return (np.trace(Pw) if criterion == \"trace\" else np.linalg.det(Pw)), Pw", "        return 0.0, _spd_inv(I1 + I2)", ["tests/fusion"]),
 ("fus_naive_sums_covariances",    "fusion/combine.py", "return xs.mean(axis=0), Ps.mean(axis=0), ()", "return xs.mean(axis=0), Ps.sum(axis=0), ()", ["tests/fusion"]),
 ("fus_evidence_ledger_removed",   "fusion/fuser.py", "            if any(ev in used_ev for ev in it[0].evidence):\n                dup_ev += 1; continue\n", "", ["tests/fusion"]),
 ("fus_duplicate_ref_keeps_oldest","fusion/fuser.py", "                if e.t <= old.t: continue", "                if e.t >= old.t: continue", ["tests/fusion"]),
 ("fus_stale_check_removed",       "fusion/fuser.py", "        if e.kind == \"remote\" and age > p[\"max_remote_age_s\"] + 1e-9:\n            return \"stale\", None\n", "", ["tests/fusion"]),
 ("fus_future_check_removed",      "fusion/fuser.py", "        if e.t > t_now + 1e-6:\n            return \"future\", None\n", "", ["tests/fusion"]),
 ("fus_horizon_check_removed",     "fusion/fuser.py", "        if age > p[\"max_horizon_s\"] + 1e-9:\n            return \"horizon\", None\n", "", ["tests/fusion"]),
 ("fus_nonfinite_check_removed",   "fusion/fuser.py", "        if x.shape != (4,) or not (np.all(np.isfinite(x)) and np.all(np.isfinite(P)) and math.isfinite(e.t)):\n            return \"nonfinite\", None\n", "", ["tests/fusion"]),
 ("fus_psd_check_removed",         "fusion/fuser.py", "            return \"bad_covariance\", None", "            pass", ["tests/fusion"]),
 ("fus_frame_check_removed",       "fusion/fuser.py", "        if e.frame != p[\"supported_frame\"]:\n            return \"frame_mismatch\", None", "        if False:\n            return \"frame_mismatch\", None", ["tests/fusion"]),
 ("fus_auth_policy_ignored",       "fusion/fuser.py", "if e.kind == \"remote\" and p[\"require_assurance\"] == AUTHENTICATED and", "if False and", ["tests/fusion"]),
 ("fus_verifier_claims_authenticated","fusion/identity.py", "        return ALLOWLIST_ONLY\n\n\nclass _Unsafe", "        return AUTHENTICATED\n\n\nclass _Unsafe", ["tests/fusion"]),
 ("fus_self_track_not_suppressed", "fusion/fuser.py", "if float(r @ np.linalg.solve(S, r)) <= self._self_gate:", "if False:", ["tests/fusion"]),
 ("fus_quarantine_inverted",       "fusion/fuser.py", "quarantined = p[\"quarantine_on_flag\"] and key[0] and self.monitor.is_flagged(src)", "quarantined = p[\"quarantine_on_flag\"] and key[0] and not self.monitor.is_flagged(src)", ["tests/fusion"]),
 ("fus_monitor_threshold_too_high","fusion/monitor.py", "self.hi = chi2_ppf(conf, 2 * window)", "self.hi = 10 * chi2_ppf(conf, 2 * window)", ["tests/fusion"]),
 ("fus_monitor_no_hysteresis",     "fusion/monitor.py", "elif self.flagged.get(source, False) and s < self.lo:", "elif self.flagged.get(source, False) and s < self.hi:", ["tests/fusion"]),
 ("fus_fid_not_persistent",        "fusion/fuser.py", "        for _, fid, i in sorted(cand):\n            if out[i] is None and fid not in taken:", "        for _, fid, i in sorted(cand):\n            if False and out[i] is None and fid not in taken:", ["tests/fusion"]),
 ("fus_b0_uses_remote",            "fusion/fuser.py", "use_local = self.method != \"B1_remote\"; use_remote = self.method != \"B0_local\"", "use_local = self.method != \"B1_remote\"; use_remote = True", ["tests/fusion"]),
 ("fus_imports_backend",           "fusion/fuser.py", "import numpy as np\n", "import numpy as np\nimport backend.world\n", ["tests/fusion"]),
 ("fus_reads_wall_clock",          "fusion/model.py", "import numpy as np\n", "import numpy as np\nimport time\n", ["tests/fusion"]),
 ("fus_adapter_uses_arrival_time", "fusion/adapters.py", "return Estimate(st.ref[0], st.ref[1], st.t_meas,", "return Estimate(st.ref[0], st.ref[1], st.t_meas + st.age_est,", ["tests/fusion"]),
 ("fus_evaluator_gate_ignored",    "experiments/metrics.py", "if cost[i][j] <= gate}", "if True}", ["tests/fusion"]),
 ("fus_evaluator_nees_uses_diag",  "experiments/metrics.py", "n = float(e @ np.linalg.solve(P, e))", "n = float(e @ e / P[0, 0])", ["tests/fusion"]),
 # ---- WP5 planning / closed-loop mutants (targets: tests/closedloop unit gates; integration mutants run the integration file)
 ("pln_trust_no_persistence",       "planning/trust.py", "            elif n < self.prm[\"min_persistence_cycles\"]:", "            elif False:", ["tests/closedloop/test_cls01_02_trust_and_risk.py"]),
 ("pln_trust_stale_not_rejected",   "planning/trust.py", "f.max_remote_age_s > self.prm[\"remote_max_age_s\"] + 1e-9 or ", "", ["tests/closedloop/test_cls01_02_trust_and_risk.py"]),
 ("pln_trust_ambiguous_accepted",   "planning/trust.py", " or \"ambiguous_association\" in f.flags:", ":", ["tests/closedloop/test_cls01_02_trust_and_risk.py"]),
 ("pln_trust_single_source_corroborated","planning/trust.py", "            elif len(remote) >= 2:", "            elif len(remote) >= 1:", ["tests/closedloop/test_cls01_02_trust_and_risk.py"]),
 ("pln_trust_claims_authenticated", "planning/trust.py", "assurance = \"local\" if not remote else \"allowlist-only\"", "assurance = \"local\" if not remote else \"authenticated\"", ["tests/closedloop/test_cls01_02_trust_and_risk.py"]),
 ("pln_risk_no_uncertainty_growth", "planning/risk.py", "sd = math.sqrt(max(pyy + 2.0 * t * pyv + t * t * pvv, 1e-9))", "sd = math.sqrt(max(pyy, 1e-9))", ["tests/closedloop/test_cls01_02_trust_and_risk.py"]),
 ("pln_risk_areq_wrong",            "planning/risk.py", "a_req = (v * v) / (2.0 * max(d, 0.1)) if v > 0 else 0.0", "a_req = (v * v) / (max(d, 0.1)) if v > 0 else 0.0", ["tests/closedloop/test_cls01_02_trust_and_risk.py"]),
 ("pln_risk_beside_rule_removed",   "planning/risk.py", "    beside = h.x <= xf - 0.3 ", "    beside = False and h.x <= xf - 0.3 ", ["tests/closedloop/test_cls01_02_trust_and_risk.py"]),
 ("pln_risk_creep_floor_removed",   "planning/risk.py", ", prm.get(\"creep_speed\", 0.0))   # creep floor", ", 0.0)   # creep floor", ["tests/closedloop/test_cls01_02_trust_and_risk.py"]),
 ("pln_risk_vcap_no_reaction",      "planning/risk.py", "            t_rd = 0.4", "            t_rd = 0.0", ["tests/closedloop/test_cls01_02_trust_and_risk.py"]),
 ("pln_planner_margin_removed",     "planning/planner.py", "ah = -min(max(r.a_req * 1.15, 0.5), cap)", "ah = -min(max(r.a_req * 1.0, 0.5), cap)", ["tests/closedloop/test_cls03_04_supervisor_planner.py"]),
 ("pln_planner_cruise_unbounded",   "planning/planner.py", "a = max(-prm[\"a_comf\"], min(prm[\"a_accel\"], self.v_ref - ego.v))", "a = self.v_ref - ego.v", ["tests/closedloop/test_cls03_04_supervisor_planner.py"]),
 ("pln_planner_hazard_ignores_threshold","planning/planner.py", "r.p_conflict >= prm[\"p_thr\"] and ", "", ["tests/closedloop/test_cls03_04_supervisor_planner.py", "tests/closedloop/test_cls01_02_trust_and_risk.py"]),
 ("pln_planner_los_rect_broken",    "planning/planner.py", "            if q < 0: return False", "            if q < 0: return True", ["tests/closedloop/test_cls03_04_supervisor_planner.py"]),
 # EQUIVALENT (documented, not executed): pln_sup_p1_min_removed  `a_prop = min(a_all, a_local)` -> `a_all`. a_all is the planner minimum over a SUPERSET of the items used for a_local, so a_all <= a_local structurally; the min() is defensive redundancy.
 ("pln_sup_advisory_cap_emergency", "planning/supervisor.py", "return {LOCAL: p[\"a_emerg\"], CORROBORATED: p[\"corroborated_cap\"], ADVISORY: p[\"advisory_cap\"]}[level]", "return {LOCAL: p[\"a_emerg\"], CORROBORATED: p[\"corroborated_cap\"], ADVISORY: p[\"a_emerg\"]}[level]", ["tests/closedloop/test_cls03_04_supervisor_planner.py"]),
 ("pln_sup_follower_cap_removed",   "planning/supervisor.py", "            if f_cap < -a_prop:", "            if False:", ["tests/closedloop/test_cls03_04_supervisor_planner.py"]),
 ("pln_sup_follower_formula_wrong", "planning/supervisor.py", "need = vf * tr + vf * vf / (2.0 * af) - g ", "need = vf * tr - g ", ["tests/closedloop/test_cls03_04_supervisor_planner.py"]),
 ("pln_sup_contradiction_off",      "planning/supervisor.py", "(not self.naive) and h.level == ADVISORY and self._contradicted(h, ego, local)", "False", ["tests/closedloop/test_cls03_04_supervisor_planner.py", "tests/closedloop/test_cls09_failure_taxonomy.py"]),
 ("pln_sup_contradiction_ignores_occluders","planning/supervisor.py", "        if occluded((sx, 0.0), (h.x, h.y), p.get(\"occluders\", ())):\n            return False ", "        if False:\n            return False ", ["tests/closedloop/test_cls03_04_supervisor_planner.py"]),
 ("pln_sup_follower_risk_not_flagged","planning/supervisor.py", "        if a_local < -f_cap and not self.naive and f_cap < INF:", "        if False:", ["tests/closedloop/test_cls03_04_supervisor_planner.py"]),
 ("pln_sup_mode_threshold_wrong",   "planning/supervisor.py", "mode = \"emergency\" if a_cmd < -p[\"a_comf\"] - 0.05 else \"comfort\"", "mode = \"emergency\" if a_cmd < -1.0 else \"comfort\"", ["tests/closedloop/test_cls03_04_supervisor_planner.py"]),
 ("pln_sup_no_command_clip",        "planning/supervisor.py", "        a_cmd = max(-p[\"a_emerg\"], min(p[\"a_accel\"], a_cmd))\n", "", ["tests/closedloop/test_cls03_04_supervisor_planner.py"]),
 ("pln_stack_nominal_reads_remote", "planning/stack.py", "if self.planner in (\"guarded\", \"naive\"):", "if True:", ["tests/closedloop/test_cls05_06_07_integration_isolation_fallback.py"]),
 ("pln_stack_naive_uses_ci",        "planning/stack.py", "method = \"B3_info\" if naive else", "method = \"B4_ci\" if naive else", ["tests/closedloop/test_cls09_failure_taxonomy.py", "tests/closedloop/test_cls05_06_07_integration_isolation_fallback.py"]),
 ("pln_imports_backend",            "planning/planner.py", "import math\n", "import math\nimport backend.world\n", ["tests/closedloop/test_cls05_06_07_integration_isolation_fallback.py"]),
 ("pln_reads_wall_clock",           "planning/risk.py", "import math\n", "import math\nimport time\n", ["tests/closedloop/test_cls05_06_07_integration_isolation_fallback.py"]),
 ("cls_eval_unnecessary_threshold", "closedloop/metrics.py", "unnecessary=any(cf >= 1.5 for _, cf in r[\"onsets\"])", "unnecessary=any(cf >= 0.5 for _, cf in r[\"onsets\"])", ["tests/closedloop/test_cls08_evaluator.py"]),
 ("cls_eval_near_miss_threshold",   "closedloop/metrics.py", "r[\"min_clearance\"] < 1.0,", "r[\"min_clearance\"] < 0.1,", ["tests/closedloop/test_cls08_evaluator.py"]),
 ("cls_eval_ece_wrong",             "closedloop/metrics.py", "if m.any(): e += m.mean() * abs(p[m].mean() - y[m].mean())", "if m.any(): e += abs(p[m].mean() - y[m].mean())", ["tests/closedloop/test_cls08_evaluator.py"]),
 ("cls_eval_jerk_ignores_step",     "closedloop/metrics.py", "max_jerk=float(np.max(np.abs(np.diff(a))) / dt)", "max_jerk=float(np.max(np.abs(np.diff(a))))", ["tests/closedloop/test_cls08_evaluator.py"]),
 ("cls_eval_censoring_removed",     "closedloop/metrics.py", "t_comp=(r[\"t_goal\"] if r[\"t_goal\"] is not None else K.DURATION)", "t_comp=(r[\"t_goal\"] if r[\"t_goal\"] is not None else 0.0)", ["tests/closedloop/test_cls08_evaluator.py"]),
 ("cls_eval_stale_counter_off",     "closedloop/metrics.py", "stale=sum(1 for t in ticks if t[\"age\"] > 0.5 + ABOVE)", "stale=0", ["tests/closedloop/test_cls08_evaluator.py"]),
]
def main():
    survivors = []
    full = '--full' in sys.argv
    only = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--only=')), None)
    for item in M:
        if only and not any(item[0].startswith(o) or item[0] == o for o in only.split(',')): continue
        name, rel, old, new = item[:4]
        targets = item[4] if len(item) > 4 else PHY

        tmp = pathlib.Path(tempfile.mkdtemp())
        for d in ("backend", "perception", "comm", "integration", "fusion", "experiments", "planning", "closedloop", "tests", "schemas", "scenarios"):
            shutil.copytree(ROOT / d, tmp / d, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "docs" / "phase2", tmp / "docs" / "phase2", ignore=shutil.ignore_patterns("evidence"))   # tests that pin hashes of the preregistration need the document
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
