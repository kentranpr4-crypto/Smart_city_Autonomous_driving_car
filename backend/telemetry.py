"""Canonical JSONL telemetry + SHA-256 over the exact bytes written."""
from __future__ import annotations
import hashlib, json, math


def _clean(o):
    if isinstance(o, float):
        if math.isnan(o) or math.isinf(o):
            raise ValueError("non-finite float in telemetry")
        return 0.0 if o == 0.0 else o      # normalise -0.0
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def canonical_line(rec: dict) -> bytes:
    return (json.dumps(_clean(rec), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


class TelemetryWriter:
    def __init__(self, path=None, keep=False):
        self._h = hashlib.sha256()
        self._f = open(path, "wb") if path else None
        self.lines = [] if keep else None
        self.count = 0

    def write(self, rec: dict):
        b = canonical_line(rec)
        self._h.update(b)
        if self._f: self._f.write(b)
        if self.lines is not None: self.lines.append(rec)
        self.count += 1

    def hexdigest(self) -> str:
        return self._h.hexdigest()

    def close(self):
        if self._f: self._f.close(); self._f = None
