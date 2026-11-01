"""Scenario validation (AC-M02, partial) and telemetry schema conformance (AC-VS-10, physics subset)."""
import copy, json, pathlib
import jsonschema, pytest
from backend.run import run_scenario
from backend.scenario import ScenarioError, scenario_from_dict, load_scenario
from tests.physics.helpers import make, run

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "schemas" / "telemetry.schema.json").read_text())


@pytest.mark.parametrize("mutate,msg", [
    (lambda d: d.pop("dt"), "schema"),
    (lambda d: d.update(dt=-0.01), "schema"),
    (lambda d: d.update(surprise=1), "schema"),
    (lambda d: d["vehicles"].append(copy.deepcopy(d["vehicles"][0])), "duplicate"),
    (lambda d: d["vehicles"][0]["init"].update(v=30.0), "ODD cap"),
    (lambda d: d["vehicles"][0].update(script=[{"t": 0.005, "a_cmd": -1}]), "multiple of dt"),
    (lambda d: d.update(vehicle_params={"t_act": 0.155}), "multiple of dt"),
    (lambda d: d.update(road={"mu": 0}), "schema"),
])
def test_invalid_scenarios_are_rejected_with_location(mutate, msg):
    d = make(); mutate(d)
    with pytest.raises(ScenarioError, match=msg):
        scenario_from_dict(d)


@pytest.mark.parametrize("name", ["s00a_physics_sandbox_brake_early.yaml", "s00b_physics_sandbox_brake_late.yaml"])
def test_shipped_scenarios_load_and_telemetry_validates(name, tmp_path):
    m, tw = run_scenario(ROOT / "scenarios" / name, 7, tmp_path, keep=True)
    v = jsonschema.Draft202012Validator(SCHEMA)
    bad = [(i, e.message) for i, rec in enumerate(tw.lines) for e in v.iter_errors(rec)]
    assert not bad, bad[:3]
    assert (tmp_path / "manifest.json").exists()
    assert m["backend"]["carla_equivalent"] is False and m["backend"]["limitations"]


def test_manifest_records_environment_and_config_hash(tmp_path):
    m, _ = run_scenario(ROOT / "scenarios" / "s00a_physics_sandbox_brake_early.yaml", 7, tmp_path)
    assert {"python", "numpy", "platform"} <= set(m["environment"]) and len(m["config_sha256"]) == 64
