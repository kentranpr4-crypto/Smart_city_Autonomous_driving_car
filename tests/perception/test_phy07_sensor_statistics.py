"""PHY-07 (FOV/range boundaries, noise, p_d(r), clutter, timestamps, paired-seed RNG discipline).
Statistical tolerances are PRE-REGISTERED: two-sided 95% chi-square interval, ONE fixed seed (SEED), no re-rolling on failure."""
import math, hashlib, json
import numpy as np
import pytest
from backend.observation import frame_to_dict
from backend.sensors import SensorProvider
from perception.stats import chi2_ppf
from tests.perception.helpers import *

pytestmark = pytest.mark.phy
SEED = 20261101


# ------------------------------------------------------------------ FOV and range boundaries
def _candidate(spec, x, y):
    pv = SensorProvider([spec], SEED, DT)
    (f, lab), = pv.sample(snap([ped("p", x, y)]), 0)
    return "p" in lab.candidates


def test_fov_boundary_is_inclusive_and_exact_to_1e9_rad():
    spec = cctv(pose=(0.0, 0.0, 0.3), fov_deg=90.0, range_m=50.0, **PERFECT)
    half = math.radians(45.0)
    for sign in (+1, -1):
        for off, expect in ((-1e-9, True), (+1e-9, False)):
            ang = 0.3 + sign * (half + off)
            assert _candidate(spec, 20 * math.cos(ang), 20 * math.sin(ang)) is expect, (sign, off)


def test_range_boundary_located_within_1mm():
    spec = cctv(pose=(0.0, 0.0, 0.0), fov_deg=90.0, range_m=50.0, **PERFECT)
    lo, hi = 49.0, 51.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if _candidate(spec, mid, 0.0) else (lo, mid)
    assert abs(0.5 * (lo + hi) - 50.0) <= 1e-3


# ------------------------------------------------------------------ measurement noise (chi-square, bias, independence)
@pytest.mark.parametrize("r", [5.0, 20.0, 45.0])
def test_position_noise_matches_sigma_of_range_chi2_95(r):
    spec = cctv(pose=(0.0, 0.0, 0.0), fov_deg=120.0, range_m=60.0, sigma0=0.1, sigma1=0.01, bias=(0.3, -0.2), **PERFECT)
    sg = 0.1 + 0.01 * r
    n = 2000
    fr = stream(spec, snap([ped("p", r, 0.0)]), n, seed=SEED)
    assert len(fr) == n
    ex = np.array([(f.detections[0].x - r - 0.3) / sg for f, _ in fr]); ey = np.array([(f.detections[0].y - 0.0 + 0.2) / sg for f, _ in fr])
    stat = float((ex ** 2 + ey ** 2).sum())                                      # ~ chi2(2n) under the model
    lo, hi = chi2_ppf(0.025, 2 * n), chi2_ppf(0.975, 2 * n)
    assert lo <= stat <= hi, (stat, lo, hi)
    assert abs(ex.mean()) <= 4 / math.sqrt(n) and abs(ey.mean()) <= 4 / math.sqrt(n)    # unbiased after removing the configured bias
    rho = float(np.corrcoef(ex, ey)[0, 1])
    assert abs(rho) <= 4 / math.sqrt(n)                                          # x and y noise independent
    assert all(f.detections[0].cov == pytest.approx((sg * sg, 0.0, sg * sg)) for f, _ in fr[:5])   # declared covariance == true sigma^2


def test_declared_covariance_can_be_misreported_and_bias_is_not_declared():
    spec = cctv(pose=(0.0, 0.0, 0.0), sigma0=0.2, sigma1=0.0, declared_sigma_scale=0.5, bias=(1.0, 0.0), **PERFECT)
    (f, _), = stream(spec, snap([ped("p", 10.0, 0.0)]), 1, seed=SEED)
    assert f.detections[0].cov == pytest.approx((0.01, 0.0, 0.01))               # over-confident: declares 0.1 m while true sigma is 0.2 m
    assert not hasattr(f.detections[0], "bias") and not hasattr(f, "bias")      # the systematic offset is invisible to consumers


