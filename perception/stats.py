"""Chi-square distribution utilities in pure Python (no scipy)."""
from __future__ import annotations
import math


def _gser(a: float, x: float) -> float:
    s = term = 1.0 / a; ap = a
    for _ in range(10000):
        ap += 1.0; term *= x / ap; s += term
        if abs(term) < abs(s) * 1e-16: break
    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gcf(a: float, x: float) -> float:
    tiny = 1e-300
    b = x + 1.0 - a; c = 1.0 / tiny; d = 1.0 / b; h = d
    for i in range(1, 10000):
        an = -i * (i - a); b += 2.0
        d = an * d + b; d = tiny if abs(d) < tiny else d
        c = b + an / c; c = tiny if abs(c) < tiny else c
        d = 1.0 / d; delta = d * c; h *= delta
        if abs(delta - 1.0) < 1e-16: break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def gammainc_lower_reg(a: float, x: float) -> float:
    if x <= 0.0: return 0.0
    return _gser(a, x) if x < a + 1.0 else 1.0 - _gcf(a, x)


def chi2_cdf(x: float, k: float) -> float:
    return gammainc_lower_reg(k / 2.0, x / 2.0)


def chi2_ppf(p: float, k: float) -> float:
    if not 0.0 < p < 1.0: raise ValueError("p must be in (0,1)")
    lo, hi = 0.0, max(1.0, k)
    while chi2_cdf(hi, k) < p: hi *= 2.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if chi2_cdf(mid, k) < p: lo = mid
        else: hi = mid
    return 0.5 * (lo + hi)
