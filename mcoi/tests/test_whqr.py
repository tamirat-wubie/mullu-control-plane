"""Purpose: verify WHQR contract, evaluator, connector compiler, and static checks.
Governance scope: side-effect-free WHQR trees, split gates, deterministic serialization, explicit connector lowering, and static validation.
Dependencies: WHQR contracts and WHQR pure helpers.
Invariants: truth is not permission; missing evidence is unknown; connectors compile to assertions; static checks catch cycles and unsafe negation.
"""

from __future__ import annotations

import json

import pytest

from mcoi_runtime.contracts.whqr import (
    ADVERB_THRESHOLDS,
    SEMANTICS_HASH,
    WHQR_VERSION,
    Adverb,
    Connector,
    ConnectorExpr,
    EvidenceGate,
    GateResult,
    LogicalExpr,
    LogicalOp,
    NormGate,
    Quantifier,
    TruthGate,
    WHQRDocument,
    WHQRNode,
    WHRole,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.whqr.connectors import AssertionKind, compile_connector
from mcoi_runtime.whqr.evaluator import WHQREvaluationContext, evaluate
from mcoi_runtime.whqr.static_checks import validate_static


def _node(target: str, role: WHRole = WHRole.WHAT) -> WHQRNode:
    return WHQRNode(role=role, target=target)


def test_contract_keeps_truth_norm_and_evidence_split() -> None:
    result = GateResult(
        truth=TruthGate.UNKNOWN,
        norm=NormGate.FORBIDDEN,
        evidence=EvidenceGate.UNPROVEN,
        reason="tenant_boundary",
    )

    assert result.truth != TruthGate.FALSE
    assert result.norm == NormGate.FORBIDDEN
    assert result.evidence == EvidenceGate.UNPROVEN
    assert result.reason == "tenant_boundary"


def test_document_semantics_are_versioned_and_canonical() -> None:
    root = ConnectorExpr(
        connector=Connector.BECAUSE,
        left=WHQRNode(
            role=WHRole.WHAT,
            target="payment_request",
            quantifier=Quantifier.EXISTS,
        ),
        right=WHQRNode(role=WHRole.WHY, target="invoice_due"),
    )
    first = WHQRDocument(root=root)
    second = WHQRDocument(root=root)

    assert first.whqr_version == WHQR_VERSION
    assert first.semantics_hash == SEMANTICS_HASH
    assert first.canonical_json() == second.canonical_json()
    assert json.loads(first.canonical_json())["root"]["connector"] == "because"
    assert first.canonical_hash() == second.canonical_hash()


def test_contract_validation_and_metadata_fail_closed() -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        WHQRNode(role=WHRole.WHO, target="")
    with pytest.raises(ValueError, match="role"):
        WHQRNode(role="who", target="actor")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-empty string"):
        GateResult(truth=TruthGate.TRUE, metadata={"": "empty"})

    assert ADVERB_THRESHOLDS[Adverb.ALWAYS][0] >= ADVERB_THRESHOLDS[Adverb.OFTEN][0]


def test_evaluator_resolves_and_preserves_gates() -> None:
    missing = evaluate(_node("approval"))
    ctx = WHQREvaluationContext(
        node_results={
            "p": GateResult(
                truth=TruthGate.TRUE,
                norm=NormGate.PERMITTED,
                evidence=EvidenceGate.PROVEN,
            ),
            "q": GateResult(truth=TruthGate.FALSE, evidence=EvidenceGate.PROVEN),
            "secret": GateResult(
                truth=TruthGate.UNKNOWN,
                norm=NormGate.FORBIDDEN,
                evidence=EvidenceGate.FORBIDDEN_UNKNOWN,
                reason="tenant_boundary",
            ),
        }
    )
    guarded = evaluate(
        LogicalExpr(op=LogicalOp.AND, args=(_node("p"), _node("secret"))),
        ctx,
    )
    denied_implication = evaluate(
        LogicalExpr(op=LogicalOp.IMPLIES, args=(_node("p"), _node("q"))),
        ctx,
    )

    assert missing.truth == TruthGate.UNKNOWN
    assert missing.reason == "unresolved_whqr_node"
    assert missing.metadata["role"] == "what"
    assert missing.metadata["target"] == "approval"
    assert guarded.truth == TruthGate.UNKNOWN
    assert guarded.norm == NormGate.FORBIDDEN
    assert denied_implication.truth == TruthGate.FALSE


def test_unresolved_negation_and_connector_behavior_are_bounded() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="not cannot apply"):
        evaluate(LogicalExpr(op=LogicalOp.NOT, args=(_node("missing"),)))
    ctx = WHQREvaluationContext(
        node_results={
            "payment_request": GateResult(truth=TruthGate.TRUE, evidence=EvidenceGate.PROVEN),
            "invoice_due": GateResult(truth=TruthGate.TRUE, evidence=EvidenceGate.PROVEN),
        }
    )
    result = evaluate(
        ConnectorExpr(
            connector=Connector.BECAUSE,
            left=_node("payment_request"),
            right=_node("invoice_due", WHRole.WHY),
        ),
        ctx,
    )

    assert result.truth == TruthGate.TRUE
    assert result.evidence == EvidenceGate.PROVEN
    assert result.metadata["connector"] == "because"


