"""Estimate combination rules. All take lists of (x, P) valid at the SAME time. Independence/correlation assumptions are explicit per rule."""
from __future__ import annotations
import numpy as np


def _spd_inv(P):
    return np.linalg.inv(0.5 * (P + P.T))


def naive(items):
    """B2: arithmetic mean of states, arithmetic mean of covariances. No information gain, no covariance weighting. No independence claim."""
    xs = np.array([x for x, _ in items]); Ps = np.array([P for _, P in items])
    return xs.mean(axis=0), Ps.mean(axis=0), ()


def information(items):
    """B3: P^-1 = sum P_i^-1 ; x = P sum P_i^-1 x_i.  ASSUMES the estimates are independent (errors uncorrelated)."""
    Y = sum(_spd_inv(P) for _, P in items)
    P = _spd_inv(Y)
    x = P @ sum(_spd_inv(Pi) @ xi for xi, Pi in items)
    return x, 0.5 * (P + P.T), ()


def _ci_pair(x1, P1, x2, P2, criterion="trace"):
    I1, I2 = _spd_inv(P1), _spd_inv(P2)

    def at(w):
        Pw = _spd_inv(w * I1 + (1.0 - w) * I2)
        return (np.trace(Pw) if criterion == "trace" else np.linalg.det(Pw)), Pw
    lo, hi = 0.0, 1.0; gr = (np.sqrt(5.0) - 1.0) / 2.0
    a, b = hi - gr * (hi - lo), lo + gr * (hi - lo); fa, fb = at(a)[0], at(b)[0]
    for _ in range(48):                                     # golden section: deterministic, fixed iteration count
        if fa < fb: hi, b, fb = b, a, fa; a = hi - gr * (hi - lo); fa = at(a)[0]
        else: lo, a, fa = a, b, fb; b = lo + gr * (hi - lo); fb = at(b)[0]
    cands = [0.0, 1.0, 0.5 * (lo + hi)]
    w = min(cands, key=lambda c: (at(c)[0], c))             # endpoints are legal CI solutions (one input dominates)
    Pw = at(w)[1]
    xw = Pw @ (w * I1 @ x1 + (1.0 - w) * I2 @ x2)
    return xw, 0.5 * (Pw + Pw.T), float(w)


def covariance_intersection(items, criterion="trace"):
    """B4: CI for UNKNOWN cross-correlation. n>2: sequential pairwise CI in the given order (CI of a CI output with another input stays consistent).
    Returns the weights w_i of the equivalent n-way convex combination of information matrices (sum = 1)."""
    x, P = np.asarray(items[0][0], float), np.asarray(items[0][1], float)
    weights = [1.0]
    for xi, Pi in items[1:]:
        x, P, w = _ci_pair(x, P, np.asarray(xi, float), np.asarray(Pi, float), criterion)
        weights = [w * u for u in weights] + [1.0 - w]
    return x, P, tuple(weights)
