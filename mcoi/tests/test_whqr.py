"""Purpose: verify WHQR contract, evaluator, connector compiler, and static checks.
Governance scope: side-effect-free WHQR trees, split gates, deterministic serialization, explicit connector lowering, and static validation.
Dependencies: WHQR contracts and WHQR pure helpers.
Invariants: truth is not permission; missing evidence is unknown; connectors compile to assertions; static checks catch cycles and unsafe negation.
"""

from __future__ import annotations

import json
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.conversation import ClarificationResponse
from mcoi_runtime.contracts.policy import PolicyDecisionStatus
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
from mcoi_runtime.whqr.binding_preflight import validate_binding_preflight
from mcoi_runtime.whqr.clarification import (
    admit_binding_clarification_response,
    build_binding_map_from_clarification_responses,
    build_binding_clarification_requests,
)
from mcoi_runtime.whqr.connectors import AssertionKind, compile_connector
from mcoi_runtime.whqr.entity_binder import EntityBindingCandidate, EntityBindingStatus, bind_entities
from mcoi_runtime.whqr.evaluator import WHQREvaluationContext, evaluate
from mcoi_runtime.whqr.governance import build_guard_verdict, build_policy_decision
from mcoi_runtime.whqr.static_checks import validate_static


def _node(target: str, role: WHRole = WHRole.WHAT) -> WHQRNode:
    return WHQRNode(role=role, target=target)


def _forged_logical_expr(op: LogicalOp, args: tuple[WHQRNode, ...]) -> LogicalExpr:
    expr = object.__new__(LogicalExpr)
    object.__setattr__(expr, "op", op)
    object.__setattr__(expr, "args", args)
    return expr


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
    assert first.semantics_hash.startswith("sha256:")
    assert len(first.semantics_hash.removeprefix("sha256:")) == 64
    assert all(
        char in "0123456789abcdef"
        for char in first.semantics_hash.removeprefix("sha256:")
    )
    assert first.canonical_json() == second.canonical_json()
    assert json.loads(first.canonical_json())["root"]["connector"] == "because"
    assert first.canonical_hash() == second.canonical_hash()


def test_document_semantics_header_must_match_canonical_pair() -> None:
    root = WHQRNode(role=WHRole.WHAT, target="payment_request")
    valid_wrong_semantics_hash = "sha256:" + ("0" * 64)
    if valid_wrong_semantics_hash == SEMANTICS_HASH:
        valid_wrong_semantics_hash = "sha256:" + ("1" * 64)

    with pytest.raises(ValueError, match="canonical WHQR semantics"):
        WHQRDocument(root=root, whqr_version="0.2.0")
    with pytest.raises(ValueError, match="canonical WHQR semantics"):
        WHQRDocument(root=root, semantics_hash=valid_wrong_semantics_hash)
    for malformed_semantics_hash in (
        "sha256:custom-whqr-semantics",
        "sha256:" + ("A" * 64),
        "sha256:" + ("g" * 64),
        "custom-whqr-semantics",
    ):
        with pytest.raises(ValueError, match="semantics_hash must be sha256"):
            WHQRDocument(root=root, semantics_hash=malformed_semantics_hash)


def test_document_verify_semantics_replays_hash_and_header() -> None:
    document = WHQRDocument(root=WHQRNode(role=WHRole.WHAT, target="payment_request"))
    canonical_hash = document.canonical_hash()
    wrong_valid_hash = "sha256:" + ("0" * 64)
    if wrong_valid_hash == canonical_hash:
        wrong_valid_hash = "sha256:" + ("1" * 64)

    assert document.verify_semantics() == canonical_hash
    assert document.verify_semantics(expected_canonical_hash=canonical_hash) == canonical_hash
    assert len(canonical_hash.removeprefix("sha256:")) == 64
    assert all(char in "0123456789abcdef" for char in canonical_hash.removeprefix("sha256:"))
    with pytest.raises(ValueError, match="canonical hash mismatch"):
        document.verify_semantics(expected_canonical_hash=wrong_valid_hash)
    with pytest.raises(ValueError, match="expected_canonical_hash"):
        document.verify_semantics(expected_canonical_hash="")
    for malformed_hash in (
        "sha256:different",
        "sha256:" + ("A" * 64),
        "sha256:" + ("g" * 64),
        "notsha256:" + ("0" * 64),
    ):
        with pytest.raises(ValueError, match="expected_canonical_hash must be sha256"):
            document.verify_semantics(expected_canonical_hash=malformed_hash)


def test_document_verify_semantics_rejects_replay_header_tampering() -> None:
    document = WHQRDocument(root=WHQRNode(role=WHRole.WHAT, target="payment_request"))
    version_tampered = WHQRDocument(root=WHQRNode(role=WHRole.WHAT, target="payment_request"))
    hash_tampered = WHQRDocument(root=WHQRNode(role=WHRole.WHAT, target="payment_request"))
    root_tampered = WHQRDocument(root=WHQRNode(role=WHRole.WHAT, target="payment_request"))
    source_ref_blank_tampered = WHQRDocument(
        root=WHQRNode(role=WHRole.WHAT, target="payment_request"),
        source_ref="request:payment-approval",
    )
    source_ref_type_tampered = WHQRDocument(
        root=WHQRNode(role=WHRole.WHAT, target="payment_request"),
        source_ref="request:payment-approval",
    )

    object.__setattr__(version_tampered, "whqr_version", "0.2.0")
    object.__setattr__(hash_tampered, "semantics_hash", "sha256:other")
    object.__setattr__(root_tampered, "root", object())
    object.__setattr__(source_ref_blank_tampered, "source_ref", " ")
    object.__setattr__(source_ref_type_tampered, "source_ref", ("request", "payment-approval"))

    assert document.verify_semantics() == document.canonical_hash()
    with pytest.raises(ValueError, match="semantic version mismatch"):
        version_tampered.verify_semantics()
    with pytest.raises(ValueError, match="semantics hash mismatch"):
        hash_tampered.verify_semantics()
    with pytest.raises(ValueError, match="root"):
        root_tampered.verify_semantics()
    with pytest.raises(ValueError, match="source_ref"):
        source_ref_blank_tampered.verify_semantics()
    with pytest.raises(ValueError, match="source_ref"):
        source_ref_type_tampered.verify_semantics()


def test_document_canonical_serialization_rejects_header_and_root_tampering() -> None:
    version_tampered = WHQRDocument(root=WHQRNode(role=WHRole.WHAT, target="payment_request"))
    hash_tampered = WHQRDocument(root=WHQRNode(role=WHRole.WHAT, target="payment_request"))
    root_role_tampered = WHQRDocument(root=WHQRNode(role=WHRole.WHAT, target="payment_request"))

    object.__setattr__(version_tampered, "whqr_version", "0.2.0")
    object.__setattr__(hash_tampered, "semantics_hash", "sha256:other")
    object.__setattr__(root_role_tampered.root, "role", "what")

    with pytest.raises(ValueError, match="deterministic canonical JSON"):
        version_tampered.canonical_json()
    with pytest.raises(ValueError, match="deterministic canonical JSON"):
        hash_tampered.canonical_hash()
    with pytest.raises(ValueError, match="deterministic canonical JSON"):
        root_role_tampered.canonical_json()


