"""FUS-08 world state independent of planner/truth, deterministic · FUS-09 consistency monitor + authenticated-identity interface (fail closed)."""
import ast, dataclasses, hashlib, json, pathlib, subprocess, sys, textwrap
import numpy as np, pytest
from fusion.fuser import CooperativeFuser
from fusion.identity import AUTHENTICATED, ALLOWLIST_ONLY, _UnsafeTestOnlyAcceptAllVerifier, UnauthenticatedVerifier
from fusion.monitor import ConsistencyMonitor
from fusion.types import FusedTrack, WorldState
from perception.stats import chi2_ppf
from tests.fusion.helpers import est, loc, P4

pytestmark = pytest.mark.fus
ROOT = pathlib.Path(__file__).resolve().parents[2]
FILES = sorted((ROOT / "fusion").glob("*.py"))
ALLOWED = {"__future__", "math", "dataclasses", "collections", "typing", "numpy", "fusion", "perception"}
BANNED = {"time", "datetime", "random", "os", "sys", "subprocess", "socket", "threading", "backend", "comm", "experiments", "integration", "scipy"}
FORBIDDEN_IDS = {"FrameLabels", "TruthActor", "TruthSnapshot", "truth_snapshot", "SensorProvider", "World", "PerceptionRig", "labels", "planner", "controller", "brake", "free_space", "is_free"}


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_fus08_fusion_imports_are_whitelisted_and_exclude_truth_comm_backend_clock_and_random(path):
    tree = ast.parse(path.read_text())
    for n in ast.walk(tree):
        mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [("." * n.level) + (n.module or "")] if isinstance(n, ast.ImportFrom) else []
        for mod in mods:
            if mod.startswith("."): continue
            top = mod.split(".")[0]
            assert top not in BANNED and top in ALLOWED, f"{path.name}: {mod}"
            if top == "perception": assert mod in ("perception.hungarian", "perception.stats"), mod
    ids = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    assert not (ids & FORBIDDEN_IDS), ids & FORBIDDEN_IDS
    assert "perf_counter" not in path.read_text() and "time.time" not in path.read_text()


BLOCKER = textwrap.dedent('''
    import sys, importlib.abc, json, hashlib
    BLOCK = ("backend", "comm", "experiments", "integration")
    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name.split(".")[0] in BLOCK and name != "backend.observation":
                raise ImportError("BLOCKED: " + name)
    sys.meta_path.insert(0, Block())
    try:
        import backend.world; print("BLOCKER_FAILED"); sys.exit(3)
    except ImportError: print("BLOCKER_OK")
    import numpy as np
    from fusion.fuser import CooperativeFuser
    from tests.fusion.helpers import est, loc
    out = []
    for m in ("B0_local", "B1_remote", "B2_naive", "B3_info", "B4_ci", "B4q_ci_quarantine"):
        f = CooperativeFuser(m)
        for k in range(5):
            t = 1.0 + 0.1 * k
            w = f.step(t, [loc(1, t=t, x=(10 + t, 0, 1, 0)), est("k", 1, t=t - 0.05, x=(10 + t - 0.05, 0.1, 1, 0), seq=k), est("k", 2, t=t - 0.05, x=(30, 5, 0, 1), seq=k)])
            out.append([(tr.fid, tr.x, tr.P, tr.members) for tr in w.tracks])
    print(json.dumps({"hash": hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest(), "leaked": [m for m in sys.modules if m.split(".")[0] in BLOCK and m != "backend.observation"]}))
''')


