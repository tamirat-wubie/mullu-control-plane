"""Purpose: shared contracts for holistic governed loop read models.
Governance scope: loop manifests, loop state, step receipts, receipt lineage,
    closure reports, bounded read-model summaries, and read-only evidence
    bindings.
Dependencies: Python standard library dataclasses, enum, and shared contract
    serialization helpers.
Invariants:
  - Loop contracts describe existing governed loops without executing them.
  - Missing required evidence is represented as a blocker, never as closure.
  - Loop modes, statuses, and phases are typed and deterministic.
  - Read-model records are immutable and JSON-serializable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Sequence, TypeVar, cast

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
)


ContractT = TypeVar("ContractT")


class LoopMode(StrEnum):
    """Execution posture a governed loop may run under."""

    REAL = "real"
    DRY_RUN = "dry_run"
    SHADOW = "shadow"
    SIMULATION = "simulation"
    REPLAY = "replay"


class LoopStatus(StrEnum):
    """Read-model status for a governed loop."""

    OPEN = "open"
    BLOCKED = "blocked"
    VERIFIED = "verified"
    CLOSED = "closed"


class LoopPhase(StrEnum):
    """Canonical holistic loop phase."""

    OBSERVE = "observe"
    DECIDE = "decide"
    ACT = "act"
    VERIFY = "verify"
    RECORD_RECEIPT = "record_receipt"
    UPDATE_STATE = "update_state"
    LEARN = "learn"
    AUDIT = "audit"
    CLOSE = "close"


@dataclass(frozen=True, slots=True)
class LoopManifest(ContractRecord):
    """Static contract that describes one governed loop."""

    loop_id: str
    name: str
    purpose: str
    owner: str
    risk_class: str
    allowed_modes: tuple[LoopMode, ...]
    required_authority: tuple[str, ...]
    required_evidence: tuple[str, ...]
    closure_conditions: tuple[str, ...]
    rollback_policy: str
    learning_policy: str
    canonical_steps: tuple[LoopPhase, ...] = (
        LoopPhase.OBSERVE,
        LoopPhase.DECIDE,
        LoopPhase.ACT,
        LoopPhase.VERIFY,
        LoopPhase.RECORD_RECEIPT,
        LoopPhase.UPDATE_STATE,
        LoopPhase.LEARN,
        LoopPhase.AUDIT,
    )
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "loop_id",
            "name",
            "purpose",
            "owner",
            "risk_class",
            "rollback_policy",
            "learning_policy",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "allowed_modes",
            _freeze_enum_tuple(self.allowed_modes, "allowed_modes", LoopMode, "LoopMode"),
        )
        object.__setattr__(
            self,
            "required_authority",
            _freeze_text_tuple(self.required_authority, "required_authority"),
        )
        object.__setattr__(
            self,
            "required_evidence",
            _freeze_text_tuple(self.required_evidence, "required_evidence"),
        )
        object.__setattr__(
            self,
            "closure_conditions",
            _freeze_text_tuple(self.closure_conditions, "closure_conditions"),
        )
        object.__setattr__(
            self,
            "canonical_steps",
            _freeze_enum_tuple(self.canonical_steps, "canonical_steps", LoopPhase, "LoopPhase"),
        )
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LoopState(ContractRecord):
    """Read-only current state projection for one governed loop."""

    loop_id: str
    status: LoopStatus
    current_step: LoopPhase
    mode: LoopMode
    updated_at: str
    last_receipt: str = ""
    open_blockers: tuple[str, ...] = ()
    authority_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "loop_id", require_non_empty_text(self.loop_id, "loop_id"))
        if not isinstance(self.status, LoopStatus):
            raise ValueError("status must be a LoopStatus value")
        if not isinstance(self.current_step, LoopPhase):
            raise ValueError("current_step must be a LoopPhase value")
        if not isinstance(self.mode, LoopMode):
            raise ValueError("mode must be a LoopMode value")
        object.__setattr__(self, "updated_at", require_datetime_text(self.updated_at, "updated_at"))
        if self.last_receipt:
            object.__setattr__(
                self,
                "last_receipt",
                require_non_empty_text(self.last_receipt, "last_receipt"),
            )
        object.__setattr__(
            self,
            "open_blockers",
            _freeze_text_tuple(self.open_blockers, "open_blockers", allow_empty=True),
        )
        object.__setattr__(
            self,
            "authority_refs",
            _freeze_text_tuple(self.authority_refs, "authority_refs", allow_empty=True),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _freeze_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True),
        )
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LoopStepReceipt(ContractRecord):
    """Receipt for one observe/decide/act/verify loop step."""

    loop_id: str
    step: LoopPhase
    input_hash: str
    output_hash: str
    decision: str
    evidence_refs: tuple[str, ...]
    status: LoopStatus
    errors: tuple[str, ...]
    timestamp: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("loop_id", "input_hash", "output_hash", "decision"):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if not isinstance(self.step, LoopPhase):
            raise ValueError("step must be a LoopPhase value")
        if not isinstance(self.status, LoopStatus):
            raise ValueError("status must be a LoopStatus value")
        object.__setattr__(
            self,
            "evidence_refs",
            _freeze_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True),
        )
        object.__setattr__(
            self,
            "errors",
            _freeze_text_tuple(self.errors, "errors", allow_empty=True),
        )
        if self.status is LoopStatus.CLOSED:
            raise ValueError("step receipt cannot claim terminal closure")
        object.__setattr__(self, "timestamp", require_datetime_text(self.timestamp, "timestamp"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
        if self.metadata.get("read_only") is not True:
            raise ValueError("step receipt metadata read_only must be true")
        if self.metadata.get("terminal_closure") is not False:
            raise ValueError("step receipt metadata terminal_closure must be false")


@dataclass(frozen=True, slots=True)
class LoopClosureReport(ContractRecord):
    """Closure assessment for one governed loop."""

    loop_id: str
    closed: bool
    closure_reason: str
    evidence_complete: bool
    unresolved_gaps: tuple[str, ...]
    rollback_available: bool
    learning_candidates: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "loop_id", require_non_empty_text(self.loop_id, "loop_id"))
        if not isinstance(self.closed, bool):
            raise ValueError("closed must be a bool")
        object.__setattr__(
            self,
            "closure_reason",
            require_non_empty_text(self.closure_reason, "closure_reason"),
        )
        if not isinstance(self.evidence_complete, bool):
            raise ValueError("evidence_complete must be a bool")
        if not isinstance(self.rollback_available, bool):
            raise ValueError("rollback_available must be a bool")
        object.__setattr__(
            self,
            "unresolved_gaps",
            _freeze_text_tuple(self.unresolved_gaps, "unresolved_gaps", allow_empty=True),
        )
        object.__setattr__(
            self,
            "learning_candidates",
            _freeze_text_tuple(
                self.learning_candidates,
                "learning_candidates",
                allow_empty=True,
            ),
        )
        if self.closed and self.unresolved_gaps:
            raise ValueError("closed loop cannot carry unresolved gaps")
        if self.closed and not self.evidence_complete:
            raise ValueError("closed loop requires complete evidence")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LoopEvidenceBinding(ContractRecord):
    """Read-only reference map for one required loop evidence label."""

    evidence_ref: str
    purpose: str
    source_refs: tuple[str, ...]
    validator_refs: tuple[str, ...]
    proof_surface_refs: tuple[str, ...]
    read_only: bool = True
    terminal_closure: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "evidence_ref",
            require_non_empty_text(self.evidence_ref, "evidence_ref"),
        )
        object.__setattr__(self, "purpose", require_non_empty_text(self.purpose, "purpose"))
        object.__setattr__(
            self,
            "source_refs",
            _freeze_text_tuple(self.source_refs, "source_refs"),
        )
        object.__setattr__(
            self,
            "validator_refs",
            _freeze_text_tuple(self.validator_refs, "validator_refs"),
        )
        object.__setattr__(
            self,
            "proof_surface_refs",
            _freeze_text_tuple(self.proof_surface_refs, "proof_surface_refs"),
        )
        if self.read_only is not True:
            raise ValueError("evidence binding must be read-only")
        if self.terminal_closure is not False:
            raise ValueError("evidence binding cannot be terminal closure")


@dataclass(frozen=True, slots=True)
class LoopAuthorityBinding(ContractRecord):
    """Read-only reference map for one required loop authority label."""

    authority_ref: str
    purpose: str
    source_refs: tuple[str, ...]
    validator_refs: tuple[str, ...]
    proof_surface_refs: tuple[str, ...]
    read_only: bool = True
    terminal_closure: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "authority_ref",
            require_non_empty_text(self.authority_ref, "authority_ref"),
        )
        object.__setattr__(self, "purpose", require_non_empty_text(self.purpose, "purpose"))
        object.__setattr__(
            self,
            "source_refs",
            _freeze_text_tuple(self.source_refs, "source_refs"),
        )
        object.__setattr__(
            self,
            "validator_refs",
            _freeze_text_tuple(self.validator_refs, "validator_refs"),
        )
        object.__setattr__(
            self,
            "proof_surface_refs",
            _freeze_text_tuple(self.proof_surface_refs, "proof_surface_refs"),
        )
        if self.read_only is not True:
            raise ValueError("authority binding must be read-only")
        if self.terminal_closure is not False:
            raise ValueError("authority binding cannot be terminal closure")


@dataclass(frozen=True, slots=True)
class LoopRollbackBinding(ContractRecord):
    """Read-only reference map for one loop rollback policy."""

    rollback_ref: str
    purpose: str
    source_refs: tuple[str, ...]
    validator_refs: tuple[str, ...]
    proof_surface_refs: tuple[str, ...]
    read_only: bool = True
    terminal_closure: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "rollback_ref",
            require_non_empty_text(self.rollback_ref, "rollback_ref"),
        )
        object.__setattr__(self, "purpose", require_non_empty_text(self.purpose, "purpose"))
        object.__setattr__(
            self,
            "source_refs",
            _freeze_text_tuple(self.source_refs, "source_refs"),
        )
        object.__setattr__(
            self,
            "validator_refs",
            _freeze_text_tuple(self.validator_refs, "validator_refs"),
        )
        object.__setattr__(
            self,
            "proof_surface_refs",
            _freeze_text_tuple(self.proof_surface_refs, "proof_surface_refs"),
        )
        if self.read_only is not True:
            raise ValueError("rollback binding must be read-only")
        if self.terminal_closure is not False:
            raise ValueError("rollback binding cannot be terminal closure")


@dataclass(frozen=True, slots=True)
class LoopRiskBinding(ContractRecord):
    """Read-only reference map for one loop risk class."""

    risk_ref: str
    purpose: str
    hazard_refs: tuple[str, ...]
    mitigation_refs: tuple[str, ...]
    monitor_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    validator_refs: tuple[str, ...]
    proof_surface_refs: tuple[str, ...]
    read_only: bool = True
    terminal_closure: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "risk_ref",
            require_non_empty_text(self.risk_ref, "risk_ref"),
        )
        object.__setattr__(self, "purpose", require_non_empty_text(self.purpose, "purpose"))
        for field_name in (
            "hazard_refs",
            "mitigation_refs",
            "monitor_refs",
            "source_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name),
            )
        if self.read_only is not True:
            raise ValueError("risk binding must be read-only")
        if self.terminal_closure is not False:
            raise ValueError("risk binding cannot be terminal closure")


@dataclass(frozen=True, slots=True)
class LoopLearningBinding(ContractRecord):
    """Read-only reference map for one loop learning policy."""

    learning_ref: str
    purpose: str
    evidence_input_refs: tuple[str, ...]
    admission_refs: tuple[str, ...]
    retention_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    validator_refs: tuple[str, ...]
    proof_surface_refs: tuple[str, ...]
    read_only: bool = True
    terminal_closure: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "learning_ref",
            require_non_empty_text(self.learning_ref, "learning_ref"),
        )
        object.__setattr__(self, "purpose", require_non_empty_text(self.purpose, "purpose"))
        for field_name in (
            "evidence_input_refs",
            "admission_refs",
            "retention_refs",
            "source_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name),
            )
        if self.read_only is not True:
            raise ValueError("learning binding must be read-only")
        if self.terminal_closure is not False:
            raise ValueError("learning binding cannot be terminal closure")


@dataclass(frozen=True, slots=True)
class LoopModeBinding(ContractRecord):
    """Read-only reference map for loop execution mode boundaries."""

    projected_mode: LoopMode
    allowed_modes: tuple[LoopMode, ...]
    purpose: str
    separation_refs: tuple[str, ...]
    real_execution_guard_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    validator_refs: tuple[str, ...]
    proof_surface_refs: tuple[str, ...]
    read_only: bool = True
    mode_transition: bool = False
    terminal_closure: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.projected_mode, LoopMode):
            raise ValueError("projected_mode must be a LoopMode value")
        object.__setattr__(
            self,
            "allowed_modes",
            _freeze_enum_tuple(self.allowed_modes, "allowed_modes", LoopMode, "LoopMode"),
        )
        if self.projected_mode not in self.allowed_modes:
            raise ValueError("projected_mode must be included in allowed_modes")
        object.__setattr__(self, "purpose", require_non_empty_text(self.purpose, "purpose"))
        for field_name in (
            "separation_refs",
            "real_execution_guard_refs",
            "source_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name),
            )
        if self.read_only is not True:
            raise ValueError("mode binding must be read-only")
        if self.mode_transition is not False:
            raise ValueError("mode binding cannot authorize mode transition")
        if self.terminal_closure is not False:
            raise ValueError("mode binding cannot be terminal closure")


@dataclass(frozen=True, slots=True)
class LoopStatusBinding(ContractRecord):
    """Read-only reference map for projected loop status boundaries."""

    projected_status: LoopStatus
    status_reason: str
    blocker_refs: tuple[str, ...]
    verification_refs: tuple[str, ...]
    closure_gate_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    validator_refs: tuple[str, ...]
    proof_surface_refs: tuple[str, ...]
    read_only: bool = True
    status_transition: bool = False
    terminal_closure: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.projected_status, LoopStatus):
            raise ValueError("projected_status must be a LoopStatus value")
        object.__setattr__(
            self,
            "status_reason",
            require_non_empty_text(self.status_reason, "status_reason"),
        )
        object.__setattr__(
            self,
            "blocker_refs",
            _freeze_text_tuple(self.blocker_refs, "blocker_refs", allow_empty=True),
        )
        for field_name in (
            "verification_refs",
            "closure_gate_refs",
            "source_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name),
            )
        if self.read_only is not True:
            raise ValueError("status binding must be read-only")
        if self.status_transition is not False:
            raise ValueError("status binding cannot authorize status transition")
        if self.terminal_closure is not False:
            raise ValueError("status binding cannot be terminal closure")


@dataclass(frozen=True, slots=True)
class LoopTransitionBinding(ContractRecord):
    """Read-only reference map for loop status and phase transition boundaries."""

    transition_ref: str
    from_status: LoopStatus
    to_status: LoopStatus
    from_step: LoopPhase
    to_step: LoopPhase
    required_authority_refs: tuple[str, ...]
    required_evidence_refs: tuple[str, ...]
    blocker_refs: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    rollback_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    validator_refs: tuple[str, ...]
    proof_surface_refs: tuple[str, ...]
    read_only: bool = True
    executes_transition: bool = False
    terminal_closure: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "transition_ref",
            require_non_empty_text(self.transition_ref, "transition_ref"),
        )
        if not isinstance(self.from_status, LoopStatus):
            raise ValueError("from_status must be a LoopStatus value")
        if not isinstance(self.to_status, LoopStatus):
            raise ValueError("to_status must be a LoopStatus value")
        if not isinstance(self.from_step, LoopPhase):
            raise ValueError("from_step must be a LoopPhase value")
        if not isinstance(self.to_step, LoopPhase):
            raise ValueError("to_step must be a LoopPhase value")
        for field_name in (
            "required_authority_refs",
            "required_evidence_refs",
            "receipt_refs",
            "rollback_refs",
            "source_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name),
            )
        object.__setattr__(
            self,
            "blocker_refs",
            _freeze_text_tuple(self.blocker_refs, "blocker_refs", allow_empty=True),
        )
        if self.read_only is not True:
            raise ValueError("transition binding must be read-only")
        if self.executes_transition is not False:
            raise ValueError("transition binding cannot execute transition")
        if self.terminal_closure is not False:
            raise ValueError("transition binding cannot be terminal closure")


@dataclass(frozen=True, slots=True)
class LoopReceiptLineageBinding(ContractRecord):
    """Read-only provenance map for one synthetic loop step receipt."""

    lineage_ref: str
    step: LoopPhase
    receipt_ref: str
    receipt_hash: str
    required_evidence_refs: tuple[str, ...]
    observed_evidence_refs: tuple[str, ...]
    blocker_refs: tuple[str, ...]
    source_receipt_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    validator_refs: tuple[str, ...]
    proof_surface_refs: tuple[str, ...]
    read_only: bool = True
    emits_receipt: bool = False
    terminal_closure: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "lineage_ref",
            require_non_empty_text(self.lineage_ref, "lineage_ref"),
        )
        if not isinstance(self.step, LoopPhase):
            raise ValueError("step must be a LoopPhase value")
        object.__setattr__(
            self,
            "receipt_ref",
            require_non_empty_text(self.receipt_ref, "receipt_ref"),
        )
        object.__setattr__(
            self,
            "receipt_hash",
            require_non_empty_text(self.receipt_hash, "receipt_hash"),
        )
        if not self.receipt_hash.startswith("sha256:"):
            raise ValueError("receipt_hash must be a sha256 reference")
        object.__setattr__(
            self,
            "required_evidence_refs",
            _freeze_text_tuple(self.required_evidence_refs, "required_evidence_refs"),
        )
        object.__setattr__(
            self,
            "observed_evidence_refs",
            _freeze_text_tuple(
                self.observed_evidence_refs,
                "observed_evidence_refs",
                allow_empty=True,
            ),
        )
        object.__setattr__(
            self,
            "blocker_refs",
            _freeze_text_tuple(self.blocker_refs, "blocker_refs", allow_empty=True),
        )
        for field_name in (
            "source_receipt_refs",
            "source_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name),
            )
        if self.receipt_ref not in self.source_receipt_refs:
            raise ValueError("source_receipt_refs must include receipt_ref")
        if self.read_only is not True:
            raise ValueError("receipt lineage binding must be read-only")
        if self.emits_receipt is not False:
            raise ValueError("receipt lineage binding cannot emit receipt")
        if self.terminal_closure is not False:
            raise ValueError("receipt lineage binding cannot be terminal closure")


@dataclass(frozen=True, slots=True)
class LoopClosureConditionBinding(ContractRecord):
    """Read-only reference map for one loop closure condition."""

    closure_ref: str
    purpose: str
    required_evidence_refs: tuple[str, ...]
    required_authority_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    validator_refs: tuple[str, ...]
    proof_surface_refs: tuple[str, ...]
    read_only: bool = True
    terminal_closure: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "closure_ref",
            require_non_empty_text(self.closure_ref, "closure_ref"),
        )
        object.__setattr__(self, "purpose", require_non_empty_text(self.purpose, "purpose"))
        for field_name in (
            "required_evidence_refs",
            "required_authority_refs",
            "source_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name),
            )
        if self.read_only is not True:
            raise ValueError("closure condition binding must be read-only")
        if self.terminal_closure is not False:
            raise ValueError("closure condition binding cannot be terminal closure")


@dataclass(frozen=True, slots=True)
class LoopClosureEvidencePack(ContractRecord):
    """Read-only aggregate of evidence needed to evaluate loop closure."""

    pack_ref: str
    loop_id: str
    required_evidence_refs: tuple[str, ...]
    observed_evidence_refs: tuple[str, ...]
    missing_evidence_refs: tuple[str, ...]
    required_authority_refs: tuple[str, ...]
    observed_authority_refs: tuple[str, ...]
    missing_authority_refs: tuple[str, ...]
    blocker_refs: tuple[str, ...]
    closure_condition_refs: tuple[str, ...]
    receipt_lineage_refs: tuple[str, ...]
    closure_report_ref: str
    rollback_ref: str
    validator_refs: tuple[str, ...]
    proof_surface_refs: tuple[str, ...]
    evidence_complete: bool
    authority_complete: bool
    closure_blocked: bool
    rollback_available: bool
    read_only: bool = True
    emits_receipt: bool = False
    terminal_closure: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "pack_ref",
            "loop_id",
            "closure_report_ref",
            "rollback_ref",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        for field_name in (
            "required_evidence_refs",
            "required_authority_refs",
            "closure_condition_refs",
            "receipt_lineage_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name),
            )
        for field_name in (
            "observed_evidence_refs",
            "missing_evidence_refs",
            "observed_authority_refs",
            "missing_authority_refs",
            "blocker_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name, allow_empty=True),
            )
        for field_name in (
            "evidence_complete",
            "authority_complete",
            "closure_blocked",
            "rollback_available",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be boolean")
        if self.evidence_complete != (not self.missing_evidence_refs):
            raise ValueError("evidence_complete must match missing evidence refs")
        if self.authority_complete != (not self.missing_authority_refs):
            raise ValueError("authority_complete must match missing authority refs")
        if self.closure_blocked != bool(self.blocker_refs):
            raise ValueError("closure_blocked must match blocker refs")
        if self.read_only is not True:
            raise ValueError("closure evidence pack must be read-only")
        if self.emits_receipt is not False:
            raise ValueError("closure evidence pack cannot emit receipt")
        if self.terminal_closure is not False:
            raise ValueError("closure evidence pack cannot be terminal closure")


@dataclass(frozen=True, slots=True)
class LoopOperatorClosureReadinessView(ContractRecord):
    """Read-only operator projection over closure blockers and next proof action."""

    view_ref: str
    loop_id: str
    projected_status: LoopStatus
    readiness_state: str
    blocker_refs: tuple[str, ...]
    evidence_gap_refs: tuple[str, ...]
    authority_gap_refs: tuple[str, ...]
    closure_condition_refs: tuple[str, ...]
    rollback_ref: str
    rollback_available: bool
    next_proof_action: str
    next_proof_refs: tuple[str, ...]
    read_only: bool = True
    mutation_route: bool = False
    terminal_closure: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "view_ref",
            "loop_id",
            "readiness_state",
            "rollback_ref",
            "next_proof_action",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if not isinstance(self.projected_status, LoopStatus):
            raise ValueError("projected_status must be a LoopStatus value")
        allowed_readiness_states = {
            "blocked_by_unresolved_gaps",
            "ready_for_terminal_closure_review",
        }
        if self.readiness_state not in allowed_readiness_states:
            raise ValueError("readiness_state is invalid")
        for field_name in (
            "blocker_refs",
            "evidence_gap_refs",
            "authority_gap_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name, allow_empty=True),
            )
        for field_name in ("closure_condition_refs", "next_proof_refs"):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name),
            )
        if not isinstance(self.rollback_available, bool):
            raise ValueError("rollback_available must be boolean")
        expected_readiness_state = (
            "blocked_by_unresolved_gaps"
            if self.blocker_refs
            else "ready_for_terminal_closure_review"
        )
        if self.readiness_state != expected_readiness_state:
            raise ValueError("readiness_state must match blocker refs")
        if self.read_only is not True:
            raise ValueError("operator closure readiness view must be read-only")
        if self.mutation_route is not False:
            raise ValueError("operator closure readiness view cannot expose a mutation route")
        if self.terminal_closure is not False:
            raise ValueError("operator closure readiness view cannot be terminal closure")


@dataclass(frozen=True, slots=True)
class LoopProofObligationView(ContractRecord):
    """Read-only proof obligation projection over evidence, authority, and closure refs."""

    obligation_ref: str
    loop_id: str
    obligation_state: str
    required_evidence_refs: tuple[str, ...]
    satisfied_evidence_refs: tuple[str, ...]
    missing_evidence_refs: tuple[str, ...]
    required_authority_refs: tuple[str, ...]
    satisfied_authority_refs: tuple[str, ...]
    missing_authority_refs: tuple[str, ...]
    closure_condition_refs: tuple[str, ...]
    validator_refs: tuple[str, ...]
    proof_surface_refs: tuple[str, ...]
    blocker_refs: tuple[str, ...]
    read_only: bool = True
    executes_validator: bool = False
    terminal_closure: bool = False

    def __post_init__(self) -> None:
        for field_name in ("obligation_ref", "loop_id", "obligation_state"):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        allowed_states = {
            "blocked_by_missing_proof",
            "proof_obligations_satisfied_terminal_review_required",
        }
        if self.obligation_state not in allowed_states:
            raise ValueError("obligation_state is invalid")
        for field_name in (
            "required_evidence_refs",
            "required_authority_refs",
            "closure_condition_refs",
            "validator_refs",
            "proof_surface_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name),
            )
        for field_name in (
            "satisfied_evidence_refs",
            "missing_evidence_refs",
            "satisfied_authority_refs",
            "missing_authority_refs",
            "blocker_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(getattr(self, field_name), field_name, allow_empty=True),
            )
        if self.obligation_state != (
            "blocked_by_missing_proof"
            if self.blocker_refs
            else "proof_obligations_satisfied_terminal_review_required"
        ):
            raise ValueError("obligation_state must match blocker refs")
        if self.read_only is not True:
            raise ValueError("proof obligation view must be read-only")
        if self.executes_validator is not False:
            raise ValueError("proof obligation view cannot execute validators")
        if self.terminal_closure is not False:
            raise ValueError("proof obligation view cannot be terminal closure")


@dataclass(frozen=True, slots=True)
class LoopSummary(ContractRecord):
    """Bounded read-model summary for one registered governed loop."""

    loop_id: str
    name: str
    purpose: str
    owner: str
    risk_class: str
    risk_binding: LoopRiskBinding
    status: LoopStatus
    status_binding: LoopStatusBinding
    transition_bindings: tuple[LoopTransitionBinding, ...]
    mode: LoopMode
    mode_binding: LoopModeBinding
    current_step: LoopPhase
    required_authority: tuple[str, ...]
    authority_bindings: tuple[LoopAuthorityBinding, ...]
    authority_refs: tuple[str, ...]
    missing_authority: tuple[str, ...]
    required_evidence: tuple[str, ...]
    evidence_bindings: tuple[LoopEvidenceBinding, ...]
    step_receipts: tuple[LoopStepReceipt, ...]
    receipt_lineage_bindings: tuple[LoopReceiptLineageBinding, ...]
    evidence_refs: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    closure_conditions: tuple[str, ...]
    closure_condition_bindings: tuple[LoopClosureConditionBinding, ...]
    closure_report: LoopClosureReport
    closure_evidence_pack: LoopClosureEvidencePack
    operator_closure_readiness_view: LoopOperatorClosureReadinessView
    proof_obligation_view: LoopProofObligationView
    open_blockers: tuple[str, ...]
    rollback_policy: str
    rollback_binding: LoopRollbackBinding
    learning_policy: str
    learning_binding: LoopLearningBinding
    updated_at: str

    def __post_init__(self) -> None:
        for field_name in (
            "loop_id",
            "name",
            "purpose",
            "owner",
            "risk_class",
            "rollback_policy",
            "learning_policy",
        ):
            object.__setattr__(
                self,
                field_name,
                require_non_empty_text(getattr(self, field_name), field_name),
            )
        if not isinstance(self.status, LoopStatus):
            raise ValueError("status must be a LoopStatus value")
        if not isinstance(self.status_binding, LoopStatusBinding):
            raise ValueError("status_binding must be a LoopStatusBinding")
        if self.status_binding.projected_status != self.status:
            raise ValueError("status_binding projected_status must match status")
        if not isinstance(self.mode, LoopMode):
            raise ValueError("mode must be a LoopMode value")
        if not isinstance(self.mode_binding, LoopModeBinding):
            raise ValueError("mode_binding must be a LoopModeBinding")
        if self.mode_binding.projected_mode != self.mode:
            raise ValueError("mode_binding projected_mode must match mode")
        if not isinstance(self.current_step, LoopPhase):
            raise ValueError("current_step must be a LoopPhase value")
        for field_name in (
            "required_authority",
            "authority_refs",
            "missing_authority",
            "required_evidence",
            "evidence_refs",
            "missing_evidence",
            "closure_conditions",
            "open_blockers",
        ):
            object.__setattr__(
                self,
                field_name,
                _freeze_text_tuple(
                    getattr(self, field_name),
                    field_name,
                    allow_empty=field_name
                    in {
                        "authority_refs",
                        "missing_authority",
                        "evidence_refs",
                        "missing_evidence",
                        "open_blockers",
                    },
                ),
            )
        object.__setattr__(
            self,
            "authority_bindings",
            _freeze_contract_tuple(
                self.authority_bindings,
                "authority_bindings",
                LoopAuthorityBinding,
                "LoopAuthorityBinding",
            ),
        )
        object.__setattr__(
            self,
            "evidence_bindings",
            _freeze_contract_tuple(
                self.evidence_bindings,
                "evidence_bindings",
                LoopEvidenceBinding,
                "LoopEvidenceBinding",
            ),
        )
        object.__setattr__(
            self,
            "step_receipts",
            _freeze_contract_tuple(
                self.step_receipts,
                "step_receipts",
                LoopStepReceipt,
                "LoopStepReceipt",
            ),
        )
        object.__setattr__(
            self,
            "receipt_lineage_bindings",
            _freeze_contract_tuple(
                self.receipt_lineage_bindings,
                "receipt_lineage_bindings",
                LoopReceiptLineageBinding,
                "LoopReceiptLineageBinding",
            ),
        )
        object.__setattr__(
            self,
            "closure_condition_bindings",
            _freeze_contract_tuple(
                self.closure_condition_bindings,
                "closure_condition_bindings",
                LoopClosureConditionBinding,
                "LoopClosureConditionBinding",
            ),
        )
        object.__setattr__(
            self,
            "transition_bindings",
            _freeze_contract_tuple(
                self.transition_bindings,
                "transition_bindings",
                LoopTransitionBinding,
                "LoopTransitionBinding",
            ),
        )
        if not isinstance(self.risk_binding, LoopRiskBinding):
            raise ValueError("risk_binding must be a LoopRiskBinding")
        if self.risk_binding.risk_ref != self.risk_class:
            raise ValueError("risk_binding risk_ref must match risk_class")
        if not isinstance(self.closure_report, LoopClosureReport):
            raise ValueError("closure_report must be a LoopClosureReport")
        if not isinstance(self.closure_evidence_pack, LoopClosureEvidencePack):
            raise ValueError("closure_evidence_pack must be a LoopClosureEvidencePack")
        if not isinstance(self.operator_closure_readiness_view, LoopOperatorClosureReadinessView):
            raise ValueError(
                "operator_closure_readiness_view must be a LoopOperatorClosureReadinessView"
            )
        if not isinstance(self.proof_obligation_view, LoopProofObligationView):
            raise ValueError("proof_obligation_view must be a LoopProofObligationView")
        if not isinstance(self.rollback_binding, LoopRollbackBinding):
            raise ValueError("rollback_binding must be a LoopRollbackBinding")
        if self.rollback_binding.rollback_ref != self.rollback_policy:
            raise ValueError("rollback_binding rollback_ref must match rollback_policy")
        if not isinstance(self.learning_binding, LoopLearningBinding):
            raise ValueError("learning_binding must be a LoopLearningBinding")
        if self.learning_binding.learning_ref != self.learning_policy:
            raise ValueError("learning_binding learning_ref must match learning_policy")
        if self.closure_report.loop_id != self.loop_id:
            raise ValueError("closure_report loop_id must match summary loop_id")
        if self.closure_report.closed:
            raise ValueError("summary closure_report cannot claim terminal closure")
        if self.closure_evidence_pack.loop_id != self.loop_id:
            raise ValueError("closure_evidence_pack loop_id must match summary loop_id")
        if self.operator_closure_readiness_view.loop_id != self.loop_id:
            raise ValueError(
                "operator_closure_readiness_view loop_id must match summary loop_id"
            )
        if self.operator_closure_readiness_view.projected_status != self.status:
            raise ValueError(
                "operator_closure_readiness_view projected_status must match summary status"
            )
        if self.proof_obligation_view.loop_id != self.loop_id:
            raise ValueError("proof_obligation_view loop_id must match summary loop_id")
        object.__setattr__(self, "updated_at", require_datetime_text(self.updated_at, "updated_at"))
        if set(self.status_binding.blocker_refs) != set(self.open_blockers):
            raise ValueError("status_binding blocker_refs must match open blockers")
        if self.status in {LoopStatus.VERIFIED, LoopStatus.CLOSED} and self.status_binding.blocker_refs:
            raise ValueError("verified or closed status binding cannot carry blockers")
        if self.status in {LoopStatus.VERIFIED, LoopStatus.CLOSED} and self.open_blockers:
            raise ValueError("verified or closed summary cannot carry blockers")
        if not self.transition_bindings:
            raise ValueError("transition_bindings must contain at least one binding")
        transition_refs = [binding.transition_ref for binding in self.transition_bindings]
        if len(transition_refs) != len(set(transition_refs)):
            raise ValueError("transition bindings must not contain duplicate transition refs")
        for binding in self.transition_bindings:
            if set(binding.blocker_refs) != set(self.open_blockers):
                raise ValueError("transition binding blocker_refs must match open blockers")
            if self.rollback_policy not in binding.rollback_refs:
                raise ValueError("transition binding rollback_refs must include rollback policy")
        authority_binding_refs = [binding.authority_ref for binding in self.authority_bindings]
        if len(authority_binding_refs) != len(set(authority_binding_refs)):
            raise ValueError("authority bindings must not contain duplicate authority refs")
        if set(authority_binding_refs) != set(self.required_authority):
            raise ValueError("authority bindings must cover required authority exactly")
        binding_refs = [binding.evidence_ref for binding in self.evidence_bindings]
        if len(binding_refs) != len(set(binding_refs)):
            raise ValueError("evidence bindings must not contain duplicate evidence refs")
        if set(binding_refs) != set(self.required_evidence):
            raise ValueError("evidence bindings must cover required evidence exactly")
        closure_binding_refs = [
            binding.closure_ref for binding in self.closure_condition_bindings
        ]
        if len(closure_binding_refs) != len(set(closure_binding_refs)):
            raise ValueError("closure condition bindings must not contain duplicate closure refs")
        if set(closure_binding_refs) != set(self.closure_conditions):
            raise ValueError("closure condition bindings must cover closure conditions exactly")
        required_evidence_refs = set(self.required_evidence)
        required_authority_refs = set(self.required_authority)
        for binding in self.closure_condition_bindings:
            if not set(binding.required_evidence_refs) <= required_evidence_refs:
                raise ValueError("closure condition binding evidence refs must be required evidence")
            if not set(binding.required_authority_refs) <= required_authority_refs:
                raise ValueError("closure condition binding authority refs must be required authority")
        for binding in self.transition_bindings:
            if not set(binding.required_evidence_refs) <= required_evidence_refs:
                raise ValueError("transition binding evidence refs must be required evidence")
            if not set(binding.required_authority_refs) <= required_authority_refs:
                raise ValueError("transition binding authority refs must be required authority")
        if not self.step_receipts:
            raise ValueError("step_receipts must contain at least one receipt")
        receipt_steps = [receipt.step for receipt in self.step_receipts]
        if len(receipt_steps) != len(set(receipt_steps)):
            raise ValueError("step_receipts must not contain duplicate steps")
        for receipt in self.step_receipts:
            if receipt.loop_id != self.loop_id:
                raise ValueError("step receipt loop_id must match summary loop_id")
            if receipt.status is LoopStatus.CLOSED:
                raise ValueError("step receipt cannot claim terminal closure")
        if not self.receipt_lineage_bindings:
            raise ValueError("receipt_lineage_bindings must contain at least one binding")
        lineage_refs = [binding.lineage_ref for binding in self.receipt_lineage_bindings]
        if len(lineage_refs) != len(set(lineage_refs)):
            raise ValueError("receipt lineage bindings must not contain duplicate lineage refs")
        lineage_by_step = {binding.step: binding for binding in self.receipt_lineage_bindings}
        receipt_by_step = {receipt.step: receipt for receipt in self.step_receipts}
        if set(lineage_by_step) != set(receipt_by_step):
            raise ValueError("receipt lineage bindings must cover step receipts exactly")
        for step, binding in lineage_by_step.items():
            receipt = receipt_by_step[step]
            if binding.receipt_hash != receipt.output_hash:
                raise ValueError("receipt lineage binding receipt_hash must match step receipt output_hash")
            if set(binding.blocker_refs) != set(self.open_blockers):
                raise ValueError("receipt lineage binding blocker_refs must match open blockers")
            if set(binding.observed_evidence_refs) != set(self.evidence_refs):
                raise ValueError("receipt lineage binding observed_evidence_refs must match evidence refs")
            if not set(binding.required_evidence_refs) <= required_evidence_refs:
                raise ValueError("receipt lineage binding evidence refs must be required evidence")
        if set(self.closure_report.unresolved_gaps) != set(self.open_blockers):
            raise ValueError("closure_report unresolved gaps must match open blockers")
        if self.closure_report.evidence_complete != (not self.missing_evidence):
            raise ValueError("closure_report evidence_complete must match missing evidence")
        if set(self.closure_evidence_pack.required_evidence_refs) != set(self.required_evidence):
            raise ValueError("closure evidence pack required evidence refs must match required evidence")
        if set(self.closure_evidence_pack.observed_evidence_refs) != set(self.evidence_refs):
            raise ValueError("closure evidence pack observed evidence refs must match evidence refs")
        if set(self.closure_evidence_pack.missing_evidence_refs) != set(self.missing_evidence):
            raise ValueError("closure evidence pack missing evidence refs must match missing evidence")
        if set(self.closure_evidence_pack.required_authority_refs) != set(self.required_authority):
            raise ValueError("closure evidence pack required authority refs must match required authority")
        if set(self.closure_evidence_pack.observed_authority_refs) != set(self.authority_refs):
            raise ValueError("closure evidence pack observed authority refs must match authority refs")
        if set(self.closure_evidence_pack.missing_authority_refs) != set(self.missing_authority):
            raise ValueError("closure evidence pack missing authority refs must match missing authority")
        if set(self.closure_evidence_pack.blocker_refs) != set(self.open_blockers):
            raise ValueError("closure evidence pack blocker refs must match open blockers")
        if set(self.closure_evidence_pack.closure_condition_refs) != set(self.closure_conditions):
            raise ValueError("closure evidence pack closure condition refs must match closure conditions")
        if set(self.closure_evidence_pack.receipt_lineage_refs) != set(lineage_refs):
            raise ValueError("closure evidence pack receipt lineage refs must match receipt lineage bindings")
        if self.closure_evidence_pack.evidence_complete != self.closure_report.evidence_complete:
            raise ValueError("closure evidence pack evidence_complete must match closure report")
        if self.closure_evidence_pack.authority_complete != (not self.missing_authority):
            raise ValueError("closure evidence pack authority_complete must match missing authority")
        if self.closure_evidence_pack.closure_blocked != bool(self.open_blockers):
            raise ValueError("closure evidence pack closure_blocked must match open blockers")
        if self.closure_evidence_pack.rollback_available != self.closure_report.rollback_available:
            raise ValueError("closure evidence pack rollback_available must match closure report")
        if self.closure_evidence_pack.rollback_ref != self.rollback_policy:
            raise ValueError("closure evidence pack rollback_ref must match rollback policy")
        if set(self.operator_closure_readiness_view.blocker_refs) != set(self.open_blockers):
            raise ValueError("operator closure readiness blocker refs must match open blockers")
        if set(self.operator_closure_readiness_view.evidence_gap_refs) != set(self.missing_evidence):
            raise ValueError("operator closure readiness evidence gap refs must match missing evidence")
        if set(self.operator_closure_readiness_view.authority_gap_refs) != set(self.missing_authority):
            raise ValueError("operator closure readiness authority gap refs must match missing authority")
        if set(self.operator_closure_readiness_view.closure_condition_refs) != set(self.closure_conditions):
            raise ValueError(
                "operator closure readiness closure condition refs must match closure conditions"
            )
        if self.operator_closure_readiness_view.rollback_ref != self.rollback_policy:
            raise ValueError("operator closure readiness rollback ref must match rollback policy")
        if (
            self.operator_closure_readiness_view.rollback_available
            != self.closure_report.rollback_available
        ):
            raise ValueError(
                "operator closure readiness rollback_available must match closure report"
            )
        expected_readiness_state = (
            "blocked_by_unresolved_gaps"
            if self.open_blockers
            else "ready_for_terminal_closure_review"
        )
        if self.operator_closure_readiness_view.readiness_state != expected_readiness_state:
            raise ValueError("operator closure readiness state must match blockers")
        expected_next_action = (
            "resolve_blockers_before_terminal_closure_review"
            if self.open_blockers
            else "run_loop_specific_terminal_closure_workflow"
        )
        if self.operator_closure_readiness_view.next_proof_action != expected_next_action:
            raise ValueError("operator closure readiness next proof action must match blockers")
        if "closure_evidence_pack" not in self.operator_closure_readiness_view.next_proof_refs:
            raise ValueError("operator closure readiness refs must include closure evidence pack")
        if "closure_report" not in self.operator_closure_readiness_view.next_proof_refs:
            raise ValueError("operator closure readiness refs must include closure report")
        if set(self.proof_obligation_view.required_evidence_refs) != set(self.required_evidence):
            raise ValueError("proof obligation required evidence refs must match required evidence")
        if set(self.proof_obligation_view.satisfied_evidence_refs) != set(self.evidence_refs):
            raise ValueError("proof obligation satisfied evidence refs must match evidence refs")
        if set(self.proof_obligation_view.missing_evidence_refs) != set(self.missing_evidence):
            raise ValueError("proof obligation missing evidence refs must match missing evidence")
        if set(self.proof_obligation_view.required_authority_refs) != set(self.required_authority):
            raise ValueError("proof obligation required authority refs must match required authority")
        if set(self.proof_obligation_view.satisfied_authority_refs) != set(self.authority_refs):
            raise ValueError("proof obligation satisfied authority refs must match authority refs")
        if set(self.proof_obligation_view.missing_authority_refs) != set(self.missing_authority):
            raise ValueError("proof obligation missing authority refs must match missing authority")
        if set(self.proof_obligation_view.closure_condition_refs) != set(self.closure_conditions):
            raise ValueError("proof obligation closure condition refs must match closure conditions")
        if set(self.proof_obligation_view.validator_refs) != set(self.closure_evidence_pack.validator_refs):
            raise ValueError("proof obligation validator refs must match closure evidence pack")
        if set(self.proof_obligation_view.proof_surface_refs) != set(self.closure_evidence_pack.proof_surface_refs):
            raise ValueError("proof obligation proof surface refs must match closure evidence pack")
        if set(self.proof_obligation_view.blocker_refs) != set(self.open_blockers):
            raise ValueError("proof obligation blocker refs must match open blockers")
        expected_obligation_state = (
            "blocked_by_missing_proof"
            if self.open_blockers
            else "proof_obligations_satisfied_terminal_review_required"
        )
        if self.proof_obligation_view.obligation_state != expected_obligation_state:
            raise ValueError("proof obligation state must match blockers")


@dataclass(frozen=True, slots=True)
class LoopReadModel(ContractRecord):
    """Bounded read model over registered governed loops."""

    generated_at: str
    loops: tuple[LoopSummary, ...]
    total_count: int
    returned_count: int
    truncated: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))
        object.__setattr__(
            self,
            "loops",
            _freeze_contract_tuple(self.loops, "loops", LoopSummary, "LoopSummary"),
        )
        if not isinstance(self.total_count, int) or isinstance(self.total_count, bool):
            raise ValueError("total_count must be an int")
        if not isinstance(self.returned_count, int) or isinstance(self.returned_count, bool):
            raise ValueError("returned_count must be an int")
        if self.total_count < 0 or self.returned_count < 0:
            raise ValueError("counts must be non-negative")
        if self.returned_count != len(self.loops):
            raise ValueError("returned_count must equal loop summary count")
        if self.returned_count > self.total_count:
            raise ValueError("returned_count cannot exceed total_count")
        if not isinstance(self.truncated, bool):
            raise ValueError("truncated must be a bool")


def _freeze_text_tuple(
    values: Sequence[str],
    field_name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    if not values and not allow_empty:
        raise ValueError(f"{field_name} must contain at least one item")
    normalized: list[str] = []
    for value in values:
        normalized.append(require_non_empty_text(value, f"{field_name} element"))
    return cast(tuple[str, ...], freeze_value(normalized))


def _freeze_enum_tuple(
    values: Sequence[ContractT],
    field_name: str,
    enum_type: type[ContractT],
    enum_type_name: str,
) -> tuple[ContractT, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    if not values:
        raise ValueError(f"{field_name} must contain at least one item")
    normalized: list[ContractT] = []
    for value in values:
        if not isinstance(value, enum_type):
            raise ValueError(f"{field_name} must contain only {enum_type_name} values")
        normalized.append(value)
    return cast(tuple[ContractT, ...], freeze_value(normalized))


def _freeze_contract_tuple(
    values: Sequence[ContractT],
    field_name: str,
    record_type: type[ContractT],
    record_type_name: str,
) -> tuple[ContractT, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    normalized: list[ContractT] = []
    for value in values:
        if not isinstance(value, record_type):
            raise ValueError(f"{field_name} must contain only {record_type_name} values")
        normalized.append(value)
    return cast(tuple[ContractT, ...], freeze_value(normalized))


__all__ = [
    "LoopClosureReport",
    "LoopAuthorityBinding",
    "LoopClosureConditionBinding",
    "LoopClosureEvidencePack",
    "LoopEvidenceBinding",
    "LoopLearningBinding",
    "LoopModeBinding",
    "LoopOperatorClosureReadinessView",
    "LoopProofObligationView",
    "LoopReceiptLineageBinding",
    "LoopRiskBinding",
    "LoopRollbackBinding",
    "LoopManifest",
    "LoopMode",
    "LoopPhase",
    "LoopReadModel",
    "LoopState",
    "LoopStatus",
    "LoopStatusBinding",
    "LoopStepReceipt",
    "LoopSummary",
    "LoopTransitionBinding",
]
