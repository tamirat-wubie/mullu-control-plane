"""Purpose: canonical fault injection and adversarial operations contracts.
Governance scope: fault specifications, injection records, observations,
    recovery assessments, adversarial sessions, and outcomes.
Dependencies: shared contract base helpers.
Invariants:
  - Every fault has explicit type, target, severity, and disposition.
  - Injection records are immutable audit trail entries.
  - Recovery assessments explicitly state whether the system recovered.
  - Adversarial sessions aggregate multiple fault injections.
  - All fields validated at construction time.
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
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FaultType(StrEnum):
    """What kind of fault is being injected."""

    TIMEOUT = "timeout"
    FAILURE = "failure"
    CORRUPTION = "corruption"
    DELAY = "delay"
    OVERLOAD = "overload"
    UNAVAILABLE = "unavailable"
    MISMATCH = "mismatch"
    DUPLICATE = "duplicate"
    TRUNCATION = "truncation"
    POLICY_BLOCK = "policy_block"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"


class FaultTargetKind(StrEnum):
    """Which subsystem the fault targets."""

    PROVIDER = "provider"
    COMMUNICATION = "communication"
    ARTIFACT_INGESTION = "artifact_ingestion"
    MEMORY_MESH = "memory_mesh"
    EVENT_SPINE = "event_spine"
    OBLIGATION_RUNTIME = "obligation_runtime"
    CHECKPOINT = "checkpoint"
    SUPERVISOR = "supervisor"
    GOVERNANCE = "governance"
    REACTION = "reaction"
    DOMAIN_PACK = "domain_pack"
    CONTACT_IDENTITY = "contact_identity"


class FaultSeverity(StrEnum):
    """How severe the injected fault is."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FaultDisposition(StrEnum):
    """Outcome disposition of a fault injection."""

    INJECTED = "injected"
    DETECTED = "detected"
    RECOVERED = "recovered"
    ESCALATED = "escalated"
    DEGRADED = "degraded"
    FAILED = "failed"
    SKIPPED = "skipped"


class InjectionMode(StrEnum):
    """How the fault is applied."""

    SINGLE = "single"
    REPEATED = "repeated"
    WINDOWED = "windowed"
    CAMPAIGN = "campaign"


# ---------------------------------------------------------------------------
# FaultSpec
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FaultSpec(ContractRecord):
    """Specification of a single fault to inject."""

    spec_id: str = ""
    fault_type: FaultType = FaultType.FAILURE
    target_kind: FaultTargetKind = FaultTargetKind.PROVIDER
    target_ref_id: str = ""
    severity: FaultSeverity = FaultSeverity.MEDIUM
    injection_mode: InjectionMode = InjectionMode.SINGLE
    repeat_count: int = 1
    description: str = ""
    tags: tuple[str, ...] = ()
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.spec_id, "spec_id")
        if not isinstance(self.fault_type, FaultType):
            raise ValueError("fault_type must be a FaultType value")
        if not isinstance(self.target_kind, FaultTargetKind):
            raise ValueError("target_kind must be a FaultTargetKind value")
        if not isinstance(self.severity, FaultSeverity):
            raise ValueError("severity must be a FaultSeverity value")
        if not isinstance(self.injection_mode, InjectionMode):
            raise ValueError("injection_mode must be an InjectionMode value")
        require_non_negative_int(self.repeat_count, "repeat_count")
        if self.repeat_count == 0:
            raise ValueError("repeat_count must be positive")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "tags", tuple(self.tags))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# FaultWindow
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FaultWindow(ContractRecord):
    """Defines a time/tick window during which faults are active."""

    window_id: str = ""
    spec_id: str = ""
    start_tick: int = 0
    end_tick: int = 0
    active: bool = True
    created_at: str = ""

    def __post_init__(self) -> None:
        require_non_empty_text(self.window_id, "window_id")
        require_non_empty_text(self.spec_id, "spec_id")
        require_non_negative_int(self.start_tick, "start_tick")
        require_non_negative_int(self.end_tick, "end_tick")
        if self.end_tick < self.start_tick:
            raise ValueError("end_tick must be >= start_tick")
        require_datetime_text(self.created_at, "created_at")


