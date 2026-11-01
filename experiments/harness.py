"""Closed-form experiment harness (TRUTH SIDE). Simulates sensors -> trackers -> WP3 comm network -> ego; runs all fusion methods on IDENTICAL inputs each cycle
and records everything the evaluator needs. Truth is used only to generate sensor data and in the recorded `truth` field (never passed to fusion)."""
from __future__ import annotations
import heapq, math, time
from dataclasses import replace
import numpy as np
from backend.observation import Detection
from backend.sensors import SensorProvider
from comm.admission import Admission, AdmissionConfig, SourceRegistry
from comm.channel import LinkConfig
from comm.clock import NodeClock
from comm.network import CommNetwork
from comm.publisher import Publisher
from comm.store import ReceiverStore
from comm.metrics import summarize
from comm.rng import rng_stream
from fusion.adapters import from_local_track, from_stored
from fusion.fuser import CooperativeFuser
from fusion.transform import Transform2D
from perception.presets import V2X_PUBLISH
from perception.tracker import Tracker
from . import conditions as K
from .scenes import EGO_ID, REMOTE_ID, build_scene

ORIGIN = "map-origin-0"


def make_link(name: str, link_id: str) -> LinkConfig:
    return LinkConfig(link_id, **K.LINKS[name])


def run(cond_name: str, seed: int, methods=K.METHODS, params: dict | None = None, time_it: bool = True) -> dict:
    cond = K.CONDITIONS[cond_name]
    scene = build_scene(cond, remote_bias=cond.get("remote_bias", (0.0, 0.0)))
    feed = cond.get("remote_feed", "own")
    sensors = [s for s in scene.sensors if not (feed != "own" and s.id == REMOTE_ID)]            # echo/partial: the remote source re-publishes ego data
    pv = SensorProvider(sensors, seed, K.DT)
    trackers = {EGO_ID: Tracker(EGO_ID, V2X_PUBLISH), REMOTE_ID: Tracker(REMOTE_ID, V2X_PUBLISH)}
    # ---- network / topology
    net = CommNetwork(seed, proc_delay_s=0.005)
    net.add_clock(REMOTE_ID, NodeClock("c-k1", offset_s=cond.get("remote_clock_offset_s", 0.0))); net.add_clock("ego", NodeClock("c-ego"))
    topo = cond.get("topology", "direct"); direct_link = cond["link"]
    net.add_link(REMOTE_ID, "ego", make_link(direct_link, f"{REMOTE_ID}>ego"))
    dsts = ["ego"]; relays = []
    chain = {"relay1": ["rsu1"], "relay2": ["rsu1", "rsu2"]}.get(topo, [])
    if chain:
        rl = cond["relay_link"]; relays = chain
        for n in chain: net.add_clock(n, NodeClock(f"c-{n}"))
        net.add_link(REMOTE_ID, chain[0], make_link(rl, f"{REMOTE_ID}>{chain[0]}")); dsts.append(chain[0])
        for a, b in zip(chain, chain[1:] + ["ego"]): net.add_link(a, b, make_link(rl, f"{a}>{b}"))
    pub = Publisher(REMOTE_ID, "cctv", net.clock(REMOTE_ID), ORIGIN, rate_hz=10.0, ttl_s=1.0)
    net.add_publisher(pub, REMOTE_ID, dsts)
    reg = lambda: SourceRegistry({REMOTE_ID: "cctv"}, frozenset(relays))
    ego_store = ReceiverStore(0.5); net.add_receiver("ego", Admission(AdmissionConfig("ego", ORIGIN), reg()), ego_store)
    for i, n in enumerate(chain):
        net.add_receiver(n, Admission(AdmissionConfig(n, ORIGIN), reg()), ReceiverStore(0.5))
        net.add_relay(n, [(chain + ["ego"])[i + 1]])
    now = {"t": 0.0}
    net.local_tracks_fn = lambda node: trackers[EGO_ID].tracks(now["t"]) if node == "ego" else ()
    # ---- fusion
    fusers = {m: CooperativeFuser(m, {**K.FUSION_PARAMS, **(params or {})}) for m in methods}
    declared = cond.get("declared_transform_sigma_m")
    tf = Transform2D("map", "map", 0.0, 0.0, 0.0, tuple(np.diag([declared ** 2, declared ** 2, 0.0]).reshape(-1))) if declared else None
    rng_partial = rng_stream(seed, "partial-feed"); rng_loc = rng_stream(seed, "ego-localisation")
    blackout = cond.get("remote_blackout")
    heap, hn = [], 0
    labels = {EGO_ID: {}, REMOTE_ID: {}}; vis_now = {EGO_ID: set(), REMOTE_ID: set()}; det_now = {EGO_ID: set(), REMOTE_ID: set()}
    rseq = 0
    cycles = []
    n_steps = int(round(scene.duration / K.DT))
    for step in range(n_steps + 1):
        t = round(step * K.DT, 9); now["t"] = t
        snap = scene.snapshot(t)
        for frame, lab in pv.sample(snap, step):
            vis_now[frame.sensor_id] = set(lab.visible); det_now[frame.sensor_id] = set(lab.detected)
            if frame.sensor_id == REMOTE_ID and blackout and blackout[0] <= frame.t_meas < blackout[1]:
                continue                                                                      # remote camera outage: frame never delivered
            heapq.heappush(heap, (frame.t_avail, hn, frame)); hn += 1
            if feed != "own" and frame.sensor_id == EGO_ID:
                dets = frame.detections
                if feed == "partial":
                    s = cond["partial_sigma_m"]
                    dets = tuple(Detection(d.det_id, d.x + s * float(rng_partial.normal()), d.y + s * float(rng_partial.normal()), (d.cov[0] + s * s, d.cov[1], d.cov[2] + s * s), d.cls, d.cls_prob, d.score) for d in frame.detections)
                echo = replace(frame, sensor_id=REMOTE_ID, seq=rseq, detections=dets); rseq += 1
                vis_now[REMOTE_ID] = set(lab.visible); det_now[REMOTE_ID] = set(lab.detected)
                heapq.heappush(heap, (echo.t_avail, hn, echo)); hn += 1
        while heap and heap[0][0] <= t + 1e-12:
            _, _, fr = heapq.heappop(heap)
            trackers[fr.sensor_id].update(fr, t_now=t)
        net.step(t, trackers)
        if step % K.FUSION_EVERY_STEPS == K.FUSION_PHASE_STEP:
            loc = trackers[EGO_ID].tracks(t)
            stored = ego_store.tracks(t)
            ests = [from_local_track(EGO_ID, q) for q in loc]
            rem = [from_stored(q) for q in stored]
            if tf is not None:
                rem = [tf.apply(e) for e in rem]
            ests += rem
            ego_act = next(a for a in snap.actors if a.id == "ego")
            ego_pose = (ego_act.x + 0.1 * float(rng_loc.normal()), ego_act.y + 0.1 * float(rng_loc.normal()), 0.1)      # the ego's own (noisy) localisation, sigma 0.1 m
            rec = {"t": t, "truth": {a.id: (a.x, a.y, a.vx, a.vy) for a in snap.actors if a.id in scene.targets}, "truth_all": {a.id: (a.x, a.y, a.vx, a.vy) for a in snap.actors}, "vis": {k: sorted(v) for k, v in vis_now.items()},
                   "det": {k: sorted(v) for k, v in det_now.items()},
                   "local": [(EGO_ID, q.track_id, q.x) for q in loc], "remote": [(e.source_id, e.track_id, e.x, e.t) for e in rem], "methods": {}}
            for m, fu in fusers.items():
                t0 = time.perf_counter()
                w = fu.step(t, ests, ego_pose=ego_pose)
                dt = time.perf_counter() - t0
                rec["methods"][m] = {"tracks": [(q.fid, q.x, q.P, q.members, q.flags, q.evidence, q.max_remote_age_s) for q in w.tracks], "rej": w.diagnostics["rejected"],
                                     "pair_d2": w.diagnostics["pair_d2"], "runtime_s": dt if time_it else 0.0}
            cycles.append(rec)
    net.finish(scene.duration + 5.0)
    ev = net.tel.events
    send = {(e["link"], e["msg_id"]): e for e in ev if e["type"] == "send"}
    ego_adm = [e for e in ev if e["type"] == "proc" and e["verdict"] == "admit" and e["link"].endswith(">ego")]
    direct_sent = [e for e in ev if e["type"] == "send" and e["link"] == f"{REMOTE_ID}>ego"]
    n_pub = max(1, sum(1 for e in ev if e["type"] == "send" and e["node"] == REMOTE_ID and e["link"].startswith(f"{REMOTE_ID}>ego")))
    distinct = {(send[(e["link"], e["msg_id"])]["origin"], send[(e["link"], e["msg_id"])]["orig_seq"]) for e in ego_adm}
    comm = summarize(ev, net.eval_aoi, scene.duration, 0.01, scene.duration)
    return {"cond": cond_name, "seed": seed, "targets": scene.targets, "cycles": cycles,
            "comm": {"sent": n_pub, "admitted_ego": len(ego_adm), "distinct_obs_admitted": len(distinct), "bandwidth_Bps": comm["bandwidth_Bps_per_source"].get(REMOTE_ID, 0.0),
                     "rejected": comm["rejected_by_reason"], "dropped": comm["dropped_by_reason"], "hash": net.tel.hexdigest()},
            "monitor": {m: {"first_pair_t": fu.monitor.first_pair_t.get(REMOTE_ID), "first_flag_t": fu.monitor.first_flag_t.get(REMOTE_ID)} for m, fu in fusers.items()},
            "fusers": fusers, "blackout": blackout}
