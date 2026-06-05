"""Purpose: pin generalized policy-checkpoint contracts for guard-chain v2.
Governance scope: HTTP guard slots plus adjacent GovernedSession enforcement.
Dependencies: policy checkpoint declarations and existing guard-chain contracts.
Invariants:
  - Policy checkpoints are unique and ordered.
  - HTTP checkpoints mirror the canonical HTTP guard chain.
  - Session LLM checkpoints include post-dispatch output safety and PII redaction.
  - Mutating checkpoints are explicitly marked for operator review.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.governance.guards.content_safety import (
    LAMBDA_INPUT_SAFETY,
    LAMBDA_OUTPUT_SAFETY,
)
from mcoi_runtime.governance.guards.policy_checkpoint import (
    HTTP_POLICY_CHECKPOINTS,
    PROTECTED_HTTP_CHECKPOINT_IDS,
    PROTECTED_SESSION_LLM_CHECKPOINT_IDS,
    SESSION_LLM_POLICY_CHECKPOINTS,
    PolicyCheckpoint,
    PolicyCheckpointPhase,
    PolicyCheckpointSurface,
    assert_protected_checkpoint_ids,
    assert_unique_checkpoint_ids,
    checkpoint_ids,
)


def test_http_policy_checkpoints_match_guard_chain_order() -> None:
    assert_unique_checkpoint_ids(HTTP_POLICY_CHECKPOINTS)
    assert_protected_checkpoint_ids(
        HTTP_POLICY_CHECKPOINTS,
        required_ids=PROTECTED_HTTP_CHECKPOINT_IDS,
        surface_name="http_guard_chain",
    )

    assert checkpoint_ids(HTTP_POLICY_CHECKPOINTS) == (
        "api_key",
        "jwt",
        "tenant",
        "tenant_gating",
        "rbac",
        LAMBDA_INPUT_SAFETY,
        "temporal",
        "rate_limit",
        "budget",
    )
    assert {checkpoint.surface for checkpoint in HTTP_POLICY_CHECKPOINTS} == {
        PolicyCheckpointSurface.HTTP_GUARD_CHAIN,
    }
    assert all(checkpoint.phase is PolicyCheckpointPhase.PRE_DISPATCH for checkpoint in HTTP_POLICY_CHECKPOINTS)
    assert all(checkpoint.blocks_on_fail for checkpoint in HTTP_POLICY_CHECKPOINTS)


def test_session_llm_policy_checkpoints_cover_adjacent_post_dispatch_guards() -> None:
    assert_unique_checkpoint_ids(SESSION_LLM_POLICY_CHECKPOINTS)
    assert_protected_checkpoint_ids(
        SESSION_LLM_POLICY_CHECKPOINTS,
        required_ids=PROTECTED_SESSION_LLM_CHECKPOINT_IDS,
        surface_name="session_adjacent",
    )
    ids = checkpoint_ids(SESSION_LLM_POLICY_CHECKPOINTS)

    assert ids == (
        "closed_check",
        "policy",
        "tenant_gating",
        "rbac",
        "rate_limit",
        LAMBDA_INPUT_SAFETY,
        "budget",
        "proof",
        "llm_call",
        LAMBDA_OUTPUT_SAFETY,
        "pii_redaction",
        "audit",
    )
    assert ids.index(LAMBDA_OUTPUT_SAFETY) < ids.index("pii_redaction") < ids.index("audit")
    assert {checkpoint.surface for checkpoint in SESSION_LLM_POLICY_CHECKPOINTS} == {
        PolicyCheckpointSurface.SESSION_ADJACENT,
    }
    assert SESSION_LLM_POLICY_CHECKPOINTS[8].phase is PolicyCheckpointPhase.DISPATCH


def test_session_output_safety_and_pii_are_explicit_mutating_checkpoints() -> None:
    checkpoints = {checkpoint.checkpoint_id: checkpoint for checkpoint in SESSION_LLM_POLICY_CHECKPOINTS}

    assert checkpoints[LAMBDA_OUTPUT_SAFETY].phase is PolicyCheckpointPhase.POST_DISPATCH
    assert checkpoints[LAMBDA_OUTPUT_SAFETY].mutates_payload is True
    assert checkpoints[LAMBDA_OUTPUT_SAFETY].blocks_on_fail is True
    assert checkpoints["pii_redaction"].phase is PolicyCheckpointPhase.POST_DISPATCH
    assert checkpoints["pii_redaction"].mutates_payload is True
    assert checkpoints["pii_redaction"].blocks_on_fail is False


def test_duplicate_checkpoint_ids_fail_closed() -> None:
    duplicate = (
        PolicyCheckpoint(
            "proof",
            PolicyCheckpointPhase.PRE_DISPATCH,
            PolicyCheckpointSurface.SESSION_ADJACENT,
            "first",
            True,
        ),
        PolicyCheckpoint(
            "proof",
            PolicyCheckpointPhase.POST_DISPATCH,
            PolicyCheckpointSurface.SESSION_ADJACENT,
            "second",
            True,
        ),
    )

    with pytest.raises(ValueError, match="duplicate policy checkpoint ids: proof"):
        assert_unique_checkpoint_ids(duplicate)


def test_missing_protected_checkpoint_ids_fail_closed() -> None:
    missing_proof = tuple(
        checkpoint
        for checkpoint in SESSION_LLM_POLICY_CHECKPOINTS
        if checkpoint.checkpoint_id != "proof"
    )

    with pytest.raises(
        ValueError,
        match="missing protected policy checkpoint ids for session_adjacent",
    ) as exc_info:
        assert_protected_checkpoint_ids(
            missing_proof,
            required_ids=PROTECTED_SESSION_LLM_CHECKPOINT_IDS,
            surface_name="session_adjacent",
        )

    assert "proof" in str(exc_info.value)
    assert checkpoint_ids(missing_proof) != checkpoint_ids(SESSION_LLM_POLICY_CHECKPOINTS)
    assert "proof" in PROTECTED_SESSION_LLM_CHECKPOINT_IDS
