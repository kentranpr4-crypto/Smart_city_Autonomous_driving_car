"""Discrete-event orchestration: publishers -> channels -> receivers (admission -> store) -> optional relays. SIMULATION time only.
Events are processed in strict (time, kind, creation order) order with their EXACT times, independent of how often step() is called."""
from __future__ import annotations
import heapq
from .aoi import AoIMeter
from .channel import Channel, LinkConfig
from .clock import NodeClock
from .telemetry import CommTelemetry
from .trackmsg import relay_message, serialize, content_key

RECV, PROC = 0, 1            # at equal times: deliveries before processing


class CommNetwork:
    def __init__(self, seed: int, proc_delay_s: float = 0.005, telemetry: CommTelemetry | None = None, keep_wire: bool = False):
        self.seed, self.pd = seed, proc_delay_s
        self.tel = telemetry or CommTelemetry()
        self.clocks: dict = {}
        self.channels: dict = {}
        self.pubs: list = []
        self.rx: dict = {}
        self.relays: dict = {}
        self._heap, self._n = [], 0
        self._ann: dict = {}
        self.eval_aoi: dict = {}            # (receiver, source) -> AoIMeter on the SIMULATION axis (evaluation only)
        self.wire = [] if keep_wire else None
        self._relay_seq: dict = {}
        self.local_tracks_fn = lambda node: ()
        self.tel.write({"type": "header", "schema_version": "0.1.0", "seed": seed, "proc_delay_s": proc_delay_s})

    # ------------------------------------------------------------------ topology
    def add_clock(self, node_id: str, clock: NodeClock):
        self.clocks[node_id] = clock

    def clock(self, node_id: str) -> NodeClock:
        return self.clocks.setdefault(node_id, NodeClock(f"clk-{node_id}"))

    def add_link(self, src: str, dst: str, cfg: LinkConfig):
        self.channels[(src, dst)] = Channel(cfg, self.seed)

    def add_publisher(self, pub, tracker_key: str, dsts):
        self.pubs.append((pub, tracker_key, tuple(dsts)))

    def add_receiver(self, node_id: str, admission, store):
        admission.clock = self.clock(node_id)
        self.rx[node_id] = (admission, store)

    def add_relay(self, node_id: str, to):
        assert node_id in self.rx, "a relay must also be a receiver: it validates before it forwards"
        self.relays[node_id] = tuple(to)

    # ------------------------------------------------------------------ sending
    def _send(self, t: float, src: str, dst: str, msg, payload: bytes, obs_sim: float):
        ch = self.channels[(src, dst)]
        self._ann[msg.msg_id] = obs_sim
        if self.wire is not None: self.wire.append(payload)
        self.tel.write({"type": "send", "t": t, "link": ch.cfg.link_id, "msg_id": msg.msg_id, "node": src, "tx_seq": msg.tx.tx_seq, "origin": msg.origin.source_id,
                        "orig_seq": msg.origin.orig_seq, "hop": msg.hop_count, "bytes": len(payload), "t_meas": msg.t_meas, "t_sent": msg.t_sent, "eval": {"obs_sim": obs_sim}})
        out = ch.send(t, payload)
        if out.dropped:
            self.tel.write({"type": "drop", "t": t, "link": ch.cfg.link_id, "msg_id": msg.msg_id, "reason": out.dropped})
            return
        for d in out.copies:
            self.tel.write({"type": "sched", "t": t, "link": ch.cfg.link_id, "msg_id": msg.msg_id, "copy": d.copy, "t_deliver": d.t_deliver, "flags": list(d.flags)})
            heapq.heappush(self._heap, (d.t_deliver, RECV, self._n, (src, dst, msg.msg_id, d.copy, d.payload))); self._n += 1

    def inject(self, t: float, src: str, dst: str, payload: bytes, delay_s: float = 0.0):
        """TEST/ATTACK HOOK: put raw bytes on the medium (replay, garbage, forgery). It is logged as a send by node 'injector' so accounting identities still hold."""
        ch = self.channels[(src, dst)]
        mid = f"inject:{self._n}"
        self._ann[mid] = None
        if self.wire is not None: self.wire.append(payload)
        self.tel.write({"type": "send", "t": t, "link": ch.cfg.link_id, "msg_id": mid, "node": "injector", "tx_seq": 0, "origin": "unknown", "orig_seq": 0, "hop": 0,
                        "bytes": len(payload), "t_meas": 0.0, "t_sent": 0.0, "eval": {"obs_sim": None}})
        self.tel.write({"type": "sched", "t": t, "link": ch.cfg.link_id, "msg_id": mid, "copy": 0, "t_deliver": t + delay_s, "flags": ["injected"]})
        heapq.heappush(self._heap, (t + delay_s, RECV, self._n, (src, dst, mid, 0, payload))); self._n += 1

    def step(self, t_sim: float, trackers: dict):
        # Process everything due up to t_sim BEFORE publishing, so the log order is canonical whatever the call frequency of step()
        # (a coarse render/step rate must not reorder 'send at t' ahead of 'recv at t-0.03').
        self.pump(t_sim)
        for pub, key, dsts in self.pubs:
            r = pub.maybe_publish(t_sim, trackers[key])
            if r is None: continue
            msg, payload, obs_sim = r
            for dst in dsts:
                self._send(t_sim, pub.source_id, dst, msg, payload, obs_sim)
        self.pump(t_sim)

    # ------------------------------------------------------------------ event processing
    def pump(self, t_sim: float):
        while self._heap and self._heap[0][0] <= t_sim + 1e-12:
            t, kind, _, data = heapq.heappop(self._heap)
            if kind == RECV:
                src, dst, mid, copy, payload = data
                self.tel.write({"type": "recv", "t": t, "link": self.channels[(src, dst)].cfg.link_id, "msg_id": mid, "copy": copy})
                heapq.heappush(self._heap, (t + self.pd, PROC, self._n, (src, dst, mid, copy, payload, t))); self._n += 1
            else:
                self._process(t, data)

    def _process(self, t_proc: float, data):
        src, dst, mid, copy, payload, t_recv = data
        adm, store = self.rx[dst]
        res = adm.process(payload, t_recv, t_proc, self.local_tracks_fn(dst))
        obs_sim = self._ann.get(mid)
        ev = {"type": "proc", "t": t_proc, "link": self.channels[(src, dst)].cfg.link_id, "msg_id": mid, "copy": copy, "verdict": "admit" if res.admitted else "reject",
              "reason": res.reason, "age_recv_est": res.age_recv_est, "age_proc_est": res.age_proc_est, "flags": list(res.flags), "t_recv": t_recv,
              "eval": {"obs_sim": obs_sim, "age_true_proc": None if obs_sim is None else t_proc - obs_sim}}
        self.tel.write(ev)
        if not res.admitted:
            return
        store.ingest(res)
        m = res.msg
        self.eval_aoi.setdefault((dst, m.origin.source_id), AoIMeter()).observe(t_proc, obs_sim)
        if dst in self.relays and m.hop_count + 1 <= adm.cfg.max_hops:
            for nxt in self.relays[dst]:
                if (dst, nxt) not in self.channels or nxt in m.relay_path or nxt == m.origin.source_id:
                    continue
                seq = self._relay_seq.get(dst, 0); self._relay_seq[dst] = seq + 1
                ck = self.clock(dst)
                rm = relay_message(m, dst, seq, ck.clock_id, ck.local(t_proc))
                self._ann[rm.msg_id] = obs_sim                       # observation time is PRESERVED across the relay
                self._send(t_proc, dst, nxt, rm, serialize(rm), obs_sim)

    def finish(self, t_end: float):
        self.pump(t_end)
