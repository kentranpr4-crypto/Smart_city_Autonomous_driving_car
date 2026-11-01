"""COM-09 · communication telemetry: schema-valid canonical JSONL, accounting identities (incl. random channel parameters), replay hash, no truth fields."""
import json, pathlib
import pytest
from hypothesis import given, settings, strategies as st
from jsonschema import Draft202012Validator
from comm.channel import LinkConfig
from comm.metrics import summarize
from comm.telemetry import CommTelemetry, accounting, canonical_line
from tests.comm.harness import run_scripted

pytestmark = pytest.mark.com
ROOT = pathlib.Path(__file__).resolve().parents[2]
SCHEMA = Draft202012Validator(json.loads((ROOT / "schemas" / "comm_telemetry.schema.json").read_text()))
HOSTILE = LinkConfig("k>ego", base_delay_s=0.03, jitter_s=0.04, loss_p=0.15, dup_p=0.2, reorder_p=0.2, corrupt_p=0.1, blackouts=((2.0, 2.5),))


def test_every_line_is_schema_valid_and_closed():
    net, *_ = run_scripted(HOSTILE, seed=3, duration=6.0)
    types = set()
    for e in net.tel.events:
        SCHEMA.validate(e); types.add(e["type"])
    assert types == {"header", "send", "drop", "sched", "recv", "proc"}
    with pytest.raises(Exception):
        SCHEMA.validate({**net.tel.events[1], "ped1_x": 3.0})                       # unknown field rejected (closed objects)


def test_accounting_identities_hold_on_a_hostile_run():
    net, *_ = run_scripted(HOSTILE, seed=4, duration=8.0)
    a = accounting(net.tel.events)
    assert a["sent"] > 50 and a["dropped"] > 0 and a["reject"] > 0
    assert a["ok_sent"] and a["ok_recv"] and a["ok_proc"] and a["ok_verdict"]
    assert a["recv"] == a["proc"] == a["copies_scheduled"]                        # after finish() nothing is left in flight


@settings(max_examples=25, deadline=None)
@given(loss=st.floats(0, 0.9), dup=st.floats(0, 0.9), reorder=st.floats(0, 0.9), corrupt=st.floats(0, 0.5), seed=st.integers(0, 10 ** 6))
def test_identities_hold_for_random_channel_parameters(loss, dup, reorder, corrupt, seed):
    net, *_ = run_scripted(LinkConfig("k>ego", base_delay_s=0.02, jitter_s=0.02, loss_p=loss, dup_p=dup, reorder_p=reorder, corrupt_p=corrupt), seed=seed, duration=3.0, step_dt=0.05)
    a = accounting(net.tel.events)
    assert a["ok_sent"] and a["ok_recv"] and a["ok_proc"] and a["ok_verdict"] and a["recv"] == a["proc"] == a["copies_scheduled"]


def test_telemetry_file_hash_equals_in_memory_hash_and_replay_is_identical(tmp_path):
    p = tmp_path / "t.jsonl"
    t = CommTelemetry(p)
    import tests.comm.harness as H
    from comm.network import CommNetwork
    n1, *_ = run_scripted(HOSTILE, seed=9, duration=5.0)
    n2, *_ = run_scripted(HOSTILE, seed=9, duration=5.0, step_dt=0.05)             # different step granularity, same log
    n3, *_ = run_scripted(HOSTILE, seed=10, duration=5.0)
    assert n1.tel.hexdigest() == n2.tel.hexdigest() != n3.tel.hexdigest()
    import hashlib
    for e in n1.tel.events: t.write(e)
    t.close()
    assert hashlib.sha256(p.read_bytes()).hexdigest() == n1.tel.hexdigest() == t.hexdigest()


def test_non_finite_values_cannot_enter_telemetry():
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError):
            canonical_line({"type": "x", "v": bad})
    assert canonical_line({"a": -0.0}) == canonical_line({"a": 0.0})                # -0.0 normalised


def test_summary_matches_hand_counts_on_a_lossless_run():
    net, *_ = run_scripted(LinkConfig("k>ego", base_delay_s=0.03), seed=1, duration=5.0)
    s = summarize(net.tel.events, net.eval_aoi, 5.0)
    assert s["sent"] == s["copies_delivered"] == s["processed"] == s["admitted"] and s["delivery_ratio"] == 1.0 and not s["rejected_by_reason"]
    assert s["network_latency_s"]["p50"] == pytest.approx(0.03, abs=1e-9) and s["network_latency_s"]["max"] == pytest.approx(0.03, abs=1e-9)
    assert s["max_observation_age_accepted_true_s"] >= s["network_latency_s"]["p50"]


def test_summary_counts_drop_and_reject_reasons_on_hostile_run():
    net, *_ = run_scripted(HOSTILE, seed=4, duration=8.0)
    s = summarize(net.tel.events, net.eval_aoi, 8.0)
    assert sum(s["dropped_by_reason"].values()) + len({(e["link"], e["msg_id"]) for e in net.tel.events if e["type"] == "sched"}) == s["sent"]
    assert s["rejected_by_reason"].get("duplicate", 0) > 0 and s["rejected_by_reason"].get("integrity", 0) + s["rejected_by_reason"].get("malformed_bytes", 0) + s["rejected_by_reason"].get("schema", 0) > 0
    assert s["admitted"] + sum(s["rejected_by_reason"].values()) == s["processed"]


def test_telemetry_has_no_truth_fields():
    net, *_ = run_scripted(HOSTILE, seed=4, duration=4.0)
    forbidden = {"truth", "gt", "ground_truth", "visible", "candidates", "detected", "ped1", "truck"}
    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items(): yield k; yield from keys(v)
        elif isinstance(o, list):
            for v in o: yield from keys(v)
    assert not (set(keys(net.tel.events)) & forbidden)
    assert set(net.tel.events[1]["eval"]) == {"obs_sim"}                            # evaluation annotation is simulation-clock time only
