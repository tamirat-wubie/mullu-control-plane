"""Command spine tests.

Tests: command envelope creation, transition witnesses, store-backed reload,
    and environment-backed ledger construction.
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.command_spine import (  # noqa: E402
    CommandLedger,
    CommandState,
    InMemoryCommandLedgerStore,
    build_command_ledger_from_env,
    capability_passport_for,
    compile_typed_intent,
)


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


def test_command_ledger_anchor_returns_none_when_no_unanchored_events():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )

    anchor = ledger.anchor_unanchored_events(signing_secret="test-secret")

    assert anchor is None
    assert ledger.list_anchors() == []


def test_typed_intent_compiler_binds_skill_payload_to_contract():
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
    assert current.state == CommandState.EFFECT_PREDICTED
    assert action.predicted_effect_hash
    assert action.rollback_plan_hash
    assert [event.next_state for event in events][-4:] == [
        CommandState.INTENT_COMPILED,
        CommandState.CAPABILITY_BOUND,
        CommandState.GOVERNED_ACTION_BOUND,
        CommandState.EFFECT_PREDICTED,
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
    assert events[-1].next_state == CommandState.EFFECT_PREDICTED


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
    assert current.state == CommandState.DENIED
