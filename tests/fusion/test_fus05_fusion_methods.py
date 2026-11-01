"""FUS-05 · B0..B4: closed forms, CI consistency under unknown correlation, B3 over-confidence under correlation (test of the test)."""
import numpy as np, pytest
from fusion import combine
from fusion.fuser import CooperativeFuser
from tests.fusion.helpers import est, loc, P4

pytestmark = pytest.mark.fus
RNG = np.random.default_rng(5)
X = np.array([10.0, 0.0, 1.0, 0.0])


def test_fus05_information_fusion_closed_form_scalar_and_equal_covariances():
    x, P, _ = combine.information([(np.array([0.0]), np.array([[4.0]])), (np.array([3.0]), np.array([[1.0]]))])
    assert x[0] == pytest.approx(2.4) and P[0, 0] == pytest.approx(0.8)
    A = np.diag([.04, .04, .25, .25]); x2, P2, _ = combine.information([(X, A), (X + 0.1, A)])
    assert np.allclose(P2, A / 2) and np.allclose(x2, X + 0.05)


def test_fus05_naive_is_the_plain_mean_with_no_information_gain():
    A, B = np.diag([.04] * 4), np.diag([.16] * 4)
    x, P, _ = combine.naive([(X, A), (X + 1, B)])
    assert np.allclose(x, X + 0.5) and np.allclose(P, (A + B) / 2)


def test_fus05_ci_properties_weights_information_identity_and_trace_bound():
    for _ in range(40):
        A = RNG.normal(size=(4, 4)); P1 = A @ A.T + .05 * np.eye(4); B = RNG.normal(size=(4, 4)); P2 = B @ B.T + .05 * np.eye(4)
        x1, x2 = RNG.normal(size=4), RNG.normal(size=4)
        x, P, w = combine.covariance_intersection([(x1, P1), (x2, P2)])
        assert all(0.0 <= v <= 1.0 for v in w) and sum(w) == pytest.approx(1.0)
        assert np.allclose(np.linalg.inv(P), w[0] * np.linalg.inv(P1) + w[1] * np.linalg.inv(P2), rtol=1e-8, atol=1e-8)
        assert np.trace(P) <= min(np.trace(P1), np.trace(P2)) + 1e-9
        assert np.linalg.eigvalsh(P).min() > 0


def correlated_pair(rho, n=6000, s=0.2):
    """Two estimates of X with error correlation rho; each reports covariance s^2 I (cross-covariance unknown to the fuser)."""
    P = (s ** 2) * np.eye(4)
    z = RNG.normal(size=(n, 4)); w1 = RNG.normal(size=(n, 4)); w2 = RNG.normal(size=(n, 4))
    e1 = s * (np.sqrt(rho) * z + np.sqrt(1 - rho) * w1); e2 = s * (np.sqrt(rho) * z + np.sqrt(1 - rho) * w2)
    return P, e1, e2


def nees_mean(rule, rho):
    P, e1, e2 = correlated_pair(rho); out = []
    for a, b in zip(e1, e2):
        x, Pf, _ = rule([(X + a, P), (X + b, P)])
        out.append((x - X) @ np.linalg.solve(Pf, x - X))
    return float(np.mean(out))


@pytest.mark.parametrize("rho", [0.0, 0.5, 0.9, 1.0])
def test_fus05_ci_is_consistent_for_any_cross_correlation(rho):
    assert nees_mean(combine.covariance_intersection, rho) <= 4.0 * 1.05


def test_fus05_information_fusion_is_consistent_when_independent_and_overconfident_when_fully_correlated():
    assert abs(nees_mean(combine.information, 0.0) - 4.0) < 0.2                                         # its stated assumption holds
    assert nees_mean(combine.information, 1.0) > 7.0                                                    # echo: error unchanged, P halved -> NEES ~ 8
    assert nees_mean(combine.information, 0.5) > 5.0


