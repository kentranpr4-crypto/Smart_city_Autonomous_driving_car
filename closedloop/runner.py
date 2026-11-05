"""Closed-loop scenario runner (TRUTH SIDE). One run = one policy x one scenario x one seed on the SAME authoritative physics backend, control timestep and seeds.
Planning receives only: own (noisy) localisation, local tracks, admitted remote tracks, a noisy rear measurement and static map obstacles - never truth."""
from __future__ import annotations
import hashlib, math, time
from dataclasses import replace
import numpy as np
from backend.rng import rng_stream
from backend.rig import PerceptionRig
from backend.scenario import ScriptedCmd, scenario_from_dict
from backend.telemetry import TelemetryWriter
from backend.world import World
from comm.admission import Admission, AdmissionConfig, SourceRegistry
from comm.channel import LinkConfig
from comm.clock import NodeClock
from comm.network import CommNetwork
from comm.publisher import Publisher
from comm.store import ReceiverStore
from comm.trackmsg import FRAME, UNITS, YAW_CONVENTION, SCHEMA_VERSION, Origin, Tx, TrackEntry, TrackMsg, serialize
from experiments.conditions import FUSION_PARAMS
from perception.presets import V2X_PUBLISH
from planning.stack import SafetyStack
from planning.types import EGO_SOURCE, EgoState, Rear
from . import conditions as K

ORIGIN = "map-origin-0"
S = K.SCENE
SENSOR_COMMON = dict(pd0=0.95, sigma0=0.05, sigma1=0.01, t_proc=0.05)


def _link(name, link_id, blackout=False):
    p = dict(K.LINKS[name])
    if blackout: p["blackouts"] = ((0.0, 1e6),)
    return LinkConfig(link_id, **p)


def build_scenario(cond: dict, seed: int):
    rng = rng_stream(seed, "wp5-scenario")
    v0 = float(rng.uniform(*K.ODD["ego_speed_mps"])); u = float(rng.uniform(*S["arrival_lead_s"])); sp = float(rng.uniform(*S["ped_speed"]))
    gap = float(rng.uniform(*S["follower_gap_m"]))
    t_ego = (S["ped_x"] - S["ego_front_offset"]) / v0
    t_start = max(t_ego - u - (abs(S["ped_y0"]) - S["lane_edge_y"]) / sp, 0.0)
    scene = cond["scene"]
    vehicles = [dict(id="ego", init=dict(x=0.0, y=0.0, psi=0.0, v=v0)), dict(id="v2", init=dict(x=S["v2v"]["x"], y=S["v2v"]["y"], psi=S["v2v"]["psi"], v=0.0))]
    if cond.get("follower"):
        vehicles.append(dict(id="f1", init=dict(x=-(gap + 0.9 + 3.6), y=0.0, psi=0.0, v=v0)))
    peds = []
    if scene == "hazard":
        peds = [dict(id="ped1", radius=S["ped_radius"], path=[[S["ped_x"], S["ped_y0"]], [S["ped_x"], S["ped_y1"]]], start_time=t_start, speed=sp, height=1.7)]
    elif scene == "control":
        peds = [dict(id="ped1", radius=S["ped_radius"], path=[[S["ped_x"], S["ped_y0"]], [S["ped_x"], S["ped_y0"] - 0.01]], start_time=1000.0, speed=sp, height=1.7)]
    cx, cy, lx, wy, h = S["truck"]
    bias = tuple(S["bias"]) if cond.get("bias") else (0.0, 0.0)
    c = S["cctv"]
    sensors = [
        dict(id="ego_cam", kind="vehicle", mount_vehicle="ego", height=1.5, fov_deg=100, range=80, rate_hz=10, mount_offset=[0.5, 0.0], r50=60, pd_slope=8, **SENSOR_COMMON),
        dict(id="cctv_k1", kind="cctv", pose=list(c["pose"]), height=c["height"], fov_deg=c["fov_deg"], range=c["range_m"], rate_hz=10, phase=0.03, r50=c["r50"], pd_slope=c["pd_slope"], bias=list(bias), **SENSOR_COMMON),
        dict(id="v2_cam", kind="vehicle", mount_vehicle="v2", height=1.5, fov_deg=100, range=60, rate_hz=10, phase=0.05, mount_offset=[0.5, 0.0], r50=50, pd_slope=8, **SENSOR_COMMON),
    ]
    d = dict(schema_version="0.1.0", id=f"wp5_{scene}", description="WP5 closed-loop scenario", dt=K.DT, duration=K.DURATION, stop_on_collision=True, road=dict(mu=0.8),
             vehicles=vehicles, pedestrians=peds, obstacles=[dict(id="truck", center=[cx, cy], size=[lx, wy], height=h)], sensors=sensors)
    return scenario_from_dict(d), dict(v0=v0, u=u, ped_speed=sp, t_start=t_start, gap=gap, t_edge=t_start + (abs(S["ped_y0"]) - S["lane_edge_y"]) / sp)


