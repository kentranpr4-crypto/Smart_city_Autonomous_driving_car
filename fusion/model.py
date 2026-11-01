"""Constant-velocity motion model and covariance propagation (temporal alignment). Identical to perception.tracker's _F/_Q (a test asserts it)."""
from __future__ import annotations
import numpy as np


def F(dt: float) -> np.ndarray:
    m = np.eye(4); m[0, 2] = m[1, 3] = dt
    return m


def Q(dt: float, sigma_a: float) -> np.ndarray:
    q = sigma_a * sigma_a
    return q * np.array([[dt**4 / 4, 0, dt**3 / 2, 0], [0, dt**4 / 4, 0, dt**3 / 2], [dt**3 / 2, 0, dt**2, 0], [0, dt**3 / 2, 0, dt**2]])


def predict(x: np.ndarray, P: np.ndarray, dt: float, sigma_a: float, time_sigma_s: float = 0.0):
    """x' = F x ; P' = F P F^T + Q(dt) [+ v v^T sigma_t^2 on the position block: the state is EVALUATED at an uncertain time]. dt < 0 (backward) is allowed: only Q's |dt| powers matter."""
    Fm = F(dt)
    Pn = Fm @ P @ Fm.T + Q(abs(dt), sigma_a)
    if time_sigma_s > 0.0:
        v = x[2:4]
        Pn[0:2, 0:2] += np.outer(v, v) * time_sigma_s ** 2
    return Fm @ x, 0.5 * (Pn + Pn.T)