def test_document_verify_semantics_rejects_nested_tree_tampering() -> None:
    node_tampered = WHQRDocument(root=WHQRNode(role=WHRole.WHAT, target="payment_request"))
    logical_tampered = WHQRDocument(
        root=LogicalExpr(
            op=LogicalOp.AND,
            args=(
                WHQRNode(role=WHRole.WHAT, target="payment_request"),
                WHQRNode(role=WHRole.WHY, target="invoice_due"),
            ),
        )
    )
    connector_tampered = WHQRDocument(
        root=ConnectorExpr(
            connector=Connector.BECAUSE,
            left=WHQRNode(role=WHRole.WHAT, target="payment_request"),
            right=WHQRNode(role=WHRole.WHY, target="invoice_due"),
        )
    )
    metadata_sequence_tampered = WHQRDocument(
        root=WHQRNode(
            role=WHRole.WHAT,
            target="payment_request",
            metadata={"evidence_refs": ("evidence:invoice",)},
        )
    )
    metadata_mapping_tampered = WHQRDocument(
        root=WHQRNode(
            role=WHRole.WHAT,
            target="payment_request",
            metadata={"details": {"evidence_ref": "evidence:invoice"}},
        )
    )
    metadata_nested_mapping_tampered = WHQRDocument(
        root=WHQRNode(
            role=WHRole.WHAT,
            target="payment_request",
            metadata={"details": {"evidence_ref": "evidence:invoice"}},
        )
    )
    document_metadata_tampered = WHQRDocument(
        root=WHQRNode(role=WHRole.WHAT, target="payment_request"),
        metadata={"tenant": "foundation"},
    )
    document_nested_metadata_tampered = WHQRDocument(
        root=WHQRNode(role=WHRole.WHAT, target="payment_request"),
        metadata={"details": {"tenant": "foundation"}},
    )

    object.__setattr__(node_tampered.root, "role", "what")
    object.__setattr__(logical_tampered.root, "args", list(logical_tampered.root.args))
    object.__setattr__(
        connector_tampered.root.right,
        "metadata",
        MappingProxyType({"evidence": object()}),
    )
    object.__setattr__(
        metadata_sequence_tampered.root,
        "metadata",
        MappingProxyType({"evidence_refs": ["evidence:invoice"]}),
    )
    object.__setattr__(
        metadata_mapping_tampered.root,
        "metadata",
        {"details": {"evidence_ref": "evidence:invoice"}},
    )
    object.__setattr__(
        metadata_nested_mapping_tampered.root,
        "metadata",
        MappingProxyType({"details": {"evidence_ref": "evidence:invoice"}}),
    )
    object.__setattr__(document_metadata_tampered, "metadata", {"tenant": "foundation"})
    object.__setattr__(
        document_nested_metadata_tampered,
        "metadata",
        MappingProxyType({"details": {"tenant": "foundation"}}),
    )

    with pytest.raises(ValueError, match=r"root\.role"):
        node_tampered.verify_semantics()
    with pytest.raises(ValueError, match=r"root\.args"):
        logical_tampered.verify_semantics()
    with pytest.raises(ValueError, match="metadata value"):
        connector_tampered.verify_semantics()
    with pytest.raises(ValueError, match="metadata value must be immutable"):
        metadata_sequence_tampered.verify_semantics()
    with pytest.raises(ValueError, match="metadata must be immutable"):
        metadata_mapping_tampered.verify_semantics()
    with pytest.raises(ValueError, match="metadata must be immutable"):
        metadata_nested_mapping_tampered.verify_semantics()
    with pytest.raises(ValueError, match="metadata must be immutable"):
        document_metadata_tampered.verify_semantics()
    with pytest.raises(ValueError, match="metadata must be immutable"):
        document_nested_metadata_tampered.verify_semantics()


def test_document_imports_canonical_json_with_replay_hash() -> None:
    document = WHQRDocument(
        root=ConnectorExpr(
            connector=Connector.BECAUSE,
            left=WHQRNode(
                role=WHRole.WHAT,
                target="payment_request",
                node_id="request-node",
                quantifier=Quantifier.EXISTS,
                metadata={"priority": 1, "refs": ["invoice:1"]},
            ),
            right=WHQRNode(
                role=WHRole.WHY,
                target="invoice_due",
                modality=Adverb.CERTAINLY,
                evidence_ref="evidence:invoice-1",
            ),
        ),
        source_ref="request:payment-approval",
        metadata={"tenant": "foundation"},
    )
    canonical_json = document.canonical_json()
    canonical_hash = document.canonical_hash()

    imported = WHQRDocument.from_canonical_json(canonical_json, expected_canonical_hash=canonical_hash)

    assert imported.canonical_json() == canonical_json
    assert imported.verify_semantics() == canonical_hash
    assert isinstance(imported.root, ConnectorExpr)
    assert isinstance(imported.root.left, WHQRNode)
    assert imported.root.left.metadata["refs"] == ("invoice:1",)