class ChurnPublisher(Publisher):
    """Attack: the (legitimate) source renumbers its track ids in every message (ID churn)."""
    def maybe_publish(self, t_sim, tracker):
        r = super().maybe_publish(t_sim, tracker)
        if r is None: return None
        msg, _, obs = r
        self._k = getattr(self, "_k", 0) + 1
        tr = tuple(replace(t, track_id=1000 * self._k + t.track_id) for t in msg.tracks)
        m2 = replace(msg, tracks=tr)
        return m2, serialize(m2), obs


def _forged(source, seq, t_meas, x, y, cov=0.04):
    cv = tuple(cov if i % 5 == 0 else 0.0 for i in range(16))
    tr = (TrackEntry(99, "pedestrian", 0.9, x, y, 0.0, 0.0, 0.0, cv, 0.1, 0.9, t_meas),)
    prov = {"sensor_model": "forged", "algo_version": "x", "calib_id": "none", "privacy_level": "object_only", "confirmation": "3of4"}
    return TrackMsg(SCHEMA_VERSION, f"{source}:{seq}", Tx(source, seq, "c-k1"), Origin(source, "cctv", seq, f"{source}:{seq}", "c-k1", "synced", prov),
                    t_meas, t_meas + 0.01, FRAME, ORIGIN, dict(UNITS), YAW_CONVENTION, 1.0, 0, (), tr)


def _rect_circle_dist(ex0, ex1, ey0, ey1, px, py):
    dx = max(ex0 - px, 0.0, px - ex1); dy = max(ey0 - py, 0.0, py - ey1)
    return math.hypot(dx, dy)


