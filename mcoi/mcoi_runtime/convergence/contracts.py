"""Typed contracts for the CDG-RCCM recursive convergence runtime.

Purpose: define deterministic, immutable records for component contracts,
dependency requests, continuation frames, certificates, outcomes, and audit events.
Governance scope: pure data contracts only; no dispatch, connector, filesystem,
or external-effect authority is granted by this module.
Invariants:
  - All records are immutable.
  - Identifiers and externally visible strings are non-empty.
  - Hashes are deterministic over canonical JSON.
  - A result certificate is context-bound by epoch, rules, inputs, assumptions,
    and dependency-certificate lineage.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import IntEnum, StrEnum
from hashlib import sha256
import json
import math
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias


CDG_RCCM_PROTOCOL_VERSION = "cdg-rccm.v1"


class SettlementLevel(IntEnum):
    """Epistemic settlement level for one exposed component projection."""

    PROVISIONAL = 0
    LOCALLY_STABLE = 1
    BOUNDARY_RECONCILED = 2
    CLOSURE_CERTIFIED = 3
    WORLD_VERIFIED = 4


class DependencyGate(StrEnum):
    """How a dependency request gates its consumer continuation."""

    HARD = "hard"
    PROVISIONAL = "provisional"
    ADVISORY = "advisory"
    ALTERNATIVE = "alternative"
    QUORUM = "quorum"
    STREAMING = "streaming"
    TEMPORAL = "temporal"


class ConsistencyMode(StrEnum):
    """Consistency relation required between a request and a certificate."""

    SAME_EPOCH = "same_epoch"
    MONOTONIC = "monotonic"
    STREAM = "stream"
    EXTERNAL_FRESH = "external_fresh"


class DependencyRelation(StrEnum):
    """Typed edge in the dependency and reconciliation mesh."""

    REQUIRES = "requires"
    CONSTRAINS = "constrains"
    OBSERVES = "observes"
    RECONCILES_WITH = "reconciles_with"
    SHARES = "shares"
    ALTERNATIVE_TO = "alternative_to"
    PRECEDES = "precedes"
    EVIDENCES = "evidences"
    TEMPORAL_PREVIOUS = "temporal_previous"
    SUPERSEDES = "supersedes"
    RESOURCE_WAIT = "resource_wait"
    AUTHORITY_WAIT = "authority_wait"


class CycleClass(StrEnum):
    """Diagnosis assigned to one cyclic dependency region."""

    STRUCTURAL_CONTAINMENT = "structural_containment"
    SEMANTIC_FEEDBACK = "semantic_feedback"
    TEMPORAL_FEEDBACK = "temporal_feedback"
    RESOURCE_DEADLOCK = "resource_deadlock"
    AUTHORITY_DEADLOCK = "authority_deadlock"
    ALTERNATIVE_SELECTION = "alternative_selection"
    HIDDEN_SELF_DEPENDENCY = "hidden_self_dependency"


class ConvergenceMode(StrEnum):
    """Declared convergence or exhaustion strategy."""

    FINITE_MONOTONE = "finite_monotone"
    WELL_FOUNDED_DESCENT = "well_founded_descent"
    CONTRACTIVE = "contractive"
    BOUNDED_SEARCH = "bounded_search"
    STREAMING = "streaming"
    EXTERNAL_ADJUDICATION = "external_adjudication"


class EvidenceScope(StrEnum):
    """Maximum claim scope supported by a candidate or certificate."""

    MODEL_ONLY = "model_only"
    SIMULATED = "simulated"
    LAB_OBSERVED = "lab_observed"
    FIELD_OBSERVED = "field_observed"
    PHYSICALLY_VERIFIED = "physically_verified"


class FrameStatus(StrEnum):
    """Lifecycle state of an independently schedulable continuation frame."""

    READY = "ready"
    RUNNING = "running"
    SUSPENDED = "suspended"
    QUIESCENT = "quiescent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutcomeCode(StrEnum):
    """Terminal judgment taxonomy for root or component work."""

    CERTIFIED = "certified"
    UNSAT = "unsat"
    UNKNOWN = "unknown"
    BLOCKED = "blocked"
    STALE = "stale"
    FAULT = "fault"
    CANCELLED = "cancelled"
    DEGRADED = "degraded"
    RECOVERY_REQUIRED = "recovery_required"


class InvalidationReason(StrEnum):
    """Causal reason a result or frame became stale."""

    PROJECTION_CHANGED = "projection_changed"
    DEPENDENCY_STALE = "dependency_stale"
    EPOCH_CHANGED = "epoch_changed"
    RULE_CHANGED = "rule_changed"
    INPUT_CHANGED = "input_changed"
    ASSUMPTION_INVALID = "assumption_invalid"


def _require_text(value: object, field_name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_text_tuple(values: object, field_name: str) -> tuple[str, ...]:
    if type(values) not in (tuple, list):
        raise ValueError(f"{field_name} must be a tuple or list")
    result = tuple(_require_text(value, f"{field_name}[{index}]") for index, value in enumerate(values))
    if len(result) != len(set(result)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return result


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))})
    if type(value) in (list, tuple):
        return tuple(_freeze(item) for item in value)
    if type(value) is set:
        return tuple(sorted((_freeze(item) for item in value), key=repr))
    if type(value) is float and not math.isfinite(value):
        raise ValueError("floating-point contract values must be finite")
    return value


def _json_ready(value: Any) -> Any:
    if is_dataclass(value):
        return {field_info.name: _json_ready(getattr(value, field_info.name)) for field_info in fields(value)}
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, IntEnum):
        return int(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if type(value) in (tuple, list):
        return [_json_ready(item) for item in value]
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("canonical JSON does not admit non-finite floats")
        return value
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Return canonical JSON used for stable hashes and audit digests."""

    return json.dumps(
        _json_ready(value),
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def stable_hash(prefix: str, value: Any) -> str:
    """Return a namespaced SHA-256 identifier for a canonical value."""

    prefix_text = _require_text(prefix, "prefix")
    digest = sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix_text}:{digest}"


