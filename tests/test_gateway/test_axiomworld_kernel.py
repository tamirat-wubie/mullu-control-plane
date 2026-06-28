"""AxiomWorld gateway kernel MVP-1 tests.

Purpose: verify observe, claim, conflict, projection, action, simulation, and
    receipt behavior for the AxiomWorld MVP-1 kernel overlay.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.axiomworld_kernel and gateway.world_state.
Invariants:
  - Observations require evidence before symbol admission.
  - Claims without evidence remain hypotheses outside admitted world state.
  - Conflicting claims are preserved and quarantined.
  - Public projections redact private scoped state.
  - High-risk or irreversible actions require approval.
  - Simulated state remains separate from validated world state.
"""

from __future__ import annotations

from gateway.axiomworld_kernel import (
    AxiomActionProposal,
    AxiomActionStatus,
    AxiomClaimProposal,
    AxiomDecision,
    AxiomObservationEvent,
    AxiomProjectionScope,
    AxiomReversibility,
    AxiomRiskLevel,
    AxiomTruthState,
    AxiomWorldKernel,
)
from gateway.world_state import EvidenceRef


NOW = "2026-06-28T12:00:00+00:00"
TENANT = "tenant-axiom"


def test_axiomworld_observes_symbol_with_evidence_and_receipt() -> None:
    kernel = AxiomWorldKernel(clock=lambda: NOW)

    receipt = kernel.observe_event(_event(entity_id="repo:mullu-control-plane"))
    state = kernel.materialize(tenant_id=TENANT)
    receipts = kernel.receipts()

    assert receipt.decision == AxiomDecision.ACCEPT
    assert receipt.reason == "observation_admitted"
    assert receipt.evidence_used == ("evidence-1",)
    assert state.entity_count == 1
    assert state.state_id.startswith("world-state-")
    assert len(receipts) == 1
    assert receipts[0].object_id == "repo:mullu-control-plane"


def test_axiomworld_quarantines_identity_collision_without_second_symbol() -> None:
    kernel = AxiomWorldKernel(clock=lambda: NOW)
    kernel.observe_event(_event(entity_id="repo:canonical"))

    receipt = kernel.observe_event(_event(entity_id="repo:alias"))
    state = kernel.materialize(tenant_id=TENANT)

    assert receipt.decision == AxiomDecision.QUARANTINE
    assert receipt.reason == "identity_conflict_detected"
    assert receipt.conflicts == ("possible_same_as:repo:canonical",)
    assert "no_silent_identity_merge" in receipt.rules_applied
    assert state.entity_count == 1


def test_axiomworld_claim_without_evidence_stays_hypothesis() -> None:
    kernel = AxiomWorldKernel(clock=lambda: NOW)
    kernel.observe_event(_event(entity_id="repo:mullu-control-plane"))

    receipt = kernel.propose_claim(
        _claim(
            claim_id="claim:ready",
            evidence_refs=(),
            object_value="ready",
        )
    )
    claim = kernel.claim_record("claim:ready")
    state = kernel.materialize(tenant_id=TENANT)

    assert receipt.decision == AxiomDecision.REQUIRE_EVIDENCE
    assert receipt.reason == "claim_requires_evidence_before_admission"
    assert claim is not None
    assert claim.truth_state == AxiomTruthState.HYPOTHESIS
    assert claim.admitted_to_world_state is False
    assert state.claim_count == 0
    assert "no_validation_without_evidence" in receipt.rules_applied


