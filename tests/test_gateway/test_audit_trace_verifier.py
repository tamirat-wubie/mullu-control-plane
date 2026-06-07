"""Audit trace verifier tests.

Tests: read-only verification of CommandLedger audit chains. Spec mapping:
RCS-JOINT v1.0.0 AuditTraceVerifier first slice.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.audit_trace_verifier import AuditTraceVerifier, _recompute_event_hash  # noqa: E402
from gateway.authority_obligation_mesh import (  # noqa: E402
    ApprovalChainStatus,
    AuthorityObligationMesh,
    TeamOwnership,
)
from gateway.command_spine import (  # noqa: E402
    ClosureDisposition,
    CommandLedger,
    CommandState,
    InMemoryCommandLedgerStore,
)
from gateway.evidence_bundle import build_command_trust_bundle  # noqa: E402


def _ledger_through_terminal_closure() -> tuple[CommandLedger, str]:
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conv-1",
        idempotency_key="idem-verifier",
        intent="llm_completion",
        payload={"body": "hello verifier"},
    )
    ledger.bind_governed_action(command.command_id)
    ledger.observe_and_reconcile_effect(
        command.command_id,
        output={"content": "hello verifier", "succeeded": True},
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
    ledger.certify_terminal_closure(
        command.command_id,
        disposition=ClosureDisposition.COMMITTED,
        response_evidence_closure=closure,
    )
    ledger.promote_closure_memory(command.command_id)
    ledger.decide_closure_learning(command.command_id)
    return ledger, command.command_id


def test_verifier_passes_canonical_lifecycle():
    ledger, command_id = _ledger_through_terminal_closure()

    verification = AuditTraceVerifier(ledger).verify_command_trace(command_id)

    assert verification.command_present is True
    assert verification.event_count > 0
    assert verification.event_hash_chain_valid is True
    assert verification.terminal_certificate_present is True
    assert verification.terminal_certificate_id.startswith("terminal-closure-")
    assert verification.failures == ()
    assert verification.all_links_verified is True


def test_verifier_reports_missing_command():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )

    verification = AuditTraceVerifier(ledger).verify_command_trace("cmd-does-not-exist")

    assert verification.command_present is False
    assert verification.failures == ("command_not_found",)
    assert verification.all_links_verified is False


def test_verifier_detects_event_hash_tamper():
    # If any event in the ledger has a tampered event_hash, the verifier
    # must report it with the offending event_id rather than silently pass.
    ledger, command_id = _ledger_through_terminal_closure()

    # Tamper: replace the second event with a fabricated event_hash.
    events = ledger._events
    target_index = 1
    tampered = replace(events[target_index], event_hash="0" * 64)
    ledger._events[target_index] = tampered

    verification = AuditTraceVerifier(ledger).verify_command_trace(command_id)

    assert verification.event_hash_chain_valid is False
    assert any(failure.startswith("event_hash_mismatch:") for failure in verification.failures)
    assert verification.all_links_verified is False


def test_verifier_global_chain_passes_canonical_lifecycle():
    ledger, _ = _ledger_through_terminal_closure()

    verification = AuditTraceVerifier(ledger).verify_global_event_chain()

    assert verification.event_count > 0
    assert verification.chain_intact is True
    assert verification.failures == ()


def test_verifier_global_chain_accepts_restart_prefix_boundary():
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
        idempotency_key="idem-before-restart",
        intent="llm_completion",
        payload={"body": "before restart"},
    )
    first_event_hash = store.events_for(first_command.command_id)[-1].event_hash
    restarted = CommandLedger(
        clock=lambda: "2026-04-24T12:00:01+00:00",
        store=store,
    )
    restarted_command = restarted.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-2",
        idempotency_key="idem-after-restart",
        intent="llm_completion",
        payload={"body": "after restart"},
    )

    verification = AuditTraceVerifier(restarted).verify_global_event_chain()

    assert restarted._events[0].command_id == restarted_command.command_id
    assert restarted._events[0].prev_event_hash == first_event_hash
    assert verification.event_count == 1
    assert verification.chain_intact is True
    assert verification.failures == ()


def test_verifier_global_chain_detects_restart_suffix_internal_break():
    store = InMemoryCommandLedgerStore()
    first = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=store,
    )
    first.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-before-restart",
        intent="llm_completion",
        payload={"body": "before restart"},
    )
    restarted = CommandLedger(
        clock=lambda: "2026-04-24T12:00:01+00:00",
        store=store,
    )
    first_after_restart = restarted.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-2",
        idempotency_key="idem-after-restart-1",
        intent="llm_completion",
        payload={"body": "after restart 1"},
    )
    restarted.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conversation-3",
        idempotency_key="idem-after-restart-2",
        intent="llm_completion",
        payload={"body": "after restart 2"},
    )
    target_index = 1
    bad = replace(restarted._events[target_index], prev_event_hash="0" * 64)
    restarted._events[target_index] = bad

    verification = AuditTraceVerifier(restarted).verify_global_event_chain()

    assert restarted._events[0].command_id == first_after_restart.command_id
    assert verification.chain_intact is False
    assert any(failure.startswith("global_chain_break:") for failure in verification.failures)


def test_verifier_global_chain_detects_break():
    # If any event's prev_event_hash no longer matches the previous event's
    # event_hash, the global chain is broken at that event.
    ledger, _ = _ledger_through_terminal_closure()
    target_index = 2
    bad = replace(ledger._events[target_index], prev_event_hash="0" * 64)
    ledger._events[target_index] = bad

    verification = AuditTraceVerifier(ledger).verify_global_event_chain()

    assert verification.chain_intact is False
    assert any(failure.startswith("global_chain_break:") for failure in verification.failures)


def test_verifier_anchor_passes_when_signed_with_correct_secret():
    ledger, _ = _ledger_through_terminal_closure()
    anchor = ledger.anchor_unanchored_events(signing_secret="anchor-secret")
    assert anchor is not None

    verification = AuditTraceVerifier(ledger).verify_anchor(
        anchor.anchor_id,
        signing_secret="anchor-secret",
    )

    assert verification.anchor_present is True
    assert verification.merkle_root_valid is True
    assert verification.signature_valid is True
    assert verification.failures == ()


def test_verifier_anchor_rejects_wrong_secret():
    ledger, _ = _ledger_through_terminal_closure()
    anchor = ledger.anchor_unanchored_events(signing_secret="anchor-secret")
    assert anchor is not None

    verification = AuditTraceVerifier(ledger).verify_anchor(
        anchor.anchor_id,
        signing_secret="wrong-secret",
    )

    assert verification.merkle_root_valid is True
    assert verification.signature_valid is False
    assert "anchor_signature_invalid" in verification.failures


def test_verifier_anchor_reports_missing_anchor():
    ledger, _ = _ledger_through_terminal_closure()

    verification = AuditTraceVerifier(ledger).verify_anchor(
        "cmd-anchor-not-real",
        signing_secret="anchor-secret",
    )

    assert verification.anchor_present is False
    assert verification.failures == ("anchor_not_found",)


def test_verifier_anchor_requires_signing_secret():
    ledger, _ = _ledger_through_terminal_closure()

    with pytest.raises(ValueError, match="signing_secret_required"):
        AuditTraceVerifier(ledger).verify_anchor("cmd-anchor-x", signing_secret="")


def test_verifier_trust_bundle_passes_canonical_lifecycle():
    ledger, command_id = _ledger_through_terminal_closure()
    bundle = build_command_trust_bundle(
        command_ledger=ledger,
        command_id=command_id,
        deployment_id="deploy-test",
        commit_sha="abc123",
        signing_secret="bundle-secret",
        signature_key_id="bundle-key-1",
        clock=lambda: "2026-04-24T12:01:00+00:00",
    )

    verification = AuditTraceVerifier(ledger).verify_trust_bundle(
        bundle,
        signing_secret="bundle-secret",
    )

    assert verification.signature_valid is True
    assert verification.ledger_cross_reference_valid is True
    assert verification.fully_verified is True
    assert verification.failures == ()


def test_verifier_trust_bundle_rejects_wrong_secret():
    ledger, command_id = _ledger_through_terminal_closure()
    bundle = build_command_trust_bundle(
        command_ledger=ledger,
        command_id=command_id,
        deployment_id="deploy-test",
        commit_sha="abc123",
        signing_secret="bundle-secret",
        signature_key_id="bundle-key-1",
        clock=lambda: "2026-04-24T12:01:00+00:00",
    )

    verification = AuditTraceVerifier(ledger).verify_trust_bundle(
        bundle,
        signing_secret="wrong-secret",
    )

    assert verification.signature_valid is False
    # Cross-reference still passes (the bundle's ledger references are real).
    assert verification.ledger_cross_reference_valid is True
    assert verification.fully_verified is False
    assert any(failure.startswith("trust_ledger_verify_failed:") for failure in verification.failures)


def test_verifier_trust_bundle_detects_command_id_not_in_ledger():
    # A bundle that signature-verifies (issuer used the right secret) but
    # references a command that does not exist in the ledger is forged-by-
    # insider scenario: the cross-reference catches it even though the HMAC
    # would pass.
    ledger, command_id = _ledger_through_terminal_closure()
    bundle = build_command_trust_bundle(
        command_ledger=ledger,
        command_id=command_id,
        deployment_id="deploy-test",
        commit_sha="abc123",
        signing_secret="bundle-secret",
        signature_key_id="bundle-key-1",
        clock=lambda: "2026-04-24T12:01:00+00:00",
    )

    # Verify against a DIFFERENT, fresh ledger that has no record of this command.
    other_ledger = CommandLedger(
        clock=lambda: "2026-04-24T13:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    verification = AuditTraceVerifier(other_ledger).verify_trust_bundle(
        bundle,
        signing_secret="bundle-secret",
    )

    assert verification.signature_valid is True
    assert verification.ledger_cross_reference_valid is False
    assert "bundle_command_not_in_ledger" in verification.failures


def test_verifier_trust_bundle_requires_signing_secret():
    ledger, command_id = _ledger_through_terminal_closure()
    bundle = build_command_trust_bundle(
        command_ledger=ledger,
        command_id=command_id,
        deployment_id="deploy-test",
        commit_sha="abc123",
        signing_secret="bundle-secret",
        signature_key_id="bundle-key-1",
        clock=lambda: "2026-04-24T12:01:00+00:00",
    )

    with pytest.raises(ValueError, match="signing_secret_required"):
        AuditTraceVerifier(ledger).verify_trust_bundle(bundle, signing_secret="")


def _payment_command_for_chain_tests(ledger: CommandLedger):
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="requester-1",
        source="web",
        conversation_id="conversation-1",
        idempotency_key="idem-chain-verify",
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
    ledger.transition(command.command_id, CommandState.TENANT_BOUND)
    ledger.bind_governed_action(command.command_id)
    return command


def _register_payment_owner(mesh: AuthorityObligationMesh) -> None:
    mesh.register_ownership(TeamOwnership(
        tenant_id="tenant-1",
        resource_ref="financial.send_payment",
        owner_team="finance_ops",
        primary_owner_id="finance-manager-1",
        fallback_owner_id="tenant-owner-1",
        escalation_team="executive_ops",
    ))


def test_verifier_approval_chain_passes_satisfied_chain_with_distinct_approver():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = _payment_command_for_chain_tests(ledger)
    mesh = AuthorityObligationMesh(commands=ledger, clock=ledger._clock)
    _register_payment_owner(mesh)
    mesh.prepare_authority(command.command_id)
    mesh.record_approval(
        command_id=command.command_id,
        approver_id="finance-manager-1",
        approver_roles=("financial_admin",),
        approved=True,
    )

    verification = AuditTraceVerifier(ledger).verify_approval_chain(
        command.command_id,
        obligation_mesh=mesh,
    )

    assert verification.chain_present is True
    assert verification.chain_status is ApprovalChainStatus.SATISFIED
    assert verification.approver_count == 1
    assert verification.approvers_unique is True
    assert verification.failures == ()
    assert verification.fully_verified is True


def test_verifier_approval_chain_passes_low_risk_command_with_no_chain():
    # A low-risk command has no approval chain; verifier should report
    # absence cleanly without flagging it as a failure.
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conv-1",
        idempotency_key="idem-low-risk",
        intent="llm_completion",
        payload={"body": "hello"},
    )
    mesh = AuthorityObligationMesh(commands=ledger, clock=ledger._clock)

    verification = AuditTraceVerifier(ledger).verify_approval_chain(
        command.command_id,
        obligation_mesh=mesh,
    )

    assert verification.chain_present is False
    assert verification.chain_status is None
    assert verification.approver_count == 0
    assert verification.failures == ()
    assert verification.fully_verified is True


def test_verifier_approval_chain_detects_duplicate_approvers_in_satisfied_chain():
    # The mesh's own record_approval normally dedupes approvers via dict
    # ordering, but a tampered chain (or an alternate store loading raw
    # records) could carry duplicates. The verifier must flag them.
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = _payment_command_for_chain_tests(ledger)
    mesh = AuthorityObligationMesh(commands=ledger, clock=ledger._clock)
    _register_payment_owner(mesh)
    mesh.prepare_authority(command.command_id)
    mesh.record_approval(
        command_id=command.command_id,
        approver_id="finance-manager-1",
        approver_roles=("financial_admin",),
        approved=True,
    )
    chain = mesh.approval_chain_for(command.command_id)
    assert chain is not None
    tampered = replace(
        chain,
        approvals_received=("finance-manager-1", "finance-manager-1"),
    )
    mesh._store.save_approval_chain(tampered)

    verification = AuditTraceVerifier(ledger).verify_approval_chain(
        command.command_id,
        obligation_mesh=mesh,
    )

    assert verification.approvers_unique is False
    assert "approval_chain_duplicate_approvers" in verification.failures


def test_verifier_approval_chain_detects_committed_certificate_without_satisfied_chain():
    # Insider-incident scenario: a terminal certificate is COMMITTED for a
    # command whose approval chain is still PENDING. The verifier must catch
    # the inconsistency.
    ledger, command_id = _ledger_through_terminal_closure()
    mesh = AuthorityObligationMesh(commands=ledger, clock=ledger._clock)

    # Inject a PENDING approval chain for a command that the lifecycle
    # already certified as COMMITTED. (Real production would never do this;
    # we simulate the post-incident discovery.)
    from gateway.authority_obligation_mesh import ApprovalChain  # local import to keep test scope tight
    fabricated_chain = ApprovalChain(
        chain_id="chain-fabricated",
        command_id=command_id,
        tenant_id="tenant-1",
        policy_id="policy-fabricated",
        required_roles=("ops_admin",),
        required_approver_count=2,
        approvals_received=(),
        status=ApprovalChainStatus.PENDING,
        due_at="2099-01-01T00:00:00+00:00",
    )
    mesh._store.save_approval_chain(fabricated_chain)

    verification = AuditTraceVerifier(ledger).verify_approval_chain(
        command_id,
        obligation_mesh=mesh,
    )

    assert verification.certificate_disposition is ClosureDisposition.COMMITTED
    assert verification.chain_status is ApprovalChainStatus.PENDING
    assert "committed_certificate_with_unsatisfied_chain" in verification.failures
    assert verification.fully_verified is False


def test_verifier_command_without_terminal_certificate_is_valid_but_marked():
    # A command that has not yet been terminally certified should verify
    # cleanly (no tamper) while explicitly reporting the absence.
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conv-1",
        idempotency_key="idem-no-cert",
        intent="llm_completion",
        payload={"body": "no terminal yet"},
    )
    ledger.transition(command.command_id, CommandState.ALLOWED, risk_tier="low")

    verification = AuditTraceVerifier(ledger).verify_command_trace(command.command_id)

    assert verification.command_present is True
    assert verification.event_hash_chain_valid is True
    assert verification.terminal_certificate_present is False
    assert verification.terminal_certificate_id == ""
    # Absence of certificate is informational, not a failure.
    assert verification.failures == ()
    assert verification.all_links_verified is True


def test_verifier_certificate_hash_passes_canonical_lifecycle():
    ledger, command_id = _ledger_through_terminal_closure()
    verification = AuditTraceVerifier(ledger).verify_certificate_hash(command_id)
    assert verification.certificate_present is True
    assert verification.hash_matches is True
    assert verification.closure_binding_valid is True
    assert verification.recomputed_certificate_id == verification.certificate_id
    assert verification.fully_verified is True
    assert verification.failures == ()


def test_verifier_certificate_hash_detects_tampered_disposition():
    # Insider/incident: a stored certificate's disposition is flipped to
    # COMMITTED while its certificate_id (content-addressed over the
    # original disposition) is left stale. Recomputation catches it.
    ledger, command_id = _ledger_through_terminal_closure()
    cert = ledger._terminal_certificates[command_id]
    tampered = replace(cert, disposition=ClosureDisposition.REQUIRES_REVIEW)
    ledger._terminal_certificates[command_id] = tampered

    verification = AuditTraceVerifier(ledger).verify_certificate_hash(command_id)

    assert verification.hash_matches is False
    assert verification.recomputed_certificate_id != verification.certificate_id
    assert "certificate_hash_mismatch" in verification.failures


def test_verifier_certificate_hash_detects_tampered_metadata():
    ledger, command_id = _ledger_through_terminal_closure()
    cert = ledger._terminal_certificates[command_id]
    poisoned_metadata = {**cert.metadata, "injected": "by-insider"}
    tampered = replace(cert, metadata=poisoned_metadata)
    ledger._terminal_certificates[command_id] = tampered

    verification = AuditTraceVerifier(ledger).verify_certificate_hash(command_id)

    assert verification.hash_matches is False
    assert "certificate_hash_mismatch" in verification.failures


def test_verifier_certificate_hash_detects_closure_binding_mismatch():
    # The certificate carries response_evidence_closure_id but the
    # ledger's response_evidence_closed event is tampered so the closure
    # no longer hashes to that id.
    ledger, command_id = _ledger_through_terminal_closure()
    for index, event in enumerate(ledger._events):
        if event.command_id == command_id and event.detail.get("cause") == "response_evidence_closed":
            poisoned = dict(event.detail)
            closure = dict(poisoned["response_evidence_closure"])
            closure["evidence_hash"] = "tampered-evidence-hash"
            poisoned["response_evidence_closure"] = closure
            ledger._events[index] = replace(event, detail=poisoned)
            break

    verification = AuditTraceVerifier(ledger).verify_certificate_hash(command_id)

    assert verification.closure_binding_valid is False
    assert "certificate_closure_binding_mismatch" in verification.failures


def test_verifier_certificate_hash_absent_certificate_is_informational():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conv-1",
        idempotency_key="idem-no-cert-hash",
        intent="llm_completion",
        payload={"body": "no cert"},
    )
    ledger.transition(command.command_id, CommandState.ALLOWED, risk_tier="low")

    verification = AuditTraceVerifier(ledger).verify_certificate_hash(command.command_id)

    assert verification.certificate_present is False
    assert verification.failures == ()
    assert verification.fully_verified is True


def test_verifier_replay_state_passes_canonical_lifecycle():
    ledger, command_id = _ledger_through_terminal_closure()
    verification = AuditTraceVerifier(ledger).verify_replay_state_consistency(command_id)
    assert verification.command_present is True
    assert verification.transition_chain_valid is True
    assert verification.states_match is True
    assert verification.replayed_state == verification.live_state
    assert verification.event_count > 0
    assert verification.fully_replayed is True
    assert verification.failures == ()


def test_verifier_replay_state_detects_live_state_diverged_from_event_log():
    # Audit-bypass scenario: someone modified the live command state without
    # appending a corresponding transition event. Walking the event log and
    # comparing against the live state catches the divergence.
    ledger, command_id = _ledger_through_terminal_closure()
    live = ledger._commands[command_id]
    ledger._commands[command_id] = replace(live, state=CommandState.RECEIVED)

    verification = AuditTraceVerifier(ledger).verify_replay_state_consistency(command_id)

    assert verification.states_match is False
    assert verification.replayed_state != verification.live_state
    assert verification.live_state == CommandState.RECEIVED
    assert "replay_state_diverges_from_live" in verification.failures


def test_verifier_replay_state_detects_transition_gap():
    # Audit-bypass scenario: a command event is rewritten so its own hash is
    # internally consistent, but its previous_state no longer matches the
    # preceding event's next_state. Replay must detect the causal gap.
    ledger, command_id = _ledger_through_terminal_closure()
    target_index = next(
        index
        for index, event in enumerate(ledger._events)
        if event.command_id == command_id and event.previous_state != CommandState.RECEIVED
    )
    tampered = replace(ledger._events[target_index], previous_state=CommandState.RECEIVED)
    ledger._events[target_index] = replace(tampered, event_hash=_recompute_event_hash(tampered))

    verification = AuditTraceVerifier(ledger).verify_replay_state_consistency(command_id)

    assert verification.transition_chain_valid is False
    assert verification.states_match is True
    assert verification.replayed_state == verification.live_state
    assert any(failure.startswith("replay_transition_gap:") for failure in verification.failures)
    assert verification.fully_replayed is False


def test_verifier_replay_state_detects_invalid_initial_witness():
    # Audit-bypass scenario: the first event no longer proves canonical
    # ingress. Even if later events settle to the live state, replay must fail.
    ledger, command_id = _ledger_through_terminal_closure()
    first_index = next(
        index
        for index, event in enumerate(ledger._events)
        if event.command_id == command_id
    )
    tampered = replace(ledger._events[first_index], previous_state=CommandState.DENIED)
    ledger._events[first_index] = replace(tampered, event_hash=_recompute_event_hash(tampered))

    verification = AuditTraceVerifier(ledger).verify_replay_state_consistency(command_id)

    assert verification.transition_chain_valid is False
    assert verification.states_match is True
    assert verification.replayed_state == verification.live_state
    assert any(failure.startswith("replay_initial_state_gap:") for failure in verification.failures)
    assert verification.fully_replayed is False


def test_verifier_replay_state_reports_missing_command():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    verification = AuditTraceVerifier(ledger).verify_replay_state_consistency("cmd-missing")
    assert verification.command_present is False
    assert verification.failures == ("command_not_found",)


def test_verifier_tenant_isolation_passes_canonical_lifecycle():
    ledger, command_id = _ledger_through_terminal_closure()
    verification = AuditTraceVerifier(ledger).verify_tenant_isolation(command_id)
    assert verification.command_present is True
    assert verification.expected_tenant_id == "tenant-1"
    assert verification.event_tenant_mismatches == ()
    assert verification.fully_isolated is True
    assert verification.failures == ()


def test_verifier_tenant_isolation_detects_event_tenant_tamper():
    # If any event for this command carries a different tenant_id than the
    # command itself (post-write tampering), the verifier reports it.
    ledger, command_id = _ledger_through_terminal_closure()
    target_index = 1
    bad = replace(ledger._events[target_index], tenant_id="tenant-other")
    ledger._events[target_index] = bad

    verification = AuditTraceVerifier(ledger).verify_tenant_isolation(command_id)

    assert verification.fully_isolated is False
    assert "event_tenant_mismatch" in verification.failures
    assert len(verification.event_tenant_mismatches) == 1


def test_verifier_tenant_isolation_reports_missing_command():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    verification = AuditTraceVerifier(ledger).verify_tenant_isolation("cmd-missing")
    assert verification.command_present is False
    assert verification.failures == ("command_not_found",)


def test_verifier_verify_all_composes_every_method():
    # verify_all is pure composition over the five existing methods. A
    # canonical lifecycle with anchor + bundle present must report zero
    # structured failures across the unified report.
    ledger, command_id = _ledger_through_terminal_closure()
    mesh = AuthorityObligationMesh(commands=ledger, clock=ledger._clock)
    anchor = ledger.anchor_unanchored_events(signing_secret="anchor-secret")
    assert anchor is not None
    bundle = build_command_trust_bundle(
        command_ledger=ledger,
        command_id=command_id,
        deployment_id="deploy-verify-all",
        commit_sha="va123",
        signing_secret="bundle-secret",
        signature_key_id="bundle-key-va",
        clock=lambda: "2026-04-24T12:01:00+00:00",
    )

    report = AuditTraceVerifier(ledger).verify_all(
        command_id,
        obligation_mesh=mesh,
        anchor_id=anchor.anchor_id,
        anchor_signing_secret="anchor-secret",
        bundle=bundle,
        bundle_signing_secret="bundle-secret",
    )

    assert report.failures == ()
    assert report.fully_verified is True
    assert report.trace.all_links_verified is True
    assert report.global_chain.chain_intact is True
    assert report.approval.fully_verified is True
    assert report.tenant.fully_isolated is True
    assert report.replay.fully_replayed is True
    assert report.certificate_hash.fully_verified is True
    assert report.certificate_hash.hash_matches is True
    assert report.certificate_evidence_refs.fully_verified is True
    assert report.certificate_evidence_refs.unresolved_evidence_refs == ()
    assert report.evidence_records.fully_verified is True
    assert report.evidence_records.record_count > 0
    assert report.anchor is not None and report.anchor.failures == ()
    assert report.bundle is not None and report.bundle.fully_verified is True


def test_verifier_verify_all_requires_secret_when_artifact_provided():
    ledger, command_id = _ledger_through_terminal_closure()
    mesh = AuthorityObligationMesh(commands=ledger, clock=ledger._clock)

    with pytest.raises(ValueError, match="anchor_signing_secret_required"):
        AuditTraceVerifier(ledger).verify_all(
            command_id,
            obligation_mesh=mesh,
            anchor_id="cmd-anchor-x",
            anchor_signing_secret="",
        )


def test_verifier_end_to_end_canonical_lifecycle_passes_every_method():
    # Integration test: a complete lifecycle (reconcile + certify + memory
    # + learning + anchor + trust bundle), verified with all five verifier
    # methods, must produce zero structured failures. This pins the
    # property that a deployment running canonical paths is fully verifiable
    # by an external auditor with read-only ledger access plus the anchor
    # and bundle signing secrets — the operational SOC scenario.
    ledger, command_id = _ledger_through_terminal_closure()
    mesh = AuthorityObligationMesh(commands=ledger, clock=ledger._clock)
    anchor = ledger.anchor_unanchored_events(signing_secret="anchor-secret")
    bundle = build_command_trust_bundle(
        command_ledger=ledger,
        command_id=command_id,
        deployment_id="deploy-e2e",
        commit_sha="e2eabc",
        signing_secret="bundle-secret",
        signature_key_id="bundle-key-e2e",
        clock=lambda: "2026-04-24T12:01:00+00:00",
    )

    verifier = AuditTraceVerifier(ledger)

    trace = verifier.verify_command_trace(command_id)
    assert trace.all_links_verified is True
    assert trace.terminal_certificate_present is True

    chain = verifier.verify_global_event_chain()
    assert chain.chain_intact is True

    assert anchor is not None
    anchor_check = verifier.verify_anchor(anchor.anchor_id, signing_secret="anchor-secret")
    assert anchor_check.merkle_root_valid is True
    assert anchor_check.signature_valid is True
    assert anchor_check.failures == ()

    bundle_check = verifier.verify_trust_bundle(bundle, signing_secret="bundle-secret")
    assert bundle_check.fully_verified is True

    # llm_completion is low-risk so no approval chain is required; the
    # verifier reports the absence cleanly without flagging it as a failure.
    approval_check = verifier.verify_approval_chain(command_id, obligation_mesh=mesh)
    assert approval_check.fully_verified is True
    assert approval_check.chain_present is False
    assert approval_check.certificate_disposition is ClosureDisposition.COMMITTED


# ─── Refinement regression tests ─────────────────────────────────────


def test_verifier_global_chain_empty_ledger_is_intact():
    # An empty ledger has zero events; the chain is trivially intact.
    # This is an edge case that surfaces only under fresh-deployment or
    # full-rotation conditions; verify it reports cleanly instead of
    # tripping a false negative.
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    verification = AuditTraceVerifier(ledger).verify_global_event_chain()
    assert verification.event_count == 0
    assert verification.chain_intact is True
    assert verification.failures == ()


def test_verifier_anchor_detects_tampered_event_within_range():
    # Pre-refinement: verify_anchor computed the merkle root from stored
    # event.event_hash values. A tampered event payload whose stored hash
    # was left intact would leave the merkle root matching, and the
    # anchor would verify clean — even though the underlying event is
    # corrupt. Post-refinement: verify_anchor recomputes every event hash
    # within the anchored range and reports anchored_event_hash_mismatch.
    ledger, _ = _ledger_through_terminal_closure()
    anchor = ledger.anchor_unanchored_events(signing_secret="anchor-secret")
    assert anchor is not None
    # Tamper an event payload (here: the trace_id) while leaving the
    # stored event_hash untouched. _recompute_event_hash will derive a
    # different hash from the tampered fields, exposing the corruption.
    target_index = 1
    tampered = replace(ledger._events[target_index], trace_id="forged-trace")
    ledger._events[target_index] = tampered

    verification = AuditTraceVerifier(ledger).verify_anchor(
        anchor.anchor_id, signing_secret="anchor-secret",
    )
    # Merkle root still valid (computed from STORED event_hash values,
    # which were not changed), but the per-event recomputation catches it.
    assert verification.merkle_root_valid is True
    assert any(
        failure.startswith("anchored_event_hash_mismatch:")
        for failure in verification.failures
    )


def test_verifier_anchor_end_search_refuses_backward_to_event_hash():
    # Pre-refinement: if a tampered/forged anchor pointed to_event_hash
    # at an index strictly earlier than from_event_hash's index,
    # _events_for_anchor scanned enumerate(events) from index 0 and
    # returned a backward slice that fell through to events[start:] —
    # silently over-claiming the range. Post-refinement: the end search
    # starts at `start`, so a backward to_event_hash is treated as
    # not-found and the verifier returns events[start:], which then
    # produces an event_count_mismatch and merkle_root_mismatch.
    ledger, _ = _ledger_through_terminal_closure()
    anchor = ledger.anchor_unanchored_events(signing_secret="anchor-secret")
    assert anchor is not None
    # Swap from/to to point backward — this is a forged anchor that
    # would have silently over-claimed under the pre-refinement code.
    forged = replace(
        anchor,
        from_event_hash=anchor.to_event_hash,
        to_event_hash=anchor.from_event_hash,
    )
    ledger._store._anchors[-1] = forged

    verification = AuditTraceVerifier(ledger).verify_anchor(
        forged.anchor_id, signing_secret="anchor-secret",
    )
    # The forged anchor's signature was computed for the original
    # payload, so the signature also fails — but the structural check
    # is what we care about: event_count_mismatch is present because
    # the recovered range is no longer the full original span.
    assert "anchor_event_count_mismatch" in verification.failures


def test_verifier_anchor_single_event_anchor_merkle_root_matches():
    # Edge case: an anchor over exactly one event has merkle_root equal
    # to that single event's hash (the _compute_merkle_root bypass).
    # Confirm the verifier handles this cleanly.
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conv-single",
        idempotency_key="idem-single",
        intent="llm_completion",
        payload={"body": "single"},
    )
    anchor = ledger.anchor_unanchored_events(signing_secret="anchor-secret")
    assert anchor is not None
    assert anchor.event_count == 1

    verification = AuditTraceVerifier(ledger).verify_anchor(
        anchor.anchor_id, signing_secret="anchor-secret",
    )
    assert verification.merkle_root_valid is True
    assert verification.signature_valid is True
    assert verification.failures == ()


def test_verifier_certificate_hash_unrecoverable_closure_does_not_double_report():
    # Pre-refinement: when the closure event was missing but the
    # certificate carried a non-empty response_evidence_closure_id, the
    # verifier reported BOTH certificate_closure_unrecoverable AND
    # certificate_hash_mismatch — the second was mechanical (recompute
    # with None can't match) and duplicated the root cause. Post-
    # refinement: closure_unrecoverable short-circuits the hash check.
    ledger, command_id = _ledger_through_terminal_closure()
    # Drop the response_evidence_closed event payload so the closure
    # cannot be reconstructed, while leaving the certificate intact.
    for index, event in enumerate(ledger._events):
        if event.command_id != command_id:
            continue
        detail = dict(event.detail)
        closure = detail.pop("response_evidence_closure", None)
        if closure is not None:
            ledger._events[index] = replace(event, detail=detail)

    verification = AuditTraceVerifier(ledger).verify_certificate_hash(command_id)

    assert "certificate_closure_unrecoverable" in verification.failures
    # Critical: the hash-mismatch reason is NOT also reported, because
    # the unrecoverable closure makes the recomputation meaningless.
    assert "certificate_hash_mismatch" not in verification.failures
    assert verification.recomputed_certificate_id == ""
    assert verification.hash_matches is False


# ─── Certificate-evidence-ref reachability slice ─────────────────────


def test_verifier_certificate_evidence_refs_pass_canonical_lifecycle():
    # Every evidence_ref on the certificate must resolve to a real
    # EvidenceRecord in the ledger's R_evidence for this command.
    ledger, command_id = _ledger_through_terminal_closure()
    verification = AuditTraceVerifier(ledger).verify_certificate_evidence_refs(command_id)
    assert verification.command_present is True
    assert verification.certificate_present is True
    assert verification.evidence_ref_count > 0
    assert verification.unresolved_evidence_refs == ()
    assert verification.failures == ()
    assert verification.fully_verified is True


# ─── Evidence-record verification + approval-chain tenant slice ──────


def test_verifier_evidence_records_pass_canonical_lifecycle():
    # The canonical lifecycle records evidence via
    # promote_provider_receipts_to_graph and close_success_response_evidence.
    # Each record's evidence_id must derive from its ref_hash and bind to
    # the correct command_id; non-provider records' ref_hash must
    # recompute from {command_id, evidence_type, ref}.
    ledger, command_id = _ledger_through_terminal_closure()
    verification = AuditTraceVerifier(ledger).verify_evidence_records(command_id)
    assert verification.command_present is True
    assert verification.record_count > 0
    assert verification.failures == ()
    assert verification.fully_verified is True


def test_verifier_certificate_evidence_refs_detects_unresolved_ref():
    # Tamper: drop one of the certificate's referenced evidence records
    # from R_evidence. The certificate still carries the evidence_id but
    # the ledger no longer holds the record — a tampered or rotated cert
    # whose refs no longer ground anywhere.
    ledger, command_id = _ledger_through_terminal_closure()
    certificate = ledger.terminal_certificate_for(command_id)
    assert certificate is not None
    target_ref = certificate.evidence_refs[0]
    # Remove that evidence record from the per-command list.
    ledger._evidence_records[command_id] = [
        record
        for record in ledger._evidence_records[command_id]
        if record.evidence_id != target_ref
    ]

    verification = AuditTraceVerifier(ledger).verify_certificate_evidence_refs(command_id)
    assert "certificate_evidence_ref_unresolved" in verification.failures
    assert target_ref in verification.unresolved_evidence_refs
    assert verification.fully_verified is False


def test_verifier_evidence_records_detects_evidence_id_tamper():
    # Flip an evidence record's evidence_id to a value that does not
    # derive from its ref_hash. The verifier must report
    # evidence_id_derivation_mismatch.
    ledger, command_id = _ledger_through_terminal_closure()
    records = ledger._evidence_records[command_id]
    assert records, "fixture must seed at least one evidence record"
    target = records[0]
    tampered = replace(target, evidence_id="evidence-forged0000000000")
    records[0] = tampered

    verification = AuditTraceVerifier(ledger).verify_evidence_records(command_id)
    assert "evidence_id_derivation_mismatch" in verification.failures
    assert "evidence-forged0000000000" in verification.evidence_id_mismatches


def test_verifier_evidence_records_detects_command_id_tamper():
    # Flip an evidence record's command_id while leaving the verifier
    # call asking about the original command. The verifier must report
    # evidence_command_id_mismatch.
    ledger, command_id = _ledger_through_terminal_closure()
    records = ledger._evidence_records[command_id]
    assert records
    target = records[0]
    tampered = replace(target, command_id="cmd-forged")
    records[0] = tampered

    verification = AuditTraceVerifier(ledger).verify_evidence_records(command_id)
    assert "evidence_command_id_mismatch" in verification.failures
    assert target.evidence_id in verification.command_id_mismatches


def test_verifier_evidence_records_detects_hash_recompute_mismatch():
    # For non-provider-receipt evidence (ref + command_id + evidence_type
    # are the full hash inputs), tampering the ref while leaving ref_hash
    # unchanged surfaces evidence_hash_recompute_mismatch.
    ledger, command_id = _ledger_through_terminal_closure()
    records = ledger._evidence_records[command_id]
    target_index = next(
        (i for i, r in enumerate(records) if r.evidence_type != "provider_receipt"),
        None,
    )
    assert target_index is not None, "fixture must include a non-provider record"
    target = records[target_index]
    tampered = replace(target, ref="forged-ref")
    records[target_index] = tampered

    verification = AuditTraceVerifier(ledger).verify_evidence_records(command_id)
    assert "evidence_hash_recompute_mismatch" in verification.failures
    assert target.evidence_id in verification.hash_recompute_mismatches


def test_verifier_certificate_evidence_refs_reports_missing_command():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    verification = AuditTraceVerifier(ledger).verify_certificate_evidence_refs("cmd-missing")
    assert verification.command_present is False
    assert verification.failures == ("command_not_found",)


def test_verifier_evidence_records_reports_missing_command():
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    verification = AuditTraceVerifier(ledger).verify_evidence_records("cmd-missing")
    assert verification.command_present is False
    assert verification.failures == ("command_not_found",)


def test_verifier_certificate_evidence_refs_no_certificate_is_informational():
    # A command without a terminal certificate has nothing to verify;
    # absence of a certificate is informational, not a failure.
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = ledger.create_command(
        tenant_id="tenant-1",
        actor_id="identity-1",
        source="web",
        conversation_id="conv-no-cert",
        idempotency_key="idem-no-cert-refs",
        intent="llm_completion",
        payload={"body": "no cert"},
    )

    verification = AuditTraceVerifier(ledger).verify_certificate_evidence_refs(command.command_id)
    assert verification.certificate_present is False
    assert verification.evidence_ref_count == 0
    assert verification.failures == ()
    assert verification.fully_verified is True


def test_verifier_tenant_isolation_detects_approval_chain_tenant_mismatch():
    # New optional obligation_mesh param: a chain whose tenant_id differs
    # from the command's tenant_id is a real tenant-boundary violation
    # that the ledger-only checks cannot see.
    ledger = CommandLedger(
        clock=lambda: "2026-04-24T12:00:00+00:00",
        store=InMemoryCommandLedgerStore(),
    )
    command = _payment_command_for_chain_tests(ledger)
    mesh = AuthorityObligationMesh(commands=ledger, clock=ledger._clock)
    _register_payment_owner(mesh)
    mesh.prepare_authority(command.command_id)
    chain = mesh.approval_chain_for(command.command_id)
    assert chain is not None
    # Tamper: write the chain back with a different tenant_id.
    tampered = replace(chain, tenant_id="tenant-other")
    mesh._store.save_approval_chain(tampered)

    verification = AuditTraceVerifier(ledger).verify_tenant_isolation(
        command.command_id, obligation_mesh=mesh,
    )
    assert verification.approval_chain_tenant_mismatch is True
    assert "approval_chain_tenant_mismatch" in verification.failures
    assert verification.fully_isolated is False


def test_verifier_tenant_isolation_without_mesh_is_backward_compatible():
    # Existing callers (no obligation_mesh) must still see the same
    # behavior — the approval_chain check is opt-in via the new kwarg.
    ledger, command_id = _ledger_through_terminal_closure()
    verification = AuditTraceVerifier(ledger).verify_tenant_isolation(command_id)
    assert verification.approval_chain_tenant_mismatch is False
    assert verification.fully_isolated is True
    assert verification.failures == ()