def test_document_import_rejects_noncanonical_json_and_unknown_fields() -> None:
    document = WHQRDocument(root=WHQRNode(role=WHRole.WHAT, target="payment_request"))
    payload = json.loads(document.canonical_json())
    payload["ignored"] = "field"

    with pytest.raises(ValueError, match="canonical JSON"):
        WHQRDocument.from_canonical_json(json.dumps(json.loads(document.canonical_json())))
    with pytest.raises(ValueError, match="unknown fields"):
        WHQRDocument.from_canonical_json(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    with pytest.raises(ValueError, match="known WHRole"):
        WHQRDocument.from_canonical_json(
            document.canonical_json().replace('"role":"what"', '"role":"invalid_role"')
        )


def test_document_preserves_optional_binding_refs_in_canonical_form() -> None:
    document = WHQRDocument(
        root=WHQRNode(
            role=WHRole.WHO,
            target="approver",
            node_id="node-approver",
            entity_ref="identity:finance-manager",
            evidence_ref="evidence:approval-policy",
            expected_type="identity",
        ),
        source_ref="request:payment-approval",
    )
    payload = json.loads(document.canonical_json())

    assert payload["source_ref"] == "request:payment-approval"
    assert payload["root"]["node_id"] == "node-approver"
    assert payload["root"]["entity_ref"] == "identity:finance-manager"
    assert payload["root"]["evidence_ref"] == "evidence:approval-policy"
    assert payload["root"]["expected_type"] == "identity"


def test_document_metadata_rejects_nonfinite_values_before_canonical_json() -> None:
    with pytest.raises(ValueError, match="finite number") as excinfo:
        WHQRDocument(
            root=WHQRNode(
                role=WHRole.WHAT,
                target="measurement",
                metadata={"confidence": float("nan")},
            )
        )

    message = str(excinfo.value)
    assert "finite number" in message
    assert "confidence" not in message
    assert "nan" not in message.lower()


def test_metadata_values_must_be_canonical_json_compatible() -> None:
    document = WHQRDocument(
        root=WHQRNode(
            role=WHRole.WHAT,
            target="measurement",
            metadata={"confidence": 0.75, "verified": True, "note": None},
        )
    )

    with pytest.raises(ValueError, match="canonical JSON-compatible"):
        WHQRNode(role=WHRole.WHAT, target="vendor_record", metadata={"tags": {"verified"}})
    with pytest.raises(ValueError, match="canonical JSON-compatible"):
        GateResult(truth=TruthGate.TRUE, metadata={"witness": object()})
    assert json.loads(document.canonical_json())["root"]["metadata"]["confidence"] == 0.75


def test_document_metadata_is_deep_frozen_for_stable_hashes() -> None:
    source_metadata = {
        "details": {
            "evidence_refs": ["evidence:vendor-1"],
            "checks": [{"name": "freshness", "passed": True}],
        }
    }
    document = WHQRDocument(
        root=WHQRNode(
            role=WHRole.WHAT,
            target="vendor_record",
            metadata=source_metadata,
        )
    )
    original_hash = document.canonical_hash()

    source_metadata["details"]["evidence_refs"].append("evidence:vendor-2")
    source_metadata["details"]["checks"][0]["passed"] = False

    assert document.canonical_hash() == original_hash
    assert document.root.metadata["details"]["evidence_refs"] == ("evidence:vendor-1",)
    assert document.root.metadata["details"]["checks"][0]["passed"] is True
    with pytest.raises(TypeError):
        document.root.metadata["details"]["evidence_refs"] += ("evidence:vendor-3",)


def test_nested_metadata_keys_must_remain_text_for_canonical_identity() -> None:
    with pytest.raises(ValueError, match="metadata key"):
        WHQRNode(
            role=WHRole.WHAT,
            target="vendor_record",
            metadata={"details": {1: "numeric-key"}},
        )
    with pytest.raises(ValueError, match="metadata key"):
        GateResult(
            truth=TruthGate.TRUE,
            metadata={"details": {("compound", "key"): "tuple-key"}},
        )
    with pytest.raises(ValueError, match="metadata key"):
        WHQRDocument(
            root=WHQRNode(role=WHRole.WHAT, target="vendor_record"),
            metadata={"details": {False: "boolean-key"}},
        )


def test_canonical_serialization_rejects_tampered_non_text_mapping_keys() -> None:
    document_metadata_tampered = WHQRDocument(
        root=WHQRNode(role=WHRole.WHAT, target="vendor_record"),
        metadata={"tenant": "foundation"},
    )
    root_metadata_tampered = WHQRDocument(
        root=WHQRNode(
            role=WHRole.WHAT,
            target="vendor_record",
            metadata={"details": {"tenant": "foundation"}},
        )
    )

    object.__setattr__(document_metadata_tampered, "metadata", MappingProxyType({1: "numeric-key"}))
    object.__setattr__(
        root_metadata_tampered.root,
        "metadata",
        MappingProxyType({"details": MappingProxyType({("compound", "key"): "tuple-key"})}),
    )

    with pytest.raises(ValueError, match="deterministic canonical JSON"):
        document_metadata_tampered.canonical_json()
    with pytest.raises(ValueError, match="deterministic canonical JSON"):
        document_metadata_tampered.canonical_hash()
    with pytest.raises(ValueError, match="deterministic canonical JSON"):
        root_metadata_tampered.canonical_json()


def test_canonical_serialization_rejects_tampered_mutable_sequences() -> None:
    logical_args_tampered = WHQRDocument(
        root=LogicalExpr(
            op=LogicalOp.AND,
            args=(
                WHQRNode(role=WHRole.WHAT, target="payment_request"),
                WHQRNode(role=WHRole.WHY, target="invoice_due"),
            ),
        )
    )
    metadata_sequence_tampered = WHQRDocument(
        root=WHQRNode(
            role=WHRole.WHAT,
            target="vendor_record",
            metadata={"evidence_refs": ("evidence:vendor-1",)},
        )
    )

    object.__setattr__(logical_args_tampered.root, "args", list(logical_args_tampered.root.args))
    object.__setattr__(
        metadata_sequence_tampered.root,
        "metadata",
        MappingProxyType({"evidence_refs": ["evidence:vendor-1"]}),
    )

    with pytest.raises(ValueError, match="deterministic canonical JSON"):
        logical_args_tampered.canonical_json()
    with pytest.raises(ValueError, match="deterministic canonical JSON"):
        logical_args_tampered.canonical_hash()
    with pytest.raises(ValueError, match="deterministic canonical JSON"):
        metadata_sequence_tampered.canonical_json()


def test_contract_validation_and_metadata_fail_closed() -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        WHQRNode(role=WHRole.WHO, target="")
    with pytest.raises(ValueError, match="blank"):
        WHQRNode(role=WHRole.WHO, target="   ")
    with pytest.raises(ValueError, match="role"):
        WHQRNode(role="who", target="actor")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="non-empty string"):
        GateResult(truth=TruthGate.TRUE, metadata={"": "empty"})
    with pytest.raises(ValueError, match="blank"):
        GateResult(truth=TruthGate.TRUE, reason="\t")
    with pytest.raises(ValueError, match="blank"):
        WHQRNode(role=WHRole.WHAT, target="invoice", node_id=" ")
    with pytest.raises(ValueError, match="blank"):
        WHQRNode(role=WHRole.WHAT, target="invoice", entity_ref="\r\n")
    with pytest.raises(ValueError, match="blank"):
        WHQRDocument(root=WHQRNode(role=WHRole.WHAT, target="invoice"), source_ref=" ")
    with pytest.raises(ValueError, match="blank"):
        WHQRDocument.from_canonical_json("  ")
    with pytest.raises(ValueError, match="metadata key"):
        WHQRDocument(
            root=WHQRNode(role=WHRole.WHAT, target="invoice"),
            metadata={" ": "blank-key"},
        )
    with pytest.raises(ValueError, match="metadata must be a mapping"):
        WHQRDocument(root=WHQRNode(role=WHRole.WHAT, target="invoice"), metadata=[])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="metadata must be a mapping"):
        WHQRDocument(root=WHQRNode(role=WHRole.WHAT, target="invoice"), metadata="")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="root and expr"):
        WHQRDocument(
            root=WHQRNode(role=WHRole.WHAT, target="invoice"),
            expr=WHQRNode(role=WHRole.WHO, target="approver"),
        )

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


def test_evaluation_context_freezes_node_results_snapshot() -> None:
    mutable_node_results = {
        "approval": GateResult(
            truth=TruthGate.TRUE,
            norm=NormGate.PERMITTED,
            evidence=EvidenceGate.PROVEN,
            reason="initial_approval",
        )
    }
    ctx = WHQREvaluationContext(node_results=mutable_node_results)
    mutable_node_results["approval"] = GateResult(
        truth=TruthGate.FALSE,
        norm=NormGate.FORBIDDEN,
        evidence=EvidenceGate.CONTRADICTED,
        reason="mutated_approval",
    )
    mutable_node_results["budget"] = GateResult(truth=TruthGate.TRUE, evidence=EvidenceGate.PROVEN)
    approval_result = evaluate(_node("approval"), ctx)
    budget_result = evaluate(_node("budget"), ctx)

    assert isinstance(ctx.node_results, MappingProxyType)
    assert approval_result.truth is TruthGate.TRUE
    assert approval_result.norm is NormGate.PERMITTED
    assert approval_result.evidence is EvidenceGate.PROVEN
    assert approval_result.reason == "initial_approval"
    assert budget_result.truth is TruthGate.UNKNOWN
    assert budget_result.reason == "unresolved_whqr_node"


def test_evaluation_context_snapshots_gate_result_metadata() -> None:
    source_result = GateResult(
        truth=TruthGate.TRUE,
        norm=NormGate.PERMITTED,
        evidence=EvidenceGate.PROVEN,
        reason="initial_gate",
        metadata={
            "details": {
                "evidence_refs": ["evidence:gate-1"],
                "checks": [{"passed": True}],
            }
        },
    )
    ctx = WHQREvaluationContext(node_results={"gate": source_result})
    object.__setattr__(
        source_result,
        "metadata",
        MappingProxyType(
            {
                "details": MappingProxyType(
                    {
                        "evidence_refs": ("evidence:tampered",),
                        "checks": (MappingProxyType({"passed": False}),),
                    }
                )
            }
        ),
    )
    result = evaluate(_node("gate"), ctx)

    assert result.truth is TruthGate.TRUE
    assert result.reason == "initial_gate"
    assert result.metadata["details"]["evidence_refs"] == ("evidence:gate-1",)
    assert result.metadata["details"]["checks"][0]["passed"] is True
    assert source_result.metadata["details"]["evidence_refs"] == ("evidence:tampered",)


