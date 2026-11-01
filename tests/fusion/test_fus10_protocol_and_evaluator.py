"""FUS-10 · experiment protocol integrity, evaluator correctness on synthetic cases with known answers, no truth in the inference path, replay."""
import hashlib, json, math, pathlib
import numpy as np, pytest
from experiments import conditions as K
from experiments.harness import run
from experiments.metrics import match, per_run, pool, run_hash, truth_objects_reachable
from fusion.fuser import CooperativeFuser
from fusion.types import Estimate

pytestmark = pytest.mark.fus
ROOT = pathlib.Path(__file__).resolve().parents[2]
PRE = json.loads((ROOT / "fusion" / "preregistration.json").read_text())


def test_fus10_preregistration_hashes_match_the_files_and_the_document():
    assert hashlib.sha256((ROOT / "experiments" / "conditions.py").read_bytes()).hexdigest() == PRE["conditions_sha256"]
    doc = (ROOT / "docs" / "phase2" / "09-wp4-fusion-requirements.md").read_text()
    assert hashlib.sha256((ROOT / "fusion" / "preregistration.json").read_bytes()).hexdigest() in doc


def test_fus10_tuning_and_evaluation_seeds_are_disjoint_and_as_declared():
    assert not (set(K.SEEDS_TUNING) & set(K.SEEDS_EVAL)) and len(K.SEEDS_TUNING) == 15 and len(K.SEEDS_EVAL) == 30
    assert PRE["seeds"] == {"tuning": [K.SEEDS_TUNING[0], K.SEEDS_TUNING[-1]], "evaluation": [K.SEEDS_EVAL[0], K.SEEDS_EVAL[-1]], "replay": 3}
    assert set(K.REPLAY_SEEDS) <= set(K.SEEDS_EVAL)


def test_fus10_every_required_experiment_has_a_condition_and_every_method_is_registered():
    assert {c["exp"] for c in K.CONDITIONS.values()} >= set(range(1, 10))
    assert set(PRE["methods"]) == set(K.METHODS) and {"B0_local", "B1_remote", "B2_naive", "B3_info", "B4_ci"} <= set(K.METHODS)
    ids = [t["id"] for t in PRE["thresholds"]]; assert len(ids) == len(set(ids))
    conds = set(K.CONDITIONS)
    for t in PRE["thresholds"]:
        assert t["scope"] == "all" or t["scope"] in conds
        assert t["kind"] in ("invariant", "hypothesis")


def test_fus10_no_evaluation_seed_is_used_by_tests_or_default_arguments():
    for p in list((ROOT / "tests" / "fusion").glob("*.py")) + [ROOT / "experiments" / "harness.py", ROOT / "experiments" / "metrics.py"]:
        txt = p.read_text()
        assert "SEEDS_EVAL" not in txt or p.name == "test_fus10_protocol_and_evaluator.py", p.name
        assert "202613" not in txt or p.name == "test_fus10_protocol_and_evaluator.py", p.name


def synth(tracks_by_cycle, truth_by_cycle, vis_ego=True, vis_rem=True):
    cyc = []
    for i, (tr, tt) in enumerate(zip(tracks_by_cycle, truth_by_cycle)):
        cyc.append({"t": 1.5 + 0.1 * i, "truth": tt, "truth_all": tt, "vis": {"ego_cam": list(tt) if vis_ego else [], "cctv_k1": list(tt) if vis_rem else []}, "det": {"ego_cam": list(tt), "cctv_k1": list(tt)},
                    "local": [], "remote": [], "methods": {"B0_local": {"tracks": [], "rej": {}, "pair_d2": (), "runtime_s": 0.001},
                                                        "B4_ci": {"tracks": tr, "rej": {}, "pair_d2": (), "runtime_s": 0.002}}})
    return {"cond": "x", "seed": 0, "targets": ("a",), "cycles": cyc, "blackout": None, "monitor": {}}


def T(fid, x, y, vx=0.0, vy=0.0, p=0.04):
    return (fid, (x, y, vx, vy), tuple(np.diag([p, p, p, p]).reshape(-1)), (("k", fid),), (), (("k", 1, fid),), 0.0)


def test_fus10_evaluator_metrics_on_a_case_with_a_hand_computed_answer():
    truth = {"a": (10.0, 0.0, 1.0, 0.0)}
    tracks = [[T(1, 10.3, 0.4, 1.0, 0.0)], [T(1, 10.0, 0.0, 1.0, 0.0)], [], [T(1, 10.6, 0.0, 1.0, 0.0)]]      # errors: 0.5 m, 0 m, miss, 0.6 m (0.04 variance -> sigma 0.2)
    r = synth(tracks, [truth] * 4)
    S = per_run(r, "B4_ci")
    assert S["n_opp"] == 4 and S["n_hit"] == 3 and S["avail"] == pytest.approx(0.75)
    assert S["pos_sq"] == pytest.approx(0.25 + 0.0 + 0.36) and S["m"] == 3
    assert S["nees_sum"] == pytest.approx((0.09 + 0.16) / 0.04 + 0.0 + 0.36 / 0.04) and S["cov_hit"] == 3          # NEES: 6.25, 0, 9 -> all <= 9.4877
    p = pool([r], "B4_ci")
    assert p["pos_rmse"] == pytest.approx(math.sqrt(0.61 / 3)) and p["availability"] == pytest.approx(0.75)


