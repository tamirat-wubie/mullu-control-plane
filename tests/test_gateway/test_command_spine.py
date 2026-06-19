"""Command spine tests.

Tests: command envelope creation, transition witnesses, store-backed reload,
    and environment-backed ledger construction.
"""

import os
import sys
import threading
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.command_spine import (  # noqa: E402
    CapabilityPassport,
    ClosureDisposition,
    CommandAnchorProof,
    CommandLedger,
    CommandState,
    InMemoryCommandLedgerStore,
    PostgresCommandLedgerStore,
    build_governed_action,
    build_command_ledger_from_env,
    capability_passport_for,
    compile_typed_intent,
    redact_payload,
)
from gateway.capability_fabric import build_default_capability_admission_gate  # noqa: E402


class _RollbackFailingConnection:
    def __init__(self):
        self.rollback_attempts = 0

    def rollback(self):
        self.rollback_attempts += 1
        raise RuntimeError("rollback failed")

    def close(self):
        return None


class _CloseFailingConnection:
    def close(self):
        raise RuntimeError("close failed")


def _postgres_command_store_for_fault_tests(conn):
    store = PostgresCommandLedgerStore.__new__(PostgresCommandLedgerStore)
    store._connection_string = "postgresql://example/mullu"
    store._conn = conn
    store._lock = threading.Lock()
    store._available = True
    store._operation_failures = 0
    store._rollback_failures = 0
    store._close_failures = 0
    return store


def test_command_ledger_persists_command_and_events_through_store():
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=store,
    )

    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-1",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    updated = ledger.transition(command.command_id, CommandState.ALLOWED, risk_tier="low")
    reloaded = store.load_command(command.command_id)
    events = store.events_for(command.command_id)

    assert updated.state == CommandState.ALLOWED
    assert reloaded is not None
    assert reloaded.command_id == command.command_id
    assert reloaded.state == CommandState.ALLOWED
    assert len(events) == 2
    assert events[0].next_state == CommandState.RECEIVED
    assert events[1].previous_state == CommandState.RECEIVED
    assert events[1].next_state == CommandState.ALLOWED


def test_redact_payload_masks_free_text_and_secret_fields_without_breaking_capability_params():
    payload = {
        "body": "Email owner@example.com, call +1 202-555-0199, ssn 123-45-6789, card 4111 1111 1111 1111.",
        "metadata": {
            "api_key": "sk-live-secret",
            "api_key_hash": "sha256:credential-derived",
            "goal_intake_preview_id": "plan-preview-3814958822923e26",
            "password_hash": "sha256:password-derived",
            "source_sender_id_hash": "3814958822923e26",
            "notes": ["backup@example.com"],
        },
        "capability_intent": {
            "domain": "communication",
            "action": "send_email",
            "capability_id": "communication.send_email",
            "params": {
                "recipient": "owner@example.com",
                "body": "Send the report to owner@example.com",
                "api_key": "never-store-this",
            },
        },
        "skill_intent": {
            "skill": "communication",
            "action": "send_email",
            "params": {
                "recipient": "owner@example.com",
                "body": "Send the report to owner@example.com",
                "api_key": "never-store-this",
            },
        },
    }

    redacted = redact_payload(payload)

    assert redacted["body"] == (
        "Email [REDACTED:EMAIL], call [REDACTED:PHONE], ssn [REDACTED:SSN], "
        "card [REDACTED:PAYMENT_CARD]."
    )
    assert redacted["metadata"]["api_key"] == "[REDACTED:SECRET]"
    assert redacted["metadata"]["api_key_hash"] == "[REDACTED:SECRET]"
    assert redacted["metadata"]["goal_intake_preview_id"] == "plan-preview-3814958822923e26"
    assert redacted["metadata"]["password_hash"] == "[REDACTED:SECRET]"
    assert redacted["metadata"]["source_sender_id_hash"] == "3814958822923e26"
    assert redacted["metadata"]["notes"] == ["[REDACTED:EMAIL]"]
    assert redacted["capability_intent"]["params"]["recipient"] == "owner@example.com"
    assert redacted["capability_intent"]["params"]["body"] == "Send the report to owner@example.com"
    assert redacted["capability_intent"]["params"]["api_key"] == "[REDACTED:SECRET]"
    assert redacted["skill_intent"]["params"]["recipient"] == "owner@example.com"
    assert redacted["skill_intent"]["params"]["body"] == "Send the report to owner@example.com"
    assert redacted["skill_intent"]["params"]["api_key"] == "[REDACTED:SECRET]"


def test_build_command_ledger_from_env_uses_memory_backend(monkeypatch):
    monkeypatch.setitem(os.environ, "MULLU_COMMAND_LEDGER_BACKEND", "memory")
    ledger = build_command_ledger_from_env(clock=lambda: "2026-04-24T12:00:00+00:00")

    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-2",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    summary = ledger.summary()

    assert command.command_id.startswith("cmd-")
    assert summary["commands"] == 1
    assert summary["events"] == 1
    assert summary["store"]["backend"] == "memory"


