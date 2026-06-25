"""Purpose: verify the runtime personal-assistant intake-chain read model.
Governance scope: request intake, interpretation proposal, WHQR clarification,
preview plan, approval boundary, receipt boundary, and no-effect controls.
Dependencies: mcoi_runtime.personal_assistant intake-chain builder and schema
validator.
Invariants:
  - Runtime projection never grants connector, send, write, memory, deployment,
    customer-readiness, or live Nested Mind authority.
  - Missing bindings remain clarification questions and force safe defaults.
  - Raw private payloads and secret-like values are rejected.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    ConnectorProofRef,
    PersonalAssistantInvariantError,
    build_personal_assistant_intake_chain_read_model,
    interpret_user_request,
)
from scripts.validate_personal_assistant_intake_chain_read_model import (
    validate_personal_assistant_intake_chain_read_model,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


GENERATED_AT = "2026-06-25T00:00:00Z"
SCHEMA_PATH = Path("schemas/personal_assistant_intake_chain_read_model.schema.json")


def test_intake_chain_runtime_projection_validates_against_schema(tmp_path: Path) -> None:
    payload = build_personal_assistant_intake_chain_read_model(generated_at=GENERATED_AT)
    candidate = tmp_path / "personal_assistant_intake_chain_runtime.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    schema_errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), payload)
    semantic_result = validate_personal_assistant_intake_chain_read_model(read_model_path=candidate)

    assert schema_errors == []
    assert semantic_result.valid is True
    assert semantic_result.source_artifact_count == 5
    assert semantic_result.receipt_ref_count >= 2
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["foundation_only"] is True
    assert payload["effect_boundary"]["execution_allowed"] is False
    assert payload["effect_boundary"]["live_connector_execution_allowed"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False
    assert payload["effect_boundary"]["memory_write_allowed"] is False
    assert payload["private_payload_policy"]["raw_private_payload_serialized"] is False
    assert "pa_receipt_email_draft_001" in payload["receipt_refs"]


def test_intake_chain_runtime_projection_preserves_clarification_gaps() -> None:
    intent = interpret_user_request(
        "Send it to Daniel.",
        request_id="pa_request_send_daniel_001",
        submitted_at=GENERATED_AT,
        connector_refs=(
            ConnectorProofRef(
                connector_id="connector:gmail:operator",
                connector_name="gmail",
                proof_state="Pass",
                private_data_allowed=True,
                scopes=("gmail.readonly",),
            ),
        ),
    )

    payload = build_personal_assistant_intake_chain_read_model(
        generated_at=GENERATED_AT,
        intent=intent,
    )

    assert payload["solver_outcome"] == "AwaitingEvidence"
    assert payload["request"]["execution_mode"] == "blocked"
    assert payload["clarification"]["required"] is True
    assert payload["clarification"]["missing_binding_count"] == 3
    assert len(payload["clarification"]["questions"]) == 3
    assert "missing_recipient_identity" in payload["clarification"]["reason_codes"]
    assert payload["plan_preview"]["plan"]["execution_allowed"] is False
    assert payload["approval_boundary"]["approval_is_execution"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False


def test_intake_chain_runtime_rejects_unsafe_interpretation_summary() -> None:
    with pytest.raises(PersonalAssistantInvariantError) as exc:
        build_personal_assistant_intake_chain_read_model(
            generated_at=GENERATED_AT,
            interpretation_summary={
                "proposal_id": "symbolic-interpretation-proposal-1111111111111111",
                "personal_assistant_request_id": "pa_request_inbox_summary_001",
                "gateway_request_id": "interpreted-request-2222222222222222",
                "comparison_result": "matches_deterministic",
                "validation_status": "accepted_as_proposal",
                "authority_level": "proposal_only",
                "deterministic_override_allowed": False,
                "action_authority_granted": True,
                "execution_allowed": False,
                "private_payload_included": False,
                "secret_values_serialized": False,
            },
        )

    assert "interpretation.action_authority_granted must be false" in str(exc.value)
    assert "execution_allowed" not in str(exc.value)
    assert "secret" not in str(exc.value)


def test_intake_chain_runtime_rejects_secret_like_values() -> None:
    with pytest.raises(PersonalAssistantInvariantError) as exc:
        build_personal_assistant_intake_chain_read_model(
            generated_at=GENERATED_AT,
            interpretation_summary={
                "proposal_id": "symbolic-interpretation-proposal-1111111111111111",
                "personal_assistant_request_id": "pa_request_inbox_summary_001",
                "gateway_request_id": "interpreted-request-2222222222222222",
                "comparison_result": "matches_deterministic",
                "validation_status": "accepted_as_proposal",
                "authority_level": "proposal_only",
                "deterministic_override_allowed": False,
                "action_authority_granted": False,
                "execution_allowed": False,
                "private_payload_included": False,
                "secret_values_serialized": False,
                "source_ref": "examples/symbolic_interpretation_proposal.foundation.json",
                "summary": "rotate Bearer secret-worker-token",
            },
        )

    assert "secret-like value is forbidden" in str(exc.value)
    assert "$.interpretation.summary" in str(exc.value)
    assert "Bearer" not in json.dumps(build_personal_assistant_intake_chain_read_model())
