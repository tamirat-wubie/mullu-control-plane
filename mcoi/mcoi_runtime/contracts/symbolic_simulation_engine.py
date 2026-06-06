"""Purpose: governed Symbolic Simulation Engine envelope for pre-action projection.
Governance scope: OCE, RAG, CDCV, CQTE, UWMA, SRCA, and PRS simulation gating.
Dependencies: shared contract base helpers and mcoi_runtime.contracts.simulation primitives.
Invariants: actions are simulated, compared, decided, and execution-gated before any effect.
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
    require_non_empty_tuple,
    require_unit_float,
)
from .simulation import (
    RiskLevel,
    SimulationComparison,
    SimulationOutcome,
    SimulationRequest,
    SimulationVerdict,
)


class SymbolicSimulationDecisionKind(StrEnum):
    """Governed decision after comparing simulation branches."""

    EXECUTE = "execute"
    REQUIRE_APPROVAL = "require_approval"
    ESCALATE = "escalate"
    ABORT = "abort"
    DEFER = "defer"


class SymbolicSimulationGateStatus(StrEnum):
    """Execution-gate disposition for a simulated action."""

    ALLOW = "allow"
    BLOCK = "block"
    APPROVAL_REQUIRED = "approval_required"
    DEFERRED = "deferred"


@dataclass(frozen=True, slots=True)
class SymbolicSimulationBranch(ContractRecord):
    """One projected branch binding a request option to a simulated outcome."""

    branch_id: str
    option_id: str
    outcome_id: str
    predicted_state_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    risk_level: RiskLevel
    confidence: float
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "branch_id", require_non_empty_text(self.branch_id, "branch_id"))
        object.__setattr__(self, "option_id", require_non_empty_text(self.option_id, "option_id"))
        object.__setattr__(self, "outcome_id", require_non_empty_text(self.outcome_id, "outcome_id"))
        object.__setattr__(
            self,
            "predicted_state_refs",
            _require_text_tuple(self.predicted_state_refs, "predicted_state_refs"),
        )
        object.__setattr__(self, "evidence_refs", _require_text_tuple(self.evidence_refs, "evidence_refs"))
        if not isinstance(self.risk_level, RiskLevel):
            raise ValueError("risk_level must be a RiskLevel value")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SymbolicSimulationDecision(ContractRecord):
    """Decision record connecting comparison, verdict, selected option, and rationale evidence."""

    decision_id: str
    comparison_id: str
    verdict_id: str
    selected_option_id: str
    decision_kind: SymbolicSimulationDecisionKind
    rationale_refs: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    decided_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "comparison_id", require_non_empty_text(self.comparison_id, "comparison_id"))
        object.__setattr__(self, "verdict_id", require_non_empty_text(self.verdict_id, "verdict_id"))
        object.__setattr__(
            self,
            "selected_option_id",
            require_non_empty_text(self.selected_option_id, "selected_option_id"),
        )
        if not isinstance(self.decision_kind, SymbolicSimulationDecisionKind):
            raise ValueError("decision_kind must be a SymbolicSimulationDecisionKind value")
        object.__setattr__(self, "rationale_refs", _require_text_tuple(self.rationale_refs, "rationale_refs"))
        object.__setattr__(self, "receipt_refs", _require_text_tuple(self.receipt_refs, "receipt_refs"))
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))


@dataclass(frozen=True, slots=True)
class SymbolicSimulationExecutionGate(ContractRecord):
    """Explicit execution gate proving simulation verdict alone did not execute the action."""

    gate_id: str
    decision_id: str
    gate_status: SymbolicSimulationGateStatus
    can_execute: bool
    required_approval_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    evaluated_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "gate_id", require_non_empty_text(self.gate_id, "gate_id"))
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        if not isinstance(self.gate_status, SymbolicSimulationGateStatus):
            raise ValueError("gate_status must be a SymbolicSimulationGateStatus value")
        if not isinstance(self.can_execute, bool):
            raise ValueError("can_execute must be a boolean")
        object.__setattr__(
            self,
            "required_approval_refs",
            _require_text_tuple_allow_empty(self.required_approval_refs, "required_approval_refs"),
        )
        object.__setattr__(self, "evidence_refs", _require_text_tuple(self.evidence_refs, "evidence_refs"))
        object.__setattr__(self, "evaluated_at", require_datetime_text(self.evaluated_at, "evaluated_at"))
        if self.can_execute and self.gate_status is not SymbolicSimulationGateStatus.ALLOW:
            raise ValueError("can_execute requires gate_status allow")
        if not self.can_execute and self.gate_status is SymbolicSimulationGateStatus.ALLOW:
            raise ValueError("gate_status allow requires can_execute true")


@dataclass(frozen=True, slots=True)
class SymbolicSimulationEngineRun(ContractRecord):
    """Portable run envelope for Action -> Simulate -> Compare -> Decide -> Execute gate."""

    run_id: str
    version: str
    generated_at: str
    action_ref: str
    action_snapshot_ref: str
    request: SimulationRequest
    branches: tuple[SymbolicSimulationBranch, ...]
    outcomes: tuple[SimulationOutcome, ...]
    comparison: SimulationComparison
    verdict: SimulationVerdict
    decision: SymbolicSimulationDecision
    execution_gate: SymbolicSimulationExecutionGate
    receipt_refs: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_non_empty_text(self.run_id, "run_id"))
        object.__setattr__(self, "version", require_non_empty_text(self.version, "version"))
        object.__setattr__(self, "generated_at", require_datetime_text(self.generated_at, "generated_at"))
        object.__setattr__(self, "action_ref", require_non_empty_text(self.action_ref, "action_ref"))
        object.__setattr__(
            self,
            "action_snapshot_ref",
            require_non_empty_text(self.action_snapshot_ref, "action_snapshot_ref"),
        )
        if not isinstance(self.request, SimulationRequest):
            raise ValueError("request must be a SimulationRequest")
        object.__setattr__(self, "branches", _require_record_tuple(self.branches, SymbolicSimulationBranch, "branches"))
        object.__setattr__(self, "outcomes", _require_record_tuple(self.outcomes, SimulationOutcome, "outcomes"))
        if not isinstance(self.comparison, SimulationComparison):
            raise ValueError("comparison must be a SimulationComparison")
        if not isinstance(self.verdict, SimulationVerdict):
            raise ValueError("verdict must be a SimulationVerdict")
        if not isinstance(self.decision, SymbolicSimulationDecision):
            raise ValueError("decision must be a SymbolicSimulationDecision")
        if not isinstance(self.execution_gate, SymbolicSimulationExecutionGate):
            raise ValueError("execution_gate must be a SymbolicSimulationExecutionGate")
        object.__setattr__(self, "receipt_refs", _require_text_tuple(self.receipt_refs, "receipt_refs"))
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
        _validate_run_references(
            self.request,
            self.branches,
            self.outcomes,
            self.comparison,
            self.verdict,
            self.decision,
            self.execution_gate,
        )


def _require_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    items = require_non_empty_tuple(values, field_name)
    for item in items:
        require_non_empty_text(item, f"{field_name} element")
    if len(set(items)) != len(items):
        raise ValueError(f"{field_name} must not contain duplicates")
    return tuple(items)


def _require_text_tuple_allow_empty(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)) or isinstance(values, (str, bytes)):
        raise ValueError(f"{field_name} must be an array")
    items = tuple(values)
    for item in items:
        require_non_empty_text(item, f"{field_name} element")
    if len(set(items)) != len(items):
        raise ValueError(f"{field_name} must not contain duplicates")
    return items


def _require_record_tuple(values: tuple[Any, ...], record_type: type[Any], field_name: str) -> tuple[Any, ...]:
    items = require_non_empty_tuple(values, field_name)
    for item in items:
        if not isinstance(item, record_type):
            raise ValueError(f"{field_name} must contain {record_type.__name__} records")
    return tuple(items)


def _validate_run_references(
    request: SimulationRequest,
    branches: tuple[SymbolicSimulationBranch, ...],
    outcomes: tuple[SimulationOutcome, ...],
    comparison: SimulationComparison,
    verdict: SimulationVerdict,
    decision: SymbolicSimulationDecision,
    execution_gate: SymbolicSimulationExecutionGate,
) -> None:
    option_ids = [option.option_id for option in request.options]
    if len(set(option_ids)) != len(option_ids):
        raise ValueError("request options must not contain duplicate option_id values")
    option_id_set = set(option_ids)

    outcome_ids = [outcome.outcome_id for outcome in outcomes]
    if len(set(outcome_ids)) != len(outcome_ids):
        raise ValueError("outcomes must not contain duplicate outcome_id values")
    outcome_id_set = set(outcome_ids)
    for outcome in outcomes:
        if outcome.option_id not in option_id_set:
            raise ValueError("outcomes must reference existing option_id values")
        if outcome.consequence.option_id != outcome.option_id:
            raise ValueError("consequence option_id must match outcome option_id")
        if outcome.risk.option_id != outcome.option_id:
            raise ValueError("risk option_id must match outcome option_id")
        if outcome.obligation_projection.option_id != outcome.option_id:
            raise ValueError("obligation_projection option_id must match outcome option_id")

    branch_ids = [branch.branch_id for branch in branches]
    if len(set(branch_ids)) != len(branch_ids):
        raise ValueError("branches must not contain duplicate branch_id values")
    for branch in branches:
        if branch.option_id not in option_id_set:
            raise ValueError("branches must reference existing option_id values")
        if branch.outcome_id not in outcome_id_set:
            raise ValueError("branches must reference existing outcome_id values")

    if comparison.request_id != request.request_id:
        raise ValueError("comparison request_id must match request request_id")
    if set(comparison.ranked_option_ids) != option_id_set:
        raise ValueError("comparison ranked_option_ids must match request option_id values")
    if set(comparison.scores.keys()) != option_id_set:
        raise ValueError("comparison scores must match request option_id values")

    if verdict.comparison_id != comparison.comparison_id:
        raise ValueError("verdict comparison_id must match comparison comparison_id")
    if verdict.recommended_option_id not in option_id_set:
        raise ValueError("verdict recommended_option_id must reference an existing option_id")

    if decision.comparison_id != comparison.comparison_id:
        raise ValueError("decision comparison_id must match comparison comparison_id")
    if decision.verdict_id != verdict.verdict_id:
        raise ValueError("decision verdict_id must match verdict verdict_id")
    if decision.selected_option_id != verdict.recommended_option_id:
        raise ValueError("decision selected_option_id must match verdict recommended_option_id")
    if execution_gate.decision_id != decision.decision_id:
        raise ValueError("execution_gate decision_id must match decision decision_id")
    if decision.decision_kind is SymbolicSimulationDecisionKind.EXECUTE:
        if execution_gate.gate_status is not SymbolicSimulationGateStatus.ALLOW or not execution_gate.can_execute:
            raise ValueError("execute decisions require an allow execution gate")
    elif execution_gate.can_execute:
        raise ValueError("only execute decisions may allow execution")
