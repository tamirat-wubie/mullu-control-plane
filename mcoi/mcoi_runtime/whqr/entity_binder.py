"""Purpose: side-effect-free entity binding for WHQR semantic trees.
Governance scope: attach explicit entity and evidence references to WHQR nodes before evaluation or MIL compilation.
Dependencies: dataclasses and WHQR contracts.
Invariants: binder is pure, does not query stores or tools, preserves tree shape, and reports unresolved bindings explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Mapping

from mcoi_runtime.contracts.whqr import ConnectorExpr, LogicalExpr, WHQRExpr, WHQRNode


class EntityBindingStatus(StrEnum):
    BOUND = "bound"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    TYPE_MISMATCH = "type_mismatch"
    PREBOUND_CONFLICT = "prebound_conflict"


@dataclass(frozen=True, slots=True)
class EntityBindingCandidate:
    entity_ref: str
    evidence_ref: str
    entity_type: str

    def __post_init__(self) -> None:
        _require_text(self.entity_ref, "entity_ref")
        _require_text(self.evidence_ref, "evidence_ref")
        _require_text(self.entity_type, "entity_type")


@dataclass(frozen=True, slots=True)
class EntityBindingIssue:
    status: EntityBindingStatus
    target: str
    node_id: str | None = None
    expected_type: str | None = None
    observed_type: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, EntityBindingStatus):
            raise ValueError("status must be an EntityBindingStatus value")
        _require_text(self.target, "target")
        if self.node_id is not None:
            _require_text(self.node_id, "node_id")
        if self.expected_type is not None:
            _require_text(self.expected_type, "expected_type")
        if self.observed_type is not None:
            _require_text(self.observed_type, "observed_type")


@dataclass(frozen=True, slots=True)
class EntityBindingReport:
    expr: WHQRExpr
    issues: tuple[EntityBindingIssue, ...]

    @property
    def bound(self) -> bool:
        return not self.issues


def bind_entities(
    expr: WHQRExpr,
    bindings: Mapping[str, EntityBindingCandidate | tuple[EntityBindingCandidate, ...]],
) -> EntityBindingReport:
    """Bind WHQR nodes from an explicit target-to-candidate map."""
    if not isinstance(bindings, Mapping):
        raise ValueError("bindings must be a mapping")
    issues: list[EntityBindingIssue] = []
    bound_expr = _bind_expr(expr, bindings, issues)
    return EntityBindingReport(expr=bound_expr, issues=tuple(issues))


def _bind_expr(
    expr: WHQRExpr,
    bindings: Mapping[str, EntityBindingCandidate | tuple[EntityBindingCandidate, ...]],
    issues: list[EntityBindingIssue],
) -> WHQRExpr:
    if isinstance(expr, WHQRNode):
        return _bind_node(expr, bindings, issues)
    if isinstance(expr, LogicalExpr):
        return replace(expr, args=tuple(_bind_expr(arg, bindings, issues) for arg in expr.args))
    if isinstance(expr, ConnectorExpr):
        return replace(
            expr,
            left=_bind_expr(expr.left, bindings, issues),
            right=_bind_expr(expr.right, bindings, issues),
        )
    raise ValueError("expr must be a WHQR expression")


def _bind_node(
    node: WHQRNode,
    bindings: Mapping[str, EntityBindingCandidate | tuple[EntityBindingCandidate, ...]],
    issues: list[EntityBindingIssue],
) -> WHQRNode:
    raw_candidate = bindings.get(node.target)
    if node.entity_ref is not None or node.evidence_ref is not None:
        return _bind_prebound_node(node, raw_candidate, issues)
    if raw_candidate is None:
        issues.append(EntityBindingIssue(EntityBindingStatus.MISSING, node.target, node.node_id, node.expected_type))
        return node
    candidates = _candidate_tuple(raw_candidate)
    if not candidates:
        issues.append(EntityBindingIssue(EntityBindingStatus.MISSING, node.target, node.node_id, node.expected_type))
        return node
    if len(candidates) != 1:
        issues.append(EntityBindingIssue(EntityBindingStatus.AMBIGUOUS, node.target, node.node_id, node.expected_type))
        return node
    candidate = candidates[0]
    if node.expected_type is not None and node.expected_type != candidate.entity_type:
        issues.append(
            EntityBindingIssue(
                EntityBindingStatus.TYPE_MISMATCH,
                node.target,
                node.node_id,
                node.expected_type,
                candidate.entity_type,
            )
        )
        return node
    return replace(node, entity_ref=candidate.entity_ref, evidence_ref=candidate.evidence_ref)


def _bind_prebound_node(
    node: WHQRNode,
    raw_candidate: EntityBindingCandidate | tuple[EntityBindingCandidate, ...] | None,
    issues: list[EntityBindingIssue],
) -> WHQRNode:
    if node.entity_ref is None or node.evidence_ref is None:
        issues.append(EntityBindingIssue(EntityBindingStatus.PREBOUND_CONFLICT, node.target, node.node_id, node.expected_type))
        return node
    if raw_candidate is None:
        return node
    candidates = _candidate_tuple(raw_candidate)
    if len(candidates) != 1:
        issues.append(EntityBindingIssue(EntityBindingStatus.PREBOUND_CONFLICT, node.target, node.node_id, node.expected_type))
        return node
    candidate = candidates[0]
    type_matches = node.expected_type is None or node.expected_type == candidate.entity_type
    refs_match = node.entity_ref == candidate.entity_ref and node.evidence_ref == candidate.evidence_ref
    if not type_matches or not refs_match:
        issues.append(
            EntityBindingIssue(
                EntityBindingStatus.PREBOUND_CONFLICT,
                node.target,
                node.node_id,
                node.expected_type,
                candidate.entity_type,
            )
        )
    return node


def _candidate_tuple(
    value: EntityBindingCandidate | tuple[EntityBindingCandidate, ...],
) -> tuple[EntityBindingCandidate, ...]:
    if isinstance(value, EntityBindingCandidate):
        return (value,)
    if isinstance(value, tuple):
        for candidate in value:
            if not isinstance(candidate, EntityBindingCandidate):
                raise ValueError("binding candidates must be EntityBindingCandidate values")
        return value
    raise ValueError("binding value must be an EntityBindingCandidate or tuple of candidates")


def _require_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value
