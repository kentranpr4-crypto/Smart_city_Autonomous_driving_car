"""WP5 closed-loop conditions, ODD and protocol constants. PREREGISTERED (sha256 pinned in closedloop/preregistration.json).
Pure data. Truth is used ONLY by the simulator and the evaluator, never by planning/ (enforced by tests/saf)."""
from experiments.conditions import LINKS            # WP4 link models (frozen file, hash-pinned there)

SEEDS_TUNING = tuple(range(20261401, 20261416))     # 15 seeds: debugging and policy-parameter tuning ONLY
SEEDS_EVAL = tuple(range(20261501, 20261541))       # 40 seeds: final benchmark, run once after the freeze
REPLAY_SEEDS = SEEDS_EVAL[:3]
DT = 0.01
CONTROL_EVERY_STEPS = 10                            # 10 Hz decisions for EVERY policy (same control timestep)
DURATION = 18.0
GOAL_X = 75.0                                       # route completion: ego rear axle reaches x = 75 m

# Operational design domain (what the results may be generalised to - and nothing else)
ODD = dict(road="straight 2-lane urban street, dry, mu 0.8, flat", ego_speed_mps=(7.5, 10.0), ego_cap_mps=40 / 3.6, pedestrians="adult walking to fast walking/jogging, 1.4-2.2 m/s, kinematic and non-reactive",
           occluder="one parked truck 9.0 x 2.4 x 3.0 m", infrastructure="at most one CCTV (h=6 m)", v2v="at most one parked vehicle with camera", follower="at most one human-model follower", weather="clear, daylight")

SCENE = dict(truck=(38.5, -3.3, 9.0, 2.4, 3.0), ped_x=45.0, ped_y0=-3.3, ped_y1=3.0, ped_speed=(1.4, 2.2), ped_radius=0.3,
             ego_front_offset=3.6,                  # rear axle -> front bumper [m]
             lane_edge_y=1.2,                       # |y| at which a pedestrian touches the ego swept path (0.9 half-width + 0.3 radius)
             arrival_lead_s=(-0.5, 1.5),            # u ~ U(): pedestrian reaches the lane edge u seconds before the UN-BRAKED ego front reaches x = ped_x
             cctv=dict(pose=(45.0, 8.0, -1.5707963267948966), height=6.0, fov_deg=120, range_m=40, r50=40, pd_slope=6),
             v2v=dict(x=62.0, y=4.0, psi=3.141592653589793),       # parked, facing the ego, camera mounted on it
             follower_gap_m=(6.0, 11.0), follower_react_s=1.0, follower_decel=5.0,
             ghost=dict(ahead_m=14.0, y=0.0, t_spawn=5.0, follow_ahead_m=25.0), bias=(0.5, -0.3))

POLICIES = {
    "E0N": dict(sources=(), planner="nominal"),
    "E0C": dict(sources=(), planner="conservative"),
    "E1": dict(sources=("v2_cam",), planner="guarded"),
    "E2": dict(sources=("cctv_k1",), planner="guarded"),
    "E3": dict(sources=("v2_cam", "cctv_k1"), planner="guarded"),
    "E3naive": dict(sources=("v2_cam", "cctv_k1"), planner="naive"),     # ABLATION to expose harms: trusts remote fully, max braking, no follower awareness
}

CONDITIONS = {
    # S1 hazard: pedestrian emerges from behind the parked truck into the ego lane
    "H_E0N": dict(scene="hazard", policy="E0N", link="nominal"), "H_E0C": dict(scene="hazard", policy="E0C", link="nominal"),
    "H_E1": dict(scene="hazard", policy="E1", link="nominal"), "H_E2": dict(scene="hazard", policy="E2", link="nominal"),
    "H_E3": dict(scene="hazard", policy="E3", link="nominal"), "H_E3naive": dict(scene="hazard", policy="E3naive", link="nominal"),
    # S2 control: the pedestrian waits behind the truck and never enters the lane -> any slowdown is unnecessary
    "C_E0N": dict(scene="control", policy="E0N", link="nominal"), "C_E0C": dict(scene="control", policy="E0C", link="nominal"),
    "C_E1": dict(scene="control", policy="E1", link="nominal"), "C_E2": dict(scene="control", policy="E2", link="nominal"),
    "C_E3": dict(scene="control", policy="E3", link="nominal"), "C_E3naive": dict(scene="control", policy="E3naive", link="nominal"),
    # E4 degraded communication + biased CCTV
    "D_E3": dict(scene="hazard", policy="E3", link="degraded", bias=True), "D_E3naive": dict(scene="hazard", policy="E3naive", link="degraded", bias=True),
    # fallback: all remote traffic lost for the whole run
    "B_E3": dict(scene="hazard", policy="E3", link="nominal", blackout=True),
    # E5 ghost / id-churn / untrusted source
    "G_E0N": dict(scene="ghost", policy="E0N", link="nominal"), "G_E3": dict(scene="ghost", policy="E3", link="nominal", attack="ghost"),
    "G_E3naive": dict(scene="ghost", policy="E3naive", link="nominal", attack="ghost"),
    "I_E3": dict(scene="hazard", policy="E3", link="nominal", attack="id_churn"),
    "U_E3": dict(scene="ghost", policy="E3", link="nominal", attack="untrusted"),
    # extra (report-only): the first ghost design - a phantom that keeps a constant 25 m ahead of the ego (stall, not hard braking)
    "GF_E3": dict(scene="ghost", policy="E3", link="nominal", attack="ghost_follow"), "GF_E3naive": dict(scene="ghost", policy="E3naive", link="nominal", attack="ghost_follow"),
    # E6 rear-end risk
    "R_E0N": dict(scene="hazard", policy="E0N", link="nominal", follower=True), "R_E3": dict(scene="hazard", policy="E3", link="nominal", follower=True),
    "R_E3naive": dict(scene="hazard", policy="E3naive", link="nominal", follower=True),
    "RG_E0N": dict(scene="ghost", policy="E0N", link="nominal", follower=True), "RG_E3": dict(scene="ghost", policy="E3", link="nominal", attack="ghost", follower=True),
    "RG_E3naive": dict(scene="ghost", policy="E3naive", link="nominal", attack="ghost", follower=True),
}

# Safety-stack parameters declared a priori (tuning seeds may change them only with a logged deviation before the freeze)
STACK = dict(corridor_half_m=1.5, standoff_m=1.0, a_comf=3.0, a_emerg=6.0, a_accel=1.5, p_thr=0.05, ped_worst_speed=2.2, creep_speed=2.5, near_lane_m=5.0,
             advisory_cap=3.0, corroborated_cap=6.0, min_persistence_cycles=3, remote_max_age_s=0.5, cautious_speed=4.0,
             follower_react_s=1.0, follower_decel=5.0, follower_radius_m=30.0, margin_s=0.5, horizon_s=6.0, conservative_phantom=True,
             sensor_fov_deg=100, sensor_range_m=80.0)
