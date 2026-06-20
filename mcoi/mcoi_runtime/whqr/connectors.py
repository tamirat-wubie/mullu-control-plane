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
    SEMANTICS_HASH,
    WHQRDocument,
    WHQRExpr,
    WHQRNode,
    WHQR_VERSION,
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

    @classmethod
    def from_canonical_json(
        cls,
        payload: str,
        *,
        expected_canonical_hash: str | None = None,
    ) -> SemanticAssertion:
        text = _require_nonblank_text(payload, "payload")
        try:
            assertion_payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("connector assertion canonical JSON payload must be valid JSON") from exc
        assertion_map = _require_mapping_payload(assertion_payload, "payload")
        _require_allowed_keys(
            assertion_map,
            "payload",
            {"kind", "relation", "source", "source_hash", "target", "target_hash"},
        )
        assertion = cls(
            kind=_assertion_kind_from_payload(assertion_map.get("kind"), "payload.kind"),
            relation=_require_nonblank_text(assertion_map.get("relation"), "payload.relation"),
            source=_expr_from_canonical_payload(
                assertion_map.get("source"),
                "payload.source",
                _require_sha256_ref(assertion_map.get("source_hash"), "payload.source_hash"),
            ),
            target=_expr_from_canonical_payload(
                assertion_map.get("target"),
                "payload.target",
                _require_sha256_ref(assertion_map.get("target_hash"), "payload.target_hash"),
            ),
        )
        if assertion.canonical_json() != text:
            raise ValueError("connector assertion replay payload must match deterministic canonical JSON")
        assertion.verify_replay(expected_canonical_hash=expected_canonical_hash)
        return assertion

    def verify_replay(self, *, expected_canonical_hash: str | None = None) -> str:
        canonical_hash = self.canonical_hash()
        if expected_canonical_hash is not None:
            expected = _require_sha256_ref(expected_canonical_hash, "expected_canonical_hash")
            if canonical_hash != expected:
                raise ValueError("connector assertion replay canonical hash mismatch")
        return canonical_hash


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

    @classmethod
    def from_canonical_json(
        cls,
        payload: str,
        *,
        expected_canonical_hash: str | None = None,
    ) -> ConnectorCompilation:
        text = _require_nonblank_text(payload, "payload")
        try:
            compilation_payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("connector compilation canonical JSON payload must be valid JSON") from exc
        compilation_map = _require_mapping_payload(compilation_payload, "payload")
        _require_allowed_keys(compilation_map, "payload", {"logical", "logical_hash", "assertions"})
        assertions_payload = compilation_map.get("assertions")
        if not isinstance(assertions_payload, list):
            raise ValueError("payload.assertions must be a list")
        if not assertions_payload:
            raise ValueError("payload.assertions must contain at least one semantic assertion")
        compilation = cls(
            logical=_logical_from_canonical_payload(
                compilation_map.get("logical"),
                "payload.logical",
                _require_sha256_ref(compilation_map.get("logical_hash"), "payload.logical_hash"),
            ),
            assertions=tuple(
                SemanticAssertion.from_canonical_json(_canonical_json(_require_mapping_payload(item, "payload.assertions")))
                for item in assertions_payload
            ),
        )
        if compilation.canonical_json() != text:
            raise ValueError("connector compilation replay payload must match deterministic canonical JSON")
        compilation.verify_replay(expected_canonical_hash=expected_canonical_hash)
        return compilation

    def verify_replay(self, *, expected_canonical_hash: str | None = None) -> str:
        canonical_hash = self.canonical_hash()
        if expected_canonical_hash is not None:
            expected = _require_sha256_ref(expected_canonical_hash, "expected_canonical_hash")
            if canonical_hash != expected:
                raise ValueError("connector compilation replay canonical hash mismatch")
        return canonical_hash


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


def _require_mapping_payload(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _require_allowed_keys(payload: Mapping[str, object], name: str, allowed_keys: set[str]) -> None:
    unknown_keys = sorted(set(payload) - allowed_keys)
    if unknown_keys:
        raise ValueError(f"{name} contains unknown fields")
    missing_keys = sorted(allowed_keys - set(payload))
    if missing_keys:
        raise ValueError(f"{name} is missing required fields")


def _require_sha256_ref(value: object, name: str) -> str:
    text = _require_nonblank_text(value, name)
    digest = text.removeprefix("sha256:")
    if text == digest or len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"{name} must be sha256:<64 lowercase hex>")
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


def _expr_from_canonical_payload(payload: object, name: str, expected_canonical_hash: str) -> WHQRExpr:
    document = WHQRDocument.from_canonical_json(
        _canonical_json(
            {
                "root": _require_mapping_payload(payload, name),
                "semantics_hash": SEMANTICS_HASH,
                "whqr_version": WHQR_VERSION,
            }
        ),
        expected_canonical_hash=expected_canonical_hash,
    )
    return document.root


def _logical_from_canonical_payload(payload: object, name: str, expected_canonical_hash: str) -> LogicalExpr:
    expr = _expr_from_canonical_payload(payload, name, expected_canonical_hash)
    if not isinstance(expr, LogicalExpr):
        raise ValueError(f"{name} must be a LogicalExpr value")
    return expr


def _assertion_kind_from_payload(value: object, name: str) -> AssertionKind:
    text = _require_nonblank_text(value, name)
    try:
        return AssertionKind(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be an AssertionKind value") from exc


def _canonical_json(payload: Mapping[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256_ref(payload: str) -> str:
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
