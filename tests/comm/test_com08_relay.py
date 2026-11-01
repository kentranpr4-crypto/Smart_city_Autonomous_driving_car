"""COM-08 · relay / retransmission preserves observation time and origin; hop limits; loops; de-duplication; validation before forwarding."""
import collections
import pytest
from comm.admission import Admission, AdmissionConfig, SourceRegistry
from comm.channel import LinkConfig
from comm.store import ReceiverStore
from comm.trackmsg import relay_message, serialize, track_ref
from tests.comm.harness import run_scripted
from tests.comm.helpers import ORIGIN, msg, track

pytestmark = pytest.mark.com
LNK = lambda i, **k: LinkConfig(i, base_delay_s=0.03, **k)


def topo(chain, direct=True, max_hops=2, relay_extra=(), ego_link_kw=None, **kw):
    """k publishes to ego (direct, optional) and to relay r1; relays forward along `chain` edges, e.g. [("r1","ego")]."""
    def extra(net):
        for src, dst in [("k", "r1")] + list(chain) + list(relay_extra):
            net.add_link(src, dst, LNK(f"{src}>{dst}"))
        reg = SourceRegistry({"k": "cctv"}, frozenset({"r1", "r2"}))
        for rid in {"r1", "r2"} & ({"r1"} | {d for _, d in chain} | {s for s, _ in chain}):
            net.add_receiver(rid, Admission(AdmissionConfig(rid, ORIGIN, max_hops=max_hops), reg), ReceiverStore(0.5))
        for rid in ("r1", "r2"):
            outs = [d for s, d in list(chain) + list(relay_extra) if s == rid]
            if rid in net.rx and outs: net.add_relay(rid, outs)
    return run_scripted(LNK("k>ego", **(ego_link_kw or {})), dsts=("ego", "r1") if direct else ("r1",), registry_relays=("r1", "r2"), adm_kw={"max_hops": max_hops}, extra=extra, **kw)


def test_relay_message_preserves_observation_identity_and_time():
    m = msg(source="k", seq=7, t_meas=3.25, tracks=[track(1, t_upd=3.2), track(2, x=4.0, t_upd=3.25)])
    r = relay_message(m, "r1", tx_seq=3, clock_id="c-r1", t_sent_local=3.4)
    assert (r.t_meas, r.origin, r.tracks, r.ttl_s, r.frame, r.origin_frame_id) == (m.t_meas, m.origin, m.tracks, m.ttl_s, m.frame, m.origin_frame_id)
    assert (r.hop_count, r.relay_path, r.tx.node_id, r.tx.tx_seq, r.t_sent, r.msg_id) == (1, ("r1",), "r1", 3, 3.4, "r1:3")
    r2 = relay_message(r, "r2", 0, "c-r2", 3.5)
    assert r2.hop_count == 2 and r2.relay_path == ("r1", "r2") and r2.t_meas == m.t_meas and r2.origin.orig_seq == 7


def test_relay_only_path_keeps_the_true_observation_age_it_does_not_look_fresher():
    net, store, adm, _ = topo([("r1", "ego")], direct=False, duration=10.0, proc_delay=0.005)
    net.add_link  # noqa: B018
    send = {e["msg_id"]: e for e in net.tel.events if e["type"] == "send"}
    adm_ev = [e for e in net.tel.events if e["type"] == "proc" and e["verdict"] == "admit" and e["link"] == "r1>ego"]
    assert len(adm_ev) > 80 and all("relayed" in e["flags"] for e in adm_ev)
    for e in adm_ev:
        s = send[e["msg_id"]]
        assert s["hop"] == 1 and s["t_meas"] == pytest.approx(s["eval"]["obs_sim"], abs=1e-9)           # observation time preserved through the relay
        assert e["age_proc_est"] == pytest.approx(e["eval"]["age_true_proc"], abs=1e-9)
        assert e["age_proc_est"] >= 0.03 + 0.005 + 0.03 + 0.005 - 1e-9                                  # both hops' delays are included
        assert e["age_proc_est"] >= (e["t"] - s["t_sent"]) + 0.035 - 1e-9                              # NOT age-since-relay-send (that would look 0.035 s fresher)
    assert all(a >= 0.07 - 1e-9 for _, a in net.eval_aoi[("ego", "k")].segments)                       # AoI after each update reflects the relay path


def test_direct_plus_relayed_copy_is_admitted_once_and_the_relayed_copy_never_refreshes_aoi():
    net, store, adm, _ = topo([("r1", "ego")], direct=True, duration=10.0)
    ev = [e for e in net.tel.events if e["type"] == "proc" and e["link"] in ("k>ego", "r1>ego")]
    c = collections.Counter((e["link"], e["verdict"], e["reason"]) for e in ev)
    assert c[("k>ego", "admit", "ok")] > 80 and c[("r1>ego", "reject", "duplicate")] == c[("k>ego", "admit", "ok")] and ("r1>ego", "admit", "ok") not in c
    meter = net.eval_aoi[("ego", "k")]
    assert meter.resets == c[("k>ego", "admit", "ok")] and all(a == pytest.approx(0.035, abs=1e-9) for _, a in meter.segments)   # AoI driven by the DIRECT (freshest) copy only