# ---------------------------------------------------------------------------
# FaultInjectionRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FaultInjectionRecord(ContractRecord):
    """Audit trail entry for a single fault injection event."""

    record_id: str = ""
    spec_id: str = ""
    fault_type: FaultType = FaultType.FAILURE
    target_kind: FaultTargetKind = FaultTargetKind.PROVIDER
    target_ref_id: str = ""
    severity: FaultSeverity = FaultSeverity.MEDIUM
    disposition: FaultDisposition = FaultDisposition.INJECTED
    tick_number: int = 0
    description: str = ""
    injected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.record_id, "record_id")
        require_non_empty_text(self.spec_id, "spec_id")
        require_non_negative_int(self.tick_number, "tick_number")
        require_datetime_text(self.injected_at, "injected_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# FaultObservation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FaultObservation(ContractRecord):
    """Observation recorded during or after a fault injection."""

    observation_id: str = ""
    record_id: str = ""
    observed_behavior: str = ""
    expected_behavior: str = ""
    matches_expected: bool = False
    observed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.observation_id, "observation_id")
        require_non_empty_text(self.record_id, "record_id")
        require_non_empty_text(self.observed_behavior, "observed_behavior")
        require_datetime_text(self.observed_at, "observed_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# FaultRecoveryAssessment
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FaultRecoveryAssessment(ContractRecord):
    """Assessment of whether the system recovered from a fault."""

    assessment_id: str = ""
    record_id: str = ""
    recovered: bool = False
    recovery_method: str = ""
    degraded: bool = False
    degraded_reason: str = ""
    state_consistent: bool = True
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.assessment_id, "assessment_id")
        require_non_empty_text(self.record_id, "record_id")
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# AdversarialSession
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AdversarialSession(ContractRecord):
    """A campaign session that groups multiple fault injections."""

    session_id: str = ""
    name: str = ""
    fault_spec_ids: tuple[str, ...] = ()
    target_kinds: tuple[str, ...] = ()
    total_injections: int = 0
    total_observations: int = 0
    total_recoveries: int = 0
    started_at: str = ""
    completed_at: str = ""
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.session_id, "session_id")
        require_non_empty_text(self.name, "name")
        require_non_negative_int(self.total_injections, "total_injections")
        require_non_negative_int(self.total_observations, "total_observations")
        require_non_negative_int(self.total_recoveries, "total_recoveries")
        require_datetime_text(self.started_at, "started_at")
        if self.completed_at:
            require_datetime_text(self.completed_at, "completed_at")
        object.__setattr__(self, "fault_spec_ids", tuple(self.fault_spec_ids))
        object.__setattr__(self, "target_kinds", tuple(self.target_kinds))
        object.__setattr__(self, "tags", tuple(self.tags))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# AdversarialOutcome
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AdversarialOutcome(ContractRecord):
    """Final outcome of an adversarial session / campaign."""

    outcome_id: str = ""
    session_id: str = ""
    passed: bool = False
    total_faults: int = 0
    faults_detected: int = 0
    faults_recovered: int = 0
    faults_degraded: int = 0
    faults_failed: int = 0
    state_consistent: bool = True
    score: float = 0.0
    summary: str = ""
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.outcome_id, "outcome_id")
        require_non_empty_text(self.session_id, "session_id")
        require_non_negative_int(self.total_faults, "total_faults")
        require_non_negative_int(self.faults_detected, "faults_detected")
        require_non_negative_int(self.faults_recovered, "faults_recovered")
        require_non_negative_int(self.faults_degraded, "faults_degraded")
        require_non_negative_int(self.faults_failed, "faults_failed")
        require_unit_float(self.score, "score")
        require_datetime_text(self.completed_at, "completed_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
