"""COM-04 · four distinct timestamps (observation, transmission, reception, processing), node clock models, estimated vs true age, no wall clock."""
import ast, pathlib, time
import pytest
from comm.channel import LinkConfig
from comm.clock import NodeClock
from tests.comm.harness import run_scripted
from tests.comm.helpers import msg
from comm.trackmsg import to_dict

pytestmark = pytest.mark.com
ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_clock_model_is_an_exact_affine_map_and_invertible():
    c = NodeClock("c", offset_s=0.25, drift_ppm=1500.0)
    for t in (0.0, 1.0, 37.5, 1000.0):
        assert c.local(t) == pytest.approx(t * 1.0015 + 0.25, abs=1e-12) and c.sim(c.local(t)) == pytest.approx(t, abs=1e-9)


def test_timestamp_ordering_and_exact_processing_delay_on_the_simulation_axis():
    link = LinkConfig("k>ego", base_delay_s=0.03, jitter_s=0.02)
    net, *_ = run_scripted(link, seed=3, duration=20.0, proc_delay=0.005)
    send = {e["msg_id"]: e for e in net.tel.events if e["type"] == "send"}
    recv = {(e["msg_id"], e["copy"]): e for e in net.tel.events if e["type"] == "recv"}
    n = 0
    for p in (e for e in net.tel.events if e["type"] == "proc"):
        s, r = send[p["msg_id"]], recv[(p["msg_id"], p["copy"])]
        obs = s["eval"]["obs_sim"]
        assert obs <= s["t"] <= r["t"] <= p["t"]                                  # observation <= transmission <= reception <= processing
        assert 0.03 - 1e-12 <= r["t"] - s["t"] <= 0.05 + 1e-12                    # reception follows transmission by the link delay
        assert p["t"] - r["t"] == pytest.approx(0.005, abs=1e-12)                 # processing follows reception by exactly proc_delay
        n += 1
    assert n > 150


def test_the_message_carries_only_observation_and_transmission_time_receiver_times_live_in_the_result():
    d = to_dict(msg())
    assert {"t_meas", "t_sent"} <= set(d) and not ({"t_recv", "t_proc"} & set(d))
    net, store, adm, _ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03), seed=1, duration=2.0)
    r = adm.process.__defaults__  # noqa: F841 (signature check below)
    import inspect
    assert list(inspect.signature(adm.process).parameters)[:3] == ["payload", "t_recv_sim", "t_proc_sim"]


def _ages(net):
    ev = [e for e in net.tel.events if e["type"] == "proc" and e["verdict"] == "admit"]
    return [(e["age_proc_est"], e["eval"]["age_true_proc"]) for e in ev]


def test_estimated_age_differs_from_true_age_by_exactly_the_clock_error():
    net, *_ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03), seed=1, duration=10.0, pub_clock=NodeClock("c-k", offset_s=0.03))
    pairs = _ages(net)
    assert len(pairs) > 80
    assert all(est == pytest.approx(true - 0.03, abs=1e-9) for est, true in pairs)            # sender clock ahead by 30 ms -> age under-estimated by 30 ms


@pytest.mark.parametrize("pub_off,rx_off,expect_reason", [(0.20, 0.0, "future_obs"), (0.0, -0.10, "future_obs"), (0.0, 0.60, "stale")])
def test_clock_errors_beyond_tolerance_cause_explicit_rejections_not_silent_acceptance(pub_off, rx_off, expect_reason):
    net, *_ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03), seed=1, duration=5.0, pub_clock=NodeClock("c-k", offset_s=pub_off), rx_clock=NodeClock("c-ego", offset_s=rx_off))
    proc = [e for e in net.tel.events if e["type"] == "proc"]
    assert proc and all(e["verdict"] == "reject" and e["reason"] == expect_reason for e in proc)


def test_clock_drift_eventually_trips_the_future_observation_check_at_the_analytic_time():
    drift = 2000.0                                          # 0.2 %: sender clock gains 2 ms per second
    net, *_ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03), seed=1, duration=60.0, step_dt=0.1, pub_clock=NodeClock("c-k", drift_ppm=drift))
    send = {e["msg_id"]: e["eval"]["obs_sim"] for e in net.tel.events if e["type"] == "send"}
    # age_est = t_proc - obs*(1+d) = 0.035 - 0.002*obs  <  -0.05  <=>  obs > 42.5 s
    for p in (e for e in net.tel.events if e["type"] == "proc"):
        obs = send[p["msg_id"]]
        if obs < 42.4: assert p["verdict"] == "admit", (obs, p)
        if obs > 42.6: assert (p["verdict"], p["reason"]) == ("reject", "future_obs"), (obs, p)


def test_no_wall_clock_is_read_anywhere_in_the_comm_path(monkeypatch):
    def boom(*a, **k): raise AssertionError("wall clock read")
    for name in ("time", "monotonic", "perf_counter", "process_time", "time_ns", "monotonic_ns", "perf_counter_ns"):
        monkeypatch.setattr(time, name, boom)
    run_scripted(LinkConfig("k>ego", base_delay_s=0.03, jitter_s=0.01, loss_p=0.1), seed=2, duration=3.0)
    banned = {"time", "datetime", "random", "sched", "threading", "asyncio"}
    for f in (ROOT / "comm").glob("*.py"):
        tree = ast.parse(f.read_text())
        mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not (mods & banned), (f.name, mods & banned)
