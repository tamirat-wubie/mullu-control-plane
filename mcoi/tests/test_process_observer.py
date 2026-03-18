"""Purpose: verify read-only process observation for the MCOI runtime.
Governance scope: execution-slice tests only.
Dependencies: os and the execution-slice process observer.
Invariants: process observation returns typed evidence for supported targets and fails closed for unsupported ones.
"""

from __future__ import annotations

import os

from mcoi_runtime.adapters.observer_base import ObservationStatus
from mcoi_runtime.adapters.process_observer import ProcessObservationRequest, ProcessObserver


def test_process_observer_returns_current_process_evidence_without_side_effects() -> None:
    observer = ProcessObserver()
    before_pid = os.getpid()

    result = observer.observe(ProcessObservationRequest())
    after_pid = os.getpid()

    assert result.status is ObservationStatus.SUCCEEDED
    assert result.evidence[0].details["process_id"] == before_pid
    assert result.evidence[0].uri == f"process://{before_pid}"
    assert after_pid == before_pid


def test_process_observer_fails_closed_for_non_current_process_lookup() -> None:
    observer = ProcessObserver()
    result = observer.observe(ProcessObservationRequest(process_id=os.getpid() + 1))

    assert result.status is ObservationStatus.UNSUPPORTED
    assert result.failures[0].code == "unsupported_process_lookup"
    assert "current process" in result.failures[0].message
    assert result.evidence == ()