def test_evaluation_context_rejects_invalid_tampered_gate_metadata() -> None:
    invalid_result = GateResult(truth=TruthGate.TRUE, evidence=EvidenceGate.PROVEN)
    object.__setattr__(
        invalid_result,
        "metadata",
        MappingProxyType({"witness": object()}),
    )

    with pytest.raises(ValueError, match="metadata value"):
        WHQREvaluationContext(node_results={"gate": invalid_result})


def test_evaluation_context_preserves_bindings_alias_without_mutable_exposure() -> None:
    ctx = WHQREvaluationContext(
        bindings={
            "invoice": GateResult(
                truth=TruthGate.TRUE,
                norm=NormGate.PERMITTED,
                evidence=EvidenceGate.PROVEN,
                reason="invoice_verified",
            )
        }
    )
    result = evaluate(_node("invoice"), ctx)

    assert ctx.bindings is ctx.node_results
    assert isinstance(ctx.bindings, MappingProxyType)
    assert result.truth is TruthGate.TRUE
    assert result.norm is NormGate.PERMITTED
    assert result.reason == "invoice_verified"
    with pytest.raises(TypeError):
        ctx.node_results["invoice"] = GateResult(TruthGate.FALSE)  # type: ignore[index]


def test_evaluation_context_rejects_ambiguous_or_invalid_bindings() -> None:
    valid_result = GateResult(truth=TruthGate.TRUE, evidence=EvidenceGate.PROVEN)

    with pytest.raises(ValueError, match="not both"):
        WHQREvaluationContext(node_results={"approval": valid_result}, bindings={"budget": valid_result})
    with pytest.raises(ValueError, match="key must be a string"):
        WHQREvaluationContext(node_results={1: valid_result})  # type: ignore[dict-item]
    with pytest.raises(ValueError, match="cannot be blank"):
        WHQREvaluationContext(node_results={" ": valid_result})
    with pytest.raises(ValueError, match="value must be GateResult"):
        WHQREvaluationContext(node_results={"approval": TruthGate.TRUE})  # type: ignore[dict-item]


def test_or_evaluator_does_not_escalate_when_true_branch_is_proven() -> None:
    ctx = WHQREvaluationContext(
        node_results={
            "fresh_vendor_record": GateResult(
                TruthGate.TRUE,
                NormGate.PERMITTED,
                EvidenceGate.PROVEN,
                reason="fresh_vendor_record_verified",
            ),
            "stale_vendor_record": GateResult(
                TruthGate.TRUE,
                NormGate.PERMITTED,
                EvidenceGate.STALE,
                reason="stale_vendor_record_expired",
            ),
            "missing_vendor_record": GateResult(
                TruthGate.UNKNOWN,
                NormGate.PERMITTED,
                EvidenceGate.UNPROVEN,
                reason="missing_vendor_record",
            ),
        }
    )
    proven_or_stale = evaluate(
        LogicalExpr(
            op=LogicalOp.OR,
            args=(
                _node("fresh_vendor_record"),
                _node("stale_vendor_record"),
            ),
        ),
        ctx,
    )
    proven_or_missing = evaluate(
        LogicalExpr(
            op=LogicalOp.OR,
            args=(
                _node("missing_vendor_record"),
                _node("fresh_vendor_record"),
            ),
        ),
        ctx,
    )

    assert proven_or_stale.truth is TruthGate.TRUE
    assert proven_or_stale.norm is NormGate.PERMITTED
    assert proven_or_stale.evidence is EvidenceGate.PROVEN
    assert proven_or_stale.reason == "logical:fresh_vendor_record_verified"
    assert proven_or_missing.truth is TruthGate.TRUE
    assert proven_or_missing.evidence is EvidenceGate.PROVEN
    assert proven_or_missing.reason == "logical:fresh_vendor_record_verified"


def test_iff_and_xor_evaluator_resolve_declared_logical_operators() -> None:
    ctx = WHQREvaluationContext(
        node_results={
            "left_true": GateResult(
                TruthGate.TRUE,
                NormGate.PERMITTED,
                EvidenceGate.PROVEN,
                reason="left_true",
            ),
            "right_true": GateResult(
                TruthGate.TRUE,
                NormGate.PERMITTED,
                EvidenceGate.PROVEN,
                reason="right_true",
            ),
            "left_false": GateResult(
                TruthGate.FALSE,
                NormGate.PERMITTED,
                EvidenceGate.PROVEN,
                reason="left_false",
            ),
            "right_false": GateResult(
                TruthGate.FALSE,
                NormGate.PERMITTED,
                EvidenceGate.PROVEN,
                reason="right_false",
            ),
            "unknown": GateResult(
                TruthGate.UNKNOWN,
                NormGate.PERMITTED,
                EvidenceGate.UNPROVEN,
                reason="unknown",
            ),
        }
    )
    equivalent_true = evaluate(
        LogicalExpr(op=LogicalOp.IFF, args=(_node("left_true"), _node("right_true"))),
        ctx,
    )
    equivalent_false = evaluate(
        LogicalExpr(op=LogicalOp.IFF, args=(_node("left_true"), _node("right_false"))),
        ctx,
    )
    exclusive_true = evaluate(
        LogicalExpr(op=LogicalOp.XOR, args=(_node("left_true"), _node("right_false"))),
        ctx,
    )
    exclusive_false = evaluate(
        LogicalExpr(op=LogicalOp.XOR, args=(_node("left_true"), _node("right_true"))),
        ctx,
    )
    exclusive_unknown = evaluate(
        LogicalExpr(op=LogicalOp.XOR, args=(_node("left_false"), _node("unknown"))),
        ctx,
    )

    assert equivalent_true.truth is TruthGate.TRUE
    assert equivalent_true.evidence is EvidenceGate.PROVEN
    assert equivalent_true.reason == "logical:left_true;right_true"
    assert equivalent_false.truth is TruthGate.FALSE
    assert exclusive_true.truth is TruthGate.TRUE
    assert exclusive_false.truth is TruthGate.FALSE
    assert exclusive_unknown.truth is TruthGate.UNKNOWN
    assert exclusive_unknown.evidence is EvidenceGate.UNPROVEN


def test_evaluator_bounds_malformed_non_unary_logical_arity() -> None:
    ctx = WHQREvaluationContext(
        node_results={
            "left": GateResult(TruthGate.TRUE, evidence=EvidenceGate.PROVEN),
        }
    )
    malformed = (
        _forged_logical_expr(LogicalOp.AND, (_node("left"),)),
        _forged_logical_expr(LogicalOp.OR, (_node("left"),)),
        _forged_logical_expr(LogicalOp.IFF, (_node("left"),)),
        _forged_logical_expr(LogicalOp.XOR, (_node("left"),)),
        _forged_logical_expr(LogicalOp.IMPLIES, (_node("left"),)),
    )
    results = tuple(evaluate(expr, ctx) for expr in malformed)

    assert tuple(result.truth for result in results) == (TruthGate.UNKNOWN,) * len(malformed)
    assert tuple(result.evidence for result in results) == (EvidenceGate.UNPROVEN,) * len(malformed)
    assert tuple(result.reason for result in results) == (
        "invalid_logical_arity:and",
        "invalid_logical_arity:or",
        "invalid_logical_arity:iff",
        "invalid_logical_arity:xor",
        "invalid_logical_arity:implies",
    )


def test_evaluator_rejects_malformed_not_arity_explicitly() -> None:
    ctx = WHQREvaluationContext(
        node_results={
            "left": GateResult(TruthGate.TRUE, evidence=EvidenceGate.PROVEN),
            "right": GateResult(TruthGate.FALSE, evidence=EvidenceGate.PROVEN),
        }
    )

    with pytest.raises(RuntimeCoreInvariantError, match="not requires exactly one"):
        evaluate(_forged_logical_expr(LogicalOp.NOT, ()), ctx)
    with pytest.raises(RuntimeCoreInvariantError, match="not requires exactly one"):
        evaluate(_forged_logical_expr(LogicalOp.NOT, (_node("left"), _node("right"))), ctx)


