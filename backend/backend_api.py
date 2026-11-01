"""Backend-agnostic interface (docs/phase2/07 §9). CarlaBackend is NOT implemented and NOT validated; PX-1 not done."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from .scenario import Scenario, ScriptedCmd
from .telemetry import TelemetryWriter
from .world import World, BACKEND_NAME, BACKEND_VERSION
from .params import LIMITATIONS


@dataclass(frozen=True)
class ControlCmd:
    a_cmd: float
    delta_cmd: float = 0.0
    mode: str = "comfort"


@dataclass(frozen=True)
class BackendMetadata:
    name: str
    version: str
    dt: float
    limitations: tuple
    carla_equivalent: bool = False


class PhysicsBackend(Protocol):
    def reset(self, scenario: Scenario, seed: int) -> None: ...
    def step(self) -> None: ...
    def apply_control(self, actor_id: str, ctrl: ControlCmd) -> None: ...
    def truth(self) -> dict: ...
    def time(self) -> float: ...
    def metadata(self) -> BackendMetadata: ...


class LightweightBackend:
    """PhysicsBackend over backend.world.World. truth() is for metrics, UI and the SensorProvider only (I9)."""
    def __init__(self):
        self.world: World | None = None

    def reset(self, scenario: Scenario, seed: int) -> None:
        self.world = World(scenario, seed, TelemetryWriter(keep=False))

    def step(self) -> None:
        self.world.step()

    def apply_control(self, actor_id: str, ctrl: ControlCmd) -> None:
        self.world.issue(actor_id, ScriptedCmd(t=self.world.t, a_cmd=ctrl.a_cmd, delta_cmd=ctrl.delta_cmd, mode=ctrl.mode))

    def truth(self) -> dict:
        w = self.world
        return {"t": w.t, "vehicles": dict(w.veh), "pedestrians": {p.id: p.at(w.t) for p in w.peds}}

    def time(self) -> float:
        return self.world.t

    def metadata(self) -> BackendMetadata:
        return BackendMetadata(BACKEND_NAME, BACKEND_VERSION, self.world.dt, LIMITATIONS, carla_equivalent=False)
