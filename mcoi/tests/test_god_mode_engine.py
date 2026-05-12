"""Engine-level tests for the god-mode subsystem.

Verifies the activation-agreement → ticket → consume → receipt flow,
including expiry, double-consume protection, revocation, audit-sink
dispatch, and the `invoke()` context manager.
"""
from __future__ import annotations

import time

import pytest

from mcoi_runtime.contracts.god_mode import (
    GodCapability,
    GodCapabilityBlastRadius,
    GodReceiptOutcome,
    GodTicketState,
)
from mcoi_runtime.core.god_mode_engine import (
    GodModeEngine,
    GodModeEngineError,
)
from mcoi_runtime.core.god_mode_registry import GodModeRegistry


_VERY_LONG_JUST = "x" * 130


@pytest.fixture
def registry() -> GodModeRegistry:
    reg = GodModeRegistry()
    reg.register_capability(
        GodCapability(
            module="data",
            name="purge_tenant_now",
            description="Delete tenant data.",
            blast_radius=GodCapabilityBlastRadius.CATASTROPHIC,
            bypasses=("retention_window",),
            default_ttl_seconds=60,
        )
    )
    reg.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    return reg


@pytest.fixture
def engine(registry: GodModeRegistry) -> GodModeEngine:
    return GodModeEngine(registry=registry)


def test_issue_ticket_succeeds_when_armed(engine):
    ticket, agreement = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
        target={"tenant_id": "acme-7"},
    )
    assert ticket.state == GodTicketState.ISSUED
    assert ticket.actor_id == "alice"
    assert ticket.agreement_id == agreement.agreement_id
    assert agreement.target == (("tenant_id", "acme-7"),)


def test_issue_ticket_fails_when_dormant():
    reg = GodModeRegistry()
    reg.register_capability(
        GodCapability(
            module="rbac",
            name="impersonate_user",
            description="Act as another identity.",
            blast_radius=GodCapabilityBlastRadius.PLATFORM,
            bypasses=("identity_binding",),
            default_ttl_seconds=60,
        )
    )
    eng = GodModeEngine(registry=reg)
    with pytest.raises(GodModeEngineError):
        eng.issue_ticket(
            actor_id="alice",
            module="rbac",
            name="impersonate_user",
            justification=_VERY_LONG_JUST,
        )


def test_issue_ticket_fails_when_unknown(engine):
    with pytest.raises(GodModeEngineError):
        engine.issue_ticket(
            actor_id="alice",
            module="ghost",
            name="missing",
            justification=_VERY_LONG_JUST,
        )


def test_consume_emits_receipt_and_marks_consumed(engine):
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    receipt = engine.consume(
        ticket_id=ticket.ticket_id,
        outcome=GodReceiptOutcome.SUCCESS,
        pre_state={"rows": 100},
        post_state={"rows": 0},
        detail={"reason": "gdpr"},
    )
    assert receipt.outcome == GodReceiptOutcome.SUCCESS
    assert receipt.pre_state_hash != receipt.post_state_hash
    assert ("reason", "gdpr") in receipt.detail
    refreshed = engine.get_ticket(ticket.ticket_id)
    assert refreshed.state == GodTicketState.CONSUMED


def test_double_consume_raises(engine):
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    engine.consume(
        ticket_id=ticket.ticket_id,
        outcome=GodReceiptOutcome.SUCCESS,
        pre_state=None,
        post_state=None,
    )
    with pytest.raises(GodModeEngineError):
        engine.consume(
            ticket_id=ticket.ticket_id,
            outcome=GodReceiptOutcome.SUCCESS,
            pre_state=None,
            post_state=None,
        )


def test_consume_failure_records_reason(engine):
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    receipt = engine.consume(
        ticket_id=ticket.ticket_id,
        outcome=GodReceiptOutcome.FAILURE,
        pre_state=None,
        post_state=None,
        failure_reason="db down",
    )
    assert receipt.outcome == GodReceiptOutcome.FAILURE
    assert receipt.failure_reason == "db down"


def test_expired_ticket_cannot_consume(engine):
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
        ttl_seconds=5,  # the floor
    )
    # Force expiry by overriding the stored expires_at to the past.
    from mcoi_runtime.contracts.god_mode import GodModeTicket, GodTicketState

    expired = GodModeTicket(
        ticket_id=ticket.ticket_id,
        agreement_id=ticket.agreement_id,
        capability_module=ticket.capability_module,
        capability_name=ticket.capability_name,
        actor_id=ticket.actor_id,
        issued_at=ticket.issued_at,
        expires_at="2000-01-01T00:00:00Z",
        state=GodTicketState.ISSUED,
    )
    engine._tickets[ticket.ticket_id] = expired  # type: ignore[attr-defined]
    refreshed = engine.get_ticket(ticket.ticket_id)
    assert refreshed.state == GodTicketState.EXPIRED
    with pytest.raises(GodModeEngineError):
        engine.consume(
            ticket_id=ticket.ticket_id,
            outcome=GodReceiptOutcome.SUCCESS,
            pre_state=None,
            post_state=None,
        )


