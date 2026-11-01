"""Observation-time Age of Information.  AoI(t) = t - F(t), F = freshest observation time among ADMITTED information.
Only a strictly newer observation time resets the age: older, duplicate or relayed copies of the same observation never do."""
from __future__ import annotations
import math


class AoIMeter:
    def __init__(self):
        self.fresh = None            # freshest observation time so far
        self.segments = []           # (t_update, age_just_after_update)
        self.resets = 0
        self.ignored = 0             # updates that did not carry a newer observation

    def observe(self, t_now: float, t_obs: float) -> bool:
        if self.fresh is not None and not (t_obs > self.fresh):
            self.ignored += 1
            return False
        self.fresh = t_obs
        if self.segments and self.segments[-1][0] == t_now:
            self.segments[-1] = (t_now, t_now - t_obs)         # simultaneous updates: the freshest wins; no zero-length 'peak' is recorded
        else:
            self.segments.append((t_now, t_now - t_obs))
        self.resets += 1
        return True

    def age(self, t: float):
        if not self.segments or t < self.segments[0][0]:
            return None
        k = max(i for i, (u, _) in enumerate(self.segments) if u <= t)
        u, a = self.segments[k]
        return a + (t - u)

    def peak(self, t_end: float):
        """Largest age over [first update, t_end]: right before each reset, right after the first update, or at t_end."""
        if not self.segments:
            return None
        peaks = [self.segments[0][1]]
        for k in range(len(self.segments) - 1):
            (u0, a0), (u1, _) = self.segments[k], self.segments[k + 1]
            peaks.append(a0 + (u1 - u0))                      # age right before the next reset
        u, a = self.segments[-1]
        peaks.append(a + (t_end - u))
        return max(peaks)

    def time_average(self, t_end: float):
        """Exact integral of the sawtooth / duration, from the first update to t_end."""
        if not self.segments:
            return None
        total = 0.0
        for (u0, a0), nxt in zip(self.segments, self.segments[1:] + [(t_end, None)]):
            dt = nxt[0] - u0
            total += a0 * dt + 0.5 * dt * dt
        return total / (t_end - self.segments[0][0])

    def samples(self, dt: float, t_end: float):
        if not self.segments:
            return []
        out, k, t0 = [], 0, self.segments[0][0]
        n = int(math.floor((t_end - t0) / dt + 1e-9))
        for i in range(n + 1):
            t = t0 + i * dt
            while k + 1 < len(self.segments) and self.segments[k + 1][0] <= t + 1e-12:
                k += 1
            u, a = self.segments[k]
            out.append(a + (t - u))
        return out
