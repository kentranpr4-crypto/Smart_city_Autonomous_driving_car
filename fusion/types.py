"""Immutable data types of the cooperative world state. Pure data: no behaviour that touches truth, comm internals or any planner/controller."""
from __future__ import annotations
from dataclasses import dataclass, field

REASONS = ("nonfinite", "bad_covariance", "frame_mismatch", "future", "stale", "horizon", "bad_class", "duplicate_ref", "unauthenticated_source", "self_track")


@dataclass(frozen=True)
class Estimate:
    """One source's track estimate. State [x, y, vx, vy] in `frame`, valid at time `t` (the ORIGINAL observation time for remote data), covariance row-major 4x4."""
    source_id: str                   # observing source (origin), not the relay
    track_id: int                    # meaningful only inside source_id (source-scoped identity)
    t: float
    x: tuple
    P: tuple
    cls: str
    cls_prob: float
    kind: str                        # "local" | "remote"
    evidence: tuple                  # evidence ids: (origin source, origin seq, track id) for remote (one message carries several tracks), ("local:<src>", track_id) for local
    hops: int = 0
    relay_path: tuple = ()
    frame: str = "map"
    flags: tuple = ()

    @property
    def ref(self) -> tuple:
        return (self.source_id, self.track_id)


@dataclass(frozen=True)
class FusedTrack:
    fid: int                         # fusion-local identity (NOT globally persistent; derived from source-scoped refs)
    t: float
    x: tuple
    P: tuple
    cls: str
    method: str
    members: tuple                   # source-scoped refs that contributed
    evidence: tuple                  # evidence ids that contributed (each at most once)
    omega: tuple = ()                # CI weights (empty for other methods)
    flags: tuple = ()
    max_remote_age_s: float = 0.0
    assurance: str = "local"         # "local" | "allowlist-only" | "authenticated"  (weakest contributing source)


@dataclass(frozen=True)
class WorldState:
    """Cooperative world-state estimate. Positive information only: a region without tracks means NO INFORMATION, never 'free'."""
    t: float
    method: str
    tracks: tuple
    diagnostics: dict = field(default_factory=dict)