@dataclass(frozen=True, slots=True)
class ConvergencePolicy:
    """Bounded convergence contract for a component or feedback region."""

    mode: ConvergenceMode = ConvergenceMode.BOUNDED_SEARCH
    maximum_iterations: int = 64
    tolerance: float = 0.0
    stable_iterations: int = 1
    oscillation_detection: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.mode, ConvergenceMode):
            raise ValueError("mode must be a ConvergenceMode")
        if type(self.maximum_iterations) is not int or self.maximum_iterations < 1:
            raise ValueError("maximum_iterations must be a positive integer")
        if type(self.tolerance) not in (int, float) or not math.isfinite(float(self.tolerance)) or self.tolerance < 0:
            raise ValueError("tolerance must be a finite non-negative number")
        if type(self.stable_iterations) is not int or self.stable_iterations < 1:
            raise ValueError("stable_iterations must be a positive integer")
        if type(self.oscillation_detection) is not bool:
            raise ValueError("oscillation_detection must be a bool")


@dataclass(frozen=True, slots=True)
class ComponentContract:
    """Static governed contract for one convergent component."""

    component_id: str
    purpose: str
    schema_version: str
    rule_version: str
    output_projections: tuple[str, ...]
    input_projections: tuple[str, ...] = ()
    immutable_invariants: tuple[str, ...] = ()
    local_invariants: tuple[str, ...] = ()
    boundary_contracts: tuple[str, ...] = ()
    convergence_policy: ConvergencePolicy = field(default_factory=ConvergencePolicy)
    maximum_depth: int = 64
    maximum_frames: int = 1024
    evidence_scope: EvidenceScope = EvidenceScope.MODEL_ONLY
    metadata: Mapping[str, Any] = field(default_factory=dict)
    protocol_version: str = CDG_RCCM_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "component_id", _require_text(self.component_id, "component_id"))
        object.__setattr__(self, "purpose", _require_text(self.purpose, "purpose"))
        object.__setattr__(self, "schema_version", _require_text(self.schema_version, "schema_version"))
        object.__setattr__(self, "rule_version", _require_text(self.rule_version, "rule_version"))
        object.__setattr__(self, "protocol_version", _require_text(self.protocol_version, "protocol_version"))
        if self.protocol_version != CDG_RCCM_PROTOCOL_VERSION:
            raise ValueError("protocol_version must match the runtime CDG-RCCM protocol")
        object.__setattr__(self, "output_projections", _require_text_tuple(self.output_projections, "output_projections"))
        if not self.output_projections:
            raise ValueError("output_projections must not be empty")
        object.__setattr__(self, "input_projections", _require_text_tuple(self.input_projections, "input_projections"))
        object.__setattr__(self, "immutable_invariants", _require_text_tuple(self.immutable_invariants, "immutable_invariants"))
        object.__setattr__(self, "local_invariants", _require_text_tuple(self.local_invariants, "local_invariants"))
        object.__setattr__(self, "boundary_contracts", _require_text_tuple(self.boundary_contracts, "boundary_contracts"))
        if not isinstance(self.convergence_policy, ConvergencePolicy):
            raise ValueError("convergence_policy must be a ConvergencePolicy")
        if type(self.maximum_depth) is not int or self.maximum_depth < 0:
            raise ValueError("maximum_depth must be a non-negative integer")
        if type(self.maximum_frames) is not int or self.maximum_frames < 1:
            raise ValueError("maximum_frames must be a positive integer")
        if not isinstance(self.evidence_scope, EvidenceScope):
            raise ValueError("evidence_scope must be an EvidenceScope")
        object.__setattr__(self, "metadata", _freeze(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ComponentProjectionRequest:
    """Exact projection and settlement requirement issued by a consumer frame."""

    request_id: str
    consumer_component_id: str
    provider_component_id: str
    projection_name: str
    minimum_level: SettlementLevel
    gate: DependencyGate
    epoch_id: str
    relation: DependencyRelation = DependencyRelation.REQUIRES
    consistency: ConsistencyMode = ConsistencyMode.SAME_EPOCH
    assumptions: tuple[str, ...] = ()
    maximum_age_seconds: float | None = None
    fallback_provider_ids: tuple[str, ...] = ()
    quorum: int = 1

    def __post_init__(self) -> None:
        for field_name in ("request_id", "consumer_component_id", "provider_component_id", "projection_name", "epoch_id"):
            object.__setattr__(self, field_name, _require_text(getattr(self, field_name), field_name))
        if not isinstance(self.minimum_level, SettlementLevel):
            raise ValueError("minimum_level must be a SettlementLevel")
        if not isinstance(self.gate, DependencyGate):
            raise ValueError("gate must be a DependencyGate")
        if not isinstance(self.relation, DependencyRelation):
            raise ValueError("relation must be a DependencyRelation")
        if not isinstance(self.consistency, ConsistencyMode):
            raise ValueError("consistency must be a ConsistencyMode")
        object.__setattr__(self, "assumptions", _require_text_tuple(self.assumptions, "assumptions"))
        object.__setattr__(self, "fallback_provider_ids", _require_text_tuple(self.fallback_provider_ids, "fallback_provider_ids"))
        if self.maximum_age_seconds is not None:
            if type(self.maximum_age_seconds) not in (int, float) or not math.isfinite(float(self.maximum_age_seconds)) or self.maximum_age_seconds < 0:
                raise ValueError("maximum_age_seconds must be a finite non-negative number")
        if type(self.quorum) is not int or self.quorum < 1:
            raise ValueError("quorum must be a positive integer")
        if self.gate is not DependencyGate.QUORUM and self.quorum != 1:
            raise ValueError("quorum may exceed one only for QUORUM dependencies")


@dataclass(frozen=True, slots=True)
class ContinuationFrame:
    """Independently schedulable work frame with a causal resume point."""

    frame_id: str
    component_id: str
    epoch_id: str
    root_component_id: str
    phase: str
    resume_token: str
    partial_state: Mapping[str, Any] = field(default_factory=dict)
    target_projections: tuple[str, ...] = ("result",)
    pending_request_ids: tuple[str, ...] = ()
    dependency_certificate_ids: tuple[str, ...] = ()
    read_set: tuple[str, ...] = ()
    generation: int = 0
    depth: int = 0
    priority: int = 0
    status: FrameStatus = FrameStatus.READY
    parent_frame_id: str = ""

    def __post_init__(self) -> None:
        for field_name in ("frame_id", "component_id", "epoch_id", "root_component_id", "phase", "resume_token"):
            object.__setattr__(self, field_name, _require_text(getattr(self, field_name), field_name))
        if self.parent_frame_id:
            object.__setattr__(self, "parent_frame_id", _require_text(self.parent_frame_id, "parent_frame_id"))
        object.__setattr__(self, "partial_state", _freeze(dict(self.partial_state)))
        object.__setattr__(self, "target_projections", _require_text_tuple(self.target_projections, "target_projections"))
        object.__setattr__(self, "pending_request_ids", _require_text_tuple(self.pending_request_ids, "pending_request_ids"))
        object.__setattr__(self, "dependency_certificate_ids", _require_text_tuple(self.dependency_certificate_ids, "dependency_certificate_ids"))
        object.__setattr__(self, "read_set", _require_text_tuple(self.read_set, "read_set"))
        if type(self.generation) is not int or self.generation < 0:
            raise ValueError("generation must be a non-negative integer")
        if type(self.depth) is not int or self.depth < 0:
            raise ValueError("depth must be a non-negative integer")
        if type(self.priority) is not int:
            raise ValueError("priority must be an integer")
        if not isinstance(self.status, FrameStatus):
            raise ValueError("status must be a FrameStatus")


@dataclass(frozen=True, slots=True)
class ProjectionCertificate:
    """Versioned, assumption-bound certificate for one component projection."""

    certificate_id: str
    component_id: str
    projection_name: str
    level: SettlementLevel
    epoch_id: str
    state_hash: str
    rule_hash: str
    input_hash: str
    dependency_certificate_ids: tuple[str, ...]
    assumptions: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    evidence_scope: EvidenceScope
    confidence: float
    value: Any
    audit_digest: str
    valid: bool = True

    def __post_init__(self) -> None:
        for field_name in (
            "certificate_id",
            "component_id",
            "projection_name",
            "epoch_id",
            "state_hash",
            "rule_hash",
            "input_hash",
            "audit_digest",
        ):
            object.__setattr__(self, field_name, _require_text(getattr(self, field_name), field_name))
        if not isinstance(self.level, SettlementLevel):
            raise ValueError("level must be a SettlementLevel")
        object.__setattr__(
            self,
            "dependency_certificate_ids",
            _require_text_tuple(self.dependency_certificate_ids, "dependency_certificate_ids"),
        )
        object.__setattr__(self, "assumptions", _require_text_tuple(self.assumptions, "assumptions"))
        object.__setattr__(self, "evidence_refs", _require_text_tuple(self.evidence_refs, "evidence_refs"))
        if not isinstance(self.evidence_scope, EvidenceScope):
            raise ValueError("evidence_scope must be an EvidenceScope")
        if type(self.confidence) not in (int, float) or not math.isfinite(float(self.confidence)):
            raise ValueError("confidence must be a finite number")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "value", _freeze(self.value))
        if type(self.valid) is not bool:
            raise ValueError("valid must be a bool")


@dataclass(frozen=True, slots=True)
class ValidationJudgment:
    """Independent local or boundary validation judgment."""

    passed: bool
    reasons: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.passed) is not bool:
            raise ValueError("passed must be a bool")
        object.__setattr__(self, "reasons", _require_text_tuple(self.reasons, "reasons"))
        object.__setattr__(self, "evidence_refs", _require_text_tuple(self.evidence_refs, "evidence_refs"))
        if not self.passed and not self.reasons:
            raise ValueError("failed validation must provide a reason")


