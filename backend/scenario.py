"""Scenario loading + validation (schema + cross-field rules). Raises ScenarioError with a locating message."""
from __future__ import annotations
import hashlib, json, pathlib
from dataclasses import dataclass, field, fields
import jsonschema, yaml
from .params import VehicleParams, Friction

SCHEMA_PATH = pathlib.Path(__file__).resolve().parent.parent / "schemas" / "scenario.schema.json"


class ScenarioError(ValueError):
    pass


@dataclass(frozen=True)
class ScriptedCmd:
    t: float
    a_cmd: float
    delta_cmd: float = 0.0
    mode: str = "comfort"


@dataclass(frozen=True)
class VehicleSpec:
    id: str
    x: float; y: float; psi: float; v: float; delta: float
    script: tuple


@dataclass(frozen=True)
class PedSpec:
    id: str
    radius: float
    path: tuple
    start_time: object   # float or dict(uniform)
    speed: object


@dataclass(frozen=True)
class ObstacleSpec:
    id: str
    cx: float; cy: float; length: float; width: float; yaw: float
    height: float = 3.0


@dataclass(frozen=True)
class Scenario:
    id: str
    dt: float
    duration: float
    stop_on_collision: bool
    stop_when_all_stopped: bool
    telemetry_every: int
    friction: Friction
    vparams: VehicleParams
    vehicles: tuple
    pedestrians: tuple
    obstacles: tuple
    raw: dict = field(compare=False, default_factory=dict)

    def config_sha256(self) -> str:
        return hashlib.sha256(json.dumps(self.raw, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _steps(t: float, dt: float, what: str) -> int:
    n = round(t / dt)
    if abs(n * dt - t) > 1e-9:
        raise ScenarioError(f"{what}={t} is not an integer multiple of dt={dt} (deterministic stepping requires it)")
    return n


def _upper(x) -> float:
    return x["high"] if isinstance(x, dict) else x


def scenario_from_dict(d: dict) -> Scenario:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(d), key=lambda e: list(e.absolute_path))
    if errs:
        e = errs[0]
        raise ScenarioError(f"schema: {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}")
    dt = float(d["dt"])
    known = {f.name for f in fields(VehicleParams)}
    vp_raw = d.get("vehicle_params", {})
    vparams = VehicleParams(**{k: v for k, v in vp_raw.items() if k in known})
    _steps(vparams.t_act, dt, "vehicle_params.t_act"); _steps(vparams.t_steer, dt, "vehicle_params.t_steer")
    _steps(d["duration"], dt, "duration")
    fr = Friction(mu=float(d["road"]["mu"]), g=float(d["road"].get("g", 9.81)))
    ids = [v["id"] for v in d["vehicles"]] + [p["id"] for p in d.get("pedestrians", [])] + [o["id"] for o in d.get("obstacles", [])]
    if len(ids) != len(set(ids)):
        raise ScenarioError("duplicate actor ids")
    vehicles = []
    for v in d["vehicles"]:
        script = tuple(sorted((ScriptedCmd(c["t"], c["a_cmd"], c.get("delta_cmd", 0.0), c.get("mode", "comfort"))
                               for c in v.get("script", [])), key=lambda c: c.t))
        for c in script:
            _steps(c.t, dt, f"vehicle {v['id']} script t")
        i = v["init"]
        if i["v"] > vparams.v_max_odd + 1e-9:
            raise ScenarioError(f"vehicle {v['id']} init v={i['v']} exceeds ODD cap {vparams.v_max_odd:.3f} m/s")
        vehicles.append(VehicleSpec(v["id"], i["x"], i["y"], i["psi"], i["v"], i.get("delta", 0.0), script))
    peds = []
    for p in d.get("pedestrians", []):
        for lo, hi in [(_lo(p["speed"]), _upper(p["speed"]))]:
            if lo > hi: raise ScenarioError(f"pedestrian {p['id']}: speed low > high")
        peds.append(PedSpec(p["id"], p.get("radius", 0.3), tuple(tuple(q) for q in p["path"]), p.get("start_time", 0.0), p["speed"]))
    # tunnelling guard: relative displacement per step must stay below the pedestrian radius
    vmax = vparams.v_max_odd
    for p in peds:
        if (vmax + _upper(p.speed)) * dt >= p.radius:
            raise ScenarioError(f"tunnelling guard: (v_max+v_ped)*dt={(vmax + _upper(p.speed)) * dt:.3f} >= radius {p.radius}; reduce dt")
    obstacles = tuple(ObstacleSpec(o["id"], o["center"][0], o["center"][1], o["size"][0], o["size"][1], o.get("yaw", 0.0), o.get("height", 3.0))
                      for o in d.get("obstacles", []))
    return Scenario(d["id"], dt, float(d["duration"]), d.get("stop_on_collision", True), d.get("stop_when_all_stopped", False),
                    d.get("telemetry_every", 1), fr, vparams, tuple(vehicles), tuple(peds), obstacles, raw=d)


def _lo(x) -> float:
    return x["low"] if isinstance(x, dict) else x


def load_scenario(path) -> Scenario:
    d = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
    return scenario_from_dict(d)
