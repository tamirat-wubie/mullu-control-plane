"""Purpose: compile WHQR connectors into explicit logical and semantic assertions.
Governance scope: reveal causal, temporal, conditional, and concessive relations before policy execution.
Dependencies: WHQR contracts.
Invariants: connectors do not execute effects; because always emits a causal assertion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mcoi_runtime.contracts.whqr import Connector, ConnectorExpr, LogicalExpr, LogicalOp, WHQRExpr


class AssertionKind(StrEnum):
    CAUSAL = "causal"
    TEMPORAL = "temporal"
    CONDITIONAL = "conditional"
    CONCESSIVE = "concessive"


@dataclass(frozen=True, slots=True)
class SemanticAssertion:
    kind: AssertionKind
    relation: str
    source: WHQRExpr
    target: WHQRExpr


@dataclass(frozen=True, slots=True)
class ConnectorCompilation:
    logical: LogicalExpr
    assertions: tuple[SemanticAssertion, ...]

    @property
    def assertion(self) -> SemanticAssertion:
        return self.assertions[0]


def compile_connector(expr: ConnectorExpr) -> ConnectorCompilation:
    assertion = _assertion(expr)
    logical_op = LogicalOp.IMPLIES if expr.connector is Connector.UNLESS else LogicalOp.AND
    logical_args: tuple[WHQRExpr, ...]
    if expr.connector is Connector.UNLESS:
        logical_args = (LogicalExpr(op=LogicalOp.NOT, args=(expr.right,)), expr.left)
    else:
        logical_args = (expr.left, expr.right)
    return ConnectorCompilation(logical=LogicalExpr(op=logical_op, args=logical_args), assertions=(assertion,))


def _assertion(expr: ConnectorExpr) -> SemanticAssertion:
    if expr.connector is Connector.BECAUSE:
        return SemanticAssertion(AssertionKind.CAUSAL, "cause", expr.right, expr.left)
    if expr.connector is Connector.THEREFORE:
        return SemanticAssertion(AssertionKind.CAUSAL, "supports_conclusion", expr.left, expr.right)
    if expr.connector in {Connector.BEFORE, Connector.AFTER, Connector.UNTIL, Connector.WHILE}:
        return SemanticAssertion(AssertionKind.TEMPORAL, expr.connector.value, expr.left, expr.right)
    if expr.connector in {Connector.UNLESS, Connector.GIVEN, Connector.ASSUMING}:
        return SemanticAssertion(AssertionKind.CONDITIONAL, expr.connector.value, expr.left, expr.right)
    return SemanticAssertion(AssertionKind.CONCESSIVE, expr.connector.value, expr.left, expr.right)