def test_postgres_command_store_counts_operation_and_rollback_failure():
    conn = _RollbackFailingConnection()
    store = _postgres_command_store_for_fault_tests(conn)

    result = store._safe_execute(lambda: (_ for _ in ()).throw(RuntimeError("write failed")))
    status = store.status()

    assert result is None
    assert conn.rollback_attempts == 1
    assert status["operation_failures"] == 1
    assert status["rollback_failures"] == 1
    assert status["available"] is True


def test_postgres_command_store_counts_close_failure_and_clears_connection():
    store = _postgres_command_store_for_fault_tests(_CloseFailingConnection())

    store.close()
    status = store.status()

    assert store._conn is None
    assert status["available"] is False
    assert status["close_failures"] == 1


def test_command_ledger_continues_store_hash_chain():
    store = InMemoryCommandLedgerStore()
    first = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=store,
    )
    first_command = first.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-3",
        intent="llm_completion",
        payload={"body": "first"},
    )
    first_hash = store.events_for(first_command.command_id)[-1].event_hash

    second = CommandLedger(
        clock=lambda: "2026-04-24T12:00:01+00:00",
        store=store,
    )
    second_command = second.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-2",
        idempotency_key="idem-4",
        intent="llm_completion",
        payload={"body": "second"},
    )
    second_event = store.events_for(second_command.command_id)[0]

    assert second_event.prev_event_hash == first_hash
    assert second_event.event_hash
    assert second_event.event_hash != first_hash


def test_command_ledger_leases_ready_commands_once_until_release():
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=store,
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-5",
        intent="llm_completion",
        payload={"body": "ready"},
    )
    ledger.transition(command.command_id, CommandState.ALLOWED)

    first_claim = ledger.claim_ready_commands(worker_id="worker-1", limit=1)
    second_claim = ledger.claim_ready_commands(worker_id="worker-2", limit=1)
    ledger.release_command(command.command_id, "worker-1")
    third_claim = ledger.claim_ready_commands(worker_id="worker-2", limit=1)

    assert [item.command_id for item in first_claim] == [command.command_id]
    assert second_claim == []
    assert [item.command_id for item in third_claim] == [command.command_id]


def test_command_ledger_creates_signed_anchor_for_unanchored_events():
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=store,
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-6",
        intent="llm_completion",
        payload={"body": "anchor me"},
    )
    ledger.transition(command.command_id, CommandState.ALLOWED)
    ledger.transition(command.command_id, CommandState.RESPONDED, output={"body": "done"})

    anchor = ledger.anchor_unanchored_events(
        signing_secret="test-secret",
        signature_key_id="test-key",
    )
    anchors = ledger.list_anchors()
    anchored_command = ledger.get(command.command_id)

    assert anchor is not None
    assert anchor.anchor_id.startswith("cmd-anchor-")
    assert anchor.event_count == 3
    assert anchor.signature
    assert anchor.signature_key_id == "test-key"
    assert anchors == [anchor]
    assert anchored_command is not None
    assert anchored_command.state == CommandState.ANCHORED


def test_command_ledger_exports_and_verifies_anchor_proof():
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=store,
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-anchor-proof",
        intent="llm_completion",
        payload={"body": "anchor proof"},
    )
    ledger.transition(command.command_id, CommandState.ALLOWED)

    anchor = ledger.anchor_unanchored_events(
        signing_secret="test-secret",
        signature_key_id="test-key",
    )
    proof = ledger.export_anchor_proof(anchor.anchor_id if anchor is not None else "")
    verification = ledger.verify_anchor_proof(proof, signing_secret="test-secret")

    assert anchor is not None
    assert proof is not None
    assert proof.anchor == anchor
    assert proof.event_hashes[0] == anchor.from_event_hash
    assert proof.event_hashes[-1] == anchor.to_event_hash
    assert proof.proof_hash
    assert verification.valid is True
    assert verification.reason == "verified"


def test_command_ledger_exports_anchor_proof_from_store_after_restart():
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=store,
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-anchor-restart",
        intent="llm_completion",
        payload={"body": "anchor restart proof"},
    )
    ledger.transition(command.command_id, CommandState.ALLOWED)
    ledger.transition(command.command_id, CommandState.RESPONDED, output={"body": "done"})
    anchor = ledger.anchor_unanchored_events(
        signing_secret="test-secret",
        signature_key_id="test-key",
    )

    restarted_ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:01:00+00:00",
        store=store,
    )
    proof = restarted_ledger.export_anchor_proof(anchor.anchor_id if anchor is not None else "")
    verification = restarted_ledger.verify_anchor_proof(proof, signing_secret="test-secret")
    anchored_events = store.events_between_hashes(
        anchor.from_event_hash if anchor is not None else "",
        anchor.to_event_hash if anchor is not None else "",
    )
    command_events = store.events_for(command.command_id)

    assert anchor is not None
    assert proof is not None
    assert len(proof.event_hashes) == anchor.event_count
    assert proof.event_hashes == tuple(event.event_hash for event in anchored_events)
    assert anchored_events[-1].next_state == CommandState.RESPONDED
    assert command_events[-1].next_state == CommandState.ANCHORED
    assert verification.valid is True
    assert verification.reason == "verified"