# ------------------------------------------------------------------ detection probability p_d(r)
def test_detection_rate_matches_pd_of_range_chi2_95():
    spec = cctv(pose=(0.0, 0.0, 0.0), fov_deg=120.0, range_m=80.0, pd0=0.95, r50=35.0, pd_slope=8.0)
    ranges, n = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0], 3000
    stat = 0.0
    for r in ranges:
        fr = stream(spec, snap([ped("p", r, 0.0)]), n, seed=SEED)
        k = sum(len(f.detections) for f, _ in fr)
        p = 0.95 / (1.0 + math.exp((r - 35.0) / 8.0))                              # INDEPENDENT logistic (not spec.pd): the test must not share the formula under test
        assert spec.pd(r) == pytest.approx(p, rel=1e-12)                           # the documented curve itself, at every bin
        stat += (k - n * p) ** 2 / (n * p * (1 - p))
    assert stat <= chi2_ppf(0.95, len(ranges)), stat                              # pre-registered: chi2 95% quantile, df = #bins
    assert spec.pd(35.0) == pytest.approx(0.475)                                  # logistic definition: p_d(r50) = pd0 / 2


def test_detections_are_independent_of_actor_order_and_ids_leak_nothing():
    spec = cctv(pose=(0.0, 0.0, 0.0), **PERFECT)
    a = snap([ped("a", 10, 1), ped("b", 15, -2), ped("c", 20, 3)])
    pv = SensorProvider([spec], SEED, DT)
    (f, lab), = pv.sample(a, 0)
    assert sorted(d.det_id for d in f.detections) == [0, 1, 2]
    assert set(lab.truth_of.values()) == {"a", "b", "c"}
    # det_id order is shuffled: ids carry no information about truth identity
    orders = set()
    for seed in range(30):
        (f, lab), = SensorProvider([spec], seed, DT).sample(a, 0)
        orders.add(tuple(lab.truth_of[d.det_id] for d in f.detections))
    assert len(orders) >= 4


# ------------------------------------------------------------------ clutter
def test_clutter_count_is_poisson_and_positions_are_uniform_in_the_sector():
    lam, n = 3.0, 3000
    spec = cctv(pose=(0.0, 0.0, 0.0), fov_deg=120.0, range_m=40.0, clutter_rate=lam, **PERFECT)
    fr = stream(spec, snap([]), n, seed=SEED)
    counts = np.array([len(f.detections) for f, _ in fr])
    assert abs(counts.mean() - lam) <= 4 * math.sqrt(lam / n)
    disp = float(((counts - counts.mean()) ** 2).sum() / counts.mean())           # Poisson dispersion test ~ chi2(n-1)
    assert chi2_ppf(0.025, n - 1) <= disp <= chi2_ppf(0.975, n - 1), disp
    pts = np.array([(d.x, d.y) for f, _ in fr for d in f.detections])
    ang, rad2 = np.arctan2(pts[:, 1], pts[:, 0]), (pts ** 2).sum(axis=1)
    assert ang.min() >= -math.radians(60) - 1e-9 and ang.max() <= math.radians(60) + 1e-9 and rad2.max() <= 40.0 ** 2 + 1e-6
    for var, edges in ((ang, np.linspace(-math.radians(60), math.radians(60), 7)), (rad2, np.linspace(0, 40.0 ** 2, 6))):
        obs, _ = np.histogram(var, bins=edges)
        exp = len(var) / (len(edges) - 1)
        assert float(((obs - exp) ** 2 / exp).sum()) <= chi2_ppf(0.95, len(edges) - 2)   # uniform in angle and in area (r^2)


