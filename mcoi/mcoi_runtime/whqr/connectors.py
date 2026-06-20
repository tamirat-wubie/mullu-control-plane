"""Purpose: compile WHQR connectors into explicit logical and semantic assertions.
Governance scope: reveal causal, temporal, conditional, and concessive relations before policy execution.
Dependencies: WHQR contracts.
Invariants: connectors do not execute effects; because always emits a causal assertion.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from mcoi_runtime.contracts.whqr import (
    Connector,
    ConnectorExpr,
    LogicalExpr,
    LogicalOp,
    WHQRDocument,
    WHQRExpr,
    WHQRNode,
)


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

    def __post_init__(self) -> None:
        if not isinstance(self.kind, AssertionKind):
            raise ValueError("kind must be an AssertionKind value")
        object.__setattr__(self, "relation", _require_nonblank_text(self.relation, "relation"))
        _require_whqr_replay_expr(self.source, "source")
        _require_whqr_replay_expr(self.target, "target")

    def canonical_payload(self) -> Mapping[str, object]:
        return {
            "kind": self.kind.value,
            "relation": self.relation,
            "source": _canonical_expr_payload(self.source),
            "source_hash": WHQRDocument(root=self.source).canonical_hash(),
            "target": _canonical_expr_payload(self.target),
            "target_hash": WHQRDocument(root=self.target).canonical_hash(),
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_payload())

    def canonical_hash(self) -> str:
        return _sha256_ref(self.canonical_json())


@dataclass(frozen=True, slots=True)
class ConnectorCompilation:
    logical: LogicalExpr
    assertions: tuple[SemanticAssertion, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.logical, LogicalExpr):
            raise ValueError("logical must be a LogicalExpr value")
        WHQRDocument(root=self.logical).verify_semantics()
        if not isinstance(self.assertions, tuple):
            raise ValueError("assertions must be an immutable tuple")
        if not self.assertions:
            raise ValueError("assertions must contain at least one semantic assertion")
        for assertion in self.assertions:
            if not isinstance(assertion, SemanticAssertion):
                raise ValueError("assertions must contain only semantic assertions")

    @property
    def assertion(self) -> SemanticAssertion:
        return self.assertions[0]

    def canonical_payload(self) -> Mapping[str, object]:
        return {
            "logical": _canonical_expr_payload(self.logical),
            "logical_hash": WHQRDocument(root=self.logical).canonical_hash(),
            "assertions": tuple(assertion.canonical_payload() for assertion in self.assertions),
        }

    def canonical_json(self) -> str:
        return _canonical_json(self.canonical_payload())

    def canonical_hash(self) -> str:
        return _sha256_ref(self.canonical_json())


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


def _require_nonblank_text(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    text = value.strip()
    if not text:
        raise ValueError(f"{name} must not be blank")
    return text


def _require_whqr_replay_expr(value: object, name: str) -> WHQRExpr:
    if not isinstance(value, (WHQRNode, LogicalExpr, ConnectorExpr)):
        raise ValueError(f"{name} must be a WHQR expression")
    try:
        WHQRDocument(root=value).verify_semantics()
    except ValueError as exc:
        raise ValueError(f"{name} must pass WHQR replay semantics") from exc
    return value


def _canonical_expr_payload(expr: WHQRExpr) -> Mapping[str, object]:
    document_payload = json.loads(WHQRDocument(root=expr).canonical_json())
    return document_payload["root"]


def _canonical_json(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_ref(payload: str) -> str:
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
