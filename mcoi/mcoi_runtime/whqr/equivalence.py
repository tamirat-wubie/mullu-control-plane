"""Purpose: compare WHQR expressions for deterministic semantic replay equivalence.
Governance scope: detect replay drift before governed planning or execution consumes rewritten WHQR trees.
Dependencies: WHQR contracts, canonical serialization, and hashing.
Invariants: equivalence checks are pure; connector direction is preserved; commutative logical order is normalized only where declared.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from mcoi_runtime.contracts.whqr import ConnectorExpr, LogicalExpr, LogicalOp, WHQRDocument, WHQRExpr, WHQRNode


COMMUTATIVE_LOGICAL_OPS = frozenset({LogicalOp.AND, LogicalOp.OR, LogicalOp.IFF, LogicalOp.XOR})
ASSOCIATIVE_LOGICAL_OPS = frozenset({LogicalOp.AND, LogicalOp.OR, LogicalOp.XOR})


@dataclass(frozen=True, slots=True)
class NormalizationStep:
    rule: str
    before_hash: str
    after_hash: str


@dataclass(frozen=True, slots=True)
class NormalizationResult:
    expr: WHQRExpr
    steps: tuple[NormalizationStep, ...]


def normalize_expr(expr: WHQRExpr) -> WHQRExpr:
    """Return the canonical semantic form of a WHQR expression."""
    return normalize_with_trace(expr).expr


def normalize_with_trace(expr: WHQRExpr) -> NormalizationResult:
    """Return a normalized expression and deterministic normalization evidence."""
    try:
        WHQRDocument(root=expr).verify_semantics()
    except ValueError as exc:
        raise ValueError("WHQR replay expression must pass semantic validation") from exc
    normalized, steps = _normalize(expr)
    return NormalizationResult(expr=normalized, steps=tuple(steps))


def semantic_fingerprint(expr: WHQRExpr) -> str:
    """Return a stable semantic fingerprint after allowed normalization."""
    normalized = normalize_expr(expr)
    payload = WHQRDocument(root=normalized).canonical_json()
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assert_replay_equivalent(original: WHQRExpr, replayed: WHQRExpr) -> str:
    """Verify that replayed WHQR meaning matches the original after allowed normalization."""
    original_fingerprint = semantic_fingerprint(original)
    replayed_fingerprint = semantic_fingerprint(replayed)
    if original_fingerprint != replayed_fingerprint:
        raise ValueError("WHQR replay semantic fingerprint mismatch")
    return original_fingerprint


def _normalize(expr: WHQRExpr) -> tuple[WHQRExpr, list[NormalizationStep]]:
    if isinstance(expr, WHQRNode):
        return expr, []
    if isinstance(expr, ConnectorExpr):
        left, left_steps = _normalize(expr.left)
        right, right_steps = _normalize(expr.right)
        normalized = ConnectorExpr(connector=expr.connector, left=left, right=right)
        return normalized, left_steps + right_steps

    normalized_args: list[WHQRExpr] = []
    steps: list[NormalizationStep] = []
    for arg in expr.args:
        normalized_arg, arg_steps = _normalize(arg)
        steps.extend(arg_steps)
        if expr.op in ASSOCIATIVE_LOGICAL_OPS and isinstance(normalized_arg, LogicalExpr) and normalized_arg.op == expr.op:
            before_hash = _expr_hash(normalized_arg)
            normalized_args.extend(normalized_arg.args)
            after_hash = _sequence_hash(normalized_arg.args)
            steps.append(NormalizationStep("flatten_associative_logical_args", before_hash, after_hash))
        else:
            normalized_args.append(normalized_arg)

    if expr.op in COMMUTATIVE_LOGICAL_OPS:
        before_hash = _sequence_hash(tuple(normalized_args))
        normalized_args = sorted(normalized_args, key=_sort_key)
        after_hash = _sequence_hash(tuple(normalized_args))
        if before_hash != after_hash:
            steps.append(NormalizationStep("sort_commutative_logical_args", before_hash, after_hash))

    normalized = LogicalExpr(op=expr.op, args=tuple(normalized_args))
    return normalized, steps


def _sort_key(expr: WHQRExpr) -> str:
    return WHQRDocument(root=expr).canonical_json()


def _expr_hash(expr: WHQRExpr) -> str:
    return WHQRDocument(root=expr).canonical_hash()


def _sequence_hash(args: tuple[WHQRExpr, ...]) -> str:
    payload = "|".join(_expr_hash(arg) for arg in args)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