def test_logical_expr_contract_rejects_empty_args_before_evaluation() -> None:
    with pytest.raises(ValueError, match="args must contain"):
        LogicalExpr(op=LogicalOp.AND, args=())
    with pytest.raises(ValueError, match="args must contain"):
        LogicalExpr(op=LogicalOp.OR, args=())
    with pytest.raises(ValueError, match="args must contain"):
        LogicalExpr(op=LogicalOp.NOT, args=())


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


def test_static_checks_deny_invalid_implies_arity_before_policy_admission() -> None:
    expr = LogicalExpr(
        op=LogicalOp.IMPLIES,
        args=(
            _node("actor_present"),
            _node("approval_valid"),
            _node("budget_available"),
        ),
    )
    report = validate_static(expr)
    decision = build_policy_decision(
        expr,
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        goal_id="goal-invalid-implies",
        context=WHQREvaluationContext(
            node_results={
                "actor_present": GateResult(TruthGate.TRUE, evidence=EvidenceGate.PROVEN),
                "approval_valid": GateResult(TruthGate.TRUE, evidence=EvidenceGate.PROVEN),
                "budget_available": GateResult(TruthGate.TRUE, evidence=EvidenceGate.PROVEN),
            }
        ),
    )

    assert report.passed is False
    assert {issue.code for issue in report.issues} == {"invalid_logical_arity"}
    assert report.issues[0].target == "implies:3"
    assert decision.status is PolicyDecisionStatus.DENY
    assert decision.reasons[0].code == "whqr_static_deny"
    assert decision.reasons[0].details["gate_reason"] == "invalid_logical_arity:implies"
    assert decision.reasons[0].details["static_issues"][0]["code"] == "invalid_logical_arity"


def test_static_checks_deny_singleton_logical_arity() -> None:
    malformed = (
        _forged_logical_expr(LogicalOp.AND, (_node("actor_present"),)),
        _forged_logical_expr(LogicalOp.OR, (_node("actor_present"),)),
        _forged_logical_expr(LogicalOp.IFF, (_node("actor_present"),)),
        _forged_logical_expr(LogicalOp.XOR, (_node("actor_present"),)),
    )
    reports = tuple(validate_static(expr) for expr in malformed)

    assert tuple(report.passed for report in reports) == (False,) * len(malformed)
    assert tuple(report.issues[0].code for report in reports) == ("invalid_logical_arity",) * len(malformed)
    assert tuple(report.issues[0].target for report in reports) == ("and:1", "or:1", "iff:1", "xor:1")
    assert all(report.issues[0].message.endswith("requires at least two WHQR expressions") for report in reports)


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


def test_static_checks_allow_acyclic_temporal_ordering() -> None:
    sequence = LogicalExpr(
        op=LogicalOp.AND,
        args=(
            ConnectorExpr(
                connector=Connector.BEFORE,
                left=_node("request"),
                right=_node("approval"),
            ),
            ConnectorExpr(
                connector=Connector.UNTIL,
                left=_node("approval"),
                right=_node("payment"),
            ),
        ),
    )
    report = validate_static(sequence)

    assert report.passed is True
    assert report.issues == ()
    assert len(report.issues) == 0


def test_static_checks_detect_temporal_cycles_with_after_normalization() -> None:
    contradiction = LogicalExpr(
        op=LogicalOp.AND,
        args=(
            ConnectorExpr(
                connector=Connector.BEFORE,
                left=_node("approval"),
                right=_node("payment"),
            ),
            ConnectorExpr(
                connector=Connector.AFTER,
                left=_node("approval"),
                right=_node("payment"),
            ),
        ),
    )
    report = validate_static(contradiction)
    issue_codes = {issue.code for issue in report.issues}

    assert report.passed is False
    assert issue_codes == {"temporal_cycle"}
    assert len(report.issues) == 1


def test_static_checks_require_at_least_n_quantifier_bound() -> None:
    missing = validate_static(
        WHQRNode(
            role=WHRole.HOW_MANY,
            target="required_approvers",
            node_id="approver-count",
            quantifier=Quantifier.AT_LEAST_N,
        )
    )
    invalid = validate_static(
        WHQRNode(
            role=WHRole.HOW_MANY,
            target="required_approvers",
            node_id="approver-count-invalid",
            quantifier=Quantifier.AT_LEAST_N,
            metadata={"n": 0},
        )
    )
    valid = validate_static(
        WHQRNode(
            role=WHRole.HOW_MANY,
            target="required_approvers",
            node_id="approver-count-valid",
            quantifier=Quantifier.AT_LEAST_N,
            metadata={"n": 2},
        )
    )

    assert missing.passed is False
    assert {issue.code for issue in missing.issues} == {"missing_quantifier_bound"}
    assert invalid.passed is False
    assert {issue.code for issue in invalid.issues} == {"invalid_quantifier_bound"}
    assert valid.passed is True
    assert valid.issues == ()


def test_static_checks_detect_conflicting_modalities_for_same_role_target() -> None:
    expr = LogicalExpr(
        op=LogicalOp.AND,
        args=(
            WHQRNode(role=WHRole.WHEN, target="backup_runs", node_id="backup-always", modality=Adverb.ALWAYS),
            WHQRNode(role=WHRole.WHEN, target="backup_runs", node_id="backup-never", modality=Adverb.NEVER),
            WHQRNode(role=WHRole.WHY, target="backup_runs", node_id="backup-why", modality=Adverb.NEVER),
        ),
    )
    report = validate_static(expr)

    assert report.passed is False
    assert {issue.code for issue in report.issues} == {"modality_conflict"}
    assert report.issues[0].target == "backup-always|backup-never"


def test_static_checks_reject_duplicate_node_ids_and_side_effect_targets() -> None:
    expr = LogicalExpr(
        op=LogicalOp.AND,
        args=(
            WHQRNode(role=WHRole.WHAT, target="payment_request", node_id="node-1"),
            WHQRNode(role=WHRole.HOW, target="send_email", node_id="node-1"),
        ),
    )
    report = validate_static(expr)
    issue_codes = {issue.code for issue in report.issues}

    assert not report.passed
    assert issue_codes == {"duplicate_node_id", "side_effect_target"}
    assert len(report.issues) == 2


def test_static_checks_detect_camel_case_side_effect_targets() -> None:
    expr = LogicalExpr(
        op=LogicalOp.AND,
        args=(
            WHQRNode(role=WHRole.HOW, target="sendEmail", node_id="send-email"),
            WHQRNode(role=WHRole.HOW, target="writeFile", node_id="write-file"),
            WHQRNode(role=WHRole.WHAT, target="payment_request", node_id="payment-request"),
        ),
    )
    report = validate_static(expr)
    side_effect_targets = tuple(issue.target for issue in report.issues if issue.code == "side_effect_target")

    assert report.passed is False
    assert side_effect_targets == ("sendEmail", "writeFile")
    assert "payment_request" not in side_effect_targets


