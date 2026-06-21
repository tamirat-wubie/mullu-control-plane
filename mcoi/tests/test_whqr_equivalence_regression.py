from __future__ import annotations

from mcoi_runtime.contracts.whqr import LogicalExpr, LogicalOp, WHQRNode, WHRole
from mcoi_runtime.whqr.equivalence import normalize_expr, normalize_with_trace, semantic_fingerprint


def _node(target: str, role: WHRole = WHRole.WHAT) -> WHQRNode:
    return WHQRNode(role=role, target=target)


def test_whqr_semantic_normalization_is_idempotent_after_first_pass() -> None:
    nested = LogicalExpr(
        op=LogicalOp.OR,
        args=(
            _node("invoice_due"),
            LogicalExpr(op=LogicalOp.OR, args=(_node("approval_valid"), _node("budget_available"))),
        ),
    )

    first = normalize_with_trace(nested)
    second = normalize_with_trace(first.expr)

    assert first.steps
    assert second.steps == ()
    assert second.expr == first.expr
    assert normalize_expr(second.expr) == first.expr
    assert semantic_fingerprint(nested) == semantic_fingerprint(first.expr)
    assert semantic_fingerprint(first.expr) == semantic_fingerprint(second.expr)


def test_whqr_semantic_normalization_keeps_iff_non_associative() -> None:
    nested = LogicalExpr(
        op=LogicalOp.IFF,
        args=(
            _node("approval_valid"),
            LogicalExpr(op=LogicalOp.IFF, args=(_node("budget_available"), _node("invoice_due"))),
        ),
    )
    flattened = LogicalExpr(
        op=LogicalOp.IFF,
        args=(_node("approval_valid"), _node("budget_available"), _node("invoice_due")),
    )

    normalized = normalize_expr(nested)

    assert isinstance(normalized, LogicalExpr)
    assert normalized.op == LogicalOp.IFF
    assert len(normalized.args) == 2
    assert any(isinstance(arg, LogicalExpr) and arg.op == LogicalOp.IFF for arg in normalized.args)
    assert semantic_fingerprint(nested) != semantic_fingerprint(flattened)


def test_whqr_semantic_normalization_does_not_reorder_not_operand() -> None:
    expression = LogicalExpr(op=LogicalOp.NOT, args=(_node("approval_valid"),))

    normalized = normalize_expr(expression)
    trace = normalize_with_trace(expression)

    assert normalized == expression
    assert trace.steps == ()
    assert semantic_fingerprint(expression) == semantic_fingerprint(normalized)
