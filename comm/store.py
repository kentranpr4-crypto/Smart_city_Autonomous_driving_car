"""Receiver store of ADMITTED advisory tracks (P1): positive information only. Absence, staleness or rejection is never turned into 'free'.
Identity is source-scoped: key = (origin.source_id, track_id)."""
from __future__ import annotations
from dataclasses import dataclass
from .aoi import AoIMeter
from .trackmsg import TrackEntry, track_ref


@dataclass(frozen=True)
class StoredTrack:
    ref: tuple                       # (source_id, track_id)
    entry: TrackEntry
    t_meas: float
    age_est: float                   # receiver-visible estimate at query time
    ttl_left: float
    hop_count: int
    flags: tuple


class ReceiverStore:
    def __init__(self, max_age_s: float):
        self.max_age_s = max_age_s
        self._d: dict = {}
        self.aoi_src: dict = {}
        self.aoi_track: dict = {}
        self.ignored_older = 0

    def ingest(self, result) -> None:
        assert result.admitted and result.msg is not None, "only ADMITTED messages may enter the store"
        m = result.msg
        self.aoi_src.setdefault(m.origin.source_id, AoIMeter()).observe(result.t_proc, m.t_meas)
        for t in m.tracks:
            ref = track_ref(m, t)
            self.aoi_track.setdefault(ref, AoIMeter()).observe(result.t_proc, t.t_upd)
            cur = self._d.get(ref)
            if cur is not None and not (m.t_meas > cur[1]):
                self.ignored_older += 1                          # older/equal observation never overwrites a newer one
                continue
            self._d[ref] = (t, m.t_meas, m.t_meas + m.ttl_s, m.hop_count, result.flags)

    def purge(self, t_local: float) -> int:
        dead = [r for r, (_, tm, exp, _, _) in self._d.items() if t_local - tm > self.max_age_s or t_local > exp]
        for r in dead:
            del self._d[r]
        return len(dead)

    def tracks(self, t_local: float) -> list:
        """Advisory constraints: tracks that are still fresh. A missing track means 'no information', NEVER 'free'."""
        self.purge(t_local)
        return [StoredTrack(r, e, tm, t_local - tm, exp - t_local, hc, fl) for r, (e, tm, exp, hc, fl) in sorted(self._d.items())]