def test_fus05_naive_never_reduces_the_claimed_uncertainty():
    P = np.diag([.04] * 4)
    assert np.allclose(combine.naive([(X, P), (X, P)])[1], P)


def test_fus05_sequential_ci_for_three_sources_is_consistent_and_weights_sum_to_one():
    P = 0.04 * np.eye(4); z = RNG.normal(size=(3000, 4)) * 0.2
    out = []
    for e in z:
        x, Pf, w = combine.covariance_intersection([(X + e, P), (X + e, P), (X + e, P)])
        out.append((x - X) @ np.linalg.solve(Pf, x - X))
    assert np.mean(out) <= 4.2 and sum(w) == pytest.approx(1.0) and len(w) == 3


def test_fus05_methods_select_inputs_as_defined():
    L, R = loc(1, x=tuple(X)), est("k", 1, x=tuple(X + 0.1), seq=1)
    out = {m: CooperativeFuser(m).step(1.0, [L, R]).tracks for m in ("B0_local", "B1_remote", "B2_naive", "B3_info", "B4_ci")}
    assert [t.members for t in out["B0_local"]] == [(("ego", 1),)] and [t.members for t in out["B1_remote"]] == [(("k", 1),)]
    assert all(set(out[m][0].members) == {("ego", 1), ("k", 1)} for m in ("B2_naive", "B3_info", "B4_ci"))
    assert out["B4_ci"][0].omega and abs(sum(out["B4_ci"][0].omega) - 1) < 1e-12 and not out["B3_info"][0].omega
    assert CooperativeFuser("B0_local").step(1.0, [R]).tracks == () and CooperativeFuser("B1_remote").step(1.0, [L]).tracks == ()


def test_fus05_b0_and_b1_ignore_the_other_source_entirely_including_id_persistence():
    f = CooperativeFuser("B0_local")
    a = f.step(1.0, [loc(1), est("k", 1, seq=1)]).tracks[0].fid
    b = f.step(1.1, [loc(1, t=1.1, x=(10.1, 0, 1, 0))]).tracks[0].fid
    assert a == b


def test_fus05_ci_weight_is_the_trace_optimum_over_a_dense_grid():
    """Found by mutation (omega fixed at 0.5 survived): the chosen weight must minimise trace(P) against a 201-point grid."""
    for _ in range(25):
        A = RNG.normal(size=(4, 4)); P1 = A @ A.T + .05 * np.eye(4); B = RNG.normal(size=(4, 4)); P2 = 10 * (B @ B.T) + .05 * np.eye(4)
        _, P, w = combine.covariance_intersection([(RNG.normal(size=4), P1), (RNG.normal(size=4), P2)])
        grid = min(np.trace(np.linalg.inv(g * np.linalg.inv(P1) + (1 - g) * np.linalg.inv(P2))) for g in np.linspace(0, 1, 201))
        assert np.trace(P) <= grid + 1e-9
    P1, P2 = np.diag([1e-4, 1.0, 1.0, 1.0]), np.diag([1.0, 1e-4, 1.0, 1.0])
    assert 0.0 < combine.covariance_intersection([(X, P1), (X, P2)])[2][0] < 1.0


def test_fus05_b0_and_b1_do_not_even_look_at_the_other_source():
    stale_remote = est("k", 1, t=0.1, seq=1); bad_local = loc(2, x=(float("nan"), 0, 0, 0))
    assert CooperativeFuser("B0_local").step(1.0, [loc(1), stale_remote]).diagnostics["rejected"] == {}
    assert CooperativeFuser("B0_local").step(1.0, [loc(1), stale_remote]).diagnostics["n_inputs"] == 1
    assert CooperativeFuser("B1_remote").step(1.0, [bad_local, est("k", 1, seq=1)]).diagnostics["rejected"] == {}
    assert CooperativeFuser("B1_remote").step(1.0, [bad_local, est("k", 1, seq=1)]).diagnostics["n_inputs"] == 1