def test_axiomworld_preserves_conflicting_claims_as_open_contradiction() -> None:
    kernel = AxiomWorldKernel(clock=lambda: NOW)
    kernel.observe_event(_event(entity_id="repo:mullu-control-plane"))
    first = kernel.propose_claim(
        _claim(claim_id="claim:ci-green", predicate="ci_status", object_value="green")
    )

    second = kernel.propose_claim(
        _claim(claim_id="claim:ci-red", predicate="ci_status", object_value="red")
    )
    state = kernel.materialize(tenant_id=TENANT)
    first_record = kernel.claim_record("claim:ci-green")
    second_record = kernel.claim_record("claim:ci-red")

    assert first.decision == AxiomDecision.ACCEPT
    assert second.decision == AxiomDecision.QUARANTINE
    assert second.reason == "claim_conflict_preserved"
    assert second.conflicts == ("claim:ci-green",)
    assert first_record is not None
    assert first_record.truth_state == AxiomTruthState.CONFLICTED
    assert second_record is not None
    assert second_record.truth_state == AxiomTruthState.CONFLICTED
    assert state.claim_count == 2
    assert state.open_contradiction_count == 1


def test_axiomworld_public_projection_redacts_private_scope() -> None:
    kernel = AxiomWorldKernel(clock=lambda: NOW)
    kernel.observe_event(
        _event(
            entity_id="repo:public",
            scope=AxiomProjectionScope.PUBLIC,
            permissions={"public": True},
            stable_fingerprint={"provider": "github", "repo": "public"},
        )
    )
    kernel.observe_event(
        _event(
            entity_id="repo:private",
            scope=AxiomProjectionScope.PRIVATE,
            permissions={"public": False},
            stable_fingerprint={"provider": "github", "repo": "private"},
        )
    )
    kernel.propose_claim(
        _claim(
            claim_id="claim:public-ready",
            subject_ref="repo:public",
            scope=AxiomProjectionScope.PUBLIC,
            predicate="status",
            object_value="foundation-ready",
        )
    )
    kernel.propose_claim(
        _claim(
            claim_id="claim:private-secret",
            subject_ref="repo:private",
            scope=AxiomProjectionScope.PRIVATE,
            predicate="secret_state",
            object_value="operator-only",
        )
    )

    projection = kernel.project(
        observer="public-web",
        scope=AxiomProjectionScope.PUBLIC,
        tenant_id=TENANT,
    )

    assert projection.scope == AxiomProjectionScope.PUBLIC
    assert [symbol["entity_id"] for symbol in projection.symbols] == ["repo:public"]
    assert [claim["claim_id"] for claim in projection.claims] == ["claim:public-ready"]
    assert "symbol_scope_redacted" in projection.redactions
    assert "claim_subject_scope_redacted" in projection.redactions
    assert projection.world_state_hash


def test_axiomworld_action_lifecycle_gates_risk_and_reversibility() -> None:
    kernel = AxiomWorldKernel(clock=lambda: NOW)
    kernel.observe_event(_event(entity_id="repo:mullu-control-plane"))

    low_risk = kernel.propose_action(
        _action(action_id="action:label-local", risk_level=AxiomRiskLevel.LOW)
    )
    high_risk = kernel.propose_action(
        _action(
            action_id="action:publish",
            risk_level=AxiomRiskLevel.HIGH,
            reversibility=AxiomReversibility.IRREVERSIBLE,
        )
    )
    low_record = kernel.action_record("action:label-local")
    high_record = kernel.action_record("action:publish")

    assert low_risk.decision == AxiomDecision.ACCEPT
    assert low_record is not None
    assert low_record.status == AxiomActionStatus.CHECKED
    assert high_risk.decision == AxiomDecision.REQUIRE_APPROVAL
    assert high_risk.reversible is False
    assert high_record is not None
    assert high_record.status == AxiomActionStatus.PROPOSED
    assert "high_risk_action_gate" in high_risk.rules_applied


