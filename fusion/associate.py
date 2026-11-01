"""Cross-source association WITHOUT ground truth: optimal 1-1 assignment (Hungarian) on the 4-D Mahalanobis distance of the difference of two
estimates, S = Pa + Pb (correlation between the two estimates is unknown and ignored for GATING only), chi2 gate, class constraint, ambiguity flag."""
from __future__ import annotations
import numpy as np
from perception.hungarian import linear_sum_assignment

BIG = 1e9


def d2(xa, Pa, xb, Pb) -> float:
    r = np.asarray(xa, float) - np.asarray(xb, float)
    S = np.asarray(Pa, float) + np.asarray(Pb, float)
    return float(r @ np.linalg.solve(S, r))


def pair_cost_matrix(A, B, gate: float, class_gate: bool = True):
    """A, B: lists of (x(4), P(4x4), cls). Returns (cost, raw_d2). Pairs outside the gate or with conflicting KNOWN classes get BIG."""
    raw = np.full((len(A), len(B)), np.inf); cost = np.full((len(A), len(B)), BIG)
    for i, (xa, Pa, ca) in enumerate(A):
        for j, (xb, Pb, cb) in enumerate(B):
            v = d2(xa, Pa, xb, Pb); raw[i, j] = v
            conflict = class_gate and ca != cb and "unknown" not in (ca, cb)
            if v <= gate and not conflict:
                cost[i, j] = v
    return cost, raw


def associate(A, B, gate: float, class_gate: bool = True, ambiguity_margin: float = 4.0):
    """Returns (pairs [(i, j, d2)], ambiguous: set of (i, j) whose row or column has another gated candidate within `ambiguity_margin` of d2)."""
    if not A or not B:
        return [], set()
    cost, raw = pair_cost_matrix(A, B, gate, class_gate)
    pairs = [(i, j, float(raw[i, j])) for i, j in linear_sum_assignment(cost.tolist()) if cost[i, j] < BIG]
    amb = set()
    for i, j, v in pairs:
        others = [cost[i, k] for k in range(len(B)) if k != j] + [cost[k, j] for k in range(len(A)) if k != i]
        if any(c < BIG and c <= v + ambiguity_margin for c in others):
            amb.add((i, j))
    return sorted(pairs), amb
