"""Purpose: contracts for the sequential software-dev autonomy loop.
Governance scope: the bounded plan / patch-attempt / gate-evidence shapes
the loop produces. Terminal disposition is reused from terminal_closure.
Dependencies: shared contract base helpers; PatchApplicationResult,
TestResult, BuildResult from contracts.code; SoftwareQualityGate from
domain_adapters.software_dev.
Invariants:
  - WorkPlan.target_files MUST be non-empty and free of empty strings.
  - QualityGateResult is typed and self-describing — passed flag, summary,
    evidence_id are all required.
  - AttemptRecord captures patch_id and per-gate results; status reflects
    whether the attempt was applied, gates_passed, or rolled_back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
)
from .code import PatchApplicationResult


class AttemptStatus(StrEnum):
    """How a single self-debug attempt terminated."""

    PATCH_REJECTED = "patch_rejected"        # validation rejected the patch before apply
    APPLY_FAILED = "apply_failed"            # apply_patch returned non-APPLIED
    GATES_FAILED = "gates_failed"            # patch applied but at least one gate failed
    GATES_PASSED = "gates_passed"            # patch applied and all gates passed


@dataclass(frozen=True, slots=True)
class WorkPlan(ContractRecord):
    """A bounded plan a generator produces for a single SoftwareRequest.

    target_files is the set of relative paths the plan intends to touch.
    The orchestrator validates that this set lies within the request's
    affected_files (so the plan cannot escape the declared blast radius).
    """

    plan_id: str
    summary: str
    steps: tuple[str, ...]
    target_files: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "summary", require_non_empty_text(self.summary, "summary"))
        object.__setattr__(self, "steps", freeze_value(list(self.steps)))
        if not self.target_files:
            raise ValueError("target_files must be non-empty")
        for path in self.target_files:
            require_non_empty_text(path, "target_files element")
        object.__setattr__(self, "target_files", freeze_value(list(self.target_files)))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class QualityGateResult(ContractRecord):
    """Typed outcome of running one named quality gate."""

    gate: str            # SoftwareQualityGate.value (e.g. "unit_tests")
    passed: bool
    evidence_id: str
    summary: str
    exit_code: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "gate", require_non_empty_text(self.gate, "gate"))
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be a bool")
        object.__setattr__(self, "evidence_id", require_non_empty_text(self.evidence_id, "evidence_id"))
        object.__setattr__(self, "summary", require_non_empty_text(self.summary, "summary"))
        if not isinstance(self.exit_code, int) or isinstance(self.exit_code, bool):
            raise ValueError("exit_code must be int")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class AttemptRecord(ContractRecord):
    """Evidence from a single self-debug attempt."""

    attempt_index: int
    snapshot_id: str
    patch_id: str
    status: AttemptStatus
    patch_result: PatchApplicationResult | None
    gate_results: tuple[QualityGateResult, ...]
    rolled_back: bool
    notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.attempt_index, int) or self.attempt_index < 0:
            raise ValueError("attempt_index must be a non-negative int")
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "patch_id", require_non_empty_text(self.patch_id, "patch_id"))
        if not isinstance(self.status, AttemptStatus):
            raise ValueError("status must be an AttemptStatus value")
        if self.patch_result is not None and not isinstance(self.patch_result, PatchApplicationResult):
            raise ValueError("patch_result must be a PatchApplicationResult or None")
        object.__setattr__(self, "gate_results", freeze_value(list(self.gate_results)))
        if not isinstance(self.rolled_back, bool):
            raise ValueError("rolled_back must be a bool")


@dataclass(frozen=True, slots=True)
class AutonomyEvidence(ContractRecord):
    """Aggregate evidence the orchestrator returns alongside the certificate.

    Provides a structured trail: which UCJA layer (if any) blocked, the
    initial workspace snapshot, the plan, every attempt's record, the
    final review record id (if any), and any rollback evidence.
    """

    request_id: str
    ucja_job_id: str
    ucja_accepted: bool
    ucja_halted_at_layer: str | None
    ucja_reason: str
    initial_snapshot_id: str
    plan_id: str | None
    attempts: tuple[AttemptRecord, ...]
    review_record_id: str | None
    rollback_succeeded: bool | None
    rollback_evidence_id: str | None
    started_at: str
    completed_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "ucja_job_id", require_non_empty_text(self.ucja_job_id, "ucja_job_id"))
        if not isinstance(self.ucja_accepted, bool):
            raise ValueError("ucja_accepted must be a bool")
        if self.ucja_halted_at_layer is not None:
            require_non_empty_text(self.ucja_halted_at_layer, "ucja_halted_at_layer")
        object.__setattr__(self, "ucja_reason", str(self.ucja_reason))
        object.__setattr__(self, "initial_snapshot_id", require_non_empty_text(self.initial_snapshot_id, "initial_snapshot_id"))
        if self.plan_id is not None:
            require_non_empty_text(self.plan_id, "plan_id")
        object.__setattr__(self, "attempts", freeze_value(list(self.attempts)))
        if self.review_record_id is not None:
            require_non_empty_text(self.review_record_id, "review_record_id")
        if self.rollback_succeeded is not None and not isinstance(self.rollback_succeeded, bool):
            raise ValueError("rollback_succeeded must be a bool or None")
        if self.rollback_evidence_id is not None:
            require_non_empty_text(self.rollback_evidence_id, "rollback_evidence_id")
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "completed_at", require_datetime_text(self.completed_at, "completed_at"))
