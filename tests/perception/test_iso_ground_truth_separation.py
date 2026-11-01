"""AC-VS-06 / I9 · the tracker has NO access path to ground truth.
Evidence is layered: (1) static: AST scan of imports and identifiers; (2) structural: types and signatures; (3) behavioural: the rig only passes frames;
(4) dynamic: the tracker runs correctly in a subprocess where every truth-side module is un-importable."""
import ast, dataclasses, hashlib, inspect, json, pathlib, subprocess, sys, textwrap
import pytest
from backend.observation import Detection, SensorFrame, frame_to_dict, frame_from_dict
from backend.sensors import SensorProvider
from perception.tracker import Tracker, TrackerConfig
from tests.perception.helpers import *

pytestmark = pytest.mark.iso
ROOT = pathlib.Path(__file__).resolve().parents[2]
PERCEPTION_FILES = sorted((ROOT / "perception").glob("*.py"))
ALLOWED_TOP = {"__future__", "math", "dataclasses", "collections", "typing", "numpy", "perception"}
FORBIDDEN_IDENTIFIERS = {"FrameLabels", "TruthActor", "TruthObstacle", "TruthSnapshot", "truth_snapshot", "truth_of", "SensorProvider", "World", "PerceptionRig", "labels"}


def _imports(path):
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out += [(a.name, ()) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            out.append((("." * node.level) + (node.module or ""), tuple(a.name for a in node.names)))
    return out


def test_perception_package_exists_and_is_scanned():
    assert len(PERCEPTION_FILES) >= 4


@pytest.mark.parametrize("path", PERCEPTION_FILES, ids=lambda p: p.name)
def test_perception_imports_only_whitelisted_modules(path):
    for mod, names in _imports(path):
        if mod.startswith("."):                                   # relative import inside perception
            continue
        top = mod.split(".")[0]
        if top == "backend":
            assert mod == "backend.observation" or (mod == "backend" and set(names) <= {"observation"}), f"{path.name} imports {mod} {names}"
        else:
            assert top in ALLOWED_TOP, f"{path.name} imports {mod}"


@pytest.mark.parametrize("path", PERCEPTION_FILES, ids=lambda p: p.name)
def test_perception_never_references_truth_side_identifiers(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} \
        | {a.arg for n in ast.walk(tree) if isinstance(n, ast.arguments) for a in n.args + n.kwonlyargs}
    assert not (names & FORBIDDEN_IDENTIFIERS), names & FORBIDDEN_IDENTIFIERS


def test_observation_module_is_pure_data():
    mods = {m.split(".")[0] for m, _ in _imports(ROOT / "backend" / "observation.py")}
    assert mods <= {"__future__", "dataclasses"}


def test_observation_types_carry_no_truth_fields():
    assert {f.name for f in dataclasses.fields(Detection)} == {"det_id", "x", "y", "cov", "cls", "cls_prob", "score"}
    assert {f.name for f in dataclasses.fields(SensorFrame)} == {"schema_version", "sensor_id", "seq", "t_meas", "t_avail", "sensor_pose", "fov", "range_m", "detections"}


def test_tracker_api_accepts_frames_only():
    assert list(inspect.signature(Tracker.update).parameters) == ["self", "f", "t_now"]
    assert list(inspect.signature(Tracker.tracks).parameters) == ["self", "t", "confirmed_only"]


def test_rig_passes_only_frames_to_trackers(monkeypatch):
    from backend.rig import run_with_rig
    from backend.scenario import load_scenario
    calls = []
    orig = Tracker.update

    def spy(self, f, t_now=None):
        calls.append((type(f), type(t_now)))
        return orig(self, f, t_now)
    monkeypatch.setattr(Tracker, "update", spy)
    scn = load_scenario(ROOT / "scenarios" / "s01w2_occlusion_rig.yaml")
    run_with_rig(scn, 7)
    assert len(calls) > 100 and {c[0] for c in calls} == {SensorFrame} and {c[1] for c in calls} <= {float}


BLOCKER = textwrap.dedent('''
    import sys, importlib.abc, json, hashlib
    TRUTH_SIDE = ("backend.world", "backend.truth", "backend.sensors", "backend.sensor_spec", "backend.dynamics", "backend.collision",
                  "backend.scenario", "backend.rig", "backend.run", "backend.backend_api", "backend.params", "backend.rng", "backend.telemetry")
    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name in TRUTH_SIDE:
                raise ImportError("BLOCKED truth-side module: " + name)
    sys.meta_path.insert(0, Block())
    try:
        import backend.world
        print("BLOCKER_FAILED"); sys.exit(3)
    except ImportError:
        print("BLOCKER_OK")
    from backend.observation import frame_from_dict
    from perception.tracker import Tracker
    tr = Tracker(sys.argv[2]); out = []
    for line in open(sys.argv[1]):
        f = frame_from_dict(json.loads(line))
        rep = tr.update(f, t_now=f.t_avail)
        out.append([rep.accepted, [(t.track_id, t.x) for t in tr.tracks(f.t_avail)]])
    leaked = [m for m in sys.modules if m in TRUTH_SIDE]
    print(json.dumps({"hash": hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest(), "leaked": leaked}))
''')


def test_tracker_runs_in_a_process_where_truth_side_modules_cannot_be_imported(tmp_path):
    spec = cctv(id="k", pose=(0.0, -20.0, 1.5707963), height=6.0, clutter_rate=0.5, **PERFECT)
    pv = SensorProvider([spec], 20261101, DT)
    frames, in_proc = [], Tracker("k", TrackerConfig())
    ref = []
    for k in range(60):
        step = k * pv.period["k"]
        for f, _ in pv.sample(snap([ped("p", 2.0 + 0.1 * k, 0.0)], t=step * DT), step):
            frames.append(f)
            rep = in_proc.update(f, t_now=f.t_avail)
            ref.append([rep.accepted, [(t.track_id, t.x) for t in in_proc.tracks(f.t_avail)]])
    path = tmp_path / "frames.jsonl"
    path.write_text("\n".join(json.dumps(frame_to_dict(f)) for f in frames))
    r = subprocess.run([sys.executable, "-c", BLOCKER, str(path), "k"], cwd=ROOT, capture_output=True, text=True, env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin"})
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert lines[0] == "BLOCKER_OK"                                                         # control: the blocker really blocks
    res = json.loads(lines[1])
    assert res["leaked"] == []                                                              # tracker never pulled a truth-side module in
    assert res["hash"] == hashlib.sha256(json.dumps(json.loads(json.dumps(ref)), sort_keys=True).encode()).hexdigest()


def _walk(obj, seen=None, depth=0):
    """Yield every object reachable from obj through attributes, dicts, lists, tuples, sets (depth-limited)."""
    seen = set() if seen is None else seen
    if id(obj) in seen or depth > 12:
        return
    seen.add(id(obj)); yield obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(k, seen, depth + 1); yield from _walk(v, seen, depth + 1)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj:
            yield from _walk(v, seen, depth + 1)
    elif hasattr(obj, "__dict__"):
        yield from _walk(vars(obj), seen, depth + 1)
    elif hasattr(obj, "__slots__"):
        for s in obj.__slots__:
            if hasattr(obj, s): yield from _walk(getattr(obj, s), seen, depth + 1)


def test_trackers_hold_no_references_to_truth_side_objects_after_a_run():
    """Closes the 'side-channel' hole: nothing truth-side may be reachable from a tracker object after the rig has run
    (found by mutation: a rig that stashed FrameLabels on the tracker was not caught by argument-type checks alone)."""
    from backend.rig import run_with_rig
    from backend.scenario import load_scenario
    _, rig = run_with_rig(load_scenario(ROOT / "scenarios" / "s01w2_occlusion_rig.yaml"), 7)
    assert rig.trackers
    for sid, tr in rig.trackers.items():
        bad = [type(o).__module__ + "." + type(o).__qualname__ for o in _walk(tr)
               if type(o).__module__.startswith("backend") and type(o).__module__ != "backend.observation"]
        assert bad == [], (sid, bad[:3])
        assert any(isinstance(o, SensorFrame) is False and type(o).__module__ == "perception.tracker" for o in _walk(tr))   # the walk really traversed the tracker
