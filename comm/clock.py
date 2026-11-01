"""Per-node clock model. t_sim is the controlled simulation clock; local(t_sim) is what that node's clock would read."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class NodeClock:
    clock_id: str = "clk"
    offset_s: float = 0.0
    drift_ppm: float = 0.0

    def local(self, t_sim: float) -> float:
        return t_sim * (1.0 + self.drift_ppm * 1e-6) + self.offset_s

    def sim(self, t_local: float) -> float:
        return (t_local - self.offset_s) / (1.0 + self.drift_ppm * 1e-6)
