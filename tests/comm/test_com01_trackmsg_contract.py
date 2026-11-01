"""COM-01 · TrackMsg 0.2.0 contract, strict (de)serialization, canonical bytes."""
import copy, json, math
import jsonschema, pytest
from hypothesis import given, settings, strategies as st, HealthCheck
from comm.trackmsg import (MsgError, SCHEMA_PATH, SCHEMA_VERSION, TrackEntry, TrackMsg, Origin, Tx, deserialize, serialize, to_dict, from_dict, parse_bytes, track_ref, content_key,
                           UNITS, YAW_CONVENTION, FRAME)
from tests.comm.helpers import msg, track, COV, ORIGIN, mutated, with_crc

pytestmark = pytest.mark.com


def test_schema_file_is_a_valid_draft_2020_12_schema_with_closed_objects():
    s = json.loads(SCHEMA_PATH.read_text())
    jsonschema.Draft202012Validator.check_schema(s)
    def closed(node):
        if isinstance(node, dict):
            if node.get("type") == "object": assert node.get("additionalProperties") is False, node
            for v in node.values(): closed(v)
        elif isinstance(node, list):
            for v in node: closed(v)
    closed(s)
    assert s["properties"]["schema_version"] == {"const": SCHEMA_VERSION} and SCHEMA_VERSION == "0.2.0"