def run(cond_name: str, seed: int, stack_prm: dict | None = None, time_it: bool = True) -> dict:
    cond = K.CONDITIONS[cond_name]; pol = K.POLICIES[cond["policy"]]
    scn, info = build_scenario(cond, seed)
    world = World(scn, seed, TelemetryWriter(keep=False))
    rig = PerceptionRig(scn, seed, cfg=V2X_PUBLISH)
    link = cond["link"]; blackout = cond.get("blackout", False)
    net = CommNetwork(seed, proc_delay_s=0.005)
    net.add_clock("cctv_k1", NodeClock("c-k1")); net.add_clock("v2_cam", NodeClock("c-v2")); net.add_clock("ego", NodeClock("c-ego"))
    net.add_link("cctv_k1", "ego", _link(link, "cctv_k1>ego", blackout)); net.add_link("v2_cam", "ego", _link(link, "v2_cam>ego", blackout))
    PubK = ChurnPublisher if cond.get("attack") == "id_churn" else Publisher
    net.add_publisher(PubK("cctv_k1", "cctv", net.clock("cctv_k1"), ORIGIN, rate_hz=10.0, ttl_s=1.0), "cctv_k1", ["ego"])
    net.add_publisher(Publisher("v2_cam", "vehicle", net.clock("v2_cam"), ORIGIN, rate_hz=10.0, ttl_s=1.0), "v2_cam", ["ego"])
    reg = SourceRegistry({"cctv_k1": "cctv", "v2_cam": "vehicle"}, frozenset())
    store = ReceiverStore(0.5)
    net.add_receiver("ego", Admission(AdmissionConfig("ego", ORIGIN), reg), store)
    net.local_tracks_fn = lambda node: rig.trackers["ego_cam"].tracks(world.t) if node == "ego" else ()
    prm = {**K.STACK, **(stack_prm or {}), "crosswalk_spots": ((S["ped_x"], S["ped_y0"]),), "occluders": ((S["truck"][0], S["truck"][1], S["truck"][2], S["truck"][3]),)}
    stack = SafetyStack(pol["planner"], prm, FUSION_PARAMS, info["v0"])
    rng_loc = rng_stream(seed, "wp5-ego-loc"); rng_rear = rng_stream(seed, "wp5-rear")
    hist = []                                            # ego state history for the follower's reaction delay
    ticks, series, fseries = [], [], []
    seq_forged = [100000]; ghost_x = [None]
    side = dict(onsets=[], first_brake_t=None, prev_a_cmd=0.0, decisions=0)
    ped = world.peds[0] if world.peds else None

    def counterfactual(ego_x, ego_v, t0, horizon):
        """min clearance between the ego rectangle (keeping speed ego_v) and the REAL pedestrian over `horizon` s. Evaluator-side (uses the scripted pedestrian)."""
        if ped is None: return math.inf
        best = math.inf
        for k in range(int(horizon / 0.05) + 1):
            t = 0.05 * k
            px, py = ped.at(t0 + t)[:2]
            ex = ego_x + ego_v * t
            best = min(best, _rect_circle_dist(ex - 0.9, ex + 3.6, -0.9, 0.9, px, py) - ped.radius)
        return best

    def ttc(ego_x, ego_v, t0):
        if ped is None: return 10.0
        for k in range(int(10.0 / 0.05) + 1):
            t = 0.05 * k
            px, py = ped.at(t0 + t)[:2]
            ex = ego_x + ego_v * t
            if _rect_circle_dist(ex - 0.9, ex + 3.6, -0.9, 0.9, px, py) <= ped.radius: return t
        return 10.0

    def on_step(w):
        rig(w); net.step(w.t, rig.trackers)
        e = w.veh["ego"]
        series.append((w.t, e.x, e.v, e.a))
        hist.append((w.t, e.x, e.v))
        if "f1" in w.veh: fseries.append((w.t, w.veh["f1"].x, w.veh["f1"].v, e.x, e.v))
        if "f1" in w.veh and w.n % K.CONTROL_EVERY_STEPS == 0:                    # human follower (environment, not the ego's business)
            f = w.veh["f1"]; tobs = w.t - S["follower_react_s"]
            lead = next(((x, v) for (tt, x, v) in reversed(hist) if tt <= tobs + 1e-9), (hist[0][1], hist[0][2]))
            gap = lead[0] - 0.9 - (f.x + 3.6)
            a = max(-S["follower_decel"], min(1.5, 0.35 * (gap - (2.0 + 1.2 * f.v)) + 0.9 * (lead[1] - f.v)))
            w.issue("f1", ScriptedCmd(w.t, a, 0.0, "emergency" if a < -3.0 else "comfort"))
        if cond.get("attack") in ("ghost", "untrusted", "ghost_follow") and w.n % K.CONTROL_EVERY_STEPS == 0:
            src = "rogue_9" if cond["attack"] == "untrusted" else "cctv_k1"
            if cond["attack"] == "ghost_follow":
                gx = e.x + S["ghost"]["follow_ahead_m"]                                   # shadowing phantom (design 1)
            else:                                                                          # pop-up phantom: appears suddenly close ahead at t_spawn and stays at that world position
                if ghost_x[0] is None and w.t >= S["ghost"]["t_spawn"]: ghost_x[0] = e.x + S["ghost"]["ahead_m"]
                gx = ghost_x[0]
            if gx is not None:
                seq_forged[0] += 1
                m = _forged(src, seq_forged[0], w.t - 0.05, gx, S["ghost"]["y"])
                net.inject(w.t, "cctv_k1", "ego", serialize(m), delay_s=0.03)
        if w.n % K.CONTROL_EVERY_STEPS == 0:
            nx, nv = float(rng_loc.normal(0, 0.1)), float(rng_loc.normal(0, 0.05))
            gx, gv = float(rng_rear.normal(0, 0.2)), float(rng_rear.normal(0, 0.1))
            rear = Rear(None, None)
            if "f1" in w.veh:
                f = w.veh["f1"]; g = e.x - 0.9 - (f.x + 3.6)
                if g < 30.0: rear = Rear(g + gx, f.v + gv)
            ego = EgoState(w.t, e.x + nx, max(e.v + nv, 0.0))
            local = rig.trackers["ego_cam"].tracks(w.t)
            remote = [s for s in store.tracks(w.t) if s.ref[0] in pol["sources"]]
            t0 = time.perf_counter()
            d, hyps = stack.decide(ego, local, remote, rear, ego_pose=(ego.x + 1.35, 0.0, 0.1))
            lat = time.perf_counter() - t0
            w.issue("ego", ScriptedCmd(w.t, d.a_cmd, 0.0, d.mode))
            side["decisions"] += 1
            if d.a_cmd < -1.0 and side["prev_a_cmd"] >= -1.0:
                side["onsets"].append((w.t, counterfactual(e.x, e.v, w.t, 6.0)))
                if side["first_brake_t"] is None: side["first_brake_t"] = w.t
            side["prev_a_cmd"] = d.a_cmd
            ticks.append(dict(t=w.t, a_cmd=d.a_cmd, a_local=d.a_local, mode=d.mode, p=d.diag["p_max"], age=d.diag["remote_age_s"], n_remote=d.diag["n_remote_used"],
                              reasons=d.reasons, lat=lat if time_it else 0.0, outcome=int(counterfactual(e.x, e.v, w.t, 3.0) < 0.5), ttc=ttc(e.x, e.v, w.t), ego_x=e.x,
                              assur_bad=sum(1 for h in hyps if h.assurance == "authenticated"), binding=d.diag["binding"],
                              hyps=[(h.hid, h.level, round(h.x, 2), round(h.y, 2), round(h.vx, 2), round(h.vy, 2), h.cls, h.sources) for h in hyps]))
        if e.x >= K.GOAL_X and not w.finished:
            side["t_goal"] = w.t; w.finished = True

    world.run(on_step=on_step)
    cols = [x for x in world.events_log if x["type"] == "collision"]
    ego_cols = [c for c in cols if "ego" in c["actors"] and "f1" not in c["actors"]]
    fol_cols = [c for c in cols if set(c["actors"]) == {"ego", "f1"}]
    arr = np.array(series)
    ego_traj_hash = hashlib.sha256(np.round(arr[:, 1:], 9).tobytes()).hexdigest()
    return dict(cond=cond_name, seed=seed, info=info, ticks=ticks, series=arr, fseries=np.array(fseries), onsets=side["onsets"], first_brake_t=side["first_brake_t"], t_goal=side.get("t_goal"),
                ego_collision=bool(ego_cols), follower_collision=bool(fol_cols), impact_speed=(ego_cols[0]["impact_speed"] if ego_cols else None),
                follower_impact_speed=(fol_cols[0]["impact_speed"] if fol_cols else None),
                min_clearance=world.summary()["min_clearance"], standstill_events=world.counts["standstill_jerk_discontinuities"], traj_hash=ego_traj_hash,
                config=(K.DT, K.CONTROL_EVERY_STEPS, repr(scn.vparams), repr(scn.friction)), stack=stack, net_hash=net.tel.hexdigest(), t_end=world.t)
