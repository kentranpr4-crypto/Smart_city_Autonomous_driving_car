"""TRUTH-SIDE types. Perception code must never import this module (enforced by tests/perception/test_iso_*.py)."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class TruthActor:
    id: str
    kind: str                         # 'vehicle' | 'pedestrian'
    x: float
    y: float
    vx: float
    vy: float
    psi: float
    length: float
    width: float
    height: float


@dataclass(frozen=True)
class TruthObstacle:
    id: str
    cx: float
    cy: float
    yaw: float
    length: float
    width: float
    height: float


@dataclass(frozen=True)
class TruthSnapshot:
    t: float
    actors: tuple
    obstacles: tuple