def test_because_connector_compiles_to_logical_and_causal_assertion() -> None:
    expr = ConnectorExpr(
        connector=Connector.BECAUSE,
        left=_node("payment_request"),
        right=_node("invoice_due", WHRole.WHY),
    )
    compiled = compile_connector(expr)
    assertion = compiled.assertions[0]

    assert compiled.logical.op == LogicalOp.AND
    assert compiled.logical.args == (expr.left, expr.right)
    assert assertion.kind == AssertionKind.CAUSAL
    assert assertion.relation == "cause"
    assert assertion.source == expr.right
    assert assertion.target == expr.left


def test_temporal_and_conditional_connectors_compile_to_explicit_assertions() -> None:
    before = compile_connector(
        ConnectorExpr(
            connector=Connector.BEFORE,
            left=_node("ship"),
            right=_node("invoice"),
        )
    )
    unless = compile_connector(
        ConnectorExpr(
            connector=Connector.UNLESS,
            left=_node("pay"),
            right=_node("approval_missing"),
        )
    )

    assert before.assertions[0].kind == AssertionKind.TEMPORAL
    assert before.assertions[0].relation == "before"
    assert before.logical.op == LogicalOp.AND
    assert unless.assertions[0].kind == AssertionKind.CONDITIONAL
    assert unless.logical.op == LogicalOp.IMPLIES
    assert isinstance(unless.logical.args[0], LogicalExpr)


def test_static_checks_pass_for_complete_acyclic_tree() -> None:
    expr = ConnectorExpr(
        connector=Connector.BECAUSE,
        left=_node("payment_request", WHRole.WHAT),
        right=_node("invoice_due", WHRole.WHY),
    )
    report = validate_static(expr, required_roles=(WHRole.WHAT, WHRole.WHY))

    assert report.passed
    assert report.issues == ()
    assert len(report.issues) == 0


def test_static_checks_catch_missing_role_and_negated_node() -> None:
    report = validate_static(
        LogicalExpr(op=LogicalOp.NOT, args=(_node("approval", WHRole.WHO),)),
        required_roles=(WHRole.WHY,),
    )
    issue_codes = {issue.code for issue in report.issues}

    assert not report.passed
    assert issue_codes == {"missing_role", "negated_unresolved_node"}
    assert len(report.issues) == 2


def test_static_checks_detect_causal_cycles() -> None:
    left = _node("a")
    right = _node("b")
    cycle = LogicalExpr(
        op=LogicalOp.AND,
        args=(
            ConnectorExpr(connector=Connector.BECAUSE, left=left, right=right),
            ConnectorExpr(connector=Connector.BECAUSE, left=right, right=left),
        ),
    )
    report = validate_static(cycle)

    assert not report.passed
    assert "causal_cycle" in {issue.code for issue in report.issues}
    assert len(report.issues) == 1

