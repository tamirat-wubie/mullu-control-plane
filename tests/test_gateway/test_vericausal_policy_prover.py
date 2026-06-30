"""VeriCausal policy prover v2 tests.

Purpose: verify transition proof, evidence trust, policy coverage, lease
    verification, and schema-backed receipts for VCPP v2.
Governance scope: policy transition proof, default-deny behavior, evidence
    trust lattice, obligation enforcement, invariant preservation, and leases.
Dependencies: gateway.policy_prover and
    schemas/policy_transition_proof_report.schema.json.
Invariants:
  - Exact transitions are lease-bound before execution.
  - Missing policy coverage fails closed.
  - Immutable invariant deltas deny even when permission exists.
  - Insufficient evidence cannot satisfy approval requirements.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from gateway.policy_prover import (
    PolicyEvidence,
    PolicyEvidenceRequirement,
    PolicyEvidenceTrust,
    PolicyLeaseStatus,
    PolicyObligation,
    PolicyObligationPhase,
    PolicyPrecedenceLayer,
    PolicyTransition,
    PolicyTransitionEffect,
    PolicyTransitionPolicy,
    PolicyTransitionVerdict,
    VeriCausalPolicyProver,
    policy_transition_proof_report_to_json_dict,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "policy_transition_proof_report.schema.json"
PROOF_TIME = "2026-06-30T12:01:00+00:00"


def test_vericausal_transition_prover_allows_lease_bound_transition_with_obligations() -> None:
    transition = _email_transition()
    policies = (_email_send_policy(),)
    evidence = (_signed_approval(),)

    report = VeriCausalPolicyProver().prove_transition(
        transition=transition,
        policies=policies,
        evidence=evidence,
    )

    assert report.verdict is PolicyTransitionVerdict.ALLOW_WITH_ENFORCED_OBLIGATIONS
    assert report.lease is not None
    assert report.metadata["lease_bound"] is True
    assert report.delta_paths == ("email.status",)
    assert "action:email.send" in report.activated_symbols
    assert report.obligations[0].phase is PolicyObligationPhase.POST


def test_vericausal_transition_prover_blocks_missing_policy_coverage() -> None:
    transition = _email_transition(activated_symbols=("finance:data",))
    policies = (
        PolicyTransitionPolicy(
            policy_id="permit-email-send",
            description="Permit email send without covering finance symbols.",
            effect=PolicyTransitionEffect.PERMIT,
            coverage_symbols=("action:*", "resource:*", "risk:*", "exposure:*", "delta:*"),
        ),
    )

    report = VeriCausalPolicyProver().prove_transition(
        transition=transition,
        policies=policies,
        evidence=(),
    )

    assert report.verdict is PolicyTransitionVerdict.UNKNOWN_BLOCKED
    assert "finance:data" in report.missing_policy_symbols
    assert report.lease is None
    assert report.metadata["policy_coverage_complete"] is False


def test_vericausal_transition_prover_denies_invariant_delta_even_with_permission() -> None:
    transition = _profile_admin_transition()
    policies = (
        PolicyTransitionPolicy(
            policy_id="permit-profile-update",
            description="Permit normal profile updates.",
            effect=PolicyTransitionEffect.PERMIT,
            coverage_symbols=("action:*", "resource:*", "risk:*", "delta:*"),
            required_delta_paths=("profile.admin",),
            precedence_layer=PolicyPrecedenceLayer.ROLE_PERMISSION,
        ),
        PolicyTransitionPolicy(
            policy_id="admin-role-immutable",
            description="Admin role cannot be changed by profile update.",
            effect=PolicyTransitionEffect.INVARIANT,
            coverage_symbols=("delta:*",),
            invariant_delta_paths=("profile.admin",),
            precedence_layer=PolicyPrecedenceLayer.IMMUTABLE_INVARIANT,
        ),
    )

    report = VeriCausalPolicyProver().prove_transition(
        transition=transition,
        policies=policies,
        evidence=(),
    )

    assert report.verdict is PolicyTransitionVerdict.DENY_INVARIANT
    assert report.violated_policy_ids == ("admin-role-immutable",)
    assert report.lease is None
    assert any(step.stage == "invariant" and step.result == "fail" for step in report.proof_trace)


def test_vericausal_transition_prover_denies_low_trust_evidence() -> None:
    report = VeriCausalPolicyProver().prove_transition(
        transition=_email_transition(),
        policies=(_email_send_policy(),),
        evidence=(
            PolicyEvidence(
                evidence_id="approval-note",
                evidence_type="explicit_confirmation",
                issuer="operator",
                subject_id="operator",
                scope_symbols=("approval:user", "action:email.send"),
                trust_level=PolicyEvidenceTrust.SELF_CLAIMED,
                issued_at="2026-06-30T12:00:00+00:00",
                expires_at="2026-06-30T12:10:00+00:00",
                evidence_ref="proof://approval-note",
            ),
        ),
    )

    assert report.verdict is PolicyTransitionVerdict.DENY_EVIDENCE
    assert report.missing_evidence[0].requirement_id == "explicit-user-confirmation"
    assert report.missing_evidence[0].policy_id == "permit-confirmed-email-send"
    assert report.lease is None


def test_vericausal_policy_lease_requires_reprove_after_state_change_or_expiry() -> None:
    prover = VeriCausalPolicyProver()
    transition = _email_transition()
    policy = _email_send_policy()
    report = prover.prove_transition(
        transition=transition,
        policies=(policy,),
        evidence=(_signed_approval(),),
    )
    assert report.lease is not None

    active = prover.verify_lease(
        report.lease,
        observed_pre_state=transition.pre_state,
        policies=(policy,),
        observed_at="2026-06-30T12:02:00+00:00",
    )
    changed = prover.verify_lease(
        report.lease,
        observed_pre_state={"email": {"status": "queued", "recipient": "client@example.com"}},
        policies=(policy,),
        observed_at="2026-06-30T12:02:00+00:00",
    )
    expired = prover.verify_lease(
        report.lease,
        observed_pre_state=transition.pre_state,
        policies=(policy,),
        observed_at="2026-06-30T12:10:00+00:00",
    )

    assert active.status is PolicyLeaseStatus.ACTIVE
    assert changed.status is PolicyLeaseStatus.STATE_HASH_MISMATCH
    assert expired.status is PolicyLeaseStatus.LEASE_EXPIRED_REPROVE


def test_policy_transition_proof_report_schema_valid() -> None:
    report = VeriCausalPolicyProver().prove_transition(
        transition=_email_transition(),
        policies=(_email_send_policy(),),
        evidence=(_signed_approval(),),
    )
    payload = policy_transition_proof_report_to_json_dict(report)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)
    assert schema["$id"] == "urn:mullusi:schema:policy-transition-proof-report:1"
    assert payload["metadata"]["prover_version"] == "vcpp-kernel-v2"
    assert payload["report_id"].startswith("vcpp-transition-")


def _email_transition(activated_symbols: tuple[str, ...] = ("communication:external", "approval:user")) -> PolicyTransition:
    return PolicyTransition(
        transition_id="send-invoice-email",
        actor_id="assistant-agent",
        action_id="email.send",
        resource_id="invoice-email",
        resource_type="email",
        intent="send invoice email",
        pre_state={"email": {"status": "draft", "recipient": "client@example.com"}},
        post_state={"email": {"status": "sent", "recipient": "client@example.com"}},
        context={
            "fresh_until": "2026-06-30T12:05:00+00:00",
            "resource_sensitivity": "business",
        },
        proof_time=PROOF_TIME,
        actor_authenticated=True,
        authority_refs=("lineage://delegation/operator-to-agent",),
        activated_symbols=activated_symbols,
        risk_level="medium",
        external_exposure=True,
        lease_seconds=300,
    )


def _profile_admin_transition() -> PolicyTransition:
    return PolicyTransition(
        transition_id="profile-admin-update",
        actor_id="assistant-agent",
        action_id="profile.update",
        resource_id="user-profile",
        resource_type="profile",
        intent="update user profile",
        pre_state={"profile": {"admin": False, "display_name": "Tamirat"}},
        post_state={"profile": {"admin": True, "display_name": "Tamirat"}},
        context={"fresh_until": "2026-06-30T12:05:00+00:00"},
        proof_time=PROOF_TIME,
        actor_authenticated=True,
        authority_refs=("lineage://delegation/operator-to-agent",),
        risk_level="high",
    )


def _email_send_policy() -> PolicyTransitionPolicy:
    return PolicyTransitionPolicy(
        policy_id="permit-confirmed-email-send",
        description="Permit external email send only with signed confirmation and enforced receipts.",
        effect=PolicyTransitionEffect.PERMIT,
        coverage_symbols=(
            "communication:external",
            "approval:user",
            "action:*",
            "resource:*",
            "risk:*",
            "exposure:*",
            "delta:*",
        ),
        required_delta_paths=("email.status",),
        required_evidence=(
            PolicyEvidenceRequirement(
                requirement_id="explicit-user-confirmation",
                evidence_type="explicit_confirmation",
                minimum_trust=PolicyEvidenceTrust.SIGNED,
                scope_symbol="approval:user",
            ),
        ),
        obligations=(
            PolicyObligation(
                obligation_id="write-send-receipt",
                phase=PolicyObligationPhase.POST,
                description="Write an auditable send receipt.",
                enforceable=True,
                compensation_ref="compensate://delayed-send-receipt",
            ),
            PolicyObligation(
                obligation_id="preserve-sent-copy",
                phase=PolicyObligationPhase.CONTINUING,
                description="Preserve sent-copy audit evidence.",
                enforceable=True,
                compensation_ref="compensate://sent-copy-review",
            ),
        ),
    )


def _signed_approval() -> PolicyEvidence:
    return PolicyEvidence(
        evidence_id="approval-click-1",
        evidence_type="explicit_confirmation",
        issuer="operator",
        subject_id="operator",
        scope_symbols=("approval:user", "action:email.send"),
        trust_level=PolicyEvidenceTrust.SIGNED,
        issued_at="2026-06-30T12:00:00+00:00",
        expires_at="2026-06-30T12:10:00+00:00",
        evidence_ref="proof://approval-click-1",
    )
