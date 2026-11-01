"""Observation data types: the ONLY thing that crosses from the truth side to the perception side (I9).
Pure data, no references to ground truth. Perception code may import this module and nothing else from backend/."""
from __future__ import annotations
from dataclasses import dataclass

SCHEMA_VERSION = "0.1.0"


@dataclass(frozen=True)
class Detection:
    det_id: int                      # opaque index within the frame (carries NO truth identity)
    x: float
    y: float                         # map frame, metres
    cov: tuple                       # declared measurement covariance (xx, xy, yy)
    cls: str                         # 'pedestrian' | 'vehicle' | 'unknown'
    cls_prob: float
    score: float                     # detector confidence in [0, 1]


@dataclass(frozen=True)
class SensorFrame:
    schema_version: str
    sensor_id: str
    seq: int                         # per-sensor, strictly increasing; gaps = frames that never arrived
    t_meas: float                    # measurement time (sim clock; WP3 adds per-node clock models)
    t_avail: float                   # earliest time a consumer may use it (= t_meas + processing latency)
    sensor_pose: tuple               # (x, y, yaw, height) as REPORTED by the sensor
    fov: float                       # full field-of-view angle [rad]
    range_m: float
    detections: tuple


def detection_to_dict(d: Detection) -> dict:
    return {"det_id": d.det_id, "x": d.x, "y": d.y, "cov": list(d.cov), "cls": d.cls, "cls_prob": d.cls_prob, "score": d.score}


def frame_to_dict(f: SensorFrame) -> dict:
    return {"schema_version": f.schema_version, "sensor_id": f.sensor_id, "seq": f.seq, "t_meas": f.t_meas, "t_avail": f.t_avail,
            "sensor_pose": list(f.sensor_pose), "fov": f.fov, "range_m": f.range_m,
            "detections": [detection_to_dict(d) for d in f.detections]}


def frame_from_dict(d: dict) -> SensorFrame:
    dets = tuple(Detection(x["det_id"], x["x"], x["y"], tuple(x["cov"]), x["cls"], x["cls_prob"], x["score"]) for x in d["detections"])
    return SensorFrame(d["schema_version"], d["sensor_id"], d["seq"], d["t_meas"], d["t_avail"], tuple(d["sensor_pose"]), d["fov"], d["range_m"], dets)
