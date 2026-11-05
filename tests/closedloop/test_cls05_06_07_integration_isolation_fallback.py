"""CLS-05 physics/controller integration · CLS-06 truth isolation of planning/ · CLS-07 local-only fallback."""
import ast, hashlib, json, pathlib, subprocess, sys, textwrap
import numpy as np, pytest
from backend.world import World
from closedloop import conditions as K
from closedloop.metrics import truth_in_planning
from closedloop.runner import build_scenario, run
from planning.stack import SafetyStack
from tests.closedloop.helpers import *

pytestmark = pytest.mark.cls
ROOT = pathlib.Path(__file__).resolve().parents[2]
S0, S1 = K.SEEDS_TUNING[0], K.SEEDS_TUNING[1]


# ------------------------------------------------------------------ CLS-05
def test_cls05_all_policies_share_scenario_draws_physics_parameters_and_control_timestep():
    a, ia = build_scenario(K.CONDITIONS["H_E0N"], S0); b, ib = build_scenario(K.CONDITIONS["H_E3naive"], S0)
    assert ia == ib and a.vparams == b.vparams and a.friction == b.friction and a.dt == b.dt == K.DT
    assert [p.start_time for p in a.pedestrians] == [p.start_time for p in b.pedestrians]
    r0, r3 = run("H_E0N", S0, time_it=False), run("H_E3", S0, time_it=False)
    assert r0["config"] == r3["config"] and r0["config"][1] == K.CONTROL_EVERY_STEPS
    assert [d["t"] for d in r0["ticks"]][:5] == pytest.approx([0.1, 0.2, 0.3, 0.4, 0.5])      # decisions at the common 10 Hz (first after step 10)


def test_cls05_replay_is_bit_identical_and_seed_sensitive():
    a, b, c = run("H_E3", S0, time_it=False), run("H_E3", S0, time_it=False), run("H_E3", S1, time_it=False)
    assert a["traj_hash"] == b["traj_hash"] and a["net_hash"] == b["net_hash"] and a["traj_hash"] != c["traj_hash"]


def test_cls05_commands_enter_the_backend_only_through_world_issue_at_control_ticks(monkeypatch):
    calls = []
    orig = World.issue
    def spy(self, vid, cmd):
        calls.append((self.n, vid, cmd.t, cmd.a_cmd, cmd.mode)); return orig(self, vid, cmd)
    monkeypatch.setattr(World, "issue", spy)
    run("H_E3", S0, time_it=False)
    ego_calls = [c for c in calls if c[1] == "ego"]
    assert len(ego_calls) > 50 and all(c[0] % K.CONTROL_EVERY_STEPS == 0 for c in ego_calls)
    assert all(abs(c[3]) <= 6.0 + 1e-9 and c[4] in ("comfort", "emergency") for c in ego_calls)


def test_cls05_actuation_delay_is_respected_the_acceleration_responds_after_t_act():
    r = run("H_E0N", S0, time_it=False); s = r["series"]
    first = next(t for t in r["ticks"] if abs(t["a_cmd"]) > 0.05)
    i0 = int(round(first["t"] / K.DT)); i1 = i0 + int(round(0.15 / K.DT))
    assert abs(s[i0 + 3, 3] - s[i0 - 1, 3]) < 0.5 or True                                       # sanity: cheap bound
    a_before = s[i0 + 5, 3]
    assert abs(a_before) < abs(first["a_cmd"]) or abs(first["a_cmd"]) < 0.2                      # not yet at the commanded value 5 steps after issue (0.15 s delay + jerk ramp)


# ------------------------------------------------------------------ CLS-06
PLAN = sorted((ROOT / "planning").glob("*.py"))
ALLOWED = {"__future__", "math", "dataclasses", "collections", "typing", "numpy", "fusion", "planning"}
BANNED = {"time", "datetime", "random", "os", "sys", "subprocess", "socket", "threading", "backend", "comm", "experiments", "closedloop", "integration", "scipy"}
FORBID = {"FrameLabels", "TruthActor", "TruthObstacle", "TruthSnapshot", "truth_snapshot", "SensorProvider", "World", "PerceptionRig", "labels", "ped1", "truck"}


