"""Communication telemetry: canonical JSONL + SHA-256 + accounting identities. Evaluation annotations (sim-time ground truth about the simulation CLOCK,
never about the world) live under the 'eval' key and are not visible to receivers."""
from __future__ import annotations
import hashlib, json, math


def canonical_line(rec: dict) -> bytes:
    def clean(o):
        if isinstance(o, float):
            if not math.isfinite(o): raise ValueError("non-finite float in comm telemetry")
            return 0.0 if o == 0.0 else o
        if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)): return [clean(v) for v in o]
        return o
    return (json.dumps(clean(rec), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


class CommTelemetry:
    def __init__(self, path=None):
        self._h = hashlib.sha256()
        self._f = open(path, "wb") if path else None
        self.events = []

    def write(self, rec: dict):
        b = canonical_line(rec)
        self._h.update(b); self.events.append(rec)
        if self._f: self._f.write(b)

    def hexdigest(self) -> str:
        return self._h.hexdigest()

    def close(self):
        if self._f: self._f.close(); self._f = None


def accounting(events) -> dict:
    """Identities that must hold for any run:
       sent = dropped + scheduled_messages ; copies_scheduled = recv + in_flight ; recv = proc + proc_pending ; proc = admit + reject."""
    n = lambda t: sum(1 for e in events if e["type"] == t)
    sent, drop, sched, recv, proc = n("send"), n("drop"), n("sched"), n("recv"), n("proc")
    sched_msgs = len({(e["link"], e["msg_id"]) for e in events if e["type"] == "sched"})
    admit = sum(1 for e in events if e["type"] == "proc" and e["verdict"] == "admit")
    reject = proc - admit
    return {"sent": sent, "dropped": drop, "scheduled_messages": sched_msgs, "copies_scheduled": sched, "recv": recv, "proc": proc, "admit": admit, "reject": reject,
            "ok_sent": sent == drop + sched_msgs, "ok_recv": recv <= sched, "ok_proc": proc <= recv, "ok_verdict": proc == admit + reject}