def test_command_ledger_anchor_proof_detects_tampering():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-anchor-tamper",
        intent="llm_completion",
        payload={"body": "anchor tamper"},
    )
    ledger.transition(command.command_id, CommandState.ALLOWED)
    anchor = ledger.anchor_unanchored_events(
        signing_secret="test-secret",
        signature_key_id="test-key",
    )
    proof = ledger.export_anchor_proof(anchor.anchor_id if anchor is not None else "")
    tampered = CommandAnchorProof(
        anchor=proof.anchor,
        event_hashes=tuple((*proof.event_hashes[:-1], "tampered")),
        proof_hash=proof.proof_hash,
        exported_at=proof.exported_at,
    )

    verification = ledger.verify_anchor_proof(tampered, signing_secret="test-secret")

    assert proof is not None
    assert verification.valid is False
    assert verification.reason == "to_event_hash_mismatch"


def test_command_ledger_anchor_returns_none_when_no_unanchored_events():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )

    anchor = ledger.anchor_unanchored_events(signing_secret="test-secret")

    assert anchor is None
    assert ledger.list_anchors() == []


def test_typed_intent_compiler_prefers_capability_payload_to_contract():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-capability-payload",
        intent="financial.send_payment",
        payload={
            "body": "pay vendor $50",
            "capability_intent": {
                "domain": "financial",
                "action": "send_payment",
                "capability_id": "financial.send_payment",
                "params": {"amount": "50"},
            },
            "skill_intent": {
                "skill": "enterprise",
                "action": "knowledge_search",
                "params": {"query": "legacy fallback"},
            },
        },
    )

    typed_intent = compile_typed_intent(command)
    passport = capability_passport_for(typed_intent.name)

    assert typed_intent.name == "financial.send_payment"
    assert typed_intent.params == {"amount": "50"}
    assert typed_intent.payload_hash == command.payload_hash
    assert passport.capability == typed_intent.name
    assert passport.risk_tier == "high"
    assert "financial_admin" in passport.authority_required


def test_typed_intent_compiler_binds_legacy_skill_payload_to_contract():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-7",
        intent="financial.send_payment",
        payload={
            "body": "pay vendor $50",
            "skill_intent": {
                "skill": "financial",
                "action": "send_payment",
                "params": {"amount": "50"},
            },
        },
    )

    typed_intent = compile_typed_intent(command)
    passport = capability_passport_for(typed_intent.name)

    assert typed_intent.name == "financial.send_payment"
    assert typed_intent.params == {"amount": "50"}
    assert typed_intent.payload_hash == command.payload_hash
    assert passport.capability == typed_intent.name
    assert passport.risk_tier == "high"
    assert "financial_admin" in passport.authority_required
    assert "payment_provider_request_created" in passport.declared_effects
    assert "duplicate_payment" in passport.forbidden_effects
    assert "ledger_hash" in passport.evidence_required
    assert "provider_action" in passport.graph_projection["nodes"]


def test_high_risk_passport_requires_effect_contract_before_action_binding():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-effect-contract",
        intent="financial.send_payment",
        payload={
            "body": "pay vendor $50",
            "skill_intent": {
                "skill": "financial",
                "action": "send_payment",
                "params": {"amount": "50"},
            },
        },
    )
    typed_intent = compile_typed_intent(command)
    incomplete_passport = CapabilityPassport(
        capability="financial.send_payment",
        version="1",
        risk_tier="high",
        input_schema="PaymentIntent.v1",
        output_schema="PaymentReceipt.v1",
        authority_required=("financial_admin",),
        requires=("tenant_bound",),
        mutates_world=True,
        external_system="payment_provider",
        rollback_type="compensatable",
        compensation_capability="financial.refund",
        proof_required_fields=("transaction_id",),
    )

    with pytest.raises(ValueError, match="^effect-bearing capability requires declared effects$"):
        build_governed_action(command, typed_intent, incomplete_passport)


