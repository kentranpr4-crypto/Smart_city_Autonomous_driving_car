"""FUS-01 temporal alignment on ORIGINAL observation time · FUS-02 covariance propagation."""
import numpy as np, pytest
from fusion.fuser import CooperativeFuser
from fusion.model import F, Q, predict
from perception.tracker import _F, _Q
from tests.fusion.helpers import est, loc, P4

pytestmark = pytest.mark.fus
RNG = np.random.default_rng(20261101)


def test_fus01_model_equals_the_tracker_model_to_machine_precision():
    for dt in RNG.uniform(-1.5, 1.5, 50):
        assert np.max(np.abs(F(dt) - _F(dt))) < 1e-15
    for dt in RNG.uniform(0.0, 1.5, 50):
        assert np.max(np.abs(Q(dt, 1.3) - _Q(dt, 1.3))) < 1e-15


def test_fus02_process_noise_is_the_discrete_white_noise_acceleration_model_and_does_not_compose():
    """Found while writing this gate: the tracker's Q is DWNA (ONE constant acceleration per interval), NOT continuous white noise, so Q(a+b) != F Q(a) F^T + Q(b).
    Consequence (documented limitation): predicting once over [t_meas, t_now] differs slightly from the tracker's step-wise predictions. Both are valid models; fusion uses the one-draw form."""
    a, b, s = 0.3, 0.4, 1.0
    assert not np.allclose(Q(a + b, s), F(b) @ Q(a, s) @ F(b).T + Q(b, s), atol=1e-6)
    g = np.array([0.5 * 0.5 ** 2, 0.5])                                                                 # DWNA: x += a dt^2/2, v += a dt  =>  Q = sigma^2 g g^T per axis
    assert np.allclose(Q(0.5, 2.0)[np.ix_([0, 2], [0, 2])], 4.0 * np.outer(g, g), atol=1e-15)


def test_fus01_predict_closed_form_and_time_sigma_term():
    x = np.array([5.0, 1.0, 2.0, -1.0]); P = np.diag([.04, .04, .09, .09])
    xn, Pn = predict(x, P, 0.25, 1.0)
    assert np.allclose(xn, [5.5, 0.75, 2.0, -1.0]) and np.allclose(Pn, F(0.25) @ P @ F(0.25).T + Q(0.25, 1.0))
    _, Pt = predict(x, P, 0.25, 1.0, time_sigma_s=0.1)
    add = np.zeros((4, 4)); add[0:2, 0:2] = np.outer(x[2:], x[2:]) * 0.01
    assert np.allclose(Pt - Pn, add, atol=1e-15)


def test_fus01_alignment_uses_the_observation_time_not_arrival_time():
    f = CooperativeFuser("B1_remote")
    r = est(t=0.9, x=(10.0, 0.0, 2.0, 0.0))
    w = f.step(1.0, [r])
    assert len(w.tracks) == 1 and np.allclose(w.tracks[0].x, [10.2, 0.0, 2.0, 0.0])               # advanced by 0.1 s = t_now - t_meas
    assert w.tracks[0].max_remote_age_s == pytest.approx(0.1)
    older = CooperativeFuser("B1_remote").step(1.0, [est(t=0.8, x=(10.0, 0.0, 2.0, 0.0))])
    assert np.allclose(older.tracks[0].x[0], 10.4)                                                    # same message content, older observation -> a larger shift


def test_fus02_covariance_grows_with_observation_age():
    tr = []
    for t in (0.99, 0.9, 0.7, 0.5):
        w = CooperativeFuser("B1_remote").step(1.0, [est(t=t)]); tr.append(np.trace(np.array(w.tracks[0].P).reshape(4, 4)))
    assert tr == sorted(tr) and tr[-1] > tr[0]


def test_fus01_future_stale_and_beyond_horizon_observations_are_refused_with_reasons():
    f = CooperativeFuser("B1_remote")
    assert f.step(1.0, [est(t=1.2)]).diagnostics["rejected"] == {"future": 1}
    assert f.step(1.0, [est(t=0.45)]).diagnostics["rejected"] == {"stale": 1}                          # remote older than 0.5 s
    g = CooperativeFuser("B0_local")
    assert g.step(2.5, [loc(t=1.0)]).diagnostics["rejected"] == {"horizon": 1}                         # 1.5 s > 1.0 s horizon
    assert g.step(1.0, [loc(t=1.0)]).tracks


def test_fus02_propagated_error_is_consistent_against_an_independent_simulation_of_the_model():
    """Independent of Q's algebra: simulate the model DEFINITION (one constant acceleration a ~ N(0, sigma_a^2) per interval); NEES of the closed-form P must be ~4."""
    n, dt, sa = 20000, 0.7, 1.0
    x0 = np.array([0.0, 0.0, 1.0, 0.5]); P0 = np.diag([.01, .01, .04, .04])
    S = x0 + RNG.multivariate_normal(np.zeros(4), P0, n); a = RNG.normal(0.0, sa, (n, 2))
    S[:, 0:2] += S[:, 2:4] * dt + 0.5 * a * dt * dt; S[:, 2:4] += a * dt
    xn, Pn = predict(x0, P0, dt, sa)
    e = S - xn; nees = np.einsum("ni,ij,nj->n", e, np.linalg.inv(Pn), e)
    assert abs(nees.mean() - 4.0) < 4 * np.sqrt(8.0 / n)                                               # mean of chi2(4): SE sqrt(8/n)
    _, Pbad = predict(x0, P0, dt, sa * 0.5)                                                            # test of the test: wrong sigma_a is detected
    assert np.einsum("ni,ij,nj->n", e, np.linalg.inv(Pbad), e).mean() > 4.0 + 4 * 4 * np.sqrt(8.0 / n) * 0.5


def test_fus02_predicted_covariance_stays_symmetric_psd_for_random_inputs():
    for _ in range(200):
        A = RNG.normal(size=(4, 4)); P = A @ A.T + 1e-3 * np.eye(4)
        x = RNG.normal(size=4); dt = RNG.uniform(-1, 1)
        _, Pn = predict(x, P, dt, RNG.uniform(0.1, 3), RNG.uniform(0, 0.2))
        assert np.allclose(Pn, Pn.T, atol=1e-12) and np.linalg.eigvalsh(Pn).min() > 0