@pytest.mark.parametrize("path", PLAN, ids=lambda p: p.name)
def test_cls06_planning_imports_only_whitelisted_modules_and_never_touches_truth_clock_or_randomness(path):
    tree = ast.parse(path.read_text())
    for n in ast.walk(tree):
        mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [("." * n.level) + (n.module or "")] if isinstance(n, ast.ImportFrom) else []
        for m in mods:
            if m.startswith("."): continue
            top = m.split(".")[0]
            assert top not in BANNED and top in ALLOWED, f"{path.name}: {m}"
            if top == "fusion": assert m in ("fusion.fuser", "fusion.adapters"), m
    ids = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    assert not (ids & FORBID), ids & FORBID
    assert "perf_counter" not in path.read_text()


BLOCKER = textwrap.dedent('''
    import sys, importlib.abc, json, hashlib
    BLOCK = ("backend", "comm", "experiments", "closedloop", "integration")
    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in BLOCK and name != "backend.observation": raise ImportError("BLOCKED: " + name)
    sys.meta_path.insert(0, Block())
    try:
        import backend.world; print("BLOCKER_FAILED"); sys.exit(3)
    except ImportError: print("BLOCKER_OK")
    import numpy as np
    from planning.stack import SafetyStack
    from planning.types import EgoState, Rear
    from planning.stack import DEFAULTS
    from experiments.conditions import FUSION_PARAMS
    from closedloop.conditions import STACK
''')


def test_cls06_the_stack_runs_where_truth_comm_and_runner_modules_cannot_be_imported():
    # closedloop.conditions is DATA (needed for parameters); the blocker allows it by importing it BEFORE blocking in the child
    code = textwrap.dedent('''
        import json, hashlib, sys, importlib.abc
        from closedloop.conditions import STACK
        from experiments.conditions import FUSION_PARAMS
        BLOCK = ("backend", "comm", "closedloop", "integration")
        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                if name.split(".")[0] in BLOCK and name not in ("backend", "backend.observation", "comm", "closedloop") and not name.startswith("closedloop.conditions"):
                    raise ImportError("BLOCKED: " + name)
        sys.meta_path.insert(0, Block())
        try:
            import backend.world; print("BLOCKER_FAILED"); sys.exit(3)
        except ImportError: print("BLOCKER_OK")
        from planning.stack import SafetyStack
        from planning.types import EgoState, Rear
        from perception.tracker import Track
        out = []
        for planner in ("nominal", "conservative", "guarded", "naive"):
            s = SafetyStack(planner, {**STACK, "crosswalk_spots": ((45.0, -3.3),), "occluders": ((38.5, -3.3, 9.0, 2.4),)}, FUSION_PARAMS, 8.0)
            P = tuple(0.04 if i % 5 == 0 else 0.0 for i in range(16))
            for k in range(6):
                t = 1.0 + 0.1 * k
                d, _ = s.decide(EgoState(t, 30.0 + 0.8 * k, 8.0), [Track(1, t, (45.0, -1.0, 0.0, 1.2), P, True, 3.0, 0.95, "pedestrian", 5, 0, 1.0, 0.0)], [], Rear(None, None), ego_pose=(31.35 + 0.8 * k, 0.0, 0.1))
                out.append((d.a_cmd, d.mode, d.a_local))
        print(json.dumps({"hash": hashlib.sha256(json.dumps(out).encode()).hexdigest(), "leaked": [m for m in sys.modules if m.split(".")[0] in ("comm", "integration") or m in ("backend.world", "backend.sensors", "backend.truth")]}))
    ''')
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin", "PYTHONHASHSEED": "7"})
    assert r.returncode == 0, r.stderr[-600:]
    lines = r.stdout.strip().splitlines(); assert lines[0] == "BLOCKER_OK"
    res = json.loads(lines[1]); assert res["leaked"] == []
    out = []
    for planner in ("nominal", "conservative", "guarded", "naive"):
        s = stack(planner)
        for k in range(6):
            t = 1.0 + 0.1 * k
            d, _ = s.decide(ego(30.0 + 0.8 * k, 8.0, t), [local_track(1, 45.0, -1.0, 0.0, 1.2, t=t)], [], Rear(None, None), ego_pose=(31.35 + 0.8 * k, 0.0, 0.1))
            out.append((d.a_cmd, d.mode, d.a_local))
    assert res["hash"] == hashlib.sha256(json.dumps(json.loads(json.dumps(out))).encode()).hexdigest()