@dataclass(frozen=True, slots=True)
class Need:
    """Suspend the current frame until exact dependency requests are satisfied."""

    requests: tuple[ComponentProjectionRequest, ...]
    continuation: ContinuationFrame
    spawned_frames: tuple[ContinuationFrame, ...] = ()

    def __post_init__(self) -> None:
        if not self.requests:
            raise ValueError("Need.requests must not be empty")
        if any(not isinstance(request, ComponentProjectionRequest) for request in self.requests):
            raise ValueError("Need.requests must contain ComponentProjectionRequest values")
        if not isinstance(self.continuation, ContinuationFrame):
            raise ValueError("Need.continuation must be a ContinuationFrame")
        if any(not isinstance(frame, ContinuationFrame) for frame in self.spawned_frames):
            raise ValueError("Need.spawned_frames must contain ContinuationFrame values")


@dataclass(frozen=True, slots=True)
class Progress:
    """Validated component state progress plus optional independent frames."""

    continuation: ContinuationFrame
    constructive_delta: Mapping[str, Any] = field(default_factory=dict)
    fracture_delta: Mapping[str, Any] = field(default_factory=dict)
    changed_projections: tuple[str, ...] = ()
    spawned_frames: tuple[ContinuationFrame, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.continuation, ContinuationFrame):
            raise ValueError("Progress.continuation must be a ContinuationFrame")
        object.__setattr__(self, "constructive_delta", _freeze(dict(self.constructive_delta)))
        object.__setattr__(self, "fracture_delta", _freeze(dict(self.fracture_delta)))
        object.__setattr__(self, "changed_projections", _require_text_tuple(self.changed_projections, "changed_projections"))
        if any(not isinstance(frame, ContinuationFrame) for frame in self.spawned_frames):
            raise ValueError("Progress.spawned_frames must contain ContinuationFrame values")


