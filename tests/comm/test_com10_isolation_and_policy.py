"""COM-10 · isolation (I9), P1 constraints, publish policy. comm/ has no access path to truth, no wall clock, no randomness outside the seeded stream,
no 'free space' semantics, and publishes only confirmed (3-of-4) tracks that rest on a NEW observation."""
import ast, hashlib, inspect, json, pathlib, subprocess, sys, textwrap
import pytest
from comm.admission import Admission
from comm.channel import LinkConfig
from comm.clock import NodeClock
from comm.publisher import Publisher, PublishPolicyError
from comm.store import ReceiverStore
from comm.trackmsg import TrackMsg
from integration.comm_rig import run_rig_comm, ORIGIN
from perception.presets import EXPERIMENTAL_2OF3_BASELINE, V2X_PUBLISH
from perception.tracker import Tracker, TrackerConfig
from tests.comm.helpers import adm, msg, track
from tests.comm.harness import run_scripted
from tests.comm.frames import mk_frame

pytestmark = pytest.mark.com
ROOT = pathlib.Path(__file__).resolve().parents[2]
COMM_FILES = sorted((ROOT / "comm").glob("*.py"))
ALLOWED_TOP = {"__future__", "math", "dataclasses", "collections", "typing", "numpy", "json", "hashlib", "heapq", "zlib", "struct", "itertools", "functools", "pathlib",
               "enum", "jsonschema", "re", "comm", "perception"}
BANNED_TOP = {"time", "datetime", "random", "os", "sys", "subprocess", "socket", "threading", "asyncio", "secrets", "uuid"}
FORBIDDEN_IDENTIFIERS = {"FrameLabels", "TruthActor", "TruthObstacle", "TruthSnapshot", "truth_snapshot", "truth_of", "SensorProvider", "World", "PerceptionRig", "labels",
                         "free_space", "is_free", "freespace", "is_clear", "occupancy_free"}


def _imports(path):
    out = []
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import): out += [(a.name, ()) for a in n.names]
        elif isinstance(n, ast.ImportFrom): out.append((("." * n.level) + (n.module or ""), tuple(a.name for a in n.names)))
    return out


def test_comm_package_is_scanned():
    assert len(COMM_FILES) >= 10


@pytest.mark.parametrize("path", COMM_FILES, ids=lambda p: p.name)
def test_comm_imports_only_whitelisted_modules_and_no_wall_clock_or_global_random(path):
    for mod, names in _imports(path):
        if mod.startswith("."): continue
        top = mod.split(".")[0]
        assert top not in BANNED_TOP, f"{path.name} imports {mod}"
        assert top in ALLOWED_TOP, f"{path.name} imports {mod}"
        if top == "backend":
            raise AssertionError(f"{path.name} imports backend")
        if top == "perception":
            assert mod in ("perception", "perception.presets", "perception.tracker") or mod.startswith("perception."), mod
        if top == "numpy" and mod != "numpy":
            assert mod == "numpy.random" or mod.startswith("numpy."), mod


@pytest.mark.parametrize("path", COMM_FILES, ids=lambda p: p.name)
def test_comm_has_no_truth_or_free_space_identifiers(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | \
            {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))} | {a.arg for n in ast.walk(tree) if isinstance(n, ast.arguments) for a in n.args + n.kwonlyargs}
    assert not (names & FORBIDDEN_IDENTIFIERS), names & FORBIDDEN_IDENTIFIERS
    # only the seeded stream may use numpy.random; no import of the `random` module and no `time.` call anywhere
    src = path.read_text()
    assert "time.time" not in src and "perf_counter" not in src and "monotonic" not in src


