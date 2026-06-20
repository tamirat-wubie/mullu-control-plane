"""Purpose: pure WHQR semantic evaluator.
Governance scope: resolve WHQR trees to split gate results before policy or MIL execution.
Dependencies: WHQR contracts and runtime invariant errors.
Invariants: no side effects, no tool calls, unresolved negation fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from mcoi_runtime.contracts.whqr import ConnectorExpr, EvidenceGate, GateResult, LogicalExpr, LogicalOp, NormGate, TruthGate, WHQRExpr, WHQRNode
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


_INVALID_LOGICAL_ARITY_REASONS: Mapping[LogicalOp, str] = {
    LogicalOp.AND: "invalid_logical_arity:and",
    LogicalOp.OR: "invalid_logical_arity:or",
    LogicalOp.IMPLIES: "invalid_logical_arity:implies",
    LogicalOp.IFF: "invalid_logical_arity:iff",
    LogicalOp.XOR: "invalid_logical_arity:xor",
}


def _validate_node_result_key(key: object) -> str:
    if not isinstance(key, str):
        raise ValueError("WHQR evaluation context node result key must be a string")
    if not key.strip():
        raise ValueError("WHQR evaluation context node result key cannot be blank")
    return key


def _snapshot_gate_result(value: GateResult) -> GateResult:
    return GateResult(
        truth=value.truth,
        norm=value.norm,
        evidence=value.evidence,
        reason=value.reason,
        metadata=value.metadata,
    )


@dataclass(frozen=True, slots=True)
class WHQREvaluationContext:
    node_results: Mapping[str, GateResult] = field(default_factory=dict)

    def __init__(self, node_results: Mapping[str, GateResult] | None = None, bindings: Mapping[str, GateResult] | None = None) -> None:
        if node_results is not None and bindings is not None:
            raise ValueError("WHQR evaluation context accepts node_results or bindings, not both")
        source = node_results if node_results is not None else bindings
        frozen_node_results: dict[str, GateResult] = {}
        if source is not None:
            validated_pairs: list[tuple[str, GateResult]] = []
            for key, value in source.items():
                validated_key = _validate_node_result_key(key)
                if not isinstance(value, GateResult):
                    raise ValueError("WHQR evaluation context node result value must be GateResult")
                validated_pairs.append((validated_key, _snapshot_gate_result(value)))
            for validated_key, value in sorted(validated_pairs):
                frozen_node_results[validated_key] = value
        object.__setattr__(self, "node_results", MappingProxyType(frozen_node_results))

    @property
    def bindings(self) -> Mapping[str, GateResult]:
        return self.node_results


def evaluate(expr: WHQRExpr, context: WHQREvaluationContext | None = None) -> GateResult:
    ctx = context or WHQREvaluationContext()
    if isinstance(expr, WHQRNode):
        return ctx.node_results.get(expr.target, GateResult(TruthGate.UNKNOWN, evidence=EvidenceGate.UNPROVEN, reason="unresolved_whqr_node", metadata={"role": expr.role.value, "target": expr.target}))
    if isinstance(expr, ConnectorExpr):
        return _and(evaluate(expr.left, ctx), evaluate(expr.right, ctx), expr.connector.value, {"connector": expr.connector.value})
    if isinstance(expr, LogicalExpr):
        return _logical(expr, ctx)
    raise RuntimeCoreInvariantError("unsupported WHQR expression")


def _logical(expr: LogicalExpr, context: WHQREvaluationContext) -> GateResult:
    args = tuple(expr.args)
    if expr.op is LogicalOp.NOT:
        if len(args) != 1:
            raise RuntimeCoreInvariantError("not requires exactly one WHQR argument")
        value = evaluate(args[0], context)
        if value.truth is TruthGate.UNKNOWN:
            raise RuntimeCoreInvariantError("not cannot apply to unresolved WHQR expression")
        return GateResult(TruthGate.FALSE if value.truth is TruthGate.TRUE else TruthGate.TRUE, value.norm, value.evidence, value.reason)
    arity_issue = _logical_arity_issue(expr.op, len(args))
    if arity_issue is not None:
        return _invalid_logical_arity(arity_issue)
    values = tuple(evaluate(arg, context) for arg in args)
    if expr.op is LogicalOp.AND:
        result = values[0]
        for value in values[1:]:
            result = _and(result, value, "and")
        return result
    if expr.op is LogicalOp.OR:
        true_values = tuple(value for value in values if value.truth is TruthGate.TRUE)
        if true_values:
            proven_true_values = tuple(value for value in true_values if value.evidence is EvidenceGate.PROVEN)
            evidence_values = proven_true_values or true_values
            return GateResult(TruthGate.TRUE, _norm(true_values), _evidence(evidence_values), _reasons(evidence_values))
        if all(value.truth is TruthGate.FALSE for value in values):
            return GateResult(TruthGate.FALSE, _norm(values), _evidence(values), _reasons(values))
        return GateResult(TruthGate.UNKNOWN, _norm(values), _evidence(values), _reasons(values))
    if expr.op is LogicalOp.IMPLIES:
        antecedent, consequent = values
        if antecedent.truth is TruthGate.TRUE and consequent.truth is TruthGate.FALSE:
            return GateResult(TruthGate.FALSE, _norm(values), _evidence(values), _reasons(values))
        if antecedent.truth is TruthGate.UNKNOWN or consequent.truth is TruthGate.UNKNOWN:
            return GateResult(TruthGate.UNKNOWN, _norm(values), _evidence(values), _reasons(values))
        return GateResult(TruthGate.TRUE, _norm(values), _evidence(values), _reasons(values))
    if expr.op is LogicalOp.IFF:
        if any(value.truth is TruthGate.UNKNOWN for value in values):
            return GateResult(TruthGate.UNKNOWN, _norm(values), _evidence(values), _reasons(values))
        first_truth = values[0].truth
        truth = TruthGate.TRUE if all(value.truth is first_truth for value in values) else TruthGate.FALSE
        return GateResult(truth, _norm(values), _evidence(values), _reasons(values))
    if expr.op is LogicalOp.XOR:
        true_count = sum(1 for value in values if value.truth is TruthGate.TRUE)
        unknown_count = sum(1 for value in values if value.truth is TruthGate.UNKNOWN)
        if true_count > 1:
            return GateResult(TruthGate.FALSE, _norm(values), _evidence(values), _reasons(values))
        if unknown_count:
            return GateResult(TruthGate.UNKNOWN, _norm(values), _evidence(values), _reasons(values))
        truth = TruthGate.TRUE if true_count == 1 else TruthGate.FALSE
        return GateResult(truth, _norm(values), _evidence(values), _reasons(values))
    return GateResult(TruthGate.UNKNOWN, _norm(values), _evidence(values), f"unsupported_logical:{expr.op.value}")


def _logical_arity_issue(op: LogicalOp, arg_count: int) -> str | None:
    if op is LogicalOp.IMPLIES and arg_count != 2:
        return _INVALID_LOGICAL_ARITY_REASONS[op]
    if op in {LogicalOp.AND, LogicalOp.OR, LogicalOp.IFF, LogicalOp.XOR} and arg_count < 2:
        return _INVALID_LOGICAL_ARITY_REASONS[op]
    return None


def _invalid_logical_arity(reason: str) -> GateResult:
    return GateResult(
        TruthGate.UNKNOWN,
        evidence=EvidenceGate.UNPROVEN,
        reason=reason,
    )


def _and(left: GateResult, right: GateResult, relation: str, metadata: Mapping[str, str] | None = None) -> GateResult:
    if TruthGate.FALSE in (left.truth, right.truth):
        truth = TruthGate.FALSE
    elif TruthGate.UNKNOWN in (left.truth, right.truth):
        truth = TruthGate.UNKNOWN
    else:
        truth = TruthGate.TRUE
    return GateResult(truth, _norm((left, right)), _evidence((left, right)), _reasons((left, right), relation), metadata=metadata or {})


def _norm(values: tuple[GateResult, ...]) -> NormGate | None:
    norms = tuple(value.norm for value in values if value.norm is not None)
    if NormGate.FORBIDDEN in norms:
        return NormGate.FORBIDDEN
    if NormGate.REQUIRES_APPROVAL in norms:
        return NormGate.REQUIRES_APPROVAL
    if NormGate.ESCALATE in norms:
        return NormGate.ESCALATE
    if NormGate.PERMITTED in norms:
        return NormGate.PERMITTED
    return None


def _evidence(values: tuple[GateResult, ...]) -> EvidenceGate | None:
    evidences = tuple(value.evidence for value in values if value.evidence is not None)
    for gate in (EvidenceGate.CONTRADICTED, EvidenceGate.FORBIDDEN_UNKNOWN, EvidenceGate.BUDGET_UNKNOWN, EvidenceGate.STALE, EvidenceGate.UNPROVEN, EvidenceGate.PROVEN):
        if gate in evidences:
            return gate
    return None


def _reasons(values: tuple[GateResult, ...], relation: str = "logical") -> str | None:
    reasons = tuple(value.reason for value in values if value.reason)
    if not reasons:
        return None
    return f"{relation}:" + ";".join(reasons)
