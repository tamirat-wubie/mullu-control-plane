"""Gateway interpretation contract tests.

Purpose: Verify durable request interpretation and redacted interpretation
receipts before gateway planning or execution.
Governance scope: interpretation receipts, raw-message hash boundary, and
deterministic resolver authority.
Dependencies: gateway interpretation contracts and capability intent type.
Invariants:
  - Raw message text is not embedded in interpretation receipts.
  - Deterministic capability intent produces action classification.
  - Unclear input produces missing-slot evidence instead of execution authority.
"""

from dataclasses import dataclass
from pathlib import Path

from gateway.capability_dispatch import CapabilityIntent
from gateway.command_spine import canonical_hash
from gateway.interpretation import clarification_request_for, interpret_gateway_message
from scripts.validate_schemas import _load_schema, _validate_schema_instance


_ROOT = Path(__file__).resolve().parent.parent.parent
_INTERPRETED_REQUEST_SCHEMA = _ROOT / "schemas" / "interpreted_request.schema.json"
_INTERPRETATION_RECEIPT_SCHEMA = _ROOT / "schemas" / "interpretation_receipt.schema.json"
_CLARIFICATION_REQUEST_SCHEMA = _ROOT / "schemas" / "clarification_request.schema.json"


@dataclass(frozen=True, slots=True)
class StubMessage:
    message_id: str
    channel: str
    sender_id: str
    body: str
    conversation_id: str = ""


def test_interpretation_receipt_hashes_raw_message_and_redacts_params():
    body = "search knowledge docs about private roadmap token abc123"
    intent = CapabilityIntent(
        domain="enterprise",
        action="knowledge_search",
        params={"query": body},
    )

    interpreted, receipt = interpret_gateway_message(
        message=StubMessage("msg-1", "web", "user-1", body, "conv-1"),
        tenant_id="tenant-1",
        actor_id="actor-1",
        intent=intent,
        created_at="2026-06-11T10:00:00+00:00",
    )
    receipt_payload = receipt.to_dict()

    assert interpreted.raw_message_hash == canonical_hash({"body": body})
    assert interpreted.intent_class == "action_request"
    assert interpreted.search_needed is True
    assert receipt_payload["interpreted_intent"] == "enterprise.knowledge_search"
    assert receipt_payload["extracted_slots"]["param_names"] == ["query"]
    assert "private roadmap token abc123" not in str(receipt_payload)


def test_interpretation_contracts_match_public_schemas():
    body = "What is the current policy?"

    interpreted, receipt = interpret_gateway_message(
        message=StubMessage("msg-schema", "web", "user-1", body, "conv-1"),
        tenant_id="tenant-1",
        actor_id="actor-1",
        intent=None,
        created_at="2026-06-11T10:00:00+00:00",
    )
    interpreted_errors = _validate_schema_instance(
        _load_schema(_INTERPRETED_REQUEST_SCHEMA),
        interpreted.to_dict(),
    )
    receipt_errors = _validate_schema_instance(
        _load_schema(_INTERPRETATION_RECEIPT_SCHEMA),
        receipt.to_dict(),
    )

    assert interpreted_errors == []
    assert receipt_errors == []
    assert interpreted.request_id == receipt.request_id
    assert interpreted.raw_message_hash == receipt.raw_message_hash
    assert interpreted.intent_class == "question"
    assert "current policy" not in str(receipt.to_dict())


def test_explicit_command_interpretation_records_action_without_raw_body():
    body = '/run enterprise.task_schedule {"title":"call customer"}'
    intent = CapabilityIntent(
        domain="enterprise",
        action="task_schedule",
        params={"title": "call customer"},
    )

    interpreted, receipt = interpret_gateway_message(
        message=StubMessage("msg-2", "slack", "user-2", body),
        tenant_id="tenant-2",
        actor_id="actor-2",
        intent=intent,
        created_at="2026-06-11T10:00:00+00:00",
    )

    assert interpreted.intent_class == "explicit_command"
    assert interpreted.action_needed is True
    assert interpreted.risk_estimate == "medium"
    assert interpreted.approval_required is True
    assert receipt.risk_precheck == "medium"
    assert "call customer" not in str(receipt.to_dict())


def test_unclear_message_records_missing_intent_slot():
    interpreted, receipt = interpret_gateway_message(
        message=StubMessage("msg-3", "telegram", "user-3", "fix"),
        tenant_id="tenant-3",
        actor_id="actor-3",
        intent=None,
        created_at="2026-06-11T10:00:00+00:00",
    )

    assert interpreted.intent_class == "unclear_message"
    assert interpreted.missing_slots == ("target", "allowed_action")
    assert interpreted.confidence == 0.25
    assert receipt.missing_slots == ("target", "allowed_action")
    assert "deterministic_capability_intent:none" in receipt.rejected_interpretations
    assert receipt.interpreted_intent == "unclear_message"


def test_vague_action_produces_redacted_clarification_request():
    body = "fix my site secret-token-123"

    interpreted, receipt = interpret_gateway_message(
        message=StubMessage("msg-4", "web", "user-4", body, "conv-4"),
        tenant_id="tenant-4",
        actor_id="actor-4",
        intent=None,
        created_at="2026-06-11T10:00:00+00:00",
    )
    clarification = clarification_request_for(
        interpreted_request=interpreted,
        created_at="2026-06-11T10:00:01+00:00",
    )

    assert clarification is not None
    assert interpreted.intent_class == "unclear_message"
    assert interpreted.missing_slots == ("target", "allowed_action")
    assert clarification.missing_fields == ("target", "allowed_action")
    assert clarification.safe_default == "no_execution"
    assert clarification.max_questions == 1
    assert "secret-token-123" not in str(clarification.to_dict())
    assert "secret-token-123" not in str(receipt.to_dict())


def test_clarification_request_contract_matches_public_schema():
    interpreted, _receipt = interpret_gateway_message(
        message=StubMessage("msg-clarify-schema", "web", "user-5", "deploy the app"),
        tenant_id="tenant-5",
        actor_id="actor-5",
        intent=None,
        created_at="2026-06-11T10:00:00+00:00",
    )
    clarification = clarification_request_for(
        interpreted_request=interpreted,
        created_at="2026-06-11T10:00:01+00:00",
    )
    assert clarification is not None

    errors = _validate_schema_instance(
        _load_schema(_CLARIFICATION_REQUEST_SCHEMA),
        clarification.to_dict(),
    )

    assert errors == []
    assert clarification.request_id == interpreted.request_id
    assert clarification.raw_message_hash == interpreted.raw_message_hash
    assert clarification.question


def test_generic_unclear_text_does_not_force_clarification_request():
    interpreted, _receipt = interpret_gateway_message(
        message=StubMessage("msg-unclear-generic", "discord", "user-6", "/hello"),
        tenant_id="tenant-6",
        actor_id="actor-6",
        intent=None,
        created_at="2026-06-11T10:00:00+00:00",
    )

    clarification = clarification_request_for(
        interpreted_request=interpreted,
        created_at="2026-06-11T10:00:01+00:00",
    )

    assert interpreted.intent_class == "unclear_message"
    assert interpreted.missing_slots == ("intent",)
    assert clarification is None
