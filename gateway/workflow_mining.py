"""Gateway workflow mining engine.

Purpose: detect repeated human operation traces and draft governed workflow
    templates for operator review.
Governance scope: pattern evidence, policy projection, approval rules, sandbox
    replay requirements, eval requirements, and activation blocking.
Dependencies: standard-library dataclasses, hashlib, and JSON serialization.
Invariants:
  - Mining can propose a workflow but cannot activate it.
  - A draft must carry source traces and occurrence evidence.
  - Side-effecting or risky patterns require approval and recovery rules.
  - Every proposed workflow requires sandbox replay and operator review.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Iterable


_SIDE_EFFECT_OPERATIONS = frozenset({
    "payment.dispatch",
    "email.send",
    "refund.issue",
    "record.update",
    "external.write",
    "document.send",
})
_APPROVAL_KEYWORDS = ("approve", "pay", "payment", "refund", "send", "update", "delete")


@dataclass(frozen=True, slots=True)
class HumanWorkflowTrace:
    """One observed human-run workflow trace."""

    trace_id: str
    tenant_id: str
    actor_id: str
    operations: tuple[str, ...]
    observed_at: str
    outcome: str
    evidence_refs: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.trace_id:
            raise ValueError("trace_id_required")
        if not self.tenant_id:
            raise ValueError("tenant_id_required")
        if not self.actor_id:
            raise ValueError("actor_id_required")
        if not self.operations:
            raise ValueError("operations_required")
        if not self.observed_at:
            raise ValueError("observed_at_required")
        object.__setattr__(self, "operations", tuple(self.operations))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class WorkflowPattern:
    """Repeated operation sequence discovered from traces."""

    pattern_id: str
    tenant_id: str
    operation_signature: tuple[str, ...]
    occurrence_count: int
    source_trace_ids: tuple[str, ...]
    confidence: float
    risk_tier: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.occurrence_count < 1:
            raise ValueError("occurrence_count_positive")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence_between_zero_and_one")
        if self.risk_tier not in {"low", "medium", "high"}:
            raise ValueError("risk_tier_invalid")


@dataclass(frozen=True, slots=True)
class WorkflowDraftStage:
    """One stage in a proposed governed workflow template."""

    stage_id: str
    stage_type: str
    operation: str
    predecessors: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "predecessors", tuple(self.predecessors))
        object.__setattr__(self, "required_evidence", tuple(self.required_evidence))


@dataclass(frozen=True, slots=True)
class WorkflowDraft:
    """Governed workflow template proposal produced by mining."""

    draft_id: str
    tenant_id: str
    name: str
    pattern_id: str
    stages: tuple[WorkflowDraftStage, ...]
    policy_requirements: tuple[str, ...]
    approval_rules: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    eval_cases: tuple[str, ...]
    sandbox_replay_required: bool
    operator_review_required: bool
    activation_blocked: bool
    source_trace_ids: tuple[str, ...]
    draft_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "stages", tuple(self.stages))
        object.__setattr__(self, "policy_requirements", tuple(self.policy_requirements))
        object.__setattr__(self, "approval_rules", tuple(self.approval_rules))
        object.__setattr__(self, "evidence_requirements", tuple(self.evidence_requirements))
        object.__setattr__(self, "eval_cases", tuple(self.eval_cases))
        object.__setattr__(self, "source_trace_ids", tuple(self.source_trace_ids))
        if not self.operator_review_required:
            raise ValueError("operator_review_required")
        if not self.activation_blocked:
            raise ValueError("activation_must_be_blocked")


@dataclass(frozen=True, slots=True)
class WorkflowMiningReport:
    """Mining result containing discovered patterns and draft proposals."""

    report_id: str
    tenant_id: str
    trace_count: int
    patterns: tuple[WorkflowPattern, ...]
    drafts: tuple[WorkflowDraft, ...]
    report_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "patterns", tuple(self.patterns))
        object.__setattr__(self, "drafts", tuple(self.drafts))
        if self.trace_count < 0:
            raise ValueError("trace_count_non_negative")


class WorkflowMiningEngine:
    """Detect repeated human workflows and emit governed draft templates."""

    def mine(
        self,
        *,
        tenant_id: str,
        traces: Iterable[HumanWorkflowTrace],
        min_occurrences: int = 2,
    ) -> WorkflowMiningReport:
        """Mine repeated operation signatures for one tenant."""
        if not tenant_id:
            raise ValueError("tenant_id_required")
        if min_occurrences < 2:
            raise ValueError("min_occurrences_at_least_two")
        tenant_traces = tuple(trace for trace in traces if trace.tenant_id == tenant_id)
        grouped: dict[tuple[str, ...], list[HumanWorkflowTrace]] = {}
        for trace in tenant_traces:
            grouped.setdefault(_normalize_operations(trace.operations), []).append(trace)

        patterns: list[WorkflowPattern] = []
        drafts: list[WorkflowDraft] = []
        for signature, matching_traces in sorted(grouped.items()):
            if len(matching_traces) < min_occurrences:
                continue
            pattern = _pattern(tenant_id, signature, matching_traces)
            patterns.append(pattern)
            drafts.append(_draft_from_pattern(pattern))

        report = WorkflowMiningReport(
            report_id=f"workflow-mining-{_hash_payload({'tenant_id': tenant_id, 'trace_count': len(tenant_traces)})[:16]}",
            tenant_id=tenant_id,
            trace_count=len(tenant_traces),
            patterns=tuple(patterns),
            drafts=tuple(drafts),
            metadata={"min_occurrences": min_occurrences},
        )
        return _stamp_report(report)


def _normalize_operations(operations: Iterable[str]) -> tuple[str, ...]:
    return tuple(operation.strip().lower().replace(" ", ".") for operation in operations if operation.strip())


def _pattern(
    tenant_id: str,
    signature: tuple[str, ...],
    traces: list[HumanWorkflowTrace],
) -> WorkflowPattern:
    evidence_refs = tuple(sorted({ref for trace in traces for ref in trace.evidence_refs}))
    pattern_hash = _hash_payload({"tenant_id": tenant_id, "signature": signature})
    return WorkflowPattern(
        pattern_id=f"workflow-pattern-{pattern_hash[:16]}",
        tenant_id=tenant_id,
        operation_signature=signature,
        occurrence_count=len(traces),
        source_trace_ids=tuple(trace.trace_id for trace in traces),
        confidence=min(1.0, len(traces) / 5),
        risk_tier=_risk_tier(signature),
        evidence_refs=evidence_refs,
    )


def _draft_from_pattern(pattern: WorkflowPattern) -> WorkflowDraft:
    stages = []
    previous_stage_id = ""
    for index, operation in enumerate(pattern.operation_signature, start=1):
        stage_id = f"stage-{index:02d}-{_safe_id(operation)}"
        stages.append(WorkflowDraftStage(
            stage_id=stage_id,
            stage_type=_stage_type(operation),
            operation=operation,
            predecessors=(previous_stage_id,) if previous_stage_id else (),
            required_evidence=(f"evidence:{operation}",),
        ))
        previous_stage_id = stage_id
    draft = WorkflowDraft(
        draft_id=f"workflow-draft-{_hash_payload({'pattern_id': pattern.pattern_id})[:16]}",
        tenant_id=pattern.tenant_id,
        name=f"mined-{_safe_id(pattern.operation_signature[0])}-workflow",
        pattern_id=pattern.pattern_id,
        stages=tuple(stages),
        policy_requirements=("tenant_boundary", "policy_gate", "budget_check", "terminal_closure"),
        approval_rules=_approval_rules(pattern),
        evidence_requirements=tuple(sorted({item for stage in stages for item in stage.required_evidence})),
        eval_cases=("tenant_boundary", "approval_required", "replay_determinism", "no_secret_leak"),
        sandbox_replay_required=True,
        operator_review_required=True,
        activation_blocked=True,
        source_trace_ids=pattern.source_trace_ids,
        metadata={
            "occurrence_count": pattern.occurrence_count,
            "confidence": pattern.confidence,
            "risk_tier": pattern.risk_tier,
        },
    )
    return _stamp_draft(draft)


def _risk_tier(signature: tuple[str, ...]) -> str:
    if any(operation in _SIDE_EFFECT_OPERATIONS for operation in signature):
        return "high"
    if any(keyword in operation for operation in signature for keyword in _APPROVAL_KEYWORDS):
        return "medium"
    return "low"


def _stage_type(operation: str) -> str:
    if "approve" in operation or "approval" in operation:
        return "approval_gate"
    if operation.startswith("send") or operation.endswith(".send"):
        return "communication"
    if operation.startswith("wait") or operation.startswith("receive"):
        return "wait_for_event"
    if operation.startswith("check") or operation.startswith("observe"):
        return "observation"
    return "skill_execution"


def _approval_rules(pattern: WorkflowPattern) -> tuple[str, ...]:
    if pattern.risk_tier == "high":
        return ("operator_approval_required", "fresh_evidence_required", "self_approval_denied")
    if pattern.risk_tier == "medium":
        return ("operator_review_required",)
    return ()


def _stamp_draft(draft: WorkflowDraft) -> WorkflowDraft:
    payload = asdict(replace(draft, draft_hash=""))
    return replace(draft, draft_hash=_hash_payload(payload))


def _stamp_report(report: WorkflowMiningReport) -> WorkflowMiningReport:
    payload = asdict(replace(report, report_hash=""))
    return replace(report, report_hash=_hash_payload(payload))


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value).strip("-").lower()
