"""End-to-end WP2 check on scenarios/s01w2_occlusion_rig.yaml: World truth -> sensors -> t_avail queue -> trackers (AC-VS-02 behaviour, timestamps, determinism).
This is NOT a safety experiment (no control loop yet)."""
import pathlib
import pytest
from backend.rig import run_with_rig
from backend.scenario import load_scenario

pytestmark = pytest.mark.trk
ROOT = pathlib.Path(__file__).resolve().parents[2]
SCN = ROOT / "scenarios" / "s01w2_occlusion_rig.yaml"
SEED = 7
X_CRIT = 39.5          # analytic: line of sight from (x_s, 0) to the pedestrian (45, -3.3) clears the truck's NE corner (43, -2.1) iff x_s > 39.5


@pytest.fixture(scope="module")
def run():
    w, rig = run_with_rig(load_scenario(SCN), SEED)
    return w, rig


def rows(rig, sid):
    return {e["frame"]["seq"]: e for e in rig.log if e["frame"]["sensor_id"] == sid}


def test_ego_sensor_sees_the_pedestrian_exactly_when_the_analytic_line_of_sight_opens(run):
    w, rig = run
    assert not w.summary()["collision"]
    r = rows(rig, "ego_cam"); labs = rig.labels["ego_cam"]
    first = min(s for s, l in labs.items() if "ped1" in l.visible)
    x_first, x_prev = r[first]["frame"]["sensor_pose"][0], r[first - 1]["frame"]["sensor_pose"][0]
    assert x_prev <= X_CRIT < x_first                                                      # the analytic boundary lies between two consecutive frames
    for s in range(first):                                                                   # AC-VS-02: while hidden, never detected, never tracked
        assert "ped1" not in labs[s].visible and "ped1" not in labs[s].detected
        assert r[s]["tracks"] == []
    assert any("ped1" in labs[s].candidates for s in range(first))                           # it WAS inside the FOV/range, so only occlusion hid it


def test_cctv_sees_it_from_the_start_and_leads_the_ego_by_several_seconds(run):
    _, rig = run
    c, e = rows(rig, "cctv_k1"), rows(rig, "ego_cam")
    assert all("ped1" in l.visible for l in rig.labels["cctv_k1"].values())
    t_c = min(x["t"] for x in c.values() if x["tracks"]); t_e = min(x["t"] for x in e.values() if x["tracks"])
    assert t_c < 0.3 and t_e - t_c >= 6.0


def test_published_tracks_are_close_to_the_truth_and_timestamps_are_causal(run):
    w, rig = run
    for e in rig.log:
        f = e["frame"]
        assert f["t_avail"] == pytest.approx(f["t_meas"] + 0.05, abs=1e-9)
        assert e["t"] >= f["t_avail"] - 1e-9 and e["t"] - f["t_avail"] <= 0.01 + 1e-9        # released no earlier than t_avail, at most one step later
        assert e["report"]["accepted"]
    last = [e for e in rows(rig, "cctv_k1").values() if e["tracks"]][-1]
    trk = last["tracks"][0]
    assert 40.0 < trk["x"][0] < 50.0                                                           # a track exists near the pedestrian's x=45 (+ bias-free sensor)


def test_perception_log_is_deterministic_and_seed_sensitive():
    h = lambda seed: run_with_rig(load_scenario(SCN), seed)[1].hexdigest()
    assert h(SEED) == h(SEED) and h(SEED) != h(SEED + 1)


def test_physics_telemetry_is_unaffected_by_attaching_the_perception_rig():
    from backend.telemetry import TelemetryWriter
    from backend.world import World
    scn = load_scenario(SCN)
    tw = TelemetryWriter(keep=False); World(scn, SEED, tw).run()
    tw2 = TelemetryWriter(keep=False)
    w2 = World(scn, SEED, tw2)
    from backend.rig import PerceptionRig
    rig = PerceptionRig(scn, SEED); rig(w2); w2.run(on_step=rig)
    assert tw.hexdigest() == tw2.hexdigest()                                                 # sensors observe; they never perturb the physics