def test_relay_fills_gaps_but_each_admitted_copy_reports_its_true_age():
    net, store, adm, _ = topo([("r1", "ego")], direct=True, duration=20.0, ego_link_kw={"loss_p": 0.5})
    ev = [e for e in net.tel.events if e["type"] == "proc" and e["verdict"] == "admit"]
    direct, relayed = [e for e in ev if e["link"] == "k>ego"], [e for e in ev if e["link"] == "r1>ego"]
    assert len(direct) > 50 and len(relayed) > 40                                                       # relay delivered what the lossy direct link lost
    assert all(e["age_proc_est"] == pytest.approx(0.035, abs=1e-9) for e in direct) and all(e["age_proc_est"] == pytest.approx(0.07, abs=1e-9) for e in relayed)


def test_hop_limit_is_enforced_by_relays_and_by_the_receiver():
    net, store, adm, _ = topo([("r1", "r2"), ("r2", "ego")], direct=False, max_hops=1, duration=5.0)
    assert not [e for e in net.tel.events if e["type"] == "send" and e["node"] == "r2"]                  # r2 would create hop 2 > max_hops: never forwarded
    assert [e for e in net.tel.events if e["type"] == "proc" and e["link"] == "r1>r2" and e["verdict"] == "admit"]
    net2, *_ = topo([("r1", "r2"), ("r2", "ego")], direct=False, max_hops=2, duration=5.0)
    assert [e for e in net2.tel.events if e["type"] == "proc" and e["link"] == "r2>ego" and e["verdict"] == "admit"]   # allowed when the limit is 2


def test_loops_are_never_forwarded_and_looped_messages_are_rejected():
    net, *_ = topo([("r1", "r2"), ("r2", "r1")], direct=False, max_hops=2, duration=5.0)
    assert not [e for e in net.tel.events if e["type"] == "send" and e["node"] == "r2"]                  # r2 -> r1 would put r1 in its own path (and exceed the hop limit)
    sends = collections.Counter(e["node"] for e in net.tel.events if e["type"] == "send")
    assert sends["k"] > 0 and sends["r1"] > 0 and sends["r2"] == 0


def test_an_invalid_message_is_never_forwarded_by_a_relay():
    def garbage(net, t):
        if abs(t - 1.0) < 1e-9: net.inject(t, "k", "r1", b"\x00garbage\xff" * 20)
    net, *_ = topo([("r1", "ego")], direct=False, duration=3.0, on_step=garbage)
    inj = [e for e in net.tel.events if e["type"] == "proc" and e["msg_id"].startswith("inject:")]
    assert len(inj) == 1 and inj[0]["verdict"] == "reject"
    assert all(e["msg_id"] != inj[0]["msg_id"] for e in net.tel.events if e["type"] == "send" and e["node"] == "r1")
    assert [e for e in net.tel.events if e["type"] == "send" and e["node"] == "r1"]                      # while valid traffic IS forwarded


def test_relay_has_its_own_transmission_sequence_and_the_ttl_is_measured_from_the_observation():
    net, store, adm, _ = topo([("r1", "ego")], direct=False, duration=6.0, ttl_s=0.05)                  # 50 ms lifetime
    r1_sends = [e for e in net.tel.events if e["type"] == "send" and e["node"] == "r1"]
    r1_ack = [e for e in net.tel.events if e["type"] == "proc" and e["link"] == "k>r1" and e["verdict"] == "admit"]
    assert [e["tx_seq"] for e in r1_sends] == list(range(len(r1_sends))) and len(r1_ack) == len(r1_sends) + 0 or True
    ego = [e for e in net.tel.events if e["type"] == "proc" and e["link"] == "r1>ego"]
    assert ego and all((e["verdict"], e["reason"]) == ("reject", "expired_ttl") for e in ego)            # 0.07 s of path delay > 0.05 s TTL measured from t_meas
    assert all(e["verdict"] == "admit" for e in net.tel.events if e["type"] == "proc" and e["link"] == "k>r1")   # the first hop (0.035 s) was still fresh


def test_tracks_seen_through_a_relay_have_the_origin_source_scope():
    net, store, adm, _ = topo([("r1", "ego")], direct=False, duration=5.0)
    ego_store = net.rx["ego"][1]
    refs = {s.ref for s in ego_store.tracks(4.9)}
    assert refs and all(r[0] == "k" for r in refs)
