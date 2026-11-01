"""AC-VS-03 · tracker consistency on a synthetic LINEAR scene (truth generated from the filter's own model).
PRE-REGISTERED interpretation of "NEES trung bình trong khoảng chi2 95%" (docs/phase2/wp-reports/PHY07-08-reconciliation.md):
  M=100 Monte-Carlo runs, K=60 steps at 10 Hz, seeds SEED+i.  For each k in [10,59]: M*ANEES_k must lie inside the two-sided 95% interval of chi2(4M).
  PASS iff >= 90% of those 50 steps are inside (5% expected outside by chance) AND the time-mean ANEES is within [3.6, 4.4] AND mean NIS within 2 +/- 4 SE.
"""
import math
import numpy as np
import pytest
from perception.stats import chi2_ppf
from perception.tracker import Tracker, TrackerConfig
from tests.perception.tracking_helpers import mk_frame

pytestmark = pytest.mark.trk
SEED, M, K, DTM, SA, SIGV0, SIGMA = 20261101, 100, 60, 0.1, 0.5, 2.0, 0.5


def Qm(dt, sa):
    q = sa * sa
    return q * np.array([[dt**4/4, 0, dt**3/2, 0], [0, dt**4/4, 0, dt**3/2], [dt**3/2, 0, dt**2, 0], [0, dt**3/2, 0, dt**2]])


def monte_carlo(cfg, declared_scale=1.0):
    F = np.eye(4); F[0, 2] = F[1, 3] = DTM
    G = np.array([[DTM**2 / 2, 0], [0, DTM**2 / 2], [DTM, 0], [0, DTM]])      # white-noise acceleration input; G G^T sa^2 == Qm (rank 2)
    assert np.allclose(SA**2 * G @ G.T, Qm(DTM, SA))
    nees = np.zeros((M, K)); nis = []
    for i in range(M):
        rng = np.random.default_rng(SEED + i)
        x = np.array([rng.normal(0, 5), rng.normal(0, 5), rng.normal(0, SIGV0), rng.normal(0, SIGV0)])
        tr = Tracker("s", cfg)
        for k in range(K):
            if k > 0: x = F @ x + G @ (SA * rng.standard_normal(2))
            z = x[:2] + SIGMA * rng.standard_normal(2)
            rep = tr.update(mk_frame(k, k * DTM, [(z[0], z[1], (declared_scale * SIGMA) ** 2)]), t_now=k * DTM)
            assert rep.accepted
            nis += list(rep.nis)
            trk = tr.tracks(confirmed_only=False)[0]
            e = np.array(trk.x) - x; P = np.array(trk.P).reshape(4, 4)
            nees[i, k] = float(e @ np.linalg.solve(P, e))
    return nees, np.array(nis)


def verdict(nees, nis):
    a = nees.mean(axis=0)
    lo, hi = chi2_ppf(0.025, 4 * M) / M, chi2_ppf(0.975, 4 * M) / M
    ks = range(10, K)
    inside = sum(lo <= a[k] <= hi for k in ks) / len(ks)
    mean_nis = nis.mean(); se = math.sqrt(4.0 / len(nis))
    return {"inside_frac": inside, "anees_time_mean": float(a[10:].mean()), "nis_mean": float(mean_nis), "nis_ok": abs(mean_nis - 2.0) <= 4 * se,
            "bounds": (lo, hi), "ok": inside >= 0.90 and 3.6 <= a[10:].mean() <= 4.4 and abs(mean_nis - 2.0) <= 4 * se}


MATCHED = TrackerConfig(sigma_a=SA, init_speed_sigma=SIGV0)


def test_matched_filter_is_consistent_AC_VS_03():
    v = verdict(*monte_carlo(MATCHED))
    assert v["ok"], v


def test_the_consistency_check_detects_an_underestimated_process_noise():
    """Test the test: filter assumes sigma_a 10x too small -> NEES must blow past the interval (otherwise the check is toothless)."""
    v = verdict(*monte_carlo(TrackerConfig(sigma_a=SA / 10, init_speed_sigma=SIGV0)))
    assert not v["ok"] and v["anees_time_mean"] > 4.4, v


def test_the_consistency_check_detects_an_overconfident_declared_measurement_covariance():
    v = verdict(*monte_carlo(MATCHED, declared_scale=0.5))                        # sensor declares half its true sigma
    assert not v["ok"] and (v["anees_time_mean"] > 4.4 or not v["nis_ok"]), v


def test_noise_free_target_is_recovered_exactly():
    tr = Tracker("s", TrackerConfig(sigma_a=0.1))
    for k in range(40):
        t = k * 0.1; x, y = 3.0 + 1.5 * t, -2.0 + 0.5 * t
        tr.update(mk_frame(k, t, [(x, y, 1e-6)]), t_now=t)
    trk = tr.tracks()[0]
    assert trk.confirmed and trk.x[0] == pytest.approx(3.0 + 1.5 * 3.9, abs=1e-3) and trk.x[2] == pytest.approx(1.5, abs=2e-2) and trk.x[3] == pytest.approx(0.5, abs=2e-2)


def test_results_are_deterministic():
    a = monte_carlo(MATCHED)[0][:3].tobytes(); b = monte_carlo(MATCHED)[0][:3].tobytes()
    assert a == b


def test_default_gate_is_the_99_9_percent_chi2_and_not_a_hidden_constant():
    from perception.tracker import GATE_CHI2_999_2DOF
    assert TrackerConfig().gate_chi2 == GATE_CHI2_999_2DOF == pytest.approx(chi2_ppf(0.999, 2), rel=1e-12)


def test_documented_finding_duplicate_tracks_and_gate_truncation_break_consistency():
    """CHARACTERISATION (found during WP2; root cause corrected after a second measurement). With a 99% gate and NO duplicate suppression the
    pre-registered AC-VS-03 check FAILED (ANEES 4.51, 52% of steps inside): ~1% of true detections were gated out, spawned a newborn track that then
    took the measurements and starved the original track. Duplicate suppression restores consistency even at 99% (ANEES 4.09); the residual
    +0.14 vs the ungated 3.95 is genuine gate-truncation bias. Defaults: gate 99.9% + duplicate suppression (ANEES 3.96)."""
    from perception.tracker import GATE_CHI2_99_2DOF
    base = dict(sigma_a=SA, init_speed_sigma=SIGV0)
    no_dedup = verdict(*monte_carlo(TrackerConfig(**base, gate_chi2=GATE_CHI2_99_2DOF, merge_chi2=0.0)))
    dedup99 = verdict(*monte_carlo(TrackerConfig(**base, gate_chi2=GATE_CHI2_99_2DOF)))
    ungated = verdict(*monte_carlo(TrackerConfig(**base, gate_chi2=1e12)))
    assert not no_dedup["ok"] and no_dedup["anees_time_mean"] > 4.4                 # duplicates (the main cause) break consistency
    assert dedup99["ok"] and dedup99["anees_time_mean"] > ungated["anees_time_mean"] + 0.05   # truncation bias remains, but small
    assert ungated["ok"] and ungated["anees_time_mean"] == pytest.approx(4.0, abs=0.2)