def test_fus08_fusion_runs_with_truth_comm_and_backend_modules_blocked_and_gives_identical_results():
    r = subprocess.run([sys.executable, "-c", BLOCKER], cwd=ROOT, capture_output=True, text=True, env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin", "PYTHONHASHSEED": "42"})
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines(); assert lines[0] == "BLOCKER_OK"
    res = json.loads(lines[1]); assert res["leaked"] == []
    out = []
    for m in ("B0_local", "B1_remote", "B2_naive", "B3_info", "B4_ci", "B4q_ci_quarantine"):
        f = CooperativeFuser(m)
        for k in range(5):
            t = 1.0 + 0.1 * k
            w = f.step(t, [loc(1, t=t, x=(10 + t, 0, 1, 0)), est("k", 1, t=t - 0.05, x=(10 + t - 0.05, 0.1, 1, 0), seq=k), est("k", 2, t=t - 0.05, x=(30, 5, 0, 1), seq=k)])
            out.append([(tr.fid, tr.x, tr.P, tr.members) for tr in w.tracks])
    assert res["hash"] == hashlib.sha256(json.dumps(json.loads(json.dumps(out)), sort_keys=True).encode()).hexdigest()


def test_fus08_world_state_is_immutable_plain_data_with_no_planner_surface():
    w = CooperativeFuser("B4_ci").step(1.0, [loc(1), est("k", 1, seq=1)])
    with pytest.raises(dataclasses.FrozenInstanceError): w.tracks[0].x = (0, 0, 0, 0)
    with pytest.raises(dataclasses.FrozenInstanceError): w.t = 0.0
    assert dataclasses.is_dataclass(w) and dataclasses.is_dataclass(w.tracks[0])
    api = {n for n in dir(CooperativeFuser) if not n.startswith("_")}
    assert api == {"step"} | {n for n in api if False} or api <= {"step"}                              # the only public behaviour is step(t, estimates) -> WorldState


def test_fus08_replay_is_bit_identical_and_independent_of_input_order():
    ests = [loc(1), loc(2, x=(10, 5, 1, 0)), est("k", 1, seq=1, x=(10.1, 0.0, 1, 0)), est("k", 2, seq=1, x=(10.0, 5.1, 1, 0)), est("v", 3, seq=1, x=(9.9, 0.1, 1, 0))]
    runs = [CooperativeFuser("B4_ci").step(1.0, e) for e in (ests, list(reversed(ests)), sorted(ests, key=lambda q: q.track_id))]
    assert runs[0] == runs[1] == runs[2]


def test_fus08_ids_persist_across_cycles_and_survive_loss_of_one_source():
    f = CooperativeFuser("B4_ci")
    a = f.step(1.0, [loc(1), est("k", 1, seq=1)]).tracks[0].fid
    b = f.step(1.1, [loc(1, t=1.1, x=(10.1, 0, 1, 0)), est("k", 1, t=1.1, x=(10.1, 0, 1, 0), seq=2)]).tracks[0].fid
    c = f.step(1.2, [loc(1, t=1.2, x=(10.2, 0, 1, 0))]).tracks[0].fid                                   # remote lost: still the local ref
    assert a == b == c


# ------------------------------------------------------------------ FUS-09
def test_fus09_monitor_threshold_and_hysteresis():
    m = ConsistencyMonitor(10, 0.999)
    assert m.hi == pytest.approx(chi2_ppf(0.999, 20)) and m.lo == pytest.approx(chi2_ppf(0.95, 20)) and m.hi > m.lo
    for i in range(9): m.push("k", 100.0, i)
    assert not m.is_flagged("k")                                                                        # not enough pairs yet
    m.push("k", 100.0, 9); assert m.is_flagged("k") and m.first_flag_t["k"] == 9
    for i in range(10, 25): m.push("k", 0.5, i)
    assert not m.is_flagged("k")


def test_fus09_monitor_false_alarm_rate_on_iid_chi2_2dof_and_detection_of_bias():
    rng = np.random.default_rng(3); fa = 0
    for _ in range(400):
        m = ConsistencyMonitor(10, 0.999)
        for i, v in enumerate(rng.chisquare(2, 60)): m.push("k", float(v), i)
        fa += m.is_flagged("k") or "k" in m.first_flag_t
    assert fa / 400 <= 0.02
    det = 0
    for _ in range(200):
        m = ConsistencyMonitor(10, 0.999)
        for i, v in enumerate(rng.noncentral_chisquare(2, 12.0, 30)): m.push("k", float(v), i)    # bias worth ~3.5 sigma
        det += "k" in m.first_flag_t
    assert det / 200 >= 0.9


def test_fus09_quarantine_isolates_a_flagged_source_instead_of_fusing_it():
    f = CooperativeFuser("B4q_ci_quarantine")
    for i in range(12):                                                                                  # remote consistently ~6 sigma away yet still inside the 4-D gate -> d2 pairs large
        f.step(1.0 + 0.1 * i, [loc(1, t=1.0 + 0.1 * i, x=(10, 0, 0, 0), P=P4(0.15, 0.6)), est("k", 1, t=1.0 + 0.1 * i, x=(10, 0.9, 0, 0), P=P4(0.15, 0.6), seq=i)])
    assert f.monitor.is_flagged("k")
    w = f.step(2.3, [loc(1, t=2.3, x=(10, 0, 0, 0), P=P4(0.15, 0.6)), est("k", 1, t=2.3, x=(10, 0.9, 0, 0), P=P4(0.15, 0.6), seq=99)])
    assert len(w.tracks) == 2 and any("quarantined_source" in t.flags for t in w.tracks)
    g = CooperativeFuser("B4_ci")                                                                        # same data without the policy: fused
    for i in range(13): w2 = g.step(1.0 + 0.1 * i, [loc(1, t=1.0 + 0.1 * i, x=(10, 0, 0, 0), P=P4(0.15, 0.6)), est("k", 1, t=1.0 + 0.1 * i, x=(10, 0.9, 0, 0), P=P4(0.15, 0.6), seq=i)])
    assert len(w2.tracks) == 1


def test_fus09_authentication_is_not_implemented_and_the_policy_fails_closed():
    assert UnauthenticatedVerifier().assurance("k", (("k", 1, 1),)) == ALLOWLIST_ONLY
    strict = CooperativeFuser("B4_ci", {"require_assurance": AUTHENTICATED})
    w = strict.step(1.0, [loc(1), est("k", 1, seq=1)])
    assert [t.members for t in w.tracks] == [(("ego", 1),)] and w.diagnostics["rejected"] == {"unauthenticated_source": 1}
    ok = CooperativeFuser("B4_ci", {"require_assurance": AUTHENTICATED}, verifier=_UnsafeTestOnlyAcceptAllVerifier()).step(1.0, [loc(1), est("k", 1, seq=1)])
    assert len(ok.tracks[0].members) == 2 and ok.tracks[0].assurance == AUTHENTICATED                   # plumbing works with the TEST DOUBLE only
    default = CooperativeFuser("B4_ci").step(1.0, [loc(1), est("k", 1, seq=1)])
    assert default.tracks[0].assurance == ALLOWLIST_ONLY


def test_fus09_no_production_code_path_can_return_authenticated():
    for p in list((ROOT / "fusion").glob("*.py")) + list((ROOT / "comm").glob("*.py")) + list((ROOT / "integration").glob("*.py")) + list((ROOT / "experiments").glob("*.py")):
        tree = ast.parse(p.read_text())
        for cls in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
            body_src = ast.get_source_segment(p.read_text(), cls) or ""
            if "AUTHENTICATED" in body_src and "return AUTHENTICATED" in body_src:
                assert cls.name == "_UnsafeTestOnlyAcceptAllVerifier", f"{p.name}:{cls.name}"
    text = (ROOT / "fusion" / "identity.py").read_text()
    assert "no cryptographic verification" in text.lower().replace("\n", " ")
    for p in (ROOT / "experiments").glob("*.py"):
        assert "_UnsafeTestOnly" not in p.read_text()


def test_fus09_monitor_warmup_ignores_the_initialisation_transient_but_default_is_the_registered_behaviour():
    reg = ConsistencyMonitor(10, 0.999)
    w = ConsistencyMonitor(10, 0.999, warmup_s=1.0)
    for i in range(10):
        reg.push("k", 100.0, 0.1 * i); w.push("k", 100.0, 0.1 * i)        # transient: huge d2 during the first second
    assert reg.is_flagged("k") and not w.is_flagged("k")
    for i in range(10, 40): w.push("k", 100.0, 0.1 * i)
    assert w.is_flagged("k")                                              # a persistent inconsistency is still caught after the warm-up


def test_fus09_monitor_stays_flagged_between_the_clear_and_flag_thresholds():
    """Found by mutation (clear threshold = flag threshold survived): after flagging, sums between chi2_95(20)=31.4 and chi2_99.9(20)=45.3 must NOT clear the flag."""
    m = ConsistencyMonitor(10, 0.999)
    for i in range(10): m.push("k", 100.0, i)
    assert m.is_flagged("k")
    for i in range(10, 30): m.push("k", 3.8, i)                      # window sum 38: between lo and hi
    assert m.is_flagged("k")
    for i in range(30, 45): m.push("k", 2.0, i)                      # sum 20 < lo -> cleared
    assert not m.is_flagged("k")


def test_fus01_adapters_keep_the_original_observation_time_and_provenance():
    """Found by mutation (adapter used observation time + age): the Estimate time is exactly the message t_meas."""
    from comm.store import StoredTrack
    from comm.trackmsg import TrackEntry
    cov = tuple(0.04 if i % 5 == 0 else 0.0 for i in range(16))
    st = StoredTrack(("k", 3), TrackEntry(3, "pedestrian", 0.9, 1.0, 2.0, 0.0, 0.5, 0.1, cov, 0.1, 0.9, 7.2), 7.25, 0.4, 0.6, 2, ("late",), 41, ("rsu1", "rsu2"))
    from fusion.adapters import from_stored, from_local_track
    e = from_stored(st)
    assert e.t == 7.25 and e.source_id == "k" and e.track_id == 3 and e.evidence == (("k", 41, 3),) and e.hops == 2 and e.relay_path == ("rsu1", "rsu2") and e.kind == "remote" and e.x == (1.0, 2.0, 0.5, 0.1)
    from perception.tracker import Track
    lt = Track(5, 9.0, (1.0, 2.0, 0.0, 0.0), cov, True, 1.0, 0.9, "pedestrian", 4, 0, 1.0, 0.0)
    le = from_local_track("ego_cam", lt)
    assert le.t == 9.0 and le.kind == "local" and le.ref == ("ego_cam", 5) and le.evidence == (("local:ego_cam", 5),)
