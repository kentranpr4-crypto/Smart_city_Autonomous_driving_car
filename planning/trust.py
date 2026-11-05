"""Evidence / trust admission. Maps fused tracks to hypotheses with a trust LEVEL.  Rules (R-CLP-02):
 local        : has a member from the ego's own tracker  -> may trigger up to emergency braking
 corroborated : remote-only, >=2 DISTINCT remote sources, persistent -> may trigger up to the corroborated cap (follower-aware)
 advisory     : remote-only, 1 source, persistent                    -> may trigger comfort braking only
 pending      : remote-only but not yet persistent                   -> ignored (counted)
 rejected     : stale / quarantined / ambiguous remote-only         -> ignored (counted)
Nothing is ever 'authenticated': the identity assurance of a remote source is at best 'allowlist-only' (no cryptography exists)."""
from __future__ import annotations
from collections import Counter
from .types import ADVISORY, CORROBORATED, EGO_SOURCE, LOCAL, PENDING, REJECTED, Hypothesis


class TrustAdmission:
    def __init__(self, prm: dict, naive: bool = False):
        self.prm, self.naive = prm, naive
        self._seen: dict = {}
        self.counts = Counter()

    def classify(self, tracks) -> list:
        out, alive = [], set()
        for f in tracks:
            srcs = tuple(sorted({m[0] for m in f.members}))
            remote = tuple(s for s in srcs if s != EGO_SOURCE)
            local = EGO_SOURCE in srcs
            n = self._seen.get(f.fid, 0) + 1
            alive.add(f.fid); self._seen[f.fid] = n
            assurance = "local" if not remote else "allowlist-only"
            if f.assurance == "authenticated":       # unreachable by construction; counted so the invariant is measurable
                self.counts["claimed_authenticated"] += 1
            x, y, vx, vy = f.x
            if local:
                level = LOCAL
            elif self.naive:
                level = LOCAL                         # ABLATION: full trust in remote-only evidence
            elif f.max_remote_age_s > self.prm["remote_max_age_s"] + 1e-9 or "quarantined_source" in f.flags or "ambiguous_association" in f.flags:
                level = REJECTED
            elif n < self.prm["min_persistence_cycles"]:
                level = PENDING
            elif len(remote) >= 2:
                level = CORROBORATED
            else:
                level = ADVISORY
            self.counts[level] += 1
            out.append(Hypothesis(f.fid, x, y, vx, vy, f.P, f.cls, level, srcs, f.max_remote_age_s, tuple(f.flags), n, assurance))
        self._seen = {k: v for k, v in self._seen.items() if k in alive}
        return out