@dataclass(frozen=True, slots=True)
class Candidate:
    """Locally converged candidate submitted for independent validation."""

    projections: Mapping[str, Any]
    state: Mapping[str, Any] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    confidence: float = 1.0
    evidence_scope: EvidenceScope = EvidenceScope.MODEL_ONLY

    def __post_init__(self) -> None:
        if not self.projections:
            raise ValueError("Candidate.projections must not be empty")
        for projection_name in self.projections:
            _require_text(projection_name, "projection_name")
        object.__setattr__(self, "projections", _freeze(dict(self.projections)))
        object.__setattr__(self, "state", _freeze(dict(self.state)))
        object.__setattr__(self, "evidence_refs", _require_text_tuple(self.evidence_refs, "evidence_refs"))
        if type(self.confidence) not in (int, float) or not math.isfinite(float(self.confidence)):
            raise ValueError("confidence must be a finite number")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not isinstance(self.evidence_scope, EvidenceScope):
            raise ValueError("evidence_scope must be an EvidenceScope")


@dataclass(frozen=True, slots=True)
class Conflict:
    """Hard constraint conflict that cannot be hidden as generic failure."""

    constraints: tuple[str, ...]
    explanation: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "constraints", _require_text_tuple(self.constraints, "constraints"))
        if not self.constraints:
            raise ValueError("constraints must not be empty")
        object.__setattr__(self, "explanation", _require_text(self.explanation, "explanation"))


