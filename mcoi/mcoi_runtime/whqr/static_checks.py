"""Purpose: static validation for WHQR trees before governance adoption.
Governance scope: reject unresolved role coverage gaps, invalid negation scope, and causal cycles.
Dependencies: WHQR contracts and connector compiler.
Invariants: static checks are pure and report all detected issue classes once.
"""

from __future__ import annotations

from dataclasses import dataclass

from mcoi_runtime.contracts.whqr import Connector, ConnectorExpr, LogicalExpr, LogicalOp, WHQRExpr, WHQRNode, WHRole
from mcoi_runtime.whqr.connectors import AssertionKind, compile_connector


@dataclass(frozen=True, slots=True)
class StaticCheckIssue:
    code: str
    message: str
    target: str | None = None


@dataclass(frozen=True, slots=True)
class StaticCheckReport:
    passed: bool
    issues: tuple[StaticCheckIssue, ...]


def validate_static(expr: WHQRExpr, required_roles: tuple[WHRole, ...] = ()) -> StaticCheckReport:
    issues: list[StaticCheckIssue] = []
    roles: set[WHRole] = set()
    causal_edges: set[tuple[str, str]] = set()
    _walk(expr, roles, causal_edges, issues)
    for role in required_roles:
        if role not in roles:
            issues.append(StaticCheckIssue("missing_role", f"required WHQR role missing: {role.value}", role.value))
    if _has_cycle(causal_edges):
        issues.append(StaticCheckIssue("causal_cycle", "causal relation creates a cycle"))
    return StaticCheckReport(passed=not issues, issues=tuple(issues))


def _walk(expr: WHQRExpr, roles: set[WHRole], causal_edges: set[tuple[str, str]], issues: list[StaticCheckIssue]) -> None:
    if isinstance(expr, WHQRNode):
        roles.add(expr.role)
        return
    if isinstance(expr, LogicalExpr):
        if expr.op is LogicalOp.NOT and any(isinstance(arg, WHQRNode) for arg in expr.args):
            issues.append(StaticCheckIssue("negated_unresolved_node", "negation cannot apply directly to unresolved WHQR nodes"))
        for arg in expr.args:
            _walk(arg, roles, causal_edges, issues)
        return
    if isinstance(expr, ConnectorExpr):
        if expr.connector in {Connector.BECAUSE, Connector.THEREFORE}:
            compiled = compile_connector(expr)
            if compiled.assertion.kind is AssertionKind.CAUSAL:
                causal_edges.add((_target(compiled.assertion.source), _target(compiled.assertion.target)))
        _walk(expr.left, roles, causal_edges, issues)
        _walk(expr.right, roles, causal_edges, issues)


def _target(expr: WHQRExpr) -> str:
    if isinstance(expr, WHQRNode):
        return expr.target
    return repr(expr)


def _has_cycle(edges: set[tuple[str, str]]) -> bool:
    adjacency: dict[str, set[str]] = {}
    for source, target in edges:
        if source == target:
            return True
        adjacency.setdefault(source, set()).add(target)
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in adjacency.get(node, set()):
            if visit(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False
    return any(visit(node) for node in adjacency)
