"""Purpose: define the minimal read-only observer contract for the MCOI runtime.
Governance scope: execution-slice observer typing only.
Dependencies: canonical evidence contracts and runtime-core invariant helpers.
Invariants: observers return typed evidence or explicit failures without execution, policy, or state mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Generic, Mapping, Protocol, TypeVar

from mcoi_runtime.contracts.evidence import EvidenceRecord
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, freeze_mapping


RequestT = TypeVar("RequestT")


class ObservationStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class ObservationFailure:
    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code.strip():
            raise RuntimeCoreInvariantError("code must be a non-empty string")
        if not isinstance(self.message, str) or not self.message.strip():
            raise RuntimeCoreInvariantError("message must be a non-empty string")
        object.__setattr__(self, "details", freeze_mapping(dict(self.details)))


@dataclass(frozen=True, slots=True)
class ObservationResult:
    status: ObservationStatus
    evidence: tuple[EvidenceRecord, ...] = ()
    failures: tuple[ObservationFailure, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.status, ObservationStatus):
            raise RuntimeCoreInvariantError("status must be an ObservationStatus value")
        if self.status is ObservationStatus.SUCCEEDED:
            if not self.evidence or self.failures:
                raise RuntimeCoreInvariantError("successful observations require evidence and no failures")
        elif not self.failures:
            raise RuntimeCoreInvariantError("failed or unsupported observations require explicit failures")


class ObserverAdapter(Protocol, Generic[RequestT]):
    def observe(self, request: RequestT) -> ObservationResult: ...
