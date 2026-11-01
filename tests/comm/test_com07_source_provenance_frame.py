"""COM-07 · source identity, provenance, coordinate-frame validation. Track ids are SOURCE-SCOPED; unsupported transforms are rejected, never applied."""
import pytest
from comm.admission import AdmissionConfig, REASONS
from comm.store import ReceiverStore
from comm.trackmsg import serialize, to_dict, deserialize, track_ref
from perception.presets import V2X_PUBLISH, EXPERIMENTAL_2OF3_BASELINE, confirmation_label
from tests.comm.helpers import adm, msg, track, ORIGIN, mutated
import comm.admission, comm.trackmsg

pytestmark = pytest.mark.com
T = (1.03, 1.035)


def test_only_allowlisted_sources_with_the_registered_type_are_accepted():
    a = adm(sources={"k": "cctv"})
    assert a.process(serialize(msg(source="k")), *T).admitted
    assert a.process(serialize(msg(source="evil")), *T).reason == "unknown_source"
    assert a.process(serialize(msg(source="k", seq=1, source_type="vehicle")), *T).reason == "unknown_source"      # right id, wrong type
    assert a.process(serialize(msg(source="k", seq=2, tx_node="r9", hop=1, relay_path=("r9",))), *T).reason == "unknown_source"   # unregistered relay
    assert adm(sources={"k": "cctv"}, relays=("r9",)).process(serialize(msg(source="k", seq=2, tx_node="r9", hop=1, relay_path=("r9",))), *T).admitted
    assert a.process(serialize(msg(source="k", seq=3, tx_node="k2")), *T).reason == "unknown_source"               # hop 0 must be sent by its own origin


def test_track_ids_from_different_sources_never_collide_and_keep_their_scope():
    a, store = adm(), ReceiverStore(0.5)
    m1, m2 = msg(source="k", seq=0, tracks=[track(1, x=10.0)]), msg(source="v", source_type="vehicle", seq=0, tracks=[track(1, x=50.0)])
    for m in (m1, m2):
        r = a.process(serialize(m), *T); assert r.admitted; store.ingest(r)
    refs = [s.ref for s in store.tracks(1.04)]
    assert refs == [("k", 1), ("v", 1)] and {s.entry.x for s in store.tracks(1.04)} == {10.0, 50.0}      # same local id, two distinct tracks
    r = a.process(serialize(msg(source="k", seq=1, t_meas=1.02, tracks=[track(1, x=10.2, t_upd=1.02)])), 1.05, 1.055); store.ingest(r)
    assert [s.entry.x for s in store.tracks(1.06) if s.ref == ("k", 1)] == [10.2]                          # same source + id = same track, updated in place


def test_relayed_tracks_keep_the_origin_scope_not_the_relays():
    m = msg(source="k", seq=0, tx_node="r1", hop=1, relay_path=("r1",))
    assert track_ref(m, m.tracks[0]) == ("k", 1) and m.tx.node_id == "r1"


@pytest.mark.parametrize("field,value,reason", [("frame", "wgs84", "unsupported_frame"), ("frame", "ecef", "unsupported_frame"), ("origin_frame_id", "other-map", "frame_mismatch"),
                                                ("yaw_convention", "cw_from_north", "yaw_convention_mismatch")])
def test_unsupported_frames_and_conventions_are_rejected_never_transformed(field, value, reason):
    r = adm().process(mutated(msg(), lambda d: d.update({field: value})), *T)
    assert (r.admitted, r.reason, r.msg) == (False, reason, None)


@pytest.mark.parametrize("unit,value", [("length", "ft"), ("length", "km"), ("time", "ms"), ("angle", "deg"), ("speed", "km/h")])
def test_wrong_units_are_rejected_with_an_explicit_reason(unit, value):
    r = adm().process(mutated(msg(), lambda d: d["units"].update({unit: value})), *T)
    assert (r.admitted, r.reason) == (False, "units_mismatch")


def test_no_transform_capability_exists_and_the_supported_frame_set_is_exactly_map():
    assert comm.trackmsg.FRAME == "map"
    for mod in (comm.admission, comm.trackmsg):
        assert not [n for n in dir(mod) if "transform" in n.lower() or "reproject" in n.lower() or "convert" in n.lower()]
    cfg_fields = set(AdmissionConfig.__dataclass_fields__)
    assert not [f for f in cfg_fields if "transform" in f or "crs" in f]
    r = adm(origin_id="a-different-origin").process(serialize(msg()), *T)                       # even a correct message is refused if origins differ
    assert r.reason == "frame_mismatch"


@pytest.mark.parametrize("path", [("origin", "provenance", "sensor_model"), ("origin", "provenance", "algo_version"), ("origin", "provenance", "calib_id"),
                                  ("origin", "provenance", "privacy_level"), ("origin", "provenance", "confirmation"), ("origin", "clock_sync"), ("origin", "clock_id")])
def test_every_provenance_field_is_mandatory(path):
    def drop(d):
        x = d
        for k in path[:-1]: x = x[k]
        del x[path[-1]]
    r = adm().process(mutated(msg(), drop), *T)
    assert (r.admitted, r.reason) == (False, "schema")


def test_privacy_level_must_be_object_only():
    assert adm().process(mutated(msg(), lambda d: d["origin"]["provenance"].update(privacy_level="raw_video")), *T).reason == "schema"


def test_confirmation_policy_3of4_accepted_experimental_rejected_unless_explicitly_allowed():
    assert confirmation_label(V2X_PUBLISH) == "3of4" and confirmation_label(EXPERIMENTAL_2OF3_BASELINE) == "2of3-experimental"
    exp = serialize(msg(confirmation="2of3-experimental"))
    assert adm().process(exp, *T).reason == "unsupported_confirmation"                           # production receiver default
    assert adm(accepted_confirmations=("3of4", "2of3-experimental")).process(exp, *T).admitted   # a research receiver opts in explicitly
