"""Purpose: provide minimal read-only process observation for the MCOI runtime.
Governance scope: execution-slice process observation only.
Dependencies: Python standard library process metadata and observer-base typing.
Invariants: observation is read-only, fails closed for unsupported targets, and avoids platform-specific mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import sys

from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

from .observer_base import ObservationFailure, ObservationResult, ObservationStatus


@dataclass(frozen=True, slots=True)
class ProcessObservationRequest:
    process_id: int | None = None

    def __post_init__(self) -> None:
        if self.process_id is not None and self.process_id <= 0:
            raise RuntimeCoreInvariantError("process_id must be greater than zero when provided")


class ProcessObserver:
    def observe(self, request: ProcessObservationRequest) -> ObservationResult:
        current_pid = os.getpid()
        requested_pid = request.process_id if request.process_id is not None else current_pid

        if requested_pid != current_pid:
            return ObservationResult(
                status=ObservationStatus.UNSUPPORTED,
                failures=(
                    ObservationFailure(
                        code="unsupported_process_lookup",
                        message="only the current process can be observed in this slice",
                        details={"process_id": requested_pid},
                    ),
                ),
            )

        return ObservationResult(
            status=ObservationStatus.SUCCEEDED,
            evidence=(
                EvidenceRecord(
                    description="process.snapshot",
                    uri=f"process://{current_pid}",
                    details={
                        "process_id": current_pid,
                        "parent_process_id": os.getppid(),
                        "executable": sys.executable,
                        "platform": sys.platform,
                    },
                ),
            ),
        )
