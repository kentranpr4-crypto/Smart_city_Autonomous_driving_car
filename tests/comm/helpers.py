from __future__ import annotations
import copy, json
from dataclasses import replace
from comm.admission import Admission, AdmissionConfig, SourceRegistry
from comm.channel import LinkConfig
from comm.clock import NodeClock
from comm.store import ReceiverStore
from comm.trackmsg import (crc_of, SCHEMA_VERSION, FRAME, UNITS, YAW_CONVENTION, Origin, Tx, TrackEntry, TrackMsg, serialize, to_dict, deserialize)

ORIGIN = "map-origin-A"
IDENT = tuple(1.0 if i % 5 == 0 else 0.0 for i in range(16))         # 4x4 identity
COV = tuple(0.04 if i % 5 == 0 else 0.0 for i in range(16))


def track(track_id=1, x=10.0, y=2.0, vx=1.0, vy=0.0, t_upd=1.0, cls="pedestrian"):
    return TrackEntry(track_id, cls, 0.9, x, y, 0.0, vx, vy, COV, 0.1, 0.9, t_upd)


def msg(source="k", seq=0, t_meas=1.0, t_sent=None, tracks=None, ttl=1.0, confirmation="3of4", source_type="cctv", clock="c-k", tx_node=None, hop=0, relay_path=()):
    tr = tuple(tracks) if tracks is not None else (track(t_upd=t_meas),)
    ts = t_meas + 0.01 if t_sent is None else t_sent
    return TrackMsg(SCHEMA_VERSION, f"{tx_node or source}:{seq}", Tx(tx_node or source, seq, clock),
                    Origin(source, source_type, seq, f"{source}:{seq}", clock, "synced",
                           {"sensor_model": "m", "algo_version": "a", "calib_id": "c", "privacy_level": "object_only", "confirmation": confirmation}),
                    t_meas, ts, FRAME, ORIGIN, dict(UNITS), YAW_CONVENTION, ttl, hop, tuple(relay_path), tr)


def with_crc(d: dict) -> dict:
    d = dict(d); d.pop("crc32", None); d["crc32"] = crc_of(d); return d


def mutated(m: TrackMsg, fn, fix_crc=True) -> bytes:
    """Serialize m, apply fn to the plain dict (to forge invalid content that the dataclass would not construct), re-encode.
    fix_crc=True recomputes the CRC so the forged content reaches the check it is meant to test; fix_crc=False leaves a stale CRC."""
    d = copy.deepcopy(to_dict(m)); fn(d)
    d = with_crc(d) if fix_crc else {**d, "crc32": crc_of(to_dict(m))}
    return json.dumps(d, sort_keys=True, separators=(",", ":"), allow_nan=True).encode()


def adm(receiver="ego", sources=None, relays=(), origin_id=ORIGIN, **kw):
    cfg = AdmissionConfig(receiver, origin_id, **kw)
    return Admission(cfg, SourceRegistry(dict(sources or {"k": "cctv", "v": "vehicle", "agg": "aggregator"}), frozenset(relays)), NodeClock("rx"))
