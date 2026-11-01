"""Deterministic discrete-event link model. Time is SIMULATION time passed in by the caller; the wall clock is never read.
Fixed random-number consumption per packet (10 uniforms) regardless of outcome, so changing one parameter never shifts the random draws of other packets."""
from __future__ import annotations
from dataclasses import dataclass
from .rng import rng_stream

N_DRAWS = 10   # loss, ge-transition, jitter, dup, dup-delay, reorder, reorder-delay, corrupt, corrupt-pos, corrupt-byte


@dataclass(frozen=True)
class LinkConfig:
    link_id: str
    base_delay_s: float = 0.03
    jitter_s: float = 0.0                       # extra delay ~ U[0, jitter_s]
    loss_p: float = 0.0                         # Bernoulli loss (ignored when ge is set)
    ge: tuple | None = None                     # Gilbert-Elliott (p_gb, p_bg, loss_good, loss_bad), state updated once per packet
    dup_p: float = 0.0
    dup_extra_delay_s: tuple = (0.01, 0.05)     # duplicate arrives this much later: U[lo, hi]
    reorder_p: float = 0.0
    reorder_extra_delay_s: tuple = (0.05, 0.15)
    corrupt_p: float = 0.0                      # flips one byte of the payload (all copies)
    blackouts: tuple = ()                       # ((t0, t1), ...): packets SENT in [t0, t1) are lost
    bandwidth_Bps: float | None = None          # serialization rate; FIFO
    queue_limit_bytes: int | None = None        # backlog limit; overflow -> dropped 'queue_overflow'


@dataclass(frozen=True)
class Delivery:
    t_deliver: float
    payload: bytes
    link_id: str
    copy: int
    flags: tuple                                # subset of ('dup', 'reordered', 'corrupted') -- for TELEMETRY only; the receiver never sees flags


@dataclass(frozen=True)
class SendOutcome:
    dropped: str | None                         # None | 'loss' | 'blackout' | 'queue_overflow'
    copies: tuple
    t_tx_done: float                            # when the last bit left the sender (== t_now without a bandwidth model)


class Channel:
    def __init__(self, cfg: LinkConfig, seed: int):
        self.cfg = cfg
        self.rng = rng_stream(seed, f"link:{cfg.link_id}")
        self.ge_bad = False
        self.link_free = 0.0
        self.sent = 0

    def send(self, t_now: float, payload: bytes) -> SendOutcome:
        c = self.cfg
        u = self.rng.random(N_DRAWS)
        self.sent += 1
        # --- Gilbert-Elliott / Bernoulli loss probability (state advances for EVERY packet)
        if c.ge is not None:
            p_gb, p_bg, lg, lb = c.ge
            self.ge_bad = (u[1] < p_gb) if not self.ge_bad else not (u[1] < p_bg)
            p_loss = lb if self.ge_bad else lg
        else:
            p_loss = c.loss_p
        # --- bandwidth / queue
        t_base = t_now
        if c.bandwidth_Bps:
            backlog = max(0.0, self.link_free - t_now) * c.bandwidth_Bps
            if c.queue_limit_bytes is not None and backlog + len(payload) > c.queue_limit_bytes:
                return SendOutcome("queue_overflow", (), t_now)
            start = max(t_now, self.link_free)
            self.link_free = start + len(payload) / c.bandwidth_Bps
            t_base = self.link_free
        # --- loss / blackout (the packet occupied the link but never arrives)
        if any(t0 <= t_now < t1 for t0, t1 in c.blackouts):
            return SendOutcome("blackout", (), t_base)
        if u[0] < p_loss:
            return SendOutcome("loss", (), t_base)
        delay = c.base_delay_s + u[2] * c.jitter_s
        flags = []
        if u[5] < c.reorder_p:
            lo, hi = c.reorder_extra_delay_s
            delay += lo + u[6] * (hi - lo); flags.append("reordered")
        data = payload
        if u[7] < c.corrupt_p and len(payload) > 0:
            pos = min(int(u[8] * len(payload)), len(payload) - 1)
            b = bytearray(payload); b[pos] ^= 1 + int(u[9] * 255); data = bytes(b); flags.append("corrupted")
        t_del = t_base + delay
        copies = [Delivery(t_del, data, c.link_id, 0, tuple(flags))]
        if u[3] < c.dup_p:
            lo, hi = c.dup_extra_delay_s
            copies.append(Delivery(t_del + lo + u[4] * (hi - lo), data, c.link_id, 1, tuple(flags) + ("dup",)))
        return SendOutcome(None, tuple(copies), t_base)


def simulate(cfg: LinkConfig, seed: int, sends) -> tuple:
    """Pure helper for tests/benchmarks: sends = [(t, payload)] -> (outcomes, deliveries sorted by (t_deliver, send order, copy))."""
    ch = Channel(cfg, seed)
    outs, dels = [], []
    for i, (t, p) in enumerate(sends):
        o = ch.send(t, p); outs.append(o)
        dels += [(d.t_deliver, i, d.copy, d) for d in o.copies]
    dels.sort(key=lambda x: x[:3])
    return outs, [d for *_, d in dels]
