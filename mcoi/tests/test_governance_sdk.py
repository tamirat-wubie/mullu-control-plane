"""Tests for the MVK Governance SDK facade.

Purpose: verify typed builders and client methods make Runtime ABI calls without
hand-built governance JSON.
Governance scope: SDK ergonomics only; Runtime ABI and MVK gate retain proof,
authority, and decision semantics.
Dependencies: governance SDK and invariant helpers.
Invariants: builders require scope and proof obligations, gate results carry
decision/proof/witness refs, and unsupported ABI versions fail closed.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.governance_sdk import (
    ActionSentenceBuilder,
    GovernanceClient,
    GovernanceClientConfig,
    IntentFrameBuilder,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


def _client() -> GovernanceClient:
    return GovernanceClient(GovernanceClientConfig(caller_id="sdk-test"))


def _intent() -> dict[str, object]:
    return (
        IntentFrameBuilder()
        .goal("Operate inside parser scope.")
        .within_scope("src/**")
        .succeeds_when("decision_emitted")
        .build()
    )


def test_sdk_builders_create_valid_intent_and_action_payloads() -> None:
    intent = _intent()
    action = (
        ActionSentenceBuilder.read_file("src/parser.py")
        .within_scope("src/parser.py")
        .requires_proof("scope_checked")
        .build()
    )

    assert intent["user_goal"] == "Operate inside parser scope."
    assert intent["scope"] == ["src/**"]
    assert intent["success_criteria"] == ["decision_emitted"]
    assert action["verb"] == "read"
    assert action["object_kind"] == "file"
    assert action["proof_obligations"] == ["scope_checked"]


def test_sdk_builders_fail_closed_when_required_fields_are_missing() -> None:
    with pytest.raises(RuntimeCoreInvariantError, match="intent user_goal"):
        IntentFrameBuilder().within_scope("src/**").succeeds_when("done").build()
    with pytest.raises(RuntimeCoreInvariantError, match="action scope"):
        ActionSentenceBuilder.read_file("src/parser.py").requires_proof("scope_checked").build()
    with pytest.raises(RuntimeCoreInvariantError, match="proof obligations"):
        ActionSentenceBuilder.read_file("src/parser.py").within_scope("src/parser.py").build()


def test_sdk_gate_action_returns_decision_proof_and_boundary_witness() -> None:
    action = (
        ActionSentenceBuilder.read_file("src/parser.py")
        .within_scope("src/parser.py")
        .requires_proof("scope_checked")
        .build()
    )

    result = _client().gate_action(intent=_intent(), action=action)

    assert result.decision == "allow"
    assert result.decision_ref.startswith("gate-decision-")
    assert result.proof_stamp_ref.startswith("proof-")
    assert result.boundary_witness_ref.startswith("witness-")
    assert result.explanation == "all_kernel_invariants_satisfied"
    assert result.raw_call.caller_id == "sdk-test"


def test_sdk_write_builder_declares_side_effect_and_blocks_out_of_scope() -> None:
    action = (
        ActionSentenceBuilder.write_file("deploy/config.json")
        .within_scope("deploy/config.json")
        .requires_proof("scope_checked")
        .build()
    )

    result = _client().gate_action(intent=_intent(), action=action)

    assert action["expected_side_effects"] == ["local_write"]
    assert result.decision == "block"
    assert result.explanation == "hard_constraint_or_domain_law_violation"
    assert "scope_within_intent" in result.raw_call.output["result"]["decision"]["violated_constraints"]


def test_sdk_mfidel_grid_allows_and_decomposition_blocks() -> None:
    intent = (
        IntentFrameBuilder()
        .goal("Process Mfidel without decomposition.")
        .within_scope("mfidel/**")
        .succeeds_when("fidel_atomicity_preserved")
        .build()
    )
    grid_action = (
        ActionSentenceBuilder.mfidel_grid_reference("f[1][1]")
        .within_scope("mfidel/table")
        .requires_proof("scope_checked")
        .build()
    )
    bad_action = (
        ActionSentenceBuilder.mfidel_transformation("f[1][1]", "consonant_vowel_split")
        .within_scope("mfidel/table")
        .requires_proof("scope_checked")
        .build()
    )

    allowed = _client().gate_action(intent=intent, action=grid_action)
    blocked = _client().gate_action(intent=intent, action=bad_action)

    assert allowed.decision == "allow"
    assert "mfidel_grid_reference_preserved" in allowed.raw_call.output["result"]["decision"]["satisfied_constraints"]
    assert blocked.decision == "block"
    assert any(
        "mfidel_atomicity_violation" in item
        for item in blocked.raw_call.output["result"]["decision"]["violated_constraints"]
    )


def test_sdk_gate_rejects_loose_action_payload_types() -> None:
    client = _client()
    valid_action = (
        ActionSentenceBuilder.read_file("src/parser.py")
        .within_scope("src/parser.py")
        .requires_proof("scope_checked")
        .build()
    )

    for field_name, invalid_value, expected_reason in (
        ("object_ref", 7, "object_ref must be a string"),
        ("scope", ("src/parser.py", 7), "scope\\[1\\] must be a string"),
        ("proof_obligations", ("scope_checked", False), "proof_obligations\\[1\\] must be a string"),
        ("expected_side_effects", "external_write", "expected_side_effects must be a sequence"),
        ("domain", 99, "domain must be a string"),
        ("operation", ["unicode_normalize"], "operation must be a string"),
    ):
        with pytest.raises(RuntimeCoreInvariantError, match=expected_reason):
            client.gate_action(intent=_intent(), action={**valid_action, field_name: invalid_value})


def test_sdk_validate_rejects_loose_intent_and_action_sequence_members() -> None:
    client = _client()
    valid_action = (
        ActionSentenceBuilder.read_file("src/parser.py")
        .within_scope("src/parser.py")
        .requires_proof("scope_checked")
        .build()
    )

    with pytest.raises(RuntimeCoreInvariantError, match="scope\\[1\\] must be a string"):
        client.validate_intent({**_intent(), "scope": ("src/**", 7)})
    with pytest.raises(RuntimeCoreInvariantError, match="success_criteria\\[0\\] must be a string"):
        client.validate_intent({**_intent(), "success_criteria": (False,)})
    with pytest.raises(RuntimeCoreInvariantError, match="proof_obligations\\[0\\] must be a string"):
        client.validate_action({**valid_action, "proof_obligations": (False,)})


def test_sdk_stdlib_registry_and_proof_helpers() -> None:
    client = _client()
    action = (
        ActionSentenceBuilder.read_file("src/parser.py")
        .within_scope("src/parser.py")
        .requires_proof("scope_checked")
        .build()
    )
    gated = client.gate_action(intent=_intent(), action=action)
    stdlib = client.show_stdlib("std/verifiers/MfidelAtomicityVerifier")
    registry = client.query_registry(registry_kinds=("standard",), required_tag="mfidel")
    proof = client.inspect_proof(gated.raw_call.output["result"]["proof_stamp"])

    assert stdlib.output["artifact"]["name"] == "MfidelAtomicityVerifier"
    assert registry.output["result"]["count"] == 1
    assert proof.output["missing"] == ()
    assert proof.proof_stamp_id == gated.proof_stamp_ref


def test_sdk_rejects_unsupported_abi_version() -> None:
    client = GovernanceClient(GovernanceClientConfig(caller_id="sdk-test", abi_version="9.9.9"))

    with pytest.raises(RuntimeCoreInvariantError, match="unsupported SDK ABI version"):
        client.list_stdlib()