def test_governance_decision_records_static_issue_details() -> None:
    expr = WHQRNode(role=WHRole.HOW, target="send_email", node_id="unsafe-action")
    decision = build_policy_decision(
        expr,
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        goal_id="goal-static-audit",
        context=WHQREvaluationContext(
            node_results={
                "send_email": GateResult(TruthGate.TRUE, NormGate.PERMITTED, EvidenceGate.PROVEN),
            }
        ),
    )
    details = decision.reasons[0].details

    assert decision.status is PolicyDecisionStatus.DENY
    assert decision.reasons[0].code == "whqr_static_deny"
    assert decision.decision_id == (
        f"whqr:goal-static-audit:deny:whqr_static_deny:{WHQRDocument(root=expr).canonical_hash()}"
    )
    replay_document = WHQRDocument.from_canonical_json(
        decision.metadata["whqr_canonical_json"],
        expected_canonical_hash=decision.metadata["whqr_canonical_hash"],
    )
    tampered_replay_json = decision.metadata["whqr_canonical_json"].replace("send_email", "delete_file")

    assert decision.metadata["whqr_canonical_hash"] == WHQRDocument(root=expr).canonical_hash()
    assert replay_document.root == expr
    assert replay_document.canonical_hash() == decision.metadata["whqr_canonical_hash"]
    assert decision.metadata["reason_code"] == "whqr_static_deny"
    assert decision.metadata["whqr_semantics_hash"] == WHQRDocument(root=expr).semantics_hash
    assert decision.metadata["whqr_version"] == WHQRDocument(root=expr).whqr_version
    with pytest.raises(ValueError, match="canonical hash mismatch"):
        WHQRDocument.from_canonical_json(
            tampered_replay_json,
            expected_canonical_hash=decision.metadata["whqr_canonical_hash"],
        )
    assert details["truth"] == "true"
    assert details["static_issues"][0]["code"] == "side_effect_target"
    assert details["static_issues"][0]["target"] == "send_email"
    assert details["binding_issues"] == ()


def test_guard_verdict_preserves_whqr_policy_reason_details() -> None:
    decision = build_policy_decision(
        WHQRNode(role=WHRole.HOW, target="send_email", node_id="unsafe-action"),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        goal_id="goal-static-audit",
        context=WHQREvaluationContext(
            node_results={
                "send_email": GateResult(TruthGate.TRUE, NormGate.PERMITTED, EvidenceGate.PROVEN),
            }
        ),
    )
    verdict = build_guard_verdict(decision)

    assert verdict.guard_id == "whqr_policy"
    assert verdict.passed is False
    assert verdict.detail["decision_id"] == decision.decision_id
    assert verdict.detail["goal_id"] == "goal-static-audit"
    assert verdict.detail["subject_id"] == "operator"
    assert verdict.detail["issued_at"] == "2026-05-06T12:00:01Z"
    assert verdict.detail["policy_status"] == "deny"
    assert verdict.detail["reason_code"] == "whqr_static_deny"
    assert verdict.detail["decision_metadata"]["reason_code"] == "whqr_static_deny"
    assert verdict.detail["whqr_canonical_json"] == decision.metadata["whqr_canonical_json"]
    assert verdict.detail["whqr_canonical_hash"] == decision.metadata["whqr_canonical_hash"]
    assert verdict.detail["whqr_semantics_hash"] == decision.metadata["whqr_semantics_hash"]
    assert verdict.detail["whqr_version"] == decision.metadata["whqr_version"]
    assert (
        WHQRDocument.from_canonical_json(
            verdict.detail["whqr_canonical_json"],
            expected_canonical_hash=verdict.detail["whqr_canonical_hash"],
        ).canonical_hash()
        == verdict.detail["whqr_canonical_hash"]
    )
    assert verdict.detail["reason_details"]["static_issues"][0]["code"] == "side_effect_target"
    assert verdict.detail["reason_details"]["binding_issues"] == ()


def test_governance_decision_identity_is_stable_and_tree_specific() -> None:
    first_expr = WHQRNode(role=WHRole.WHAT, target="budget_available")
    second_expr = WHQRNode(role=WHRole.WHAT, target="invoice_valid")
    first_decision = build_policy_decision(
        first_expr,
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        goal_id="goal-stable-id",
        context=WHQREvaluationContext(
            node_results={"budget_available": GateResult(TruthGate.FALSE, evidence=EvidenceGate.PROVEN)}
        ),
    )
    repeated_decision = build_policy_decision(
        first_expr,
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        goal_id="goal-stable-id",
        context=WHQREvaluationContext(
            node_results={"budget_available": GateResult(TruthGate.FALSE, evidence=EvidenceGate.PROVEN)}
        ),
    )
    second_decision = build_policy_decision(
        second_expr,
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        goal_id="goal-stable-id",
        context=WHQREvaluationContext(
            node_results={"invoice_valid": GateResult(TruthGate.FALSE, evidence=EvidenceGate.PROVEN)}
        ),
    )

    assert first_decision.decision_id == repeated_decision.decision_id
    assert first_decision.decision_id != second_decision.decision_id
    assert first_decision.metadata["whqr_canonical_hash"] == WHQRDocument(root=first_expr).canonical_hash()
    assert second_decision.metadata["whqr_canonical_hash"] == WHQRDocument(root=second_expr).canonical_hash()
    assert first_decision.metadata["whqr_semantics_hash"] == WHQRDocument(root=first_expr).semantics_hash
    assert first_decision.metadata["whqr_version"] == WHQRDocument(root=first_expr).whqr_version
    assert first_decision.decision_id.endswith(str(first_decision.metadata["whqr_canonical_hash"]))


def test_governance_decision_codes_identify_primary_deny_gate() -> None:
    false_decision = build_policy_decision(
        WHQRNode(role=WHRole.WHAT, target="budget_available"),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        context=WHQREvaluationContext(
            node_results={"budget_available": GateResult(TruthGate.FALSE, evidence=EvidenceGate.PROVEN)}
        ),
    )
    forbidden_decision = build_policy_decision(
        WHQRNode(role=WHRole.WHAT, target="tenant_secret"),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        context=WHQREvaluationContext(
            node_results={
                "tenant_secret": GateResult(TruthGate.TRUE, NormGate.FORBIDDEN, EvidenceGate.PROVEN),
            }
        ),
    )
    contradicted_decision = build_policy_decision(
        WHQRNode(role=WHRole.WHAT, target="invoice_valid"),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        context=WHQREvaluationContext(
            node_results={
                "invoice_valid": GateResult(TruthGate.TRUE, NormGate.PERMITTED, EvidenceGate.CONTRADICTED),
            }
        ),
    )

    assert false_decision.status is PolicyDecisionStatus.DENY
    assert false_decision.reasons[0].code == "whqr_truth_deny"
    assert forbidden_decision.reasons[0].code == "whqr_norm_deny"
    assert contradicted_decision.reasons[0].code == "whqr_evidence_deny"