def test_axiomworld_simulation_cannot_validate_without_real_evidence() -> None:
    kernel = AxiomWorldKernel(clock=lambda: NOW)
    kernel.observe_event(_event(entity_id="repo:mullu-control-plane"))

    simulated = kernel.propose_claim(
        _claim(
            claim_id="claim:simulated-green",
            predicate="ci_status",
            object_value="green",
            evidence_refs=(),
            simulated=True,
        )
    )
    blocked = kernel.validate_claim("claim:simulated-green")
    supported = kernel.validate_claim(
        "claim:simulated-green",
        evidence_refs=(_evidence("evidence-real"),),
    )
    claim = kernel.claim_record("claim:simulated-green")
    state = kernel.materialize(tenant_id=TENANT)

    assert simulated.decision == AxiomDecision.SIMULATE_ONLY
    assert blocked.decision == AxiomDecision.REQUIRE_EVIDENCE
    assert "simulation_not_reality" in blocked.rules_applied
    assert supported.decision == AxiomDecision.ACCEPT
    assert claim is not None
    assert claim.truth_state == AxiomTruthState.SUPPORTED
    assert claim.admitted_to_world_state is True
    assert state.claim_count == 1
    assert state.open_contradiction_count == 0


def test_axiomworld_simulated_action_does_not_mutate_world_state() -> None:
    kernel = AxiomWorldKernel(clock=lambda: NOW)
    kernel.observe_event(_event(entity_id="repo:mullu-control-plane"))
    kernel.propose_action(_action(action_id="action:dry-run"))
    before = kernel.materialize(tenant_id=TENANT)

    receipt = kernel.simulate_action("action:dry-run")
    after = kernel.materialize(tenant_id=TENANT)
    action = kernel.action_record("action:dry-run")

    assert receipt.decision == AxiomDecision.SIMULATE_ONLY
    assert receipt.reason == "action_simulated_without_world_state_mutation"
    assert action is not None
    assert action.status == AxiomActionStatus.SIMULATED
    assert before.state_hash == after.state_hash
    assert before.entity_count == after.entity_count == 1


def _event(
    *,
    entity_id: str,
    scope: AxiomProjectionScope = AxiomProjectionScope.INTERNAL,
    permissions: dict[str, bool] | None = None,
    stable_fingerprint: dict[str, str] | None = None,
) -> AxiomObservationEvent:
    return AxiomObservationEvent(
        entity_id=entity_id,
        tenant_id=TENANT,
        entity_type="repository",
        display_name="Mullu Control Plane",
        source="github_snapshot",
        observed_at=NOW,
        evidence_refs=(_evidence("evidence-1"),),
        stable_fingerprint=stable_fingerprint
        or {"provider": "github", "owner": "tamirat-wubie", "repo": "mullu-control-plane"},
        scope=scope,
        permissions=permissions or {},
    )


def _claim(
    *,
    claim_id: str,
    subject_ref: str = "repo:mullu-control-plane",
    predicate: str = "status",
    object_value: str = "ready",
    evidence_refs: tuple[EvidenceRef, ...] | None = None,
    scope: AxiomProjectionScope = AxiomProjectionScope.INTERNAL,
    simulated: bool = False,
) -> AxiomClaimProposal:
    return AxiomClaimProposal(
        claim_id=claim_id,
        tenant_id=TENANT,
        subject_ref=subject_ref,
        predicate=predicate,
        object_value=object_value,
        source="github_snapshot",
        observed_at=NOW,
        evidence_refs=(_evidence("evidence-claim"),) if evidence_refs is None else evidence_refs,
        scope=scope,
        simulated=simulated,
    )


def _action(
    *,
    action_id: str,
    risk_level: AxiomRiskLevel = AxiomRiskLevel.LOW,
    reversibility: AxiomReversibility = AxiomReversibility.FULL,
) -> AxiomActionProposal:
    return AxiomActionProposal(
        action_id=action_id,
        tenant_id=TENANT,
        actor="operator",
        intent="update local world-state label",
        target_ref="repo:mullu-control-plane",
        risk_level=risk_level,
        reversibility=reversibility,
        permissions_required=("world_state:write",),
        preconditions=("target_observed",),
        expected_delta={"kind": "metadata_only"},
    )


def _evidence(evidence_id: str) -> EvidenceRef:
    return EvidenceRef(
        evidence_id=evidence_id,
        evidence_type="snapshot",
        source="fixture",
        observed_at=NOW,
        content_hash=f"sha256:{evidence_id}",
    )