BLOCKER = textwrap.dedent('''
    import sys, importlib.abc, json
    TRUTH_SIDE = ("backend.world", "backend.truth", "backend.sensors", "backend.sensor_spec", "backend.dynamics", "backend.collision",
                  "backend.scenario", "backend.rig", "backend.run", "backend.backend_api", "backend.params", "backend.rng", "backend.telemetry", "integration")
    class Block(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name in TRUTH_SIDE or name.startswith("integration."):
                raise ImportError("BLOCKED: " + name)
    sys.meta_path.insert(0, Block())
    try:
        import backend.world; print("BLOCKER_FAILED"); sys.exit(3)
    except ImportError:
        print("BLOCKER_OK")
    from tests.comm.harness import run_scripted
    from comm.channel import LinkConfig
    net, *_ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03, jitter_s=0.02, loss_p=0.1, dup_p=0.1, reorder_p=0.1, corrupt_p=0.05), seed=5, duration=4.0)
    print(json.dumps({"hash": net.tel.hexdigest(), "leaked": [m for m in sys.modules if m in TRUTH_SIDE]}))
''')


def test_comm_runs_in_a_process_where_truth_side_modules_cannot_be_imported():
    r = subprocess.run([sys.executable, "-c", BLOCKER], cwd=ROOT, capture_output=True, text=True, env={"PYTHONPATH": str(ROOT), "PATH": "/usr/bin", "PYTHONHASHSEED": "123"})
    assert r.returncode == 0, r.stderr
    lines = r.stdout.strip().splitlines()
    assert lines[0] == "BLOCKER_OK"
    res = json.loads(lines[1])
    assert res["leaked"] == []
    ref, *_ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03, jitter_s=0.02, loss_p=0.1, dup_p=0.1, reorder_p=0.1, corrupt_p=0.05), seed=5, duration=4.0)
    assert res["hash"] == ref.tel.hexdigest()                                                # same bits with and without truth-side modules


@pytest.fixture(scope="module")
def rig_run():
    return run_rig_comm(7, LinkConfig("L", base_delay_s=0.03, jitter_s=0.01), keep_wire=True)


def test_wire_bytes_carry_no_truth_identifiers(rig_run):
    w, rig, net, store, adm_, pub = rig_run
    assert len(net.wire) > 50
    truth_ids = {a.id for a in w.scn.actors} if hasattr(w.scn, "actors") else {"ped1", "truck", "ego"}
    truth_ids |= {"ped1", "truck", "ego"}
    strings = []
    def walk(o):
        if isinstance(o, dict):
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
        elif isinstance(o, str): strings.append(o)
    for b in net.wire: walk(json.loads(b))
    assert strings and not (set(strings) & truth_ids)                                         # exact string VALUES; track ids are 'cctv_k1:…'-style, not world ids
    assert all(set(json.loads(b)) <= {"schema_version", "msg_id", "tx", "origin", "t_meas", "t_sent", "frame", "origin_frame_id", "units", "yaw_convention", "ttl_s", "hop_count", "relay_path", "tracks", "crc32"} for b in net.wire)


def test_receiver_gets_fresh_confirmed_tracks_end_to_end_and_only_confirmed(rig_run):
    w, rig, net, store, adm_, pub = rig_run
    n_conf = [json.loads(b)["tracks"] for b in net.wire]
    assert any(n_conf) and all(m.origin.provenance["confirmation"] == "3of4" for m in [__import__("comm.trackmsg", fromlist=["x"]).deserialize(b) for b in net.wire])
    from comm.trackmsg import deserialize
    for b in net.wire:
        m = deserialize(b)
        assert m.origin.source_id == "cctv_k1" and m.hop_count == 0 and m.t_meas <= m.t_sent + 1e-9


def test_published_t_meas_equals_the_tracker_last_frame_time_and_never_the_publish_time(rig_run):
    from comm.trackmsg import deserialize
    w, rig, net, *_ = rig_run
    frame_times = {round(e["frame"]["t_meas"], 6) for e in rig.log if e["frame"]["sensor_id"] == "cctv_k1"}
    for b in net.wire:
        m = deserialize(b)
        assert round(m.t_meas, 6) in frame_times and m.t_meas < m.t_sent                           # strictly older than transmission: processing latency is visible