# ------------------------------------------------------------------ timestamps, schedule, outages
def test_schedule_phase_timestamps_and_sequence_numbers_are_exact():
    spec = cctv(rate_hz=10.0, phase=0.03, t_proc=0.05, **PERFECT)
    pv = SensorProvider([spec], SEED, DT)
    got = []
    for step in range(0, 100):
        for f, _ in pv.sample(snap([ped("p", 10, 0)], t=step * DT), step):
            got.append((step, f))
    steps = [s for s, _ in got]
    assert steps == list(range(3, 100, 10))                                       # phase 0.03 s, period 10 steps
    for k, (s, f) in enumerate(got):
        assert f.seq == k and f.t_meas == s * DT and f.t_avail == pytest.approx(s * DT + 0.05, abs=1e-12)
        assert f.t_avail >= f.t_meas


def test_bad_schedule_parameters_are_rejected():
    with pytest.raises(ValueError, match="integer number of steps"):
        SensorProvider([cctv(rate_hz=7.0)], 1, DT)
    with pytest.raises(ValueError, match="multiple of dt"):
        SensorProvider([cctv(t_proc=0.0123)], 1, DT)


def test_outage_bursts_create_observable_sequence_gaps_with_the_configured_stationary_rate():
    p_in, p_out = 0.05, 0.25
    spec = cctv(rate_hz=10.0, dropout=(p_in, p_out), **PERFECT)
    pv = SensorProvider([spec], SEED, DT)
    n = 20000
    seqs = []
    for k in range(n):
        seqs += [f.seq for f, _ in pv.sample(snap([ped("p", 10, 0)]), k * 10)]
    missing = n - len(seqs)
    stationary = p_in / (p_in + p_out)
    assert any(b - a > 1 for a, b in zip(seqs, seqs[1:]))                         # gaps are visible to the consumer
    assert abs(missing / n - stationary) <= 0.02                                  # bursty chain: generous tolerance, large n
    assert seqs == sorted(set(seqs))                                              # seq strictly increasing, never reused


# ------------------------------------------------------------------ determinism and paired-seed discipline
def _hash(frames):
    return hashlib.sha256(json.dumps([frame_to_dict(f) for f, _ in frames], sort_keys=True).encode()).hexdigest()


def test_same_seed_same_frames_and_different_seed_differs():
    spec = cctv(clutter_rate=1.0, **PERFECT)
    s = snap([ped("p", 12, 1)])
    assert _hash(stream(spec, s, 50, seed=SEED)) == _hash(stream(spec, s, 50, seed=SEED))
    assert _hash(stream(spec, s, 50, seed=SEED)) != _hash(stream(spec, s, 50, seed=SEED + 1))


def test_adding_an_occluder_never_shifts_another_targets_noise():
    """Random draws are consumed per target regardless of visibility, so paired comparisons across scenes stay paired."""
    spec = cctv(pose=(0.0, 0.0, 0.0), height=1.5, **PERFECT)
    a, b = ped("a", 12.0, 0.0), ped("b", 30.0, 6.0)
    clear = stream(spec, snap([a, b]), 40, seed=SEED)
    block = stream(spec, snap([a, b], [wall("w", cx=20.0, cy=3.0, length=0.2, width=6.0, h=3.0)]), 40, seed=SEED)
    for (fc, lc), (fb, lb) in zip(clear, block):
        assert "b" in lc.detected and "b" not in lb.detected                      # the wall hides b ...
        da = next(d for d in fc.detections if lc.truth_of[d.det_id] == "a")
        db = next(d for d in fb.detections if lb.truth_of[d.det_id] == "a")
        assert (da.x, da.y) == (db.x, db.y)                                       # ... but a's measurement is bit-identical


def test_class_accuracy_is_respected():
    spec = cctv(pose=(0.0, 0.0, 0.0), class_accuracy=0.8, **PERFECT)
    fr = stream(spec, snap([ped("p", 10, 0)]), 3000, seed=SEED)
    k = sum(f.detections[0].cls == "pedestrian" for f, _ in fr)
    assert abs(k / 3000 - 0.8) <= 4 * math.sqrt(0.8 * 0.2 / 3000)
