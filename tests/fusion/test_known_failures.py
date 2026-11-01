"""WP4 KNOWN FAILURES (xfail strict, desired behaviour stated). They run on TUNING seeds only (never on evaluation seeds) and are not claims about the physical world."""
import pytest
from experiments.harness import run
from experiments.metrics import pool
from experiments import conditions as K
from fusion.fuser import CooperativeFuser
from tests.fusion.helpers import est, loc

pytestmark = [pytest.mark.fus, pytest.mark.known_failure]
SEEDS = K.SEEDS_TUNING[:6]


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="KF-6: cross-source association confuses two real pedestrians 0.4 m apart (extends KF-1 to fusion; tuning seeds: precision ~0.55).")
def test_KF6_close_pedestrians_are_associated_correctly_across_sources():
    runs = [run("C2a_close_0p4", s, methods=("B4_ci",), time_it=False) for s in SEEDS]
    p = pool(runs, "B4_ci")
    assert p["assoc_precision"] >= 0.95 and p["availability"] >= 0.9


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="KF-7: an UNDECLARED constant remote bias (0.58 m) breaks the association gate part of the time and leaves duplicate ghost tracks (tuning seeds: ~0.22 false tracks/cycle).")
def test_KF7_undeclared_remote_bias_does_not_create_ghost_tracks():
    runs = [run("C5a_bias_undeclared", s, methods=("B0_local", "B4_ci"), time_it=False) for s in SEEDS]
    assert pool(runs, "B4_ci")["false_tracks_per_cycle_excess_vs_B0"] <= 0.01


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="KF-8: the evidence ledger trusts source labels; evidence re-labelled by another source is double counted by B3 (CI/B4 tolerates it).")
def test_KF8_relabelled_echo_is_not_double_counted_by_information_fusion():
    one = CooperativeFuser("B3_info").step(1.0, [loc(1), est("k", 1, seq=1)]).tracks[0].P
    two = CooperativeFuser("B3_info").step(1.0, [loc(1), est("k", 1, seq=1), est("rsu", 9, seq=1)]).tracks[0].P      # same data under another label
    assert two == one