@dataclass(frozen=True, slots=True)
class Unknown:
    """Insufficient evidence or exhausted bounded search."""

    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _require_text(self.reason, "reason"))


@dataclass(frozen=True, slots=True)
class Fault:
    """Implementation or execution fault."""

    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _require_text(self.reason, "reason"))


@dataclass(frozen=True, slots=True)
class Cancelled:
    """Explicit cancellation outcome."""

    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason", _require_text(self.reason, "reason"))


StepOutcome: TypeAlias = Need | Progress | Candidate | Conflict | Unknown | Fault | Cancelled


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Append-only causal event emitted for every meaningful transition."""

    event_id: str
    epoch_id: str
    sequence: int
    component_id: str
    frame_id: str
    event_type: str
    trigger: str
    previous_status: str
    new_status: str
    constructive_delta: Mapping[str, Any] = field(default_factory=dict)
    fracture_delta: Mapping[str, Any] = field(default_factory=dict)
    dependency_certificate_ids: tuple[str, ...] = ()
    judgment: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "event_id",
            "epoch_id",
            "component_id",
            "frame_id",
            "event_type",
            "trigger",
            "previous_status",
            "new_status",
        ):
            object.__setattr__(self, field_name, _require_text(getattr(self, field_name), field_name))
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        object.__setattr__(self, "constructive_delta", _freeze(dict(self.constructive_delta)))
        object.__setattr__(self, "fracture_delta", _freeze(dict(self.fracture_delta)))
        object.__setattr__(
            self,
            "dependency_certificate_ids",
            _require_text_tuple(self.dependency_certificate_ids, "dependency_certificate_ids"),
        )
        if self.judgment:
            object.__setattr__(self, "judgment", _require_text(self.judgment, "judgment"))


@dataclass(frozen=True, slots=True)
class ExecutionJudgment:
    """Terminal root judgment produced by the convergence kernel."""

    root_component_id: str
    epoch_id: str
    outcome: OutcomeCode
    certificate_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    executed_steps: int
    audit_digest: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_component_id", _require_text(self.root_component_id, "root_component_id"))
        object.__setattr__(self, "epoch_id", _require_text(self.epoch_id, "epoch_id"))
        if not isinstance(self.outcome, OutcomeCode):
            raise ValueError("outcome must be an OutcomeCode")
        object.__setattr__(self, "certificate_ids", _require_text_tuple(self.certificate_ids, "certificate_ids"))
        object.__setattr__(self, "reasons", _require_text_tuple(self.reasons, "reasons"))
        if type(self.executed_steps) is not int or self.executed_steps < 0:
            raise ValueError("executed_steps must be a non-negative integer")
        object.__setattr__(self, "audit_digest", _require_text(self.audit_digest, "audit_digest"))


@dataclass(frozen=True, slots=True)
class InvalidationRecord:
    """Traceable stale-result propagation record."""

    invalidation_id: str
    epoch_id: str
    provider_component_id: str
    changed_projection_paths: tuple[str, ...]
    stale_certificate_ids: tuple[str, ...]
    reactivated_frame_ids: tuple[str, ...]
    reason: InvalidationReason

    def __post_init__(self) -> None:
        for field_name in ("invalidation_id", "epoch_id", "provider_component_id"):
            object.__setattr__(self, field_name, _require_text(getattr(self, field_name), field_name))
        object.__setattr__(
            self,
            "changed_projection_paths",
            _require_text_tuple(self.changed_projection_paths, "changed_projection_paths"),
        )
        object.__setattr__(
            self,
            "stale_certificate_ids",
            _require_text_tuple(self.stale_certificate_ids, "stale_certificate_ids"),
        )
        object.__setattr__(
            self,
            "reactivated_frame_ids",
            _require_text_tuple(self.reactivated_frame_ids, "reactivated_frame_ids"),
        )
        if not isinstance(self.reason, InvalidationReason):
            raise ValueError("reason must be an InvalidationReason")
