"""WP5 KNOWN FAILURES (xfail strict; desired behaviour stated). Tuning seeds only. Not claims about the physical world."""
import pytest
from closedloop import conditions as K
from closedloop.metrics import per_run
from closedloop.runner import ORIGIN, _forged, run
from comm.admission import Admission, AdmissionConfig, SourceRegistry
from comm.clock import NodeClock
from comm.trackmsg import serialize
from tests.comm.helpers import msg

pytestmark = [pytest.mark.cls, pytest.mark.known_failure]


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="KF-9: the backend snaps acceleration to 0 when v reaches 0 (standstill jerk discontinuity). Measured and counted, NEVER claimed compliant.")
def test_KF9_hard_stops_to_standstill_do_not_violate_the_jerk_limit():
    r = run("G_E3naive", K.SEEDS_TUNING[0], time_it=False)
    assert r["standstill_events"] == 0


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="KF-10: sequence poisoning - a forged message with a huge sequence number from an allowlisted source makes the receiver reject the genuine stream as replay_old (denial of service). Needs authentication.")
def test_KF10_forged_high_sequence_does_not_lock_out_the_genuine_source():
    a = Admission(AdmissionConfig("ego", ORIGIN), SourceRegistry({"cctv_k1": "cctv"}, frozenset()), NodeClock("rx"))
    assert a.process(serialize(_forged("cctv_k1", 100001, 0.95, 55.0, 0.0)), 1.0, 1.005).admitted
    genuine = msg(source="cctv_k1", seq=7, t_meas=0.97)
    assert a.process(serialize(genuine), 1.0, 1.006).admitted


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="KF-11: an allowlisted forged ghost still causes comfort-level braking in the guarded stack (bounded, follower-aware, but a real intervention). Needs authentication.")
def test_KF11_allowlisted_forged_ghost_causes_no_intervention_in_the_guarded_stack():
    r = run("G_E3", K.SEEDS_TUNING[0], time_it=False)
    assert not per_run(r)["unnecessary"]
