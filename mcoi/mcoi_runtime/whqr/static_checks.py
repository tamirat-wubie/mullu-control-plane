"""Purpose: static validation for WHQR trees before governance adoption.
Governance scope: reject unresolved role coverage gaps, invalid negation scope, causal or temporal cycles, duplicate node ids, quantifier gaps, modality conflicts, and side-effect targets.
Dependencies: WHQR contracts and connector compiler.
Invariants: static checks are pure and report all detected issue classes once.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from mcoi_runtime.contracts.whqr import (
    ADVERB_THRESHOLDS,
    Adverb,
    Connector,
    ConnectorExpr,
    LogicalExpr,
    LogicalOp,
    Quantifier,
    WHQRExpr,
    WHQRNode,
    WHRole,
)
from mcoi_runtime.whqr.connectors import AssertionKind, compile_connector


_SIDE_EFFECT_TERMS = frozenset({
    "call",
    "delete",
    "execute",
    "mutate",
    "pay",
    "run",
    "send",
    "shell",
    "write",
})


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
    temporal_edges: set[tuple[str, str]] = set()
    node_ids: set[str] = set()
    modalities: dict[str, list[tuple[Adverb, str]]] = {}
    _walk(expr, roles, causal_edges, temporal_edges, node_ids, modalities, issues)
    for role in required_roles:
        if role not in roles:
            issues.append(StaticCheckIssue("missing_role", f"required WHQR role missing: {role.value}", role.value))
    if _has_cycle(causal_edges):
        issues.append(StaticCheckIssue("causal_cycle", "causal relation creates a cycle"))
    if _has_cycle(temporal_edges):
        issues.append(StaticCheckIssue("temporal_cycle", "temporal relation creates a cycle"))
    _append_modality_conflicts(modalities, issues)
    return StaticCheckReport(passed=not issues, issues=tuple(issues))


def _walk(
    expr: WHQRExpr,
    roles: set[WHRole],
    causal_edges: set[tuple[str, str]],
    temporal_edges: set[tuple[str, str]],
    node_ids: set[str],
    modalities: dict[str, list[tuple[Adverb, str]]],
    issues: list[StaticCheckIssue],
) -> None:
    if isinstance(expr, WHQRNode):
        roles.add(expr.role)
        if expr.node_id is not None:
            if expr.node_id in node_ids:
                issues.append(StaticCheckIssue("duplicate_node_id", "WHQR node_id values must be unique", expr.node_id))
            node_ids.add(expr.node_id)
        if _has_side_effect_target(expr.target):
            issues.append(StaticCheckIssue("side_effect_target", "WHQR nodes may not encode side-effect actions", expr.target))
        if expr.quantifier is Quantifier.AT_LEAST_N:
            _validate_at_least_n(expr, issues)
        if expr.modality is not None:
            modalities.setdefault(_modality_key(expr), []).append((expr.modality, expr.node_id or expr.target))
        return
    if isinstance(expr, LogicalExpr):
        _validate_logical_arity(expr, issues)
        if expr.op is LogicalOp.NOT and any(isinstance(arg, WHQRNode) for arg in expr.args):
            issues.append(StaticCheckIssue("negated_unresolved_node", "negation cannot apply directly to unresolved WHQR nodes"))
        for arg in expr.args:
            _walk(arg, roles, causal_edges, temporal_edges, node_ids, modalities, issues)
        return
    if isinstance(expr, ConnectorExpr):
        compiled = compile_connector(expr)
        if compiled.assertion.kind is AssertionKind.CAUSAL:
            causal_edges.add((_target(compiled.assertion.source), _target(compiled.assertion.target)))
        if compiled.assertion.kind is AssertionKind.TEMPORAL:
            edge = _temporal_edge(compiled.assertion.relation, compiled.assertion.source, compiled.assertion.target)
            if edge is not None:
                temporal_edges.add(edge)
        _walk(expr.left, roles, causal_edges, temporal_edges, node_ids, modalities, issues)
        _walk(expr.right, roles, causal_edges, temporal_edges, node_ids, modalities, issues)


def _target(expr: WHQRExpr) -> str:
    if isinstance(expr, WHQRNode):
        return expr.node_id or expr.target
    return repr(expr)


def _temporal_edge(relation: str, source: WHQRExpr, target: WHQRExpr) -> tuple[str, str] | None:
    if relation in {"before", "until"}:
        return (_target(source), _target(target))
    if relation == "after":
        return (_target(target), _target(source))
    return None


def _validate_at_least_n(node: WHQRNode, issues: list[StaticCheckIssue]) -> None:
    if "n" not in node.metadata:
        issues.append(StaticCheckIssue("missing_quantifier_bound", "at_least_n requires metadata['n']", node.node_id or node.target))
        return
    value = node.metadata["n"]
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        issues.append(StaticCheckIssue("invalid_quantifier_bound", "at_least_n metadata['n'] must be a positive integer", node.node_id or node.target))


def _validate_logical_arity(expr: LogicalExpr, issues: list[StaticCheckIssue]) -> None:
    if expr.op is LogicalOp.IMPLIES and len(expr.args) != 2:
        issues.append(
            StaticCheckIssue(
                "invalid_logical_arity",
                "implies requires exactly two WHQR expressions",
                f"{expr.op.value}:{len(expr.args)}",
            )
        )
        return
    if expr.op is LogicalOp.NOT and len(expr.args) != 1:
        issues.append(
            StaticCheckIssue(
                "invalid_logical_arity",
                "not requires exactly one WHQR expression",
                f"{expr.op.value}:{len(expr.args)}",
            )
        )
        return
    if expr.op in {LogicalOp.AND, LogicalOp.OR, LogicalOp.IFF, LogicalOp.XOR} and len(expr.args) < 2:
        issues.append(
            StaticCheckIssue(
                "invalid_logical_arity",
                f"{expr.op.value} requires at least two WHQR expressions",
                f"{expr.op.value}:{len(expr.args)}",
            )
        )


def _modality_key(node: WHQRNode) -> str:
    return f"{node.role.value}:{node.target}"


def _append_modality_conflicts(
    modalities: dict[str, list[tuple[Adverb, str]]],
    issues: list[StaticCheckIssue],
) -> None:
    for entries in modalities.values():
        for index, left in enumerate(entries):
            for right in entries[index + 1:]:
                if _ranges_disjoint(ADVERB_THRESHOLDS[left[0]], ADVERB_THRESHOLDS[right[0]]):
                    issues.append(
                        StaticCheckIssue(
                            "modality_conflict",
                            f"WHQR modality ranges conflict: {left[0].value} vs {right[0].value}",
                            f"{left[1]}|{right[1]}",
                        )
                    )


def _ranges_disjoint(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return left[1] < right[0] or right[1] < left[0]


def _has_side_effect_target(target: str) -> bool:
    terms = _target_terms(target)
    return any(term in _SIDE_EFFECT_TERMS for term in terms)


def _target_terms(target: str) -> tuple[str, ...]:
    camel_bounded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", target)
    acronym_bounded = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", camel_bounded)
    return tuple(term.lower() for term in re.split(r"[^A-Za-z0-9]+", acronym_bounded) if term)


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