def test_capability_passports_declare_effect_contracts():
    llm_passport = capability_passport_for("llm_completion")
    balance_passport = capability_passport_for("financial.balance_check")
    payment_passport = capability_passport_for("financial.send_payment")

    assert llm_passport.declared_effects == ("response_emitted",)
    assert llm_passport.forbidden_effects == ("unauthorized_state_mutation",)
    assert llm_passport.evidence_required == ("command_id", "trace_id", "output_hash")
    assert llm_passport.graph_projection["nodes"] == ("command", "provider_action", "verification")
    assert balance_passport.declared_effects == ("balance_snapshot_read", "provider_receipt_received")
    assert balance_passport.forbidden_effects == ("account_state_mutation", "budget_mutation")
    assert balance_passport.evidence_required == ("command_id", "provider_receipt_hash")
    assert payment_passport.declared_effects == (
        "payment_provider_request_created",
        "payment_receipt_received",
        "ledger_entry_created",
        "tenant_budget_decremented",
    )
    assert payment_passport.forbidden_effects == (
        "duplicate_payment",
        "amount_mismatch",
        "recipient_mismatch",
        "unapproved_budget_mutation",
    )
    assert payment_passport.graph_projection["edges"] == ("decided_by", "verified_by", "produced")


def test_command_ledger_binds_governed_action_before_policy():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-8",
        intent="financial.balance_check",
        payload={
            "body": "check balance",
            "skill_intent": {
                "skill": "financial",
                "action": "balance_check",
                "params": {},
            },
        },
    )

    action = ledger.bind_governed_action(command.command_id)
    reloaded_action = ledger.governed_action_for(command.command_id)
    events = ledger.events_for(command.command_id)
    current = ledger.get(command.command_id)

    assert action.command_id == command.command_id
    assert action.capability == "financial.balance_check"
    assert action.capability_passport_hash
    assert action.intent_hash
    assert reloaded_action == action
    assert current is not None
    assert current.state == CommandState.EFFECT_PLANNED
    assert action.predicted_effect_hash
    assert action.rollback_plan_hash
    assert [event.next_state for event in events][-5:] == [
        CommandState.INTENT_COMPILED,
        CommandState.CAPABILITY_BOUND,
        CommandState.GOVERNED_ACTION_BOUND,
        CommandState.EFFECT_PREDICTED,
        CommandState.EFFECT_PLANNED,
    ]


def test_command_ledger_predicts_high_risk_payment_effects():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-9",
        intent="financial.send_payment",
        payload={
            "body": "make a payment of $50",
            "skill_intent": {
                "skill": "financial",
                "action": "send_payment",
                "params": {"amount": "50"},
            },
        },
    )

    action = ledger.bind_governed_action(command.command_id)
    prediction = ledger.effect_prediction_for(command.command_id)
    events = ledger.events_for(command.command_id)

    assert action.risk_tier == "high"
    assert action.predicted_effect_hash
    assert action.rollback_plan_hash
    assert prediction is not None
    assert prediction.capability == "financial.send_payment"
    assert "payment_provider" in prediction.expected_external_calls
    assert "ledger_hash" in prediction.expected_receipts
    assert "financial.refund" in prediction.rollback_plan
    assert events[-1].next_state == CommandState.EFFECT_PLANNED
    assert events[-1].detail["effect_plan"]["capability_id"] == "financial.send_payment"
    effect_names = {
        effect["name"]
        for effect in events[-1].detail["effect_plan"]["expected_effects"]
    }
    assert "payment_provider_request_created" in effect_names
    assert "tenant_budget_decremented" in effect_names
    assert "transaction_id" in effect_names
    assert events[-1].detail["effect_plan"]["forbidden_effects"]
    assert "duplicate_payment" in events[-1].detail["effect_plan"]["forbidden_effects"]
    assert "projected:provider_action" in events[-1].detail["effect_plan"]["graph_node_refs"]
    assert "projected:verified_by" in events[-1].detail["effect_plan"]["graph_edge_refs"]
    assert events[-1].detail["effect_plan_hash"]


def test_command_ledger_binds_compensation_recovery_plan():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-recovery",
        intent="financial.send_payment",
        payload={
            "body": "make a payment of $50",
            "skill_intent": {
                "skill": "financial",
                "action": "send_payment",
                "params": {"amount": "50"},
            },
        },
    )

    action = ledger.bind_governed_action(command.command_id)
    plan = ledger.recovery_plan_for(command.command_id)

    assert action.rollback_plan_hash
    assert action.state == CommandState.EFFECT_PLANNED
    assert plan is not None
    assert plan.recovery_type == "compensatable"
    assert plan.recovery_capabilities == ("financial.refund",)
    assert plan.requires_higher_approval is False
    assert "ledger_hash" in plan.proof_required_fields


