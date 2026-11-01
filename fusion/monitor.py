"""Cross-source consistency monitor: sliding sum of pairwise position innovations d2 (S = Pa + Pb, 2 dof each) per remote source.
Flag when sum over the last N pairs > chi2_{conf}(2N); clear with hysteresis below chi2_{0.95}(2N). Detects constant bias / over-confident sources; it is a
HEURISTIC detector (consecutive pairs are autocorrelated, so the nominal false-alarm rate is approximate)."""
from __future__ import annotations
from collections import deque
from perception.stats import chi2_ppf


class ConsistencyMonitor:
    def __init__(self, window: int = 10, conf: float = 0.999, warmup_s: float = 0.0):
        self.N = window; self.warmup_s = warmup_s       # pairs during the first warmup_s after a source's first pair are ignored (track-initialisation transient)
        self.hi = chi2_ppf(conf, 2 * window); self.lo = chi2_ppf(0.95, 2 * window)
        self._w: dict = {}
        self.flagged: dict = {}
        self.first_pair_t: dict = {}
        self.first_flag_t: dict = {}

    def push(self, source: str, d2_pos: float, t: float):
        w = self._w.setdefault(source, deque(maxlen=self.N))
        self.first_pair_t.setdefault(source, t)
        if t - self.first_pair_t[source] < self.warmup_s:
            return
        w.append(d2_pos)
        if len(w) < self.N:
            return
        s = sum(w)
        if not self.flagged.get(source, False) and s > self.hi:
            self.flagged[source] = True; self.first_flag_t.setdefault(source, t)
        elif self.flagged.get(source, False) and s < self.lo:
            self.flagged[source] = False

    def is_flagged(self, source: str) -> bool:
        return bool(self.flagged.get(source, False))
