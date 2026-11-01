"""WP4 experimental conditions and protocol constants. PREREGISTERED (sha256 pinned in fusion/preregistration.json) before any WP4 benchmark ran.
Pure data: no behaviour. Scene geometry is built from these parameters by experiments/scenes.py. Truth is used ONLY by the evaluator, never in the inference path."""

SEEDS_TUNING = tuple(range(20261201, 20261216))          # 15 seeds: debugging / sanity only; results are NOT used for claims
SEEDS_EVAL = tuple(range(20261301, 20261331))            # 30 seeds: final benchmark, run once after preregistration
REPLAY_SEEDS = SEEDS_EVAL[:3]
DT = 0.01
FUSION_EVERY_STEPS, FUSION_PHASE_STEP = 10, 9            # fuse at t = 0.09, 0.19, ... (after both sensors' t_avail)
WARMUP_S = 1.0                                           # error/consistency metrics ignore the first second (track confirmation); availability does not
EVAL_GATE_M = 2.0                                        # evaluator-side truth association gate
CHI2_95_4DOF = 9.487729036781154

LINKS = {
    "nominal":  dict(base_delay_s=0.030, jitter_s=0.010, loss_p=0.01),
    "degraded": dict(base_delay_s=0.080, jitter_s=0.040, ge=(0.05, 0.30, 0.02, 0.60), dup_p=0.02, reorder_p=0.05, reorder_extra_delay_s=(0.05, 0.15)),
    "severe":   dict(base_delay_s=0.200, jitter_s=0.100, loss_p=0.30, dup_p=0.10, reorder_p=0.15, reorder_extra_delay_s=(0.10, 0.40), corrupt_p=0.02),
}

FUSION_PARAMS = dict(sigma_a=1.0, gate_chi2_4dof=18.466826, max_horizon_s=1.0, max_remote_age_s=0.5, time_sigma_s=0.0, ci_criterion="trace",
                     monitor_window=10, monitor_chi2_conf=0.999, class_gate=True, quarantine_on_flag=False)

# scene kinds: occ (moving pedestrian hidden by a truck from the ego, seen by CCTV), solo (one pedestrian, both sensors see it),
#              close (two parallel pedestrians, gap d), cross (two crossing pedestrians, closest approach `miss`)
CONDITIONS = {
    "C1_occ_nominal":      dict(exp=1, scene="occ", link="nominal"),
    "C2a_close_0p4":       dict(exp=2, scene="close", d=0.4, link="nominal"),
    "C2b_close_1p5":       dict(exp=2, scene="close", d=1.5, link="nominal"),
    "C3a_cross_collision": dict(exp=3, scene="cross", miss=0.0, link="nominal"),
    "C3b_cross_miss_1p77": dict(exp=3, scene="cross", miss=1.77, link="nominal"),
    "C4a_corr_echo":       dict(exp=4, scene="solo", link="nominal", remote_feed="echo"),
    "C4b_corr_partial":    dict(exp=4, scene="solo", link="nominal", remote_feed="partial", partial_sigma_m=0.15),
    "C0_solo_control":     dict(exp=0, scene="solo", link="nominal"),
    "C5a_bias_undeclared": dict(exp=5, scene="solo", link="nominal", remote_bias=(0.5, -0.3)),
    "C5b_bias_declared":   dict(exp=5, scene="solo", link="nominal", remote_bias=(0.5, -0.3), declared_transform_sigma_m=0.5),
    "C6a_skew_m0p3":       dict(exp=6, scene="solo", link="nominal", remote_clock_offset_s=-0.3),
    "C6b_skew_m0p1":       dict(exp=6, scene="solo", link="nominal", remote_clock_offset_s=-0.1),
    "C6c_skew_p0p1":       dict(exp=6, scene="solo", link="nominal", remote_clock_offset_s=0.1),
    "C6d_skew_p0p3":       dict(exp=6, scene="solo", link="nominal", remote_clock_offset_s=0.3),
    "C7a_occ_degraded":    dict(exp=7, scene="occ", link="degraded"),
    "C7b_occ_severe":      dict(exp=7, scene="occ", link="severe"),
    "C8a_relay_direct_only": dict(exp=8, scene="occ", link="severe", topology="direct"),
    "C8b_relay_1hop":      dict(exp=8, scene="occ", link="severe", topology="relay1", relay_link="nominal"),
    "C8c_relay_2hop":      dict(exp=8, scene="occ", link="severe", topology="relay2", relay_link="nominal"),
    "C9a_blackout_solo":   dict(exp=9, scene="solo", link="nominal", remote_blackout=(4.0, 7.0)),
    "C9b_blackout_occ":    dict(exp=9, scene="occ", link="nominal", remote_blackout=(1.0, 4.0)),
}
METHODS = ("B0_local", "B1_remote", "B2_naive", "B3_info", "B4_ci", "B4q_ci_quarantine")   # B4q = extra (not mandatory) variant
