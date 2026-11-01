"""Scripted end-to-end harness (no World, no truth): a moving target feeds a Tracker every 0.1 s; the tracker's source publishes over a link."""
from __future__ import annotations
import time
from comm.admission import Admission, AdmissionConfig, SourceRegistry
from comm.channel import LinkConfig
from comm.clock import NodeClock
from comm.network import CommNetwork
from comm.publisher import Publisher
from comm.store import ReceiverStore
from perception.presets import V2X_PUBLISH
from perception.tracker import Tracker
from tests.comm.helpers import ORIGIN
from tests.comm.frames import mk_frame


def run_scripted(link: LinkConfig | None = None, seed=1, duration=10.0, step_dt=0.01, adm_kw=None, pub_clock=None, rx_clock=None, proc_delay=0.005,
                 on_step=None, publisher_kw=None, keep_wire=False, rate_hz=10.0, extra=None, det_fn=None, dsts=("ego",), registry_relays=(), ttl_s=None):
    net = CommNetwork(seed, proc_delay_s=proc_delay, keep_wire=keep_wire)
    net.add_clock("k", pub_clock or NodeClock("c-k")); net.add_clock("ego", rx_clock or NodeClock("c-ego"))
    link = link or LinkConfig("k>ego", base_delay_s=0.03)
    net.add_link("k", "ego", link)
    pub = Publisher("k", "cctv", net.clock("k"), ORIGIN, rate_hz=rate_hz, **({**({"ttl_s": ttl_s} if ttl_s else {}), **(publisher_kw or {})}))
    net.add_publisher(pub, "k", list(dsts))
    adm = Admission(AdmissionConfig("ego", ORIGIN, **(adm_kw or {})), SourceRegistry({"k": "cctv"}, frozenset(registry_relays)))
    store = ReceiverStore(adm.cfg.max_age_s)
    net.add_receiver("ego", adm, store)
    if extra: extra(net)
    tr = Tracker("k", V2X_PUBLISH); trs = {"k": tr}
    n_steps = int(round(duration / step_dt)); k_frame = 0
    for i in range(n_steps + 1):
        t = round(i * step_dt, 9)
        while k_frame * 0.1 <= t + 1e-9:                       # one sensor frame every 0.1 s, independent of step_dt
            tf = round(k_frame * 0.1, 9)
            dets = det_fn(tf) if det_fn else [(2.0 + 1.0 * tf, 0.0, 0.04)]
            tr.update(mk_frame(k_frame, tf, dets, sensor="k"), t_now=tf); k_frame += 1
        net.step(t, trs)
        if on_step: on_step(net, t)
    net.finish(duration + 5.0)
    return net, store, adm, pub
