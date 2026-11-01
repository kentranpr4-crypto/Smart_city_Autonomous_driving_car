"""KNOWN FAILURES of the WP3 communication layer (xfail strict, desired behaviour stated; each stays red-as-expected until genuinely fixed).
KF-3 / KF-4 need cryptographic authentication and a nonce/session design (E05/E06 UNKNOWN: ETSI TS 103 324 only references security specs).
KF-5 is a clock-synchronisation limit (B04 UNKNOWN). CRC-32 is an integrity check against accidental corruption, NOT authentication."""
import pytest
from comm.trackmsg import serialize, deserialize, to_dict, crc_of
from tests.comm.helpers import adm, msg, track, with_crc, mutated
from comm.clock import NodeClock
import json

pytestmark = [pytest.mark.com, pytest.mark.known_failure]


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="KF-3: an attacker who knows an allowlisted source_id can forge a message and recompute CRC-32; no cryptographic authentication exists (E05/E06 UNKNOWN).")
def test_KF3_forged_message_from_allowlisted_source_id_is_rejected():
    a = adm()
    genuine = msg(source="k", seq=0, t_meas=1.0)
    forged = msg(source="k", seq=1, t_meas=1.1, tracks=[track(x=999.0, y=999.0, t_upd=1.1)])                    # ghost obstacle / forged position
    assert a.process(serialize(genuine), 1.05, 1.055).admitted
    res = a.process(serialize(forged), 1.15, 1.155)
    assert not res.admitted                                                                                  # DESIRED; currently admitted (documented)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="KF-4: replay of a captured, never-delivered FRESH message is indistinguishable from the original (no nonce/session binding).")
def test_KF4_replay_of_captured_fresh_message_by_a_third_party_is_rejected():
    a = adm()
    m = msg(source="k", seq=5, t_meas=1.0)
    captured = serialize(m)                                                                                   # eavesdropped; the original is jammed and never arrives
    res = a.process(captured, 1.2, 1.205)
    assert not res.admitted                                                                                  # DESIRED: reject. Currently admitted (a fresh copy is legitimate by every check)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="KF-5: a clock offset inside clock_tolerance_s (50 ms) silently biases the receiver-estimated age; sync accuracy is UNKNOWN (B04).")
def test_KF5_estimated_age_equals_true_age_despite_in_tolerance_clock_offset():
    a = adm()
    off = 0.04                                                                                                # source clock runs 40 ms ahead, inside the tolerance
    sc = NodeClock("c-k", offset_s=off)
    t_true_meas = 1.0
    m = msg(source="k", seq=0, t_meas=sc.local(t_true_meas), t_sent=sc.local(t_true_meas + 0.01))
    res = a.process(serialize(m), 1.06, 1.065)
    true_age = 1.065 - t_true_meas
    assert res.admitted and res.age_proc_est == pytest.approx(true_age, abs=1e-6)                             # DESIRED; actual error = offset