def test_command_ledger_reconciles_read_only_effect_observation():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-10",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    action = ledger.bind_governed_action(command.command_id)

    reconciliation = ledger.observe_and_reconcile_effect(
        command.command_id,
        output={"content": "hello", "succeeded": True},
    )
    current = ledger.get(command.command_id)

    assert action.predicted_effect_hash
    assert reconciliation.reconciled is True
    assert reconciliation.predicted_effect_hash == action.predicted_effect_hash
    assert reconciliation.observed_effect_hash
    assert current is not None
    assert current.state == CommandState.RECONCILED
    events = ledger.events_for(command.command_id)
    assert events[-2].detail["observed_effects"]
    assert events[-2].detail["execution_result"]["actual_effects"]
    assert events[-2].detail["mcoi_observed_effects"]
    assert events[-1].detail["effect_verification"]["status"] == "pass"
    assert events[-1].detail["effect_assurance_reconciliation"]["status"] == "match"
    assert events[-1].detail["mcoi_verification"]["status"] == "pass"
    assert events[-1].detail["mcoi_reconciliation"]["status"] == "match"


def test_command_ledger_keeps_native_passport_for_builtin_fabric_capability():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
        capability_admission_gate=build_default_capability_admission_gate(
            clock=lambda: "2026-04-24T12:00:00+00:00"
        ),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-native-fabric",
        intent="enterprise.knowledge_search",
        payload={
            "body": "/run enterprise.knowledge_search {\"query\":\"deployment witness canary\"}",
            "capability_intent": {
                "skill": "enterprise",
                "action": "knowledge_search",
                "params": {"query": "deployment witness canary"},
            },
        },
    )

    action = ledger.bind_governed_action(command.command_id)
    prediction = ledger.effect_prediction_for(command.command_id)
    reconciliation = ledger.observe_and_reconcile_effect(
        command.command_id,
        output={
            "response": "Knowledge search is not available right now.",
            "total_chunks_searched": 0,
            "receipt_status": "executor_unavailable",
        },
    )
    events = ledger.events_for(command.command_id)
    bound_event = next(
        event for event in events
        if event.next_state is CommandState.CAPABILITY_BOUND
    )

    assert action.capability == "enterprise.knowledge_search"
    assert action.risk_tier == "low"
    assert prediction is not None
    assert prediction.expected_mutations == ()
    assert prediction.expected_receipts == (
        "total_chunks_searched",
        "search_decision_receipt",
    )
    assert reconciliation.reconciled is True
    assert bound_event.detail["capability_admission_status"] == "accepted"
    assert bound_event.detail["capability_passport_source"] == "native"
    assert bound_event.detail["capability_registry_entry"]["capability_id"] == "enterprise.knowledge_search"


def test_command_ledger_records_evidence_backed_claim():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-claim",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    ledger.bind_governed_action(command.command_id)
    ledger.observe_and_reconcile_effect(
        command.command_id,
        output={"content": "hello", "succeeded": True},
    )

    claim = ledger.record_operational_claim(
        command.command_id,
        text="Command llm_completion completed.",
        verified=True,
    )
    claims = ledger.claims_for(command.command_id)
    evidence = ledger.evidence_for(command.command_id)
    events = ledger.events_for(command.command_id)

    assert claim.verified is True
    assert claim.confidence == 1.0
    assert claim.evidence_refs
    assert claims == [claim]
    assert evidence
    assert {record.evidence_type for record in evidence} >= {"payload_hash", "latest_event_hash"}
    assert events[-1].detail["claim"]["claim_id"] == claim.claim_id
    assert events[-1].detail["evidence"]

    closure = ledger.close_success_response_evidence(command.command_id, claim_id=claim.claim_id)
    events = ledger.events_for(command.command_id)

    assert closure.command_id == command.command_id
    assert closure.claim_id == claim.claim_id
    assert closure.evidence_refs == claim.evidence_refs
    assert closure.reconciliation_hash
    assert closure.evidence_hash
    assert events[-1].detail["response_evidence_closure"]["claim_id"] == claim.claim_id


def test_command_ledger_promotes_observed_receipts_to_graph_and_evidence_refs():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-provider-receipt",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    ledger.bind_governed_action(command.command_id)
    ledger.observe_and_reconcile_effect(
        command.command_id,
        output={"content": "hello", "succeeded": True},
    )

    promotions = ledger.promote_provider_receipts_to_graph(command.command_id)
    evidence = ledger.evidence_for(command.command_id)
    events = ledger.events_for(command.command_id)

    assert promotions
    assert any(promotion.effect_id == "content" for promotion in promotions)
    assert any(promotion.provider_action_node_ref.startswith("provider_action:") for promotion in promotions)
    assert any(promotion.evidence_node_ref.startswith("evidence:receipt:") for promotion in promotions)
    assert any(promotion.verification_node_ref.startswith("verification:") for promotion in promotions)
    assert all(promotion.evidence_id in {record.evidence_id for record in evidence} for promotion in promotions)
    assert "provider_receipt_graph_promotions" in events[-1].detail