def test_governance_decision_codes_identify_primary_escalation_gate() -> None:
    unknown_decision = build_policy_decision(
        WHQRNode(role=WHRole.WHAT, target="approval_known"),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        context=WHQREvaluationContext(
            node_results={"approval_known": GateResult(TruthGate.UNKNOWN, evidence=EvidenceGate.PROVEN)}
        ),
    )
    approval_decision = build_policy_decision(
        WHQRNode(role=WHRole.WHAT, target="payment_request"),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        context=WHQREvaluationContext(
            node_results={
                "payment_request": GateResult(TruthGate.TRUE, NormGate.REQUIRES_APPROVAL, EvidenceGate.PROVEN),
            }
        ),
    )
    stale_decision = build_policy_decision(
        WHQRNode(role=WHRole.WHAT, target="vendor_record"),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        context=WHQREvaluationContext(
            node_results={"vendor_record": GateResult(TruthGate.TRUE, NormGate.PERMITTED, EvidenceGate.STALE)}
        ),
    )
    unproven_decision = build_policy_decision(
        WHQRNode(role=WHRole.WHAT, target="invoice_evidence"),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        context=WHQREvaluationContext(
            node_results={
                "invoice_evidence": GateResult(TruthGate.TRUE, NormGate.PERMITTED, EvidenceGate.UNPROVEN),
            }
        ),
    )
    budget_unknown_decision = build_policy_decision(
        WHQRNode(role=WHRole.WHAT, target="budget_check"),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        context=WHQREvaluationContext(
            node_results={
                "budget_check": GateResult(TruthGate.TRUE, NormGate.PERMITTED, EvidenceGate.BUDGET_UNKNOWN),
            }
        ),
    )
    forbidden_unknown_decision = build_policy_decision(
        WHQRNode(role=WHRole.WHAT, target="tenant_secret"),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        context=WHQREvaluationContext(
            node_results={
                "tenant_secret": GateResult(TruthGate.TRUE, NormGate.PERMITTED, EvidenceGate.FORBIDDEN_UNKNOWN),
            }
        ),
    )

    assert unknown_decision.status is PolicyDecisionStatus.ESCALATE
    assert unknown_decision.reasons[0].code == "whqr_truth_escalate"
    assert approval_decision.reasons[0].code == "whqr_norm_escalate"
    assert stale_decision.reasons[0].code == "whqr_evidence_stale_escalate"
    assert unproven_decision.reasons[0].code == "whqr_evidence_unproven_escalate"
    assert budget_unknown_decision.reasons[0].code == "whqr_evidence_budget_unknown_escalate"
    assert forbidden_unknown_decision.reasons[0].code == "whqr_evidence_forbidden_unknown_escalate"
    assert forbidden_unknown_decision.reasons[0].details["evidence"] == EvidenceGate.FORBIDDEN_UNKNOWN.value


def test_governance_reason_details_preserve_gate_reason_and_metadata() -> None:
    decision = build_policy_decision(
        WHQRNode(role=WHRole.WHAT, target="vendor_record"),
        subject_id="operator",
        issued_at="2026-05-06T12:00:01Z",
        context=WHQREvaluationContext(
            node_results={
                "vendor_record": GateResult(
                    TruthGate.TRUE,
                    NormGate.PERMITTED,
                    EvidenceGate.STALE,
                    reason="evidence_freshness_window_expired",
                    metadata={
                        "checked_at": "2026-05-06T12:00:00Z",
                        "evidence_ref": "evidence:vendor-record-1",
                        "fresh_until": "2026-05-05T12:00:00Z",
                    },
                ),
            }
        ),
    )
    verdict = build_guard_verdict(decision)

    assert decision.status is PolicyDecisionStatus.ESCALATE
    assert decision.reasons[0].code == "whqr_evidence_stale_escalate"
    assert decision.reasons[0].details["gate_reason"] == "evidence_freshness_window_expired"
    assert decision.reasons[0].details["gate_metadata"]["evidence_ref"] == "evidence:vendor-record-1"
    assert decision.reasons[0].details["gate_metadata"]["fresh_until"] == "2026-05-05T12:00:00Z"
    assert verdict.detail["reason_details"]["gate_reason"] == decision.reasons[0].details["gate_reason"]
    assert verdict.detail["reason_details"]["gate_metadata"] == decision.reasons[0].details["gate_metadata"]


def test_entity_binder_attaches_entity_and_evidence_refs_without_changing_tree_shape() -> None:
    expr = ConnectorExpr(
        connector=Connector.BECAUSE,
        left=WHQRNode(role=WHRole.WHO, target="approver", node_id="n1", expected_type="identity"),
        right=WHQRNode(role=WHRole.WHY, target="approval_policy", node_id="n2", expected_type="policy"),
    )
    report = bind_entities(
        expr,
        {
            "approver": EntityBindingCandidate(
                entity_ref="identity:finance-manager",
                evidence_ref="evidence:directory-1",
                entity_type="identity",
            ),
            "approval_policy": EntityBindingCandidate(
                entity_ref="policy:payment-approval",
                evidence_ref="evidence:policy-1",
                entity_type="policy",
            ),
        },
    )

    assert report.bound is True
    assert report.issues == ()
    assert isinstance(report.expr, ConnectorExpr)
    assert isinstance(report.expr.left, WHQRNode)
    assert report.expr.connector is Connector.BECAUSE
    assert report.expr.left.entity_ref == "identity:finance-manager"
    assert report.expr.left.evidence_ref == "evidence:directory-1"
    assert report.expr.right.entity_ref == "policy:payment-approval"
    assert report.expr.right.evidence_ref == "evidence:policy-1"


def test_entity_binder_reports_missing_ambiguous_and_type_mismatch_without_binding() -> None:
    expr = LogicalExpr(
        op=LogicalOp.AND,
        args=(
            WHQRNode(role=WHRole.WHO, target="approver", node_id="n1", expected_type="identity"),
            WHQRNode(role=WHRole.WHOM, target="vendor", node_id="n2", expected_type="vendor"),
            WHQRNode(role=WHRole.WHAT, target="invoice", node_id="n3", expected_type="invoice"),
        ),
    )
    report = bind_entities(
        expr,
        {
            "vendor": (
                EntityBindingCandidate("vendor:a", "evidence:vendor-a", "vendor"),
                EntityBindingCandidate("vendor:b", "evidence:vendor-b", "vendor"),
            ),
            "invoice": EntityBindingCandidate("invoice:1", "evidence:invoice-1", "document"),
        },
    )
    statuses = {issue.target: issue.status for issue in report.issues}

    assert report.bound is False
    assert statuses == {
        "approver": EntityBindingStatus.MISSING,
        "vendor": EntityBindingStatus.AMBIGUOUS,
        "invoice": EntityBindingStatus.TYPE_MISMATCH,
    }
    assert len(report.issues) == 3
    assert report.issues[2].expected_type == "invoice"
    assert report.issues[2].observed_type == "document"
    assert isinstance(report.expr, LogicalExpr)
    assert all(isinstance(arg, WHQRNode) and arg.entity_ref is None for arg in report.expr.args)


def test_entity_binder_rejects_invalid_binding_candidates() -> None:
    with pytest.raises(ValueError, match="entity_ref"):
        EntityBindingCandidate("", "evidence:1", "identity")
    with pytest.raises(ValueError, match="binding value"):
        bind_entities(WHQRNode(role=WHRole.WHO, target="actor"), {"actor": "identity:1"})  # type: ignore[dict-item]


def test_entity_binder_preserves_prebound_nodes_and_reports_conflicts() -> None:
    prebound = WHQRNode(
        role=WHRole.WHO,
        target="approver",
        node_id="n1",
        expected_type="identity",
        entity_ref="identity:finance-manager",
        evidence_ref="evidence:directory-1",
    )
    preserved = bind_entities(prebound, {})
    matching = bind_entities(
        prebound,
        {
            "approver": EntityBindingCandidate(
                "identity:finance-manager",
                "evidence:directory-1",
                "identity",
            )
        },
    )
    conflicting = bind_entities(
        prebound,
        {
            "approver": EntityBindingCandidate(
                "identity:other-manager",
                "evidence:directory-2",
                "identity",
            )
        },
    )

    assert preserved.bound is True
    assert matching.bound is True
    assert preserved.expr is prebound
    assert matching.expr is prebound
    assert conflicting.bound is False
    assert conflicting.issues[0].status is EntityBindingStatus.PREBOUND_CONFLICT


def test_entity_binder_reports_empty_candidate_tuple_as_missing() -> None:
    report = bind_entities(WHQRNode(role=WHRole.WHO, target="actor"), {"actor": ()})

    assert report.bound is False
    assert len(report.issues) == 1
    assert report.issues[0].status is EntityBindingStatus.MISSING


