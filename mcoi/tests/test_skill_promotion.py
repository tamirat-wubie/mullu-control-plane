"""Tests for evidence-bound skill lifecycle promotion.

Purpose: verify skill lifecycle changes require explicit execution and verification evidence.
Governance scope: promotion decision contracts and registry transition admission.
Dependencies: skill contracts, SkillRegistry, and skill_promotion gate.
Invariants:
  - Candidate promotion requires successful execution evidence.
  - Verified and trusted promotion require verification evidence.
  - Rejected promotion decisions do not mutate registry lifecycle.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.skill import (
    DeterminismClass,
    EffectClass,
    SkillClass,
    SkillDescriptor,
    SkillExecutionRecord,
    SkillLifecycle,
    SkillOutcome,
    SkillOutcomeStatus,
    SkillPromotionDecision,
    SkillPromotionEvidence,
    SkillStepOutcome,
    TrustClass,
    VerificationStrength,
)
from mcoi_runtime.core.skill_promotion import (
    evaluate_skill_promotion,
    promote_skill_with_evidence,
)
from mcoi_runtime.core.skills import SkillRegistry


FIXED_CLOCK = "2026-05-27T16:00:00+00:00"


def _registry_with_skill(
    *,
    skill_id: str = "skill.promote",
    lifecycle: SkillLifecycle = SkillLifecycle.CANDIDATE,
) -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(
        SkillDescriptor(
            skill_id=skill_id,
            name="Promotion candidate",
            skill_class=SkillClass.PRIMITIVE,
            effect_class=EffectClass.INTERNAL_PURE,
            determinism_class=DeterminismClass.DETERMINISTIC,
            trust_class=TrustClass.TRUSTED_INTERNAL,
            verification_strength=VerificationStrength.STRONG,
            lifecycle=lifecycle,
        )
    )
    return registry


def _record(
    *,
    skill_id: str = "skill.promote",
    record_id: str = "skill-record-1",
    status: SkillOutcomeStatus = SkillOutcomeStatus.SUCCEEDED,
    execution_id: str | None = "execution-1",
    verification_id: str | None = None,
) -> SkillExecutionRecord:
    return SkillExecutionRecord(
        record_id=record_id,
        skill_id=skill_id,
        outcome=SkillOutcome(
            skill_id=skill_id,
            status=status,
            step_outcomes=(
                SkillStepOutcome(
                    step_id=f"{record_id}-step",
                    status=status,
                    execution_id=execution_id,
                    verification_id=verification_id,
                ),
            ),
        ),
        started_at=FIXED_CLOCK,
        finished_at=FIXED_CLOCK,
    )


def test_candidate_promotion_requires_execution_evidence_without_mutation() -> None:
    registry = _registry_with_skill()
    record_without_evidence = _record(execution_id=None)

    decision = promote_skill_with_evidence(
        registry,
        skill_id="skill.promote",
        target_lifecycle=SkillLifecycle.PROVISIONAL,
        execution_records=(record_without_evidence,),
        created_at=FIXED_CLOCK,
    )

    assert decision.approved is False
    assert decision.reason == "execution_evidence_missing"
    assert decision.evidence is None
    assert registry.get("skill.promote").lifecycle is SkillLifecycle.CANDIDATE


def test_candidate_promotion_applies_with_successful_execution_evidence() -> None:
    registry = _registry_with_skill()

    decision = promote_skill_with_evidence(
        registry,
        skill_id="skill.promote",
        target_lifecycle=SkillLifecycle.PROVISIONAL,
        execution_records=(_record(),),
        created_at=FIXED_CLOCK,
    )

    assert decision.approved is True
    assert decision.reason == "successful_execution_evidence"
    assert decision.evidence.evidence_refs == ("execution-1",)
    assert registry.get("skill.promote").lifecycle is SkillLifecycle.PROVISIONAL


def test_verified_promotion_requires_verification_evidence() -> None:
    registry = _registry_with_skill(lifecycle=SkillLifecycle.PROVISIONAL)

    decision = promote_skill_with_evidence(
        registry,
        skill_id="skill.promote",
        target_lifecycle=SkillLifecycle.VERIFIED,
        execution_records=(_record(),),
        created_at=FIXED_CLOCK,
    )

    assert decision.approved is False
    assert decision.reason == "verification_evidence_missing"
    assert decision.evidence is None
    assert registry.get("skill.promote").lifecycle is SkillLifecycle.PROVISIONAL


def test_trusted_promotion_requires_repeated_verified_execution_evidence() -> None:
    registry = _registry_with_skill(lifecycle=SkillLifecycle.VERIFIED)
    first_record = _record(record_id="skill-record-1", verification_id="verification-1")

    first_decision = evaluate_skill_promotion(
        registry,
        skill_id="skill.promote",
        target_lifecycle=SkillLifecycle.TRUSTED,
        execution_records=(first_record,),
        created_at=FIXED_CLOCK,
    )
    second_decision = promote_skill_with_evidence(
        registry,
        skill_id="skill.promote",
        target_lifecycle=SkillLifecycle.TRUSTED,
        execution_records=(
            first_record,
            _record(record_id="skill-record-2", execution_id="execution-2", verification_id="verification-2"),
        ),
        created_at=FIXED_CLOCK,
    )

    assert first_decision.approved is False
    assert first_decision.reason == "trusted_repetition_evidence_missing"
    assert second_decision.approved is True
    assert second_decision.evidence.verification_ids == ("verification-1", "verification-2")
    assert registry.get("skill.promote").lifecycle is SkillLifecycle.TRUSTED


def test_promotion_rejects_mismatched_record_skill_without_mutation() -> None:
    registry = _registry_with_skill()

    decision = promote_skill_with_evidence(
        registry,
        skill_id="skill.promote",
        target_lifecycle=SkillLifecycle.PROVISIONAL,
        execution_records=(_record(skill_id="skill.other"),),
        created_at=FIXED_CLOCK,
    )

    assert decision.approved is False
    assert decision.reason == "execution_record_skill_mismatch"
    assert decision.evidence is None
    assert registry.get("skill.promote").lifecycle is SkillLifecycle.CANDIDATE


def test_promotion_decision_contract_requires_evidence_for_approved_state() -> None:
    evidence = SkillPromotionEvidence(
        evidence_id="skill-promotion-evidence-1",
        skill_id="skill.promote",
        target_lifecycle=SkillLifecycle.PROVISIONAL,
        execution_record_ids=("skill-record-1",),
        evidence_refs=("execution-1",),
        created_at=FIXED_CLOCK,
        reason="successful_execution_evidence",
    )

    approved = SkillPromotionDecision(
        skill_id="skill.promote",
        from_lifecycle=SkillLifecycle.CANDIDATE,
        target_lifecycle=SkillLifecycle.PROVISIONAL,
        approved=True,
        reason="successful_execution_evidence",
        evidence=evidence,
    )

    assert approved.evidence is evidence
    assert approved.approved is True
    assert approved.evidence.skill_id == approved.skill_id
    with pytest.raises(ValueError, match="approved promotion decisions must include evidence"):
        SkillPromotionDecision(
            skill_id="skill.promote",
            from_lifecycle=SkillLifecycle.CANDIDATE,
            target_lifecycle=SkillLifecycle.PROVISIONAL,
            approved=True,
            reason="successful_execution_evidence",
            evidence=None,
        )
