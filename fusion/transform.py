"""Explicit SE(2) coordinate transform of a [x, y, vx, vy] estimate WITH covariance propagation, including the uncertainty of the transform itself.
p' = R(theta) p + t ; v' = R(theta) v.  Params u = [tx, ty, theta] ~ N(u0, Sigma_u).  P' = J_x P J_x^T + J_u Sigma_u J_u^T.
Cross-correlation induced by a transform SHARED by several estimates is NOT modelled (documented limitation)."""
from __future__ import annotations
import math
from dataclasses import dataclass
import numpy as np


class TransformError(ValueError):
    pass


@dataclass(frozen=True)
class Transform2D:
    src_frame: str
    dst_frame: str
    tx: float
    ty: float
    theta: float
    cov: tuple = (0.0,) * 9                       # 3x3 covariance of (tx, ty, theta), row-major

    def __post_init__(self):
        S = np.array(self.cov, dtype=float).reshape(3, 3)
        if not (np.all(np.isfinite(S)) and np.allclose(S, S.T, atol=1e-12) and np.linalg.eigvalsh(0.5 * (S + S.T)).min() > -1e-12):
            raise TransformError("transform covariance must be finite, symmetric and positive semi-definite")
        if not all(math.isfinite(v) for v in (self.tx, self.ty, self.theta)):
            raise TransformError("non-finite transform parameters")

    def R(self) -> np.ndarray:
        c, s = math.cos(self.theta), math.sin(self.theta)
        return np.array([[c, -s], [s, c]])

    def apply_state(self, x: np.ndarray, P: np.ndarray):
        R = self.R(); c, s = math.cos(self.theta), math.sin(self.theta)
        px, py, vx, vy = x
        xn = np.array([R[0, 0] * px + R[0, 1] * py + self.tx, R[1, 0] * px + R[1, 1] * py + self.ty, R[0, 0] * vx + R[0, 1] * vy, R[1, 0] * vx + R[1, 1] * vy])
        Jx = np.zeros((4, 4)); Jx[0:2, 0:2] = R; Jx[2:4, 2:4] = R
        dR = np.array([[-s, -c], [c, -s]])                           # dR/dtheta
        Ju = np.zeros((4, 3))
        Ju[0, 0] = Ju[1, 1] = 1.0
        Ju[0:2, 2] = dR @ np.array([px, py]); Ju[2:4, 2] = dR @ np.array([vx, vy])
        Sig = np.array(self.cov, dtype=float).reshape(3, 3)
        Pn = Jx @ P @ Jx.T + Ju @ Sig @ Ju.T
        return xn, 0.5 * (Pn + Pn.T)

    def inverse(self) -> "Transform2D":
        """Nominal inverse (the parameter covariance is mapped to first order)."""
        c, s = math.cos(-self.theta), math.sin(-self.theta)
        Ri = np.array([[c, -s], [s, c]])
        t = -Ri @ np.array([self.tx, self.ty])
        # d(inv params)/d(params): ti = -R^T t ; theta_i = -theta
        dRi = np.array([[-s, -c], [c, -s]])                          # d(R(-theta))/d(-theta)
        J = np.zeros((3, 3)); J[0:2, 0:2] = -Ri; J[0:2, 2] = -(dRi @ np.array([self.tx, self.ty])) * (-1.0); J[2, 2] = -1.0
        S = J @ np.array(self.cov, dtype=float).reshape(3, 3) @ J.T
        return Transform2D(self.dst_frame, self.src_frame, float(t[0]), float(t[1]), -self.theta, tuple(float(v) for v in S.reshape(-1)))

    def apply(self, est):
        """Transform an Estimate; the frame must match src_frame (no silent transforms)."""
        from dataclasses import replace
        if est.frame != self.src_frame:
            raise TransformError(f"estimate frame {est.frame!r} != transform source frame {self.src_frame!r}")
        x, P = self.apply_state(np.array(est.x, dtype=float), np.array(est.P, dtype=float).reshape(4, 4))
        return replace(est, x=tuple(float(v) for v in x), P=tuple(float(v) for v in P.reshape(-1)), frame=self.dst_frame)


def compose(a: Transform2D, b: Transform2D) -> Transform2D:
    """(a o b): apply b first, then a. Nominal composition; covariance mapped to first order (independence of a and b assumed)."""
    if b.dst_frame != a.src_frame:
        raise TransformError("frame mismatch in composition")
    Ra = a.R(); t = Ra @ np.array([b.tx, b.ty]) + np.array([a.tx, a.ty]); th = a.theta + b.theta
    Jb = np.zeros((3, 3)); Jb[0:2, 0:2] = Ra; Jb[0:2, 2] = 0.0; Jb[2, 2] = 1.0
    dRa = np.array([[-math.sin(a.theta), -math.cos(a.theta)], [math.cos(a.theta), -math.sin(a.theta)]])
    Ja = np.eye(3); Ja[0:2, 2] = dRa @ np.array([b.tx, b.ty])
    S = Ja @ np.array(a.cov).reshape(3, 3) @ Ja.T + Jb @ np.array(b.cov).reshape(3, 3) @ Jb.T
    return Transform2D(b.src_frame, a.dst_frame, float(t[0]), float(t[1]), float(th), tuple(float(v) for v in S.reshape(-1)))