def test_revoke_blocks_consume(engine):
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    revoked = engine.revoke(
        ticket_id=ticket.ticket_id,
        actor_id="auditor",
        reason="false alarm",
    )
    assert revoked.state == GodTicketState.REVOKED
    with pytest.raises(GodModeEngineError):
        engine.consume(
            ticket_id=ticket.ticket_id,
            outcome=GodReceiptOutcome.SUCCESS,
            pre_state=None,
            post_state=None,
        )


def test_revoke_consumed_ticket_raises(engine):
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    engine.consume(
        ticket_id=ticket.ticket_id,
        outcome=GodReceiptOutcome.SUCCESS,
        pre_state=None,
        post_state=None,
    )
    with pytest.raises(GodModeEngineError):
        engine.revoke(
            ticket_id=ticket.ticket_id,
            actor_id="auditor",
            reason="late",
        )


def test_revoke_requires_reason(engine):
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    with pytest.raises(GodModeEngineError):
        engine.revoke(ticket_id=ticket.ticket_id, actor_id="auditor", reason=" ")


def test_invoke_context_manager_success(engine):
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    with engine.invoke(ticket_id=ticket.ticket_id, pre_state={"rows": 5}) as carrier:
        carrier["post"] = {"rows": 0}
    refreshed = engine.get_ticket(ticket.ticket_id)
    assert refreshed.state == GodTicketState.CONSUMED
    receipts = engine.list_receipts(actor_id="alice")
    assert len(receipts) == 1
    assert receipts[0].outcome == GodReceiptOutcome.SUCCESS


def test_invoke_context_manager_failure(engine):
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    with pytest.raises(RuntimeError):
        with engine.invoke(ticket_id=ticket.ticket_id, pre_state={"rows": 5}) as carrier:
            carrier["post"] = {"rows": 5}
            raise RuntimeError("disk full")
    receipts = engine.list_receipts(actor_id="alice")
    assert len(receipts) == 1
    assert receipts[0].outcome == GodReceiptOutcome.FAILURE
    assert "disk full" in receipts[0].failure_reason


def test_audit_sink_invoked(registry):
    captured = []

    class Sink:
        def record(self, **kwargs):
            captured.append(kwargs)

    eng = GodModeEngine(registry=registry, receipt_sink=Sink())
    ticket, _ = eng.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    eng.consume(
        ticket_id=ticket.ticket_id,
        outcome=GodReceiptOutcome.SUCCESS,
        pre_state=None,
        post_state=None,
    )
    assert len(captured) == 1
    assert captured[0]["action"].startswith("god_mode.consume.data.purge_tenant_now")
    assert captured[0]["actor_id"] == "alice"
    assert captured[0]["outcome"] == "success"


def test_audit_sink_exception_does_not_break_consume(registry):
    class BadSink:
        def record(self, **kwargs):
            raise RuntimeError("sink down")

    eng = GodModeEngine(registry=registry, receipt_sink=BadSink())
    ticket, _ = eng.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    receipt = eng.consume(
        ticket_id=ticket.ticket_id,
        outcome=GodReceiptOutcome.SUCCESS,
        pre_state=None,
        post_state=None,
    )
    assert receipt.outcome == GodReceiptOutcome.SUCCESS


def test_list_tickets_filters(engine):
    t1, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    # Slight time gap so issued_at differs even at second precision when sorting
    time.sleep(0.001)
    t2, _ = engine.issue_ticket(
        actor_id="bob",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    by_alice = engine.list_tickets(actor_id="alice")
    assert len(by_alice) == 1
    assert by_alice[0].ticket_id == t1.ticket_id
    by_bob = engine.list_tickets(actor_id="bob")
    assert len(by_bob) == 1
    assert by_bob[0].ticket_id == t2.ticket_id


def test_list_tickets_active_only_excludes_consumed(engine):
    t1, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    engine.consume(
        ticket_id=t1.ticket_id,
        outcome=GodReceiptOutcome.SUCCESS,
        pre_state=None,
        post_state=None,
    )
    t2, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    active = engine.list_tickets(actor_id="alice", active_only=True)
    assert {t.ticket_id for t in active} == {t2.ticket_id}


def test_consume_unknown_ticket_raises(engine):
    with pytest.raises(GodModeEngineError):
        engine.consume(
            ticket_id="god-tkt-doesnotexist",
            outcome=GodReceiptOutcome.SUCCESS,
            pre_state=None,
            post_state=None,
        )