def test_binding_preflight_requires_refs_for_typed_or_partial_nodes_only() -> None:
    expr = LogicalExpr(
        op=LogicalOp.AND,
        args=(
            WHQRNode(role=WHRole.WHO, target="actor"),
            WHQRNode(role=WHRole.WHOM, target="vendor", node_id="n1", expected_type="vendor"),
            WHQRNode(role=WHRole.WHAT, target="invoice", entity_ref="invoice:1"),
            WHQRNode(
                role=WHRole.WHY,
                target="policy",
                expected_type="policy",
                entity_ref="policy:refund",
                evidence_ref="evidence:policy",
            ),
        ),
    )
    report = validate_binding_preflight(expr)
    issue_codes = {(issue.target, issue.code) for issue in report.issues}

    assert report.passed is False
    assert issue_codes == {
        ("vendor", "missing_entity_ref"),
        ("vendor", "missing_evidence_ref"),
        ("invoice", "missing_evidence_ref"),
    }
    assert report.issues[0].node_id == "n1"
    assert report.issues[0].expected_type == "vendor"


def test_binding_clarification_requests_group_issues_by_target() -> None:
    report = validate_binding_preflight(
        LogicalExpr(
            op=LogicalOp.AND,
            args=(
                WHQRNode(role=WHRole.WHOM, target="vendor", node_id="vendor-node", expected_type="vendor"),
                WHQRNode(role=WHRole.WHAT, target="invoice", entity_ref="invoice:1"),
            ),
        )
    )
    bundle = build_binding_clarification_requests(
        report,
        thread_id="thread-1",
        requested_from_id="operator",
        requested_at="2026-05-06T12:00:01Z",
        request_prefix="whqr-binding:goal",
    )

    assert bundle.empty is False
    assert len(bundle.requests) == 2
    assert bundle.requests[0].request_id == "whqr-binding:goal:1:invoice"
    assert bundle.requests[0].question == "Which evidence reference proves WHQR target 'invoice'?"
    assert bundle.requests[1].request_id == "whqr-binding:goal:2:vendor-node"
    assert "entity reference and evidence reference" in bundle.requests[1].question
    assert "missing_entity_ref,missing_evidence_ref" in bundle.requests[1].context


def test_binding_clarification_response_admits_explicit_refs_only() -> None:
    expr = WHQRNode(role=WHRole.WHOM, target="vendor", node_id="vendor-node", expected_type="vendor")
    report = validate_binding_preflight(expr)
    bundle = build_binding_clarification_requests(
        report,
        thread_id="thread-1",
        requested_from_id="operator",
        requested_at="2026-05-06T12:00:01Z",
    )
    request = bundle.requests[0]
    response = ClarificationResponse(
        request_id=request.request_id,
        thread_id=request.thread_id,
        answer="entity_ref=vendor:acme;evidence_ref=evidence:vendor-doc-1",
        responded_by_id="operator",
        responded_at="2026-05-06T12:05:01Z",
    )

    result = admit_binding_clarification_response(request, response)

    assert result.accepted is True
    assert result.reason == "accepted"
    assert result.target == "vendor"
    assert result.candidate is not None
    assert result.candidate == EntityBindingCandidate("vendor:acme", "evidence:vendor-doc-1", "vendor")
    binding_report = bind_entities(expr, {result.target: result.candidate})

    assert binding_report.issues == ()
    assert isinstance(binding_report.expr, WHQRNode)
    assert binding_report.expr.entity_ref == "vendor:acme"
    assert binding_report.expr.evidence_ref == "evidence:vendor-doc-1"


def test_binding_clarification_response_rejects_free_text_and_mismatch() -> None:
    report = validate_binding_preflight(
        WHQRNode(role=WHRole.WHOM, target="vendor", node_id="vendor-node", expected_type="vendor")
    )
    request = build_binding_clarification_requests(
        report,
        thread_id="thread-1",
        requested_from_id="operator",
        requested_at="2026-05-06T12:00:01Z",
    ).requests[0]
    free_text = ClarificationResponse(
        request_id=request.request_id,
        thread_id=request.thread_id,
        answer="Use Acme from the vendor document",
        responded_by_id="operator",
        responded_at="2026-05-06T12:05:01Z",
    )
    mismatch = ClarificationResponse(
        request_id="other-request",
        thread_id=request.thread_id,
        answer="entity_ref=vendor:acme;evidence_ref=evidence:vendor-doc-1",
        responded_by_id="operator",
        responded_at="2026-05-06T12:05:01Z",
    )

    free_text_result = admit_binding_clarification_response(request, free_text)
    mismatch_result = admit_binding_clarification_response(request, mismatch)

    assert free_text_result.accepted is False
    assert free_text_result.reason == "invalid_response_binding_field"
    assert free_text_result.candidate is None
    assert free_text_result.target == "vendor"
    assert mismatch_result.accepted is False
    assert mismatch_result.reason == "request_mismatch"
    assert mismatch_result.candidate is None


def test_binding_clarification_response_map_is_deterministic_and_explicit() -> None:
    report = validate_binding_preflight(
        WHQRNode(role=WHRole.WHOM, target="vendor", node_id="vendor-node", expected_type="vendor")
    )
    request = build_binding_clarification_requests(
        report,
        thread_id="thread-1",
        requested_from_id="operator",
        requested_at="2026-05-06T12:00:01Z",
    ).requests[0]
    response = ClarificationResponse(
        request_id=request.request_id,
        thread_id=request.thread_id,
        answer="evidence_ref=evidence:vendor-doc-1;entity_ref=vendor:acme",
        responded_by_id="operator",
        responded_at="2026-05-06T12:05:01Z",
    )

    binding_map = build_binding_map_from_clarification_responses((request,), (response,))

    assert binding_map.passed is True
    assert binding_map.accepted_count == 1
    assert binding_map.rejected_count == 0
    assert binding_map.bindings == (("vendor", EntityBindingCandidate("vendor:acme", "evidence:vendor-doc-1", "vendor")),)
    assert binding_map.as_binding_candidates()["vendor"].entity_ref == "vendor:acme"


def test_binding_clarification_response_map_rejects_unknown_and_duplicate_targets() -> None:
    report = validate_binding_preflight(
        WHQRNode(role=WHRole.WHOM, target="vendor", node_id="vendor-node", expected_type="vendor")
    )
    request = build_binding_clarification_requests(
        report,
        thread_id="thread-1",
        requested_from_id="operator",
        requested_at="2026-05-06T12:00:01Z",
    ).requests[0]
    first = ClarificationResponse(
        request_id=request.request_id,
        thread_id=request.thread_id,
        answer="entity_ref=vendor:acme;evidence_ref=evidence:vendor-doc-1",
        responded_by_id="operator",
        responded_at="2026-05-06T12:05:01Z",
    )
    duplicate = ClarificationResponse(
        request_id=request.request_id,
        thread_id=request.thread_id,
        answer="entity_ref=vendor:other;evidence_ref=evidence:vendor-doc-2",
        responded_by_id="operator",
        responded_at="2026-05-06T12:06:01Z",
    )
    unknown = ClarificationResponse(
        request_id="unknown-request",
        thread_id=request.thread_id,
        answer="entity_ref=vendor:orphan;evidence_ref=evidence:vendor-doc-3",
        responded_by_id="operator",
        responded_at="2026-05-06T12:07:01Z",
    )

    binding_map = build_binding_map_from_clarification_responses((request,), (unknown, duplicate, first))
    reasons = [result.reason for result in binding_map.results]

    assert binding_map.passed is False
    assert binding_map.accepted_count == 1
    assert binding_map.rejected_count == 2
    assert reasons == ["unknown_request", "accepted", "duplicate_target_binding"]
    assert binding_map.bindings == (("vendor", EntityBindingCandidate("vendor:acme", "evidence:vendor-doc-1", "vendor")),)
