"""Purpose: validate WHQR binding readiness before goal and MIL compilation.
Governance scope: block typed WHQR nodes with unresolved entity or evidence references from governed execution.
Dependencies: dataclasses and WHQR contracts.
Invariants: preflight is pure, traverses complete WHQR trees, preserves input expressions, and reports every binding gap explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts.whqr import ConnectorExpr, LogicalExpr, WHQRExpr, WHQRNode


@dataclass(frozen=True, slots=True)
class BindingPreflightIssue:
    code: str
    message: str
    target: str
    node_id: str | None = None
    expected_type: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.code, "code")
        _require_text(self.message, "message")
        _require_text(self.target, "target")
        if self.node_id is not None:
            _require_text(self.node_id, "node_id")
        if self.expected_type is not None:
            _require_text(self.expected_type, "expected_type")


@dataclass(frozen=True, slots=True)
class BindingPreflightReport:
    issues: tuple[BindingPreflightIssue, ...]

    @property
    def passed(self) -> bool:
        return not self.issues


def validate_binding_preflight(expr: WHQRExpr) -> BindingPreflightReport:
    """Return binding issues that must be resolved before WHQR can compile to MIL."""
    issues: list[BindingPreflightIssue] = []
    _visit_expr(expr, issues)
    return BindingPreflightReport(tuple(issues))


def _visit_expr(expr: WHQRExpr, issues: list[BindingPreflightIssue]) -> None:
    if isinstance(expr, WHQRNode):
        _visit_node(expr, issues)
        return
    if isinstance(expr, LogicalExpr):
        for arg in expr.args:
            _visit_expr(arg, issues)
        return
    if isinstance(expr, ConnectorExpr):
        _visit_expr(expr.left, issues)
        _visit_expr(expr.right, issues)
        return
    raise ValueError("expr must be a WHQR expression")


def _visit_node(node: WHQRNode, issues: list[BindingPreflightIssue]) -> None:
    entity_bound = node.entity_ref is not None
    evidence_bound = node.evidence_ref is not None
    binding_required = node.expected_type is not None or entity_bound or evidence_bound
    if not binding_required:
        return
    if not entity_bound:
        issues.append(
            BindingPreflightIssue(
                "missing_entity_ref",
                "typed WHQR node must bind to an entity reference before MIL compilation",
                node.target,
                node.node_id,
                node.expected_type,
            )
        )
    if not evidence_bound:
        issues.append(
            BindingPreflightIssue(
                "missing_evidence_ref",
                "typed WHQR node must bind to an evidence reference before MIL compilation",
                node.target,
                node.node_id,
                node.expected_type,
            )
        )


def _require_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value
