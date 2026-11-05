"""CLS-10 · protocol integrity: preregistration pins, freeze record, seed separation, computable metrics, complete final evidence."""
import hashlib, json, pathlib
import pytest
from closedloop import conditions as K
from closedloop.freeze import tree_hashes
from closedloop.metrics import pool
from closedloop.runner import run

pytestmark = pytest.mark.cls
ROOT = pathlib.Path(__file__).resolve().parents[2]
PRE = json.loads((ROOT / "closedloop" / "preregistration.json").read_text())
DOC = (ROOT / "docs" / "phase2" / "10-wp5-closedloop-safety.md").read_text()


def test_cls10_preregistration_pins_match_the_files_and_the_document():
    assert hashlib.sha256((ROOT / "closedloop" / "conditions.py").read_bytes()).hexdigest() == PRE["conditions_sha256"]
    assert hashlib.sha256((ROOT / "closedloop" / "preregistration.json").read_bytes()).hexdigest() in DOC


def test_cls10_seeds_are_disjoint_and_as_declared():
    assert not (set(K.SEEDS_TUNING) & set(K.SEEDS_EVAL)) and len(K.SEEDS_TUNING) == 15 and len(K.SEEDS_EVAL) == 40
    assert PRE["seeds"] == {"tuning": [K.SEEDS_TUNING[0], K.SEEDS_TUNING[-1]], "evaluation": [K.SEEDS_EVAL[0], K.SEEDS_EVAL[-1]], "replay": 3} and set(K.REPLAY_SEEDS) <= set(K.SEEDS_EVAL)


def test_cls10_no_test_or_default_argument_uses_an_evaluation_seed():
    for p in list((ROOT / "tests" / "closedloop").glob("*.py")) + [ROOT / "closedloop" / "runner.py", ROOT / "closedloop" / "metrics.py"]:
        txt = p.read_text()
        assert ("SEEDS_EVAL" not in txt and "202615" not in txt) or p.name == "test_cls10_protocol.py", p.name


def test_cls10_every_condition_references_known_policies_and_every_threshold_a_known_condition():
    for c in K.CONDITIONS.values(): assert c["policy"] in K.POLICIES and c["scene"] in ("hazard", "control", "ghost") and c["link"] in K.LINKS
    ids = [t["id"] for t in PRE["thresholds"]]; assert len(ids) == len(set(ids))
    for t in PRE["thresholds"]:
        assert t["scope"] == "all" or t["scope"] in K.CONDITIONS
        if isinstance(t["value"], dict): assert all(r.split(":")[0] in K.CONDITIONS for r in t["value"]["of"])
        assert t["kind"] in ("invariant", "hypothesis", "report")
    assert {"E0N", "E0C", "E1", "E2", "E3"} <= set(K.POLICIES)


def test_cls10_every_threshold_metric_is_produced_by_the_pooling_code():
    keys = set(pool([run("H_E3", K.SEEDS_TUNING[0], time_it=True)], base_runs={K.SEEDS_TUNING[0]: run("H_E0N", K.SEEDS_TUNING[0])}, ref_traj={K.SEEDS_TUNING[0]: "x"}))
    run_level = {"truth_in_planning", "replay_mismatches", "run_exceptions", "physics_config_mismatch"}
    for t in PRE["thresholds"]: assert t["metric"] in keys or t["metric"] in run_level, t["metric"]


def test_cls10_freeze_record_if_present_matches_the_frozen_tree():
    p = ROOT / "closedloop" / "FREEZE.json"
    if not p.exists(): pytest.skip("freeze not recorded yet")
    fz = json.loads(p.read_text())
    assert fz["tree_hashes"] == tree_hashes(), "frozen code, physics or protocol changed after the freeze record"
    assert fz["preregistration_sha256"] == hashlib.sha256((ROOT / "closedloop" / "preregistration.json").read_bytes()).hexdigest()


def test_cls10_final_evidence_if_present_is_complete_and_consistent():
    p = ROOT / "docs" / "phase2" / "wp-reports" / "evidence" / "wp5" / "eval" / "results.json"
    if not p.exists(): pytest.skip("final evaluation not generated yet")
    R = json.loads(p.read_text())
    assert R["mode"] == "eval" and R["n_seeds"] == 40 and {v["id"] for v in R["verdicts"]} == {t["id"] for t in PRE["thresholds"]}
    assert all(v["status"] == "PASS" for v in R["verdicts"] if v["kind"] == "invariant")
    assert all(v["status"] in ("SUPPORTED", "REFUTED", "NOT_EVALUABLE") for v in R["verdicts"] if v["kind"] == "hypothesis")