def test_canonical_bytes_match_an_independent_encoding_and_are_key_order_independent():
    m = msg(tracks=[track(1), track(2, x=5.5)])
    b = serialize(m)
    import zlib
    body = to_dict(m)
    body["crc32"] = zlib.crc32(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")) & 0xFFFFFFFF   # independent CRC-32
    assert b == json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    d = json.loads(b)
    shuffled = dict(reversed(list(d.items())))                         # same content, different insertion order
    assert serialize(from_dict(shuffled)) == b


finite = st.floats(allow_nan=False, allow_infinity=False, width=64)
pos_int = st.integers(0, 2**53)
trk = st.builds(TrackEntry, track_id=st.integers(0, 10**6), cls=st.sampled_from(["pedestrian", "vehicle", "unknown"]), cls_prob=finite, x=finite, y=finite, yaw=finite, vx=finite, vy=finite,
                cov=st.tuples(*[finite] * 16), var_yaw=finite, existence=finite, t_upd=finite)
msgs = st.builds(lambda tr, a, b, ttl, hop, seq: msg(seq=seq, t_meas=a, t_sent=b, tracks=tr, ttl=ttl), st.lists(trk, max_size=6), finite, finite,
                 st.floats(1e-3, 1e3), st.just(0), pos_int)


@settings(max_examples=300, derandomize=True, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(m=msgs)
def test_round_trip_is_bit_exact_for_arbitrary_finite_values(m):
    b = serialize(m)
    m2 = deserialize(b)
    assert m2 == m and serialize(m2) == b                               # field-by-field AND byte-by-byte


def test_unsupported_versions_and_unknown_or_missing_fields_are_rejected_with_reasons():
    base = to_dict(msg())
    def enc(d): return json.dumps(with_crc(d)).encode()
    cases = [
        ("unsupported_version", lambda d: d.update(schema_version="0.1.0")),
        ("unsupported_version", lambda d: d.update(schema_version="0.3.0")),
        ("schema", lambda d: d.update(surprise=1)),
        ("schema", lambda d: d["tx"].update(extra=1)),
        ("schema", lambda d: d["origin"]["provenance"].update(extra=1)),
        ("schema", lambda d: d["tracks"][0].update(extra=1)),
        ("schema", lambda d: d.pop("tracks")),
        ("schema", lambda d: d["origin"].pop("orig_seq")),
        ("schema", lambda d: d["tracks"][0].update(x="1.0")),
        ("schema", lambda d: d["tracks"][0].update(x=True)),           # bool is not a number
        ("schema", lambda d: d["tx"].update(tx_seq=-1)),
        ("schema", lambda d: d["tx"].update(tx_seq=1.5)),
        ("schema", lambda d: d["tracks"][0].update(cov=[0.0] * 15)),
        ("schema", lambda d: d["tracks"][0].update(cls="truck")),
        ("schema", lambda d: d.update(ttl_s=0)),
        ("schema", lambda d: d["origin"]["provenance"].update(privacy_level="raw_video")),
        ("schema", lambda d: d.update(relay_path=["a"] * 9)),
        ("schema", lambda d: d.update(t_recv=1.0)),                    # receiver timestamps are NOT part of the message
        ("schema", lambda d: d.update(t_proc=1.0)),
    ]
    for reason, fn in cases:
        d = copy.deepcopy(base); fn(d)
        with pytest.raises(MsgError) as e:
            deserialize(enc(d))
        assert e.value.reason == reason, (reason, e.value)


def test_malformed_bytes_and_non_finite_tokens_are_rejected():
    good = serialize(msg())
    for raw, reason in [(b"", "malformed_bytes"), (b"[]", "malformed_bytes"), (b"\xff\xfe\x00", "malformed_bytes"), (good[:-5], "malformed_bytes"),
                        (b'{"a":1,"a":2}', "malformed_bytes"), (b"null", "malformed_bytes"),
                        (good.replace(b'"x":10.0', b'"x":NaN'), "non_finite"), (good.replace(b'"x":10.0', b'"x":Infinity'), "non_finite"),
                        (good.replace(b'"x":10.0', b'"x":-Infinity'), "non_finite")]:
        assert b'"x":' in good
        with pytest.raises(MsgError) as e:
            deserialize(raw)
        assert e.value.reason == reason, (raw[:30], e.value)


def test_nan_and_inf_can_never_be_serialized():
    import dataclasses
    for bad in (float("nan"), float("inf"), float("-inf")):
        m = dataclasses.replace(msg(), t_meas=bad)
        with pytest.raises(MsgError) as e:
            serialize(m)
        assert e.value.reason == "non_finite"


def test_unit_and_coordinate_conventions_are_explicit_constants():
    assert UNITS == {"length": "m", "time": "s", "angle": "rad", "speed": "m/s"} and YAW_CONVENTION == "ccw_from_+x" and FRAME == "map"
    m = msg()
    assert (m.frame, m.units, m.yaw_convention, m.origin_frame_id) == ("map", UNITS, "ccw_from_+x", ORIGIN)


def test_track_identity_is_source_scoped_and_message_size_is_accounted():
    a, b = msg(source="k", tracks=[track(1)]), msg(source="v", source_type="vehicle", tracks=[track(1)])
    assert track_ref(a, a.tracks[0]) != track_ref(b, b.tracks[0]) and track_ref(a, a.tracks[0]) == ("k", 1)
    sizes = [len(serialize(msg(tracks=[track(i) for i in range(n)]))) for n in (0, 1, 2, 3)]
    assert sizes == sorted(sizes) and len(set(sizes[i + 1] - sizes[i] for i in range(1, 3))) <= 2      # grows ~linearly per track
    assert sizes[0] < 800 and (sizes[3] - sizes[0]) / 3 < 450                                          # informational budget: JSON, NOT CPM/SDSM encoding


def test_integrity_field_detects_every_single_byte_corruption_that_keeps_the_json_valid():
    """Found by experiment (WP3): without CRC, 5 of 320 channel-corrupted packets were ADMITTED with wrong content. CRC-32 detects every single-byte error."""
    import zlib
    good = serialize(msg(tracks=[track(1), track(2, x=33.25)]))
    undetected = 0
    for pos in range(len(good)):
        for xor in (1, 2, 4, 8, 16, 32, 64, 128, 0x55, 0xFF):
            bad = bytearray(good); bad[pos] ^= xor; bad = bytes(bad)
            try:
                deserialize(bad)
                undetected += 1
            except MsgError as e:
                assert e.reason in ("integrity", "malformed_bytes", "unsupported_version", "schema", "non_finite"), e.reason
    assert undetected == 0, undetected


def test_crc_is_not_authentication_a_forger_can_recompute_it():
    """DOCUMENTED LIMITATION (E05/E06 UNKNOWN): CRC-32 stops random corruption, not an adversary."""
    d = to_dict(msg()); d["tracks"][0]["x"] = 99.0
    forged = json.dumps(with_crc(d), sort_keys=True, separators=(",", ":")).encode()
    assert deserialize(forged).tracks[0].x == 99.0


def test_missing_or_ill_typed_crc_is_a_schema_error_and_a_wrong_crc_is_an_integrity_error():
    d = to_dict(msg())
    for bad, reason in ((None, "schema"), ("x", "schema"), (1.5, "schema"), (12345, "integrity"), (-1, "integrity")):
        e = copy.deepcopy(d)
        if bad is not None: e["crc32"] = bad
        with pytest.raises(MsgError) as ex:
            deserialize(json.dumps(e).encode())
        assert ex.value.reason == reason, (bad, ex.value)