def test_command_ledger_reloads_provider_receipt_promotions_for_response_closure():
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=store,
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-provider-reload",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    ledger.bind_governed_action(command.command_id)
    ledger.observe_and_reconcile_effect(
        command.command_id,
        output={"content": "hello", "succeeded": True},
    )
    promotions = ledger.promote_provider_receipts_to_graph(command.command_id)

    reloaded = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=store,
    )
    reloaded_promotions = reloaded.provider_receipt_promotions_for(command.command_id)
    claim = reloaded.record_operational_claim(
        command.command_id,
        text="Command completed with reloaded receipt evidence.",
        verified=True,
    )
    closure = reloaded.close_success_response_evidence(command.command_id, claim_id=claim.claim_id)
    evidence = reloaded.evidence_for(command.command_id)

    assert reloaded_promotions == promotions
    assert {promotion.evidence_id for promotion in promotions}.issubset(set(claim.evidence_refs))
    assert {promotion.evidence_id for promotion in promotions}.issubset(set(closure.evidence_refs))
    assert all(record.verified for record in evidence if record.evidence_type == "provider_receipt")


def test_command_ledger_blocks_success_response_closure_without_reconciliation():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-response-closure",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    ledger.bind_governed_action(command.command_id)
    claim = ledger.record_operational_claim(
        command.command_id,
        text="Command llm_completion completed.",
        verified=True,
    )

    with pytest.raises(ValueError, match="^response requires reconciled observed effects$"):
        ledger.close_success_response_evidence(command.command_id, claim_id=claim.claim_id)


def test_command_ledger_requires_terminal_certificate_before_success_response():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-terminal-closure",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    ledger.bind_governed_action(command.command_id)
    ledger.observe_and_reconcile_effect(
        command.command_id,
        output={"content": "hello", "succeeded": True},
    )
    ledger.promote_provider_receipts_to_graph(command.command_id)
    claim = ledger.record_operational_claim(
        command.command_id,
        text="Command llm_completion completed.",
        verified=True,
    )
    closure = ledger.close_success_response_evidence(command.command_id, claim_id=claim.claim_id)

    with pytest.raises(ValueError, match="^success response requires terminal closure certificate$"):
        ledger.transition(
            command.command_id,
            CommandState.RESPONDED,
            output={"body": "hello"},
            detail={"success_claim": True},
        )

    certificate = ledger.certify_terminal_closure(
        command.command_id,
        disposition=ClosureDisposition.COMMITTED,
        response_evidence_closure=closure,
    )
    memory_entry = ledger.promote_closure_memory(command.command_id)
    learning = ledger.decide_closure_learning(command.command_id)
    responded = ledger.transition(
        command.command_id,
        CommandState.RESPONDED,
        output={"body": "hello"},
        detail={"success_claim": True},
    )

    assert certificate.disposition is ClosureDisposition.COMMITTED
    assert certificate.evidence_refs
    assert certificate.metadata["mcoi_terminal_disposition"] == "committed"
    assert certificate.metadata["mcoi_terminal_certificate"]["evidence_refs"]
    assert memory_entry.terminal_certificate_id == certificate.certificate_id
    assert learning.status == "admit"
    assert responded.state == CommandState.RESPONDED


def test_success_response_requires_full_post_cert_bookkeeping():
    # Ψ I-PSI-6 atomicity guard: assert_success_response_allowed refuses
    # to grant a success response until the full _certify_committed
    # sequence is present — terminal certificate AND closure memory AND
    # admitted learning decision. This prevents a partial failure mid-
    # sequence from leaving a TERMINALLY_CERTIFIED event in the audit
    # log paired with a missing-bookkeeping success response.
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-atomicity-guard",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    ledger.bind_governed_action(command.command_id)
    ledger.observe_and_reconcile_effect(
        command.command_id,
        output={"content": "hello", "succeeded": True},
    )
    ledger.promote_provider_receipts_to_graph(command.command_id)
    claim = ledger.record_operational_claim(
        command.command_id,
        text="Command llm_completion completed.",
        verified=True,
    )
    closure = ledger.close_success_response_evidence(
        command.command_id, claim_id=claim.claim_id,
    )

    certificate = ledger.certify_terminal_closure(
        command.command_id,
        disposition=ClosureDisposition.COMMITTED,
        response_evidence_closure=closure,
    )

    # Certificate is stored, but post-cert bookkeeping is absent.
    assert ledger.terminal_certificate_for(command.command_id) is certificate
    with pytest.raises(ValueError, match="closure memory entry"):
        ledger.assert_success_response_allowed(command.command_id)

    # After memory exists but learning is missing, still refused.
    ledger.promote_closure_memory(command.command_id)
    with pytest.raises(ValueError, match="learning admission decision"):
        ledger.assert_success_response_allowed(command.command_id)

    # Once learning is admitted, the success response is allowed.
    ledger.decide_closure_learning(command.command_id)
    allowed = ledger.assert_success_response_allowed(command.command_id)
    assert allowed == certificate


