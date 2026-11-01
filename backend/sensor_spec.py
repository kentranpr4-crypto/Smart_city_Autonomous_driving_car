"""Sensor specification (config). Statistical sensor models over ground truth; NOT a learned detector (R-PER-03)."""
from __future__ import annotations
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SensorSpec:
    id: str
    kind: str                         # 'vehicle' | 'cctv'
    height: float                     # mounting height h_s [m]
    fov: float                        # full angle [rad]
    range_m: float
    rate_hz: float
    mount_vehicle: str | None = None  # kind == 'vehicle'
    mount_offset: tuple = (0.5, 0.0)  # (dx, dy) from the vehicle OBB centre, in the vehicle frame
    yaw_offset: float = 0.0
    pose: tuple | None = None         # kind == 'cctv': (x, y, yaw) true pose
    pd0: float = 0.95                 # detection probability at r -> 0
    r50: float = 60.0                 # range at which p_d = pd0 / 2
    pd_slope: float = 8.0
    sigma0: float = 0.05              # position noise sigma(r) = sigma0 + sigma1 * r  [m]
    sigma1: float = 0.01
    bias: tuple = (0.0, 0.0)          # systematic offset in the map frame (extrinsic / localisation error), UNKNOWN to the tracker
    declared_sigma_scale: float = 1.0 # <1: over-confident sensor, >1: pessimistic
    clutter_rate: float = 0.0         # expected false positives per frame (Poisson, uniform in the FOV sector)
    class_accuracy: float = 1.0
    phase: float = 0.0
    t_proc: float = 0.0
    dropout: tuple | None = None      # (p_enter, p_exit): frame-level outage bursts (frames never delivered)

    def pd(self, r: float) -> float:
        return self.pd0 / (1.0 + math.exp((r - self.r50) / self.pd_slope))

    def sigma(self, r: float) -> float:
        return self.sigma0 + self.sigma1 * r
