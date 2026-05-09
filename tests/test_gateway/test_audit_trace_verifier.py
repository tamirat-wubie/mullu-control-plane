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