def test_command_ledger_rehydrates_closure_artifacts_from_store_after_restart():
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=store,
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-restart-closure-proof",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    ledger.bind_governed_action(command.command_id)
    ledger.observe_and_reconcile_effect(
        command.command_id,
        output={"content": "hello", "succeeded": True},
    )
    ledger.promote_provider_receipts_to_graph(command.command_id)
    claim = ledger.record_operational_claim(
        command.command_id,
        text="Command llm_completion completed.",
        verified=True,
    )
    closure = ledger.close_success_response_evidence(
        command.command_id,
        claim_id=claim.claim_id,
    )
    certificate = ledger.certify_terminal_closure(
        command.command_id,
        disposition=ClosureDisposition.COMMITTED,
        response_evidence_closure=closure,
    )
    memory_entry = ledger.promote_closure_memory(command.command_id)
    learning = ledger.decide_closure_learning(command.command_id)

    restarted = CommandLedger(
        clock=lambda: "2026-04-24T12:00:01+00:00",
        store=store,
    )
    restarted_summary = restarted.summary()
    restarted_latest = restarted.latest_terminal_certificate()
    allowed = restarted.assert_success_response_allowed(command.command_id)

    assert restarted_summary["terminal_certificates"] == 1
    assert restarted_summary["closure_memory_entries"] == 1
    assert restarted_summary["closure_learning_decisions"] == 1
    assert restarted_latest is not None
    assert restarted_latest.certificate_id == certificate.certificate_id
    assert allowed.certificate_id == certificate.certificate_id
    assert memory_entry.terminal_certificate_id == certificate.certificate_id
    assert learning.memory_entry_id == memory_entry.entry_id


def test_bind_governed_action_is_idempotent_to_preserve_freeze():
    # I-PRED-2 freeze: the governed action is captured at first bind and is
    # immutable for the lifetime of the command. A second bind would let the
    # capability registry / admission gate drift mid-lifecycle and would
    # leave duplicate GOVERNED_ACTION_BOUND events in the audit log.
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-rebind-refused",
        intent="llm_completion",
        payload={"body": "hello"},
    )

    first = ledger.bind_governed_action(command.command_id)

    with pytest.raises(ValueError, match="governed action already bound"):
        ledger.bind_governed_action(command.command_id)

    bind_events = [
        event
        for event in ledger.events_for(command.command_id)
        if event.next_state is CommandState.GOVERNED_ACTION_BOUND
    ]
    assert len(bind_events) == 1

    resolved = ledger.governed_action_for(command.command_id)
    assert resolved == first


def test_command_id_is_uuid_so_lifecycle_is_not_bit_identical_across_creates():
    # I-PRED-9 characterization. The spec requires "given the same inputs,
    # bit-identical outputs". create_command (gateway/command_spine.py:2283)
    # generates command_id = f"cmd-{uuid4().hex}", so two ledger instances
    # given identical (tenant_id, actor_id, idempotency_key, payload, clock)
    # produce DIFFERENT command_ids. Every downstream identifier is content-
    # addressed over command_id (terminal_certificate_id, memory entry_id,
    # learning admission_id, event hash chain) so the entire lifecycle drifts.
    #
    # The closure_evidence_hash IS bit-identical across creates because it
    # excludes command_id from its content. Everything that includes
    # command_id varies. Replay determinism in this codebase therefore holds
    # CONDITIONAL ON command_id stability (e.g., when replaying from
    # governance_log where command_ids are already fixed), not for fresh
    # creates with the same logical inputs.
    def run_lifecycle() -> dict[str, str]:
        ledger = CommandLedger(
            clock=lambda: "2026-04-24T12:00:00+00:00",
            store=InMemoryCommandLedgerStore(),
        )
        command = ledger.create_command(
            tenant_id="tenant-determinism",
            actor_id="identity-determinism",
            source="web",
            conversation_id="conv-determinism",
            idempotency_key="idem-determinism",
            intent="llm_completion",
            payload={"body": "hello determinism"},
        )
        ledger.bind_governed_action(command.command_id)
        ledger.observe_and_reconcile_effect(
            command.command_id,
            output={"content": "hello determinism", "succeeded": True},
        )
        ledger.promote_provider_receipts_to_graph(command.command_id)
        claim = ledger.record_operational_claim(
            command.command_id,
            text="Command llm_completion completed.",
            verified=True,
        )
        closure = ledger.close_success_response_evidence(
            command.command_id, claim_id=claim.claim_id,
        )
        certificate = ledger.certify_terminal_closure(
            command.command_id,
            disposition=ClosureDisposition.COMMITTED,
            response_evidence_closure=closure,
        )
        memory_entry = ledger.promote_closure_memory(command.command_id)
        learning = ledger.decide_closure_learning(command.command_id)
        events = ledger.events_for(command.command_id)
        return {
            "command_id": command.command_id,
            "closure_evidence_hash": closure.evidence_hash,
            "certificate_id": certificate.certificate_id,
            "memory_entry_id": memory_entry.entry_id,
            "learning_admission_id": learning.admission_id,
            "final_event_hash": events[-1].event_hash,
        }

    first = run_lifecycle()
    second = run_lifecycle()

    # command_id varies because create_command generates uuid4.
    assert first["command_id"] != second["command_id"]

    # Every downstream identifier varies because command_id is part of the
    # content addressed by each: terminal_certificate_id, memory entry_id,
    # learning admission_id, the closure evidence hash (over per-command
    # evidence records), and the event hash chain.
    assert first["closure_evidence_hash"] != second["closure_evidence_hash"]
    assert first["certificate_id"] != second["certificate_id"]
    assert first["memory_entry_id"] != second["memory_entry_id"]
    assert first["learning_admission_id"] != second["learning_admission_id"]
    assert first["final_event_hash"] != second["final_event_hash"]


