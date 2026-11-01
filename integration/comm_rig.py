"""Integration (truth-side allowed): runs the WP2 perception rig on a scenario and publishes the CCTV tracker's confirmed tracks over the WP3 comm network to the ego.
This module lives OUTSIDE comm/ on purpose: comm/ must never import the world or the rig (COM-10)."""
from __future__ import annotations
import pathlib
from backend.rig import PerceptionRig
from backend.scenario import load_scenario
from backend.telemetry import TelemetryWriter
from backend.world import World
from comm.admission import Admission, AdmissionConfig, SourceRegistry
from comm.channel import LinkConfig
from comm.clock import NodeClock
from comm.network import CommNetwork
from comm.publisher import Publisher
from comm.store import ReceiverStore
from perception.presets import V2X_PUBLISH

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCN = ROOT / "scenarios" / "s01w2_occlusion_rig.yaml"
ORIGIN = "map-origin-0"


def run_rig_comm(seed: int, link: LinkConfig, keep_wire=False, proc_delay=0.005, adm_kw=None, rate_hz=10.0, ttl_s=1.0, telemetry=None, publisher_kw=None):
    scn = load_scenario(SCN)
    w = World(scn, seed, TelemetryWriter(keep=False))
    rig = PerceptionRig(scn, seed, cfg=V2X_PUBLISH)
    net = CommNetwork(seed, proc_delay_s=proc_delay, keep_wire=keep_wire, telemetry=telemetry)
    net.add_clock("cctv_k1", NodeClock("c-k1")); net.add_clock("ego", NodeClock("c-ego"))
    net.add_link("cctv_k1", "ego", link)
    pub = Publisher("cctv_k1", "cctv", net.clock("cctv_k1"), ORIGIN, rate_hz=rate_hz, ttl_s=ttl_s, **(publisher_kw or {}))
    net.add_publisher(pub, "cctv_k1", ["ego"])
    adm = Admission(AdmissionConfig("ego", ORIGIN, **(adm_kw or {})), SourceRegistry({"cctv_k1": "cctv"}, frozenset()))
    store = ReceiverStore(adm.cfg.max_age_s)
    net.add_receiver("ego", adm, store)

    def step(world):
        rig(world); net.step(world.t, rig.trackers)
    step(w)
    w.run(on_step=step)
    net.finish(w.t + 5.0)
    return w, rig, net, store, adm, pub