def test_no_republish_without_a_new_observation():
    clk = NodeClock("c")
    tr = Tracker("k", V2X_PUBLISH)
    for k in range(6): tr.update(mk_frame(k, k * 0.1, [(2.0 + k * 0.1, 0.0, 0.04)], sensor="k"), t_now=k * 0.1)
    pub = Publisher("k", "cctv", clk, ORIGIN, rate_hz=10.0)
    first = pub.maybe_publish(0.5, tr)
    again = pub.maybe_publish(0.6, tr)                                                               # tracker has not seen a newer frame
    assert first is not None and again is None and pub.suppressed_no_new_obs == 1


def test_publisher_enforces_3_of_4_and_stamps_the_experimental_baseline():
    clk = NodeClock("c")
    tr = Tracker("k", EXPERIMENTAL_2OF3_BASELINE)
    for k in range(5): tr.update(mk_frame(k, k * 0.1, [(2.0, 0.0, 0.04)], sensor="k"), t_now=k * 0.1)
    with pytest.raises(PublishPolicyError):
        Publisher("k", "cctv", clk, ORIGIN).maybe_publish(0.4, tr)
    r = Publisher("k", "cctv", clk, ORIGIN, experimental=True).maybe_publish(0.4, tr)
    assert r is not None and r[0].origin.provenance["confirmation"] == "2of3-experimental"
    assert TrackerConfig().confirm_m == 2 and V2X_PUBLISH.confirm_m == 3 and V2X_PUBLISH.confirm_n == 4        # 2-of-3 preserved as default baseline; 3-of-4 is the V2X preset


def test_receiver_rejects_experimental_messages_by_default():
    a = adm()
    m = msg(confirmation="2of3-experimental")
    res = a.process(__import__("comm.trackmsg", fromlist=["x"]).serialize(m), m.t_sent + 0.03, m.t_sent + 0.035)
    assert not res.admitted and res.reason == "unsupported_confirmation"


def test_only_confirmed_tracks_are_published():
    clk = NodeClock("c"); tr = Tracker("k", V2X_PUBLISH)
    for k in range(2): tr.update(mk_frame(k, k * 0.1, [(2.0, 0.0, 0.04)], sensor="k"), t_now=k * 0.1)          # 2 hits < 3-of-4: tentative
    assert tr.tracks(0.1, confirmed_only=True) == []
    r = Publisher("k", "cctv", clk, ORIGIN).maybe_publish(0.1, tr)
    assert r is None or r[0].tracks == ()


def test_store_and_schema_have_no_free_space_semantics():
    api = {n for n in dir(ReceiverStore) if not n.startswith("_")}
    assert api >= {"ingest", "purge", "tracks"} and not {n for n in api if any(w in n.lower() for w in ("free", "clear", "empty", "occupan"))}
    props = json.loads((ROOT / "schemas" / "trackmsg.schema.json").read_text())
    def names(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "properties":
                    yield from v.keys()
                yield from names(v)
        elif isinstance(o, list):
            for v in o: yield from names(v)
    assert not [p for p in names(props) if any(w in p.lower() for w in ("free", "clear", "empty", "occupan", "safe"))]


def test_stale_or_missing_information_is_absence_not_freedom():
    snap = {}
    def cap(net, t):
        st = net.rx["ego"][1]
        for tq in (1.9, 7.9):
            if abs(t - tq) < 1e-9: snap[tq] = st.tracks(t)
    run_scripted(LinkConfig("k>ego", base_delay_s=0.03, blackouts=((2.0, 8.0),)), seed=1, duration=8.0, on_step=cap)
    assert snap[1.9] and snap[7.9] == []                                                              # blackout: entries expire to NOTHING, never to 'free'
    assert not hasattr(ReceiverStore, "is_free")