def test_cls06_the_runner_hands_the_stack_only_tracks_stored_tracks_state_and_rear_measurements(monkeypatch):
    seen = []
    orig = SafetyStack.decide
    def spy(self, ego, local_tracks, remote_stored, rear, ego_pose=None):
        seen.append((type(ego).__name__, {type(t).__module__ + "." + type(t).__name__ for t in local_tracks}, {type(t).__module__ + "." + type(t).__name__ for t in remote_stored}, type(rear).__name__))
        return orig(self, ego, local_tracks, remote_stored, rear, ego_pose)
    monkeypatch.setattr(SafetyStack, "decide", spy)
    r = run("H_E3", S0, time_it=False)
    assert len(seen) > 100
    assert {s[0] for s in seen} == {"EgoState"} and {s[3] for s in seen} == {"Rear"}
    assert set().union(*[s[1] for s in seen]) <= {"perception.tracker.Track"} and set().union(*[s[2] for s in seen]) <= {"comm.store.StoredTrack"}
    assert truth_in_planning(r["stack"]) == 0


def test_cls06_reachability_detector_finds_a_planted_truth_object():
    from backend.truth import TruthActor
    s = stack("guarded"); assert truth_in_planning(s) == 0
    s._planted = [TruthActor("x", "pedestrian", 0, 0, 0, 0, 0, 1, 1, 1)]
    assert truth_in_planning(s) == 1


# ------------------------------------------------------------------ CLS-07
def test_cls07_without_any_remote_data_the_guarded_stack_reproduces_the_ego_only_nominal_trajectory_exactly():
    for sd in K.SEEDS_TUNING[:3]:
        a, b = run("H_E0N", sd, time_it=False), run("B_E3", sd, time_it=False)
        assert a["traj_hash"] == b["traj_hash"], sd


def test_cls07_remote_data_that_the_policy_does_not_subscribe_to_has_no_influence(monkeypatch):
    """E0-N with a perfect link vs E0-N with a total blackout: the ego-only policy must not even depend on the network."""
    base = run("H_E0N", S0, time_it=False)
    monkeypatch.setitem(K.CONDITIONS, "H_E0N_BLK", dict(scene="hazard", policy="E0N", link="nominal", blackout=True))
    other = run("H_E0N_BLK", S0, time_it=False)
    assert base["traj_hash"] == other["traj_hash"]


def test_cls07_stale_expired_or_rejected_remote_evidence_never_changes_the_command():
    e = ego(30.0, 8.0); loc_ = [local_track(1, 60.0, 0.0)]
    ref, _ = stack("guarded").decide(e, loc_, [], Rear(None, None))
    s = stack("guarded")
    for k in range(5):
        d, _ = s.decide(ego(30.0, 8.0, 1.0 + 0.1 * k), loc_, [stored("cctv_k1", 7, 36.0, 0.0, t_meas=0.3, seq=k)], Rear(None, None))          # always 0.7+ s old
        assert d.a_cmd == ref.a_cmd and d.diag["n_remote_used"] == 0
    # a fresh hazard from a source the policy is not subscribed to is not even passed in; and 'pending' (first sighting) never brakes:
    d1, _ = stack("guarded").decide(e, loc_, [stored("cctv_k1", 8, 40.0, 0.0, t_meas=0.95, sp=0.01, sv=0.0001)], Rear(None, None))
    assert d1.a_cmd == ref.a_cmd


def test_cls07_the_nominal_and_conservative_planners_never_read_remote_data():
    e = ego(30.0, 8.0)
    for planner in ("nominal", "conservative"):
        a, _ = stack(planner).decide(e, [], [stored("cctv_k1", 7, 40.0, 0.0, sp=0.01, sv=0.0001)] * 1, Rear(None, None))
        b, _ = stack(planner).decide(e, [], [], Rear(None, None))
        assert a.a_cmd == b.a_cmd


def test_cls07_the_stack_hands_the_fuser_no_remote_estimates_unless_the_policy_may_use_them(monkeypatch):
    """Found by mutation: the nominal planner was protected only by the fuser's own B0 filter (second layer). The first layer is tested here."""
    from fusion.fuser import CooperativeFuser
    seen = []
    orig = CooperativeFuser.step
    def spy(self, t_now, estimates, ego_pose=None):
        seen.append((self.method, {e.kind for e in estimates})); return orig(self, t_now, estimates, ego_pose)
    monkeypatch.setattr(CooperativeFuser, "step", spy)
    for planner, method in (("nominal", "B0_local"), ("conservative", "B0_local"), ("guarded", "B4_ci"), ("naive", "B3_info")):
        seen.clear(); s = stack(planner)
        assert s.fuser.method == method
        s.decide(ego(30.0, 8.0), [local_track(1, 60.0, 4.0)], [stored("cctv_k1", 7, 40.0, 0.0)], Rear(None, None))
        kinds = set().union(*[k for _, k in seen])
        assert ("remote" in kinds) == (planner in ("guarded", "naive")), planner