def test_command_ledger_fracture_test_requires_high_risk_approval():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-fracture",
        intent="financial.send_payment",
        payload={
            "body": "make a payment of $50",
            "skill_intent": {
                "skill": "financial",
                "action": "send_payment",
                "params": {"amount": "50"},
            },
        },
    )
    ledger.bind_governed_action(command.command_id)

    result = ledger.fracture_test(command.command_id)
    current = ledger.get(command.command_id)

    assert result.passed is False
    assert "missing_high_risk_approval" in result.fractures
    assert result.result_hash
    assert current is not None
    assert current.state == CommandState.REQUIRES_REVIEW


def test_command_ledger_fracture_test_passes_after_approval():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-fracture-pass",
        intent="financial.send_payment",
        payload={
            "body": "make a payment of $50",
            "skill_intent": {
                "skill": "financial",
                "action": "send_payment",
                "params": {"amount": "50"},
            },
        },
    )
    ledger.bind_governed_action(command.command_id)
    ledger.transition(command.command_id, CommandState.APPROVED, approval_id="apr-1", risk_tier="high")

    result = ledger.fracture_test(command.command_id)
    current = ledger.get(command.command_id)

    assert result.passed is True
    assert result.fractures == ()
    assert "duplicate_dispatch_absent" in result.checks
    assert current is not None
    assert current.state == CommandState.FRACTURE_TESTED


def test_command_ledger_blocks_mutating_effect_without_required_receipts():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-11",
        intent="financial.send_payment",
        payload={
            "body": "make a payment of $50",
            "skill_intent": {
                "skill": "financial",
                "action": "send_payment",
                "params": {"amount": "50"},
            },
        },
    )
    ledger.bind_governed_action(command.command_id)

    reconciliation = ledger.observe_and_reconcile_effect(
        command.command_id,
        output={"response": "Payment processed."},
    )
    current = ledger.get(command.command_id)

    assert reconciliation.reconciled is False
    assert reconciliation.mismatch_reason.startswith("missing_receipts:")
    assert "ledger_hash" in reconciliation.mismatch_reason
    assert current is not None
    assert current.state == CommandState.REQUIRES_REVIEW
    events = ledger.events_for(command.command_id)
    assert events[-1].detail["effect_verification"]["status"] == "fail"
    assert events[-1].detail["effect_assurance_reconciliation"]["status"] == "mismatch"
    assert events[-1].detail["effect_assurance_reconciliation"]["case_id"] == f"case-{command.command_id}"


def test_command_ledger_records_operational_claim_with_evidence():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-claim",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    ledger.bind_governed_action(command.command_id)
    ledger.observe_and_reconcile_effect(
        command.command_id,
        output={"succeeded": True, "content": "hello"},
    )

    claim = ledger.record_operational_claim(
        command.command_id,
        text="Command completed with reconciled effects.",
        verified=True,
        confidence=0.95,
    )
    claims = ledger.claims_for(command.command_id)
    evidence = ledger.evidence_for(command.command_id)

    assert claim.verified is True
    assert claim.confidence == 0.95
    assert claims == [claim]
    assert len(evidence) >= 5
    assert "latest_event_hash" in {record.evidence_type for record in evidence}


def test_command_ledger_reloads_claims_and_evidence_from_events():
    store = InMemoryCommandLedgerStore()
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=store,
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-claim-reload",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    ledger.bind_governed_action(command.command_id)
    claim = ledger.record_operational_claim(
        command.command_id,
        text="Command has immutable evidence.",
        verified=True,
    )

    reloaded = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=store,
    )
    claims = reloaded.claims_for(command.command_id)
    evidence = reloaded.evidence_for(command.command_id)

    assert claims == [claim]
    assert evidence
    assert all(record.command_id == command.command_id for record in evidence)
    assert all(record.ref_hash for record in evidence)
