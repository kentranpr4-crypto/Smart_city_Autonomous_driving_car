"""Physical parameters. EVERY value here is a [PARAM]: no source in the evidence registry (see docs/phase2/01 V02/V03)."""
from __future__ import annotations
import math
from dataclasses import dataclass

G = 9.81

LIMITATIONS = (
    "Flat horizontal plane; no slope or road elevation.",
    "Kinematic bicycle + friction circle; no tyre slip, load transfer, suspension, pitch, aero or rolling resistance.",
    "Uniform friction mu (a parameter); no source for Vietnamese inner-city roads.",
    "Jerk limit is NOT guaranteed at standstill: if braking is commanded until v=0, acceleration snaps to 0 within one step (jerk = |a|/dt, far above the limit). The model REPORTS this as event standstill_jerk_discontinuity; it only meets the limit if the controller eases the brake command to ~0 as v->0 (soft stop, tested in PHY-05).",
    "Rigid bodies; contact ends the run; no deformation, injury or post-impact dynamics.",
    "Pedestrians are kinematic and non-reactive (no gap acceptance, no crowd behaviour).",
    "Sensors/channel (later WPs) are statistical models over ground truth, not raw sensors or real V2X PHY/MAC.",
    "Not equivalent to CARLA or any commercial simulator; results hold only inside this model.",
    "Valid only inside the ODD: v <= 40 km/h and lateral accel <= ay_validity_fraction * mu * g, clear weather.",
    "Bit-exact determinism is guaranteed only within one recorded environment (Python/numpy/OS).",
)


@dataclass(frozen=True)
class VehicleParams:
    length: float = 4.5
    width: float = 1.8
    wheelbase: float = 2.7
    rear_overhang: float = 0.9
    wheel_radius: float = 0.32
    height: float = 1.5
    delta_max: float = math.radians(35.0)
    delta_rate_max: float = 0.6
    t_act: float = 0.15
    t_steer: float = 0.10
    a_brk_emergency: float = 6.0
    a_brk_comfort: float = 3.0
    j_emergency: float = 10.0
    j_comfort: float = 2.5
    a_acc: float = 2.0
    v_max_odd: float = 40.0 / 3.6
    ay_validity_fraction: float = 0.5

    def __post_init__(self):
        if self.rear_overhang + self.wheelbase > self.length + 1e-12:
            raise ValueError("rear_overhang + wheelbase exceeds vehicle length")

    @property
    def obb_offset(self) -> float:
        """Distance from the rear-axle reference point forward to the OBB centre."""
        return self.length / 2.0 - self.rear_overhang


@dataclass(frozen=True)
class Friction:
    mu: float = 0.8
    g: float = G

    @property
    def mug(self) -> float:
        return self.mu * self.g
