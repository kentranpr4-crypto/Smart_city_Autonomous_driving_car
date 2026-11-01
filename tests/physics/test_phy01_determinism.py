"""PHY-01 · determinism and independence from wall-clock / render rate. Seeds are fixed in the test source."""
import json, os, pathlib, platform, random, subprocess, sys, time
import numpy
import pytest
from backend.run import run_scenario
from backend.world import rng_stream
from tests.physics.helpers import make, run

pytestmark = pytest.mark.phy
ROOT = pathlib.Path(__file__).resolve().parents[2]
SCN = ROOT / "scenarios" / "s00a_physics_sandbox_brake_early.yaml"
GOLDEN = pathlib.Path(__file__).with_name("golden_hashes.json")
SEED = 7


def _hash(seed=SEED):
    return run_scenario(SCN, seed)[0]["telemetry_sha256"]


def test_same_seed_same_hash_in_process():
    assert _hash() == _hash()


def test_different_seed_different_hash():
    assert _hash(7) != _hash(8)          # pedestrian speed/start are drawn from the seed


def test_wall_clock_jitter_does_not_change_results():
    """Observer that sleeps a random wall-clock time every step (simulates slow render / paced mode). Hash must be unchanged."""
    rnd = random.Random(1234)                       # fixed seed -> reproducible test
    base = run_scenario(SCN, SEED)[0]["telemetry_sha256"]
    from backend.scenario import load_scenario
    from backend.telemetry import TelemetryWriter
    from backend.world import World
    tw = TelemetryWriter(keep=False)
    w = World(load_scenario(SCN), SEED, tw)
    w.run(on_step=lambda _w: time.sleep(rnd.random() * 0.0008))
    assert tw.hexdigest() == base


@pytest.mark.parametrize("hashseed", ["0", "12345"])
def test_separate_process_matches_regardless_of_pythonhashseed(hashseed, tmp_path):
    env = dict(os.environ, PYTHONHASHSEED=hashseed)
    r = subprocess.run([sys.executable, "-m", "backend.run", str(SCN), "--seed", str(SEED), "--out", str(tmp_path)],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout)["telemetry_sha256"] == _hash()


def test_rng_streams_are_independent_of_actor_order():
    """Adding another pedestrian must not change an existing pedestrian's draws (streams are keyed by id, not by order)."""
    a = rng_stream(5, "ped:p1").uniform(0, 1)
    _ = rng_stream(5, "ped:p0").uniform(0, 1)
    b = rng_stream(5, "ped:p1").uniform(0, 1)
    assert a == b


def test_negative_zero_is_normalised_in_telemetry():
    from backend.telemetry import canonical_line
    assert canonical_line({"x": -0.0}) == canonical_line({"x": 0.0})


def test_golden_hash_same_environment_regression():
    """Regression anchor. Bit-exactness is only promised within the recorded environment (07 §6); otherwise skip, never fake a pass."""
    g = json.loads(GOLDEN.read_text())
    env = {"python": platform.python_version(), "numpy": numpy.__version__, "machine": platform.machine(), "system": platform.system()}
    if g["environment"] != env:
        pytest.skip(f"golden recorded in a different environment: {g['environment']} vs {env}")
    assert _hash() == g["s00a_seed7_sha256"]