def test_fus10_evaluator_counts_id_switches_false_tracks_and_gates():
    truth = {"a": (10.0, 0.0, 0.0, 0.0)}
    tr = [[T(1, 10, 0)], [T(1, 10, 0)], [T(2, 10, 0)], [T(2, 10, 0), T(9, 40, 40)]]
    S = per_run(synth(tr, [truth] * 4), "B4_ci")
    assert S["switches"] == 1 and S["false"] == 1
    assert match([("k", 14.0, 0.0)], truth) == {}                                                          # beyond the 2 m gate
    assert match([("k", 11.0, 0.0)], truth) == {"a": "k"}


def test_fus10_ttfv_is_measured_from_first_observability_and_censored_when_never_valid():
    truth = {"a": (10.0, 0.0, 0.0, 0.0)}
    r = synth([[], [], [T(1, 10, 0)]], [truth] * 3)
    assert per_run(r, "B4_ci")["ttfv"] == [pytest.approx(0.2)]
    never = synth([[], [], []], [truth] * 3)
    assert per_run(never, "B4_ci")["ttfv"][0] >= 0.3 - 1e-9


def test_fus10_truth_reachability_detector_really_detects_a_planted_truth_object():
    f = CooperativeFuser("B4_ci"); assert truth_objects_reachable(f) == 0
    from backend.truth import TruthActor
    f._planted = [TruthActor("x", "pedestrian", 0, 0, 0, 0, 0, 1, 1, 1)]
    assert truth_objects_reachable(f) == 1


def test_fus10_fusion_only_ever_receives_estimates_and_an_ego_pose(monkeypatch):
    seen = []
    orig = CooperativeFuser.step
    def spy(self, t_now, estimates, ego_pose=None):
        seen.append((type(t_now), {type(e) for e in estimates}, type(ego_pose)))
        return orig(self, t_now, estimates, ego_pose)
    monkeypatch.setattr(CooperativeFuser, "step", spy)
    r = run("C1_occ_nominal", K.SEEDS_TUNING[0], methods=("B4_ci",), time_it=False)
    assert len(seen) > 100 and {s[0] for s in seen} == {float} and set().union(*[s[1] for s in seen]) == {Estimate} and {s[2] for s in seen} == {tuple}
    assert truth_objects_reachable(r["fusers"]["B4_ci"]) == 0


def test_fus10_experiment_replay_is_bit_identical_and_seed_sensitive():
    a = run("C7a_occ_degraded", K.SEEDS_TUNING[1], time_it=False); b = run("C7a_occ_degraded", K.SEEDS_TUNING[1], time_it=False); c = run("C7a_occ_degraded", K.SEEDS_TUNING[2], time_it=False)
    assert run_hash(a) == run_hash(b) != run_hash(c)


def test_fus10_every_threshold_metric_is_computable_by_the_pooling_code():
    r = [run("C1_occ_nominal", K.SEEDS_TUNING[0], time_it=False)]
    keys = set(pool(r, "B4_ci"))
    pooled_only = {"remote_admitted_fraction", "distinct_obs_admitted_ratio", "replay_mismatches", "run_exceptions", "truth_objects_reachable_from_fuser"}
    for t in PRE["thresholds"]:
        assert t["metric"] in keys or t["metric"] in pooled_only, t["metric"]


def test_fus10_committed_final_evidence_if_present_is_complete_and_consistent():
    p = ROOT / "docs" / "phase2" / "wp-reports" / "evidence" / "wp4" / "eval" / "results.json"
    if not p.exists():
        pytest.skip("final evaluation not generated yet")
    R = json.loads(p.read_text())
    assert R["mode"] == "eval" and R["n_seeds"] == 30 and R["preregistration_sha256"] == hashlib.sha256((ROOT / "fusion" / "preregistration.json").read_bytes()).hexdigest()
    assert {v["id"] for v in R["verdicts"]} == {t["id"] for t in PRE["thresholds"]}
    assert all(v["status"] == "PASS" for v in R["verdicts"] if v["kind"] == "invariant")
    assert all(v["status"] in ("SUPPORTED", "REFUTED", "NOT_EVALUABLE") for v in R["verdicts"] if v["kind"] == "hypothesis")


def test_fus10_nees_uses_the_full_covariance_not_just_its_first_diagonal_entry():
    """Found by mutation (NEES = e.e / P00 survived because the earlier synthetic covariance was isotropic): anisotropic P, error along y."""
    truth = {"a": (10.0, 0.0, 0.0, 0.0)}
    P = np.diag([0.04, 0.16, 0.04, 0.04])
    tr = [(1, (10.0, 0.4, 0.0, 0.0), tuple(P.reshape(-1)), (("k", 1),), (), (("k", 1, 1),), 0.0)]
    S = per_run(synth([tr], [truth]), "B4_ci")
    assert S["nees_sum"] == pytest.approx(0.4 ** 2 / 0.16) and S["cov_hit"] == 1
    off = np.array([[0.04, 0.03, 0, 0], [0.03, 0.04, 0, 0], [0, 0, 0.04, 0], [0, 0, 0, 0.04]])
    tr2 = [(1, (10.2, 0.0, 0.0, 0.0), tuple(off.reshape(-1)), (("k", 1),), (), (("k", 1, 1),), 0.0)]
    e = np.array([0.2, 0, 0, 0]); assert per_run(synth([tr2], [truth]), "B4_ci")["nees_sum"] == pytest.approx(float(e @ np.linalg.solve(off, e)))
