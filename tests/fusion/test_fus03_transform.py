"""FUS-03 · SE(2) transform with covariance propagation (including the uncertainty of the transform)."""
import numpy as np, pytest
from fusion.transform import Transform2D, TransformError, compose
from tests.fusion.helpers import est, P4

pytestmark = pytest.mark.fus
RNG = np.random.default_rng(7)


def num_jac(f, u, h=1e-6):
    return np.stack([(f(u + h * e) - f(u - h * e)) / (2 * h) for e in np.eye(len(u))], axis=1)


def T(tx=1.0, ty=-2.0, th=0.7, cov=None):
    return Transform2D("a", "b", tx, ty, th, tuple((cov if cov is not None else np.zeros((3, 3))).reshape(-1)))


def test_fus03_jacobians_equal_central_finite_differences():
    x = np.array([3.0, -1.0, 1.2, 0.4]); t = T()
    f_state = lambda s: Transform2D("a", "b", t.tx, t.ty, t.theta).apply_state(s, np.eye(4))[0]
    Jx = num_jac(f_state, x)
    R = t.R(); assert np.allclose(Jx[0:2, 0:2], R, atol=1e-8) and np.allclose(Jx[2:4, 2:4], R, atol=1e-8)
    f_par = lambda u: Transform2D("a", "b", u[0], u[1], u[2]).apply_state(x, np.eye(4))[0]
    Ju = num_jac(f_par, np.array([t.tx, t.ty, t.theta]))
    # recover the analytic Ju through a covariance probe: P' - R P R^T with Sigma_u = e_k e_k^T equals Ju[:,k] Ju[:,k]^T
    for k in range(3):
        S = np.zeros((3, 3)); S[k, k] = 1.0
        _, Pn = Transform2D("a", "b", t.tx, t.ty, t.theta, tuple(S.reshape(-1))).apply_state(x, np.zeros((4, 4)))
        assert np.allclose(Pn, np.outer(Ju[:, k], Ju[:, k]), atol=1e-6)


def test_fus03_exact_transform_without_uncertainty_rotates_the_covariance():
    t = T(); P = np.array(P4(0.2, 0.5)).reshape(4, 4); P[0, 1] = P[1, 0] = 0.01
    _, Pn = t.apply_state(np.array([1.0, 2, 3, 4]), P)
    R = t.R(); Rb = np.block([[R, np.zeros((2, 2))], [np.zeros((2, 2)), R]])
    assert np.allclose(Pn, Rb @ P @ Rb.T, atol=1e-14)


def test_fus03_inverse_and_composition_round_trip_on_states():
    t1 = Transform2D("a", "b", 1.0, 2.0, 0.4); t2 = Transform2D("b", "c", -3.0, 0.5, -1.1)
    x = np.array([5.0, -2.0, 1.0, 0.3]); P = np.diag([.04, .04, .09, .09])
    xi, _ = t1.inverse().apply_state(*t1.apply_state(x, P))
    assert np.allclose(xi, x, atol=1e-12)
    c = compose(t2, t1)
    assert np.allclose(c.apply_state(x, P)[0], t2.apply_state(*t1.apply_state(x, P))[0], atol=1e-12)
    assert np.allclose(c.apply_state(x, P)[1], t2.apply_state(*t1.apply_state(x, P))[1], atol=1e-12)


def test_fus03_transform_uncertainty_is_consistent_in_monte_carlo():
    sig = np.diag([0.2 ** 2, 0.2 ** 2, 0.01 ** 2]); x0 = np.array([30.0, 10.0, 1.0, 0.5]); P0 = np.diag([.04, .04, .09, .09])
    t = T(1.0, 2.0, 0.3, sig); n = 20000
    xn, Pn = t.apply_state(x0, P0)
    errs = []
    for _ in range(n):
        u = RNG.multivariate_normal([1.0, 2.0, 0.3], sig); xs = x0 + RNG.multivariate_normal(np.zeros(4), P0)
        errs.append(Transform2D("a", "b", *u).apply_state(xs, np.zeros((4, 4)))[0] - xn)
    e = np.array(errs); nees = np.einsum("ni,ij,nj->n", e, np.linalg.inv(Pn), e)
    assert abs(nees.mean() - 4.0) < 0.12
    _, P_ignored = T(1.0, 2.0, 0.3).apply_state(x0, P0)                                               # ignoring the transform uncertainty is over-confident (test of the test)
    nees2 = np.einsum("ni,ij,nj->n", e, np.linalg.inv(P_ignored), e)
    assert nees2.mean() > 5.0


def test_fus03_frames_are_explicit_and_bad_transforms_are_refused():
    t = T()
    with pytest.raises(TransformError): t.apply(est(frame="map"))                                       # estimate is in 'map', transform expects 'a'
    out = t.apply(est(frame="a"))
    assert out.frame == "b"
    with pytest.raises(TransformError): T(cov=-np.eye(3))
    with pytest.raises(TransformError): T(cov=np.array([[1, 2, 0], [0, 1, 0], [0, 0, 1.0]]))
    with pytest.raises(TransformError): Transform2D("a", "b", float("nan"), 0, 0)
    with pytest.raises(TransformError): compose(T(), T())                                              # b != a
