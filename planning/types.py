"""Immutable data of the decision stack. No truth types, no backend types."""
from __future__ import annotations
from dataclasses import dataclass, field

LOCAL, CORROBORATED, ADVISORY, PENDING, REJECTED = "local", "corroborated", "advisory", "pending", "rejected"
EGO_SOURCE = "ego_cam"


@dataclass(frozen=True)
class EgoState:
    t: float
    x: float                  # rear-axle reference [m] (own localisation, noisy)
    v: float                  # speed [m/s]
    front_offset: float = 3.6 # rear axle -> front bumper
    length: float = 4.5


@dataclass(frozen=True)
class Rear:
    """Measurement of the vehicle behind (e.g. rear radar). None = nothing detected within range (NOT proof that nothing is there)."""
    gap: float | None
    v_follower: float | None


@dataclass(frozen=True)
class Hypothesis:
    hid: int
    x: float
    y: float
    vx: float
    vy: float
    P: tuple                  # 4x4 row-major
    cls: str
    level: str                # LOCAL | CORROBORATED | ADVISORY | PENDING | REJECTED
    sources: tuple
    remote_age_s: float = 0.0
    flags: tuple = ()
    persistence: int = 0
    assurance: str = "local"  # never "authenticated"
    phantom: bool = False     # E0-C map-prior hypothesis (not an observation)


@dataclass(frozen=True)
class Risk:
    p_conflict: float
    d_stop: float             # distance from the front bumper to the stop line (>= 0), inf if no longitudinal conflict
    a_req: float              # constant deceleration needed to stop before the conflict point
    precaution: bool
    v_cap: float              # speed ceiling that keeps a comfortable stop possible if the worst case materialises (inf = none)
    t_arrive: float


@dataclass(frozen=True)
class Decision:
    a_cmd: float
    mode: str
    a_local: float            # command that LOCAL evidence alone would have produced (P1 reference)
    a_prop: float             # command before supervisor limits
    reasons: tuple = ()
    diag: dict = field(default_factory=dict)
