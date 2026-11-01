"""TrackMsg 0.2.0: dataclasses, strict (de)serialization, relay.  Canonical bytes: sorted keys, compact separators, shortest round-trip floats."""
from __future__ import annotations
import json, math, pathlib, zlib
from dataclasses import dataclass, field
import jsonschema

SCHEMA_VERSION = "0.2.0"
FRAME = "map"
UNITS = {"length": "m", "time": "s", "angle": "rad", "speed": "m/s"}
YAW_CONVENTION = "ccw_from_+x"
SCHEMA_PATH = pathlib.Path(__file__).resolve().parent.parent / "schemas" / "trackmsg.schema.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
_VALIDATOR = jsonschema.Draft202012Validator(_SCHEMA)


class MsgError(ValueError):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason, self.detail = reason, detail


@dataclass(frozen=True)
class Tx:
    node_id: str
    tx_seq: int
    clock_id: str


@dataclass(frozen=True)
class Origin:
    source_id: str
    source_type: str
    orig_seq: int
    orig_msg_id: str
    clock_id: str
    clock_sync: str
    provenance: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TrackEntry:
    track_id: int
    cls: str
    cls_prob: float
    x: float
    y: float
    yaw: float
    vx: float
    vy: float
    cov: tuple
    var_yaw: float
    existence: float
    t_upd: float


@dataclass(frozen=True)
class TrackMsg:
    schema_version: str
    msg_id: str
    tx: Tx
    origin: Origin
    t_meas: float
    t_sent: float
    frame: str
    origin_frame_id: str
    units: dict
    yaw_convention: str
    ttl_s: float
    hop_count: int
    relay_path: tuple
    tracks: tuple


def to_dict(m: TrackMsg) -> dict:
    return {
        "schema_version": m.schema_version, "msg_id": m.msg_id,
        "tx": {"node_id": m.tx.node_id, "tx_seq": m.tx.tx_seq, "clock_id": m.tx.clock_id},
        "origin": {"source_id": m.origin.source_id, "source_type": m.origin.source_type, "orig_seq": m.origin.orig_seq, "orig_msg_id": m.origin.orig_msg_id,
                   "clock_id": m.origin.clock_id, "clock_sync": m.origin.clock_sync, "provenance": dict(m.origin.provenance)},
        "t_meas": m.t_meas, "t_sent": m.t_sent, "frame": m.frame, "origin_frame_id": m.origin_frame_id, "units": dict(m.units),
        "yaw_convention": m.yaw_convention, "ttl_s": m.ttl_s, "hop_count": m.hop_count, "relay_path": list(m.relay_path),
        "tracks": [{"track_id": t.track_id, "cls": t.cls, "cls_prob": t.cls_prob, "x": t.x, "y": t.y, "yaw": t.yaw, "vx": t.vx, "vy": t.vy,
                    "cov": list(t.cov), "var_yaw": t.var_yaw, "existence": t.existence, "t_upd": t.t_upd} for t in m.tracks],
    }


def from_dict(d: dict) -> TrackMsg:
    """Structure is validated against the JSON Schema; values are NOT range-checked here (that is admission's job)."""
    errs = sorted(_VALIDATOR.iter_errors(d), key=lambda e: list(e.absolute_path))
    if errs:
        e = errs[0]
        raise MsgError("schema", f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}")
    o, tx = d["origin"], d["tx"]
    return TrackMsg(
        d["schema_version"], d["msg_id"], Tx(tx["node_id"], int(tx["tx_seq"]), tx["clock_id"]),
        Origin(o["source_id"], o["source_type"], int(o["orig_seq"]), o["orig_msg_id"], o["clock_id"], o["clock_sync"], dict(o["provenance"])),
        float(d["t_meas"]), float(d["t_sent"]), d["frame"], d["origin_frame_id"], dict(d["units"]), d["yaw_convention"], float(d["ttl_s"]),
        int(d["hop_count"]), tuple(d["relay_path"]),
        tuple(TrackEntry(int(t["track_id"]), t["cls"], float(t["cls_prob"]), float(t["x"]), float(t["y"]), float(t["yaw"]), float(t["vx"]), float(t["vy"]),
                         tuple(float(c) for c in t["cov"]), float(t["var_yaw"]), float(t["existence"]), float(t["t_upd"])) for t in d["tracks"]))


def _canonical(d: dict) -> bytes:
    return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def crc_of(d: dict) -> int:
    """CRC-32 over the canonical bytes of the message dict WITHOUT its crc32 field."""
    return zlib.crc32(_canonical({k: v for k, v in d.items() if k != "crc32"})) & 0xFFFFFFFF


def serialize(m: TrackMsg) -> bytes:
    try:
        d = to_dict(m)
        d["crc32"] = crc_of(d)
        return _canonical(d)
    except ValueError as e:                                   # NaN/Inf can never be put on the wire
        raise MsgError("non_finite", str(e))


def _reject_constant(name):
    raise MsgError("non_finite", f"JSON constant {name} is not allowed")


def _no_dup_keys(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise MsgError("malformed_bytes", f"duplicate JSON key {k!r}")
        d[k] = v
    return d


def parse_bytes(b: bytes) -> dict:
    try:
        text = b.decode("utf-8")
    except UnicodeDecodeError as e:
        raise MsgError("malformed_bytes", f"utf-8: {e.reason}")
    try:
        d = json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_no_dup_keys)
    except MsgError:
        raise
    except (json.JSONDecodeError, RecursionError) as e:
        raise MsgError("malformed_bytes", str(e)[:80])
    if not isinstance(d, dict):
        raise MsgError("malformed_bytes", "top level is not an object")
    return d


def deserialize(b: bytes) -> TrackMsg:
    d = parse_bytes(b)
    v = d.get("schema_version")
    if v != SCHEMA_VERSION:
        raise MsgError("unsupported_version", f"{v!r} (supported: {SCHEMA_VERSION})")
    c = d.get("crc32")
    if isinstance(c, int) and not isinstance(c, bool):
        try:
            ok = crc_of(d) == c
        except ValueError:                                    # a non-finite value inside a CRC-carrying dict
            raise MsgError("non_finite", "non-finite number")
        if not ok:
            raise MsgError("integrity", "crc32 mismatch")
    return from_dict(d)


def relay_message(m: TrackMsg, node_id: str, tx_seq: int, clock_id: str, t_sent_local: float) -> TrackMsg:
    """Retransmit/relay: observation identity and time are PRESERVED; only the hop identity, send time, hop count and path change."""
    from dataclasses import replace
    return replace(m, msg_id=f"{node_id}:{tx_seq}", tx=Tx(node_id, tx_seq, clock_id), t_sent=t_sent_local,
                   hop_count=m.hop_count + 1, relay_path=tuple(m.relay_path) + (node_id,))


def track_ref(m: TrackMsg, t: TrackEntry) -> tuple:
    """SOURCE-SCOPED identity of a track. Never a global identity; relays do not change it."""
    return (m.origin.source_id, t.track_id)


def content_key(m: TrackMsg) -> tuple:
    return (m.origin.source_id, m.origin.orig_seq)
