"""Adapters from WP2/WP3 objects to fusion Estimates (duck-typed: fusion never imports comm or backend)."""
from __future__ import annotations
from .types import Estimate


def from_local_track(source_id: str, trk) -> Estimate:
    """perception.tracker.Track (state valid at trk.t, already predicted to the query time)."""
    return Estimate(source_id, trk.track_id, trk.t, tuple(trk.x), tuple(trk.P), trk.cls, 1.0, "local", ((f"local:{source_id}", trk.track_id),))


def from_stored(st) -> Estimate:
    """comm.store.StoredTrack: valid at the ORIGINAL observation time st.t_meas (receiver time base, clock sync UNKNOWN B04)."""
    e = st.entry
    return Estimate(st.ref[0], st.ref[1], st.t_meas, (e.x, e.y, e.vx, e.vy), tuple(e.cov[i] for i in range(16)), e.cls, e.cls_prob, "remote",
                    ((st.ref[0], st.orig_seq, st.ref[1]),), st.hop_count, tuple(st.relay_path), "map", tuple(st.flags))
